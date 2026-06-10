"""Price-feed latency — how delayed the data we trade on actually is.

Two signals feed one in-memory registry, with no DB writes on the hot path:

- *Feed latency*: Binance stream payloads carry the exchange event time
  (`E`, ms). On receipt the hub records `local_clock − event_time`.
- *REST round-trip*: each candle refresh records how long the HTTP call took.

Per `(market, symbol, kind)` a rolling window of recent samples backs the
current / p50 / p95 / max stats the API serves. A 1-minute rollup row is
persisted by the engine tick so history survives restarts. The freshness
module's hard freeze is unchanged — latency adds the softer "degraded"
signal (default threshold 2 s) that warns before staleness trips.
"""

import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Field, Session, SQLModel

log = logging.getLogger("capital.marketdata.latency")

_AMT = {"max_digits": 12, "decimal_places": 2}

#: Feed latency above this is *degraded* — surfaced, but trading continues.
DEFAULT_WARN_MS = 2000.0

_WINDOW = 500  # samples kept per key for the rolling stats


class FeedLatency(SQLModel, table=True):
    """One persisted minute-rollup of feed latency for one key."""

    __tablename__ = "feed_latency"

    id: int | None = Field(default=None, primary_key=True)
    market: str = Field(max_length=8, index=True)
    symbol: str = Field(max_length=24, index=True)
    kind: str = Field(max_length=8)  # ws | rest
    samples: int = Field(default=0)
    avg_ms: Decimal = Field(default=Decimal(0), **_AMT)
    p95_ms: Decimal = Field(default=Decimal(0), **_AMT)
    max_ms: Decimal = Field(default=Decimal(0), **_AMT)
    recorded_at: datetime = Field(index=True)


@dataclass
class LatencyStats:
    """The rolling-window view for one `(market, symbol, kind)`."""

    market: str
    symbol: str
    kind: str
    current_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    samples: int
    degraded: bool


def _percentile(ordered: list[float], q: float) -> float:
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


class LatencyRegistry:
    """Thread-safe in-memory latency samples (stream + engine threads write)."""

    def __init__(self, *, window: int = _WINDOW) -> None:
        self._window = window
        self._lock = threading.Lock()
        self._samples: dict[tuple[str, str, str], deque[float]] = {}
        # Samples since the last rollup flush, per key.
        self._pending: dict[tuple[str, str, str], list[float]] = {}

    def record(self, market: str, symbol: str, kind: str, latency_ms: float) -> None:
        """Record one sample. Negative values (clock skew) clamp to zero."""
        value = max(0.0, float(latency_ms))
        key = (market, symbol, kind)
        with self._lock:
            window = self._samples.get(key)
            if window is None:
                window = self._samples[key] = deque(maxlen=self._window)
            window.append(value)
            self._pending.setdefault(key, []).append(value)

    def stats(self, *, warn_ms: float = DEFAULT_WARN_MS) -> list[LatencyStats]:
        """Rolling-window stats for every key seen so far."""
        with self._lock:
            items = [(key, list(window)) for key, window in self._samples.items()]
        out: list[LatencyStats] = []
        for (market, symbol, kind), values in sorted(items):
            ordered = sorted(values)
            current = values[-1] if values else 0.0
            p95 = _percentile(ordered, 0.95)
            out.append(
                LatencyStats(
                    market=market,
                    symbol=symbol,
                    kind=kind,
                    current_ms=round(current, 1),
                    p50_ms=round(_percentile(ordered, 0.50), 1),
                    p95_ms=round(p95, 1),
                    max_ms=round(ordered[-1] if ordered else 0.0, 1),
                    samples=len(values),
                    degraded=current > warn_ms or p95 > warn_ms,
                )
            )
        return out

    def degraded(self, *, warn_ms: float = DEFAULT_WARN_MS) -> bool:
        """Whether any feed is currently above the warn threshold."""
        return any(s.degraded for s in self.stats(warn_ms=warn_ms))

    def flush_rollups(self, session: Session) -> int:
        """Persist (and clear) the pending samples as one rollup row per key."""
        with self._lock:
            pending, self._pending = self._pending, {}
        now = datetime.now(UTC).replace(tzinfo=None)
        written = 0
        for (market, symbol, kind), values in pending.items():
            if not values:
                continue
            ordered = sorted(values)
            session.add(
                FeedLatency(
                    market=market,
                    symbol=symbol,
                    kind=kind,
                    samples=len(values),
                    avg_ms=Decimal(str(round(sum(values) / len(values), 2))),
                    p95_ms=Decimal(str(round(_percentile(ordered, 0.95), 2))),
                    max_ms=Decimal(str(round(ordered[-1], 2))),
                    recorded_at=now,
                )
            )
            written += 1
        if written:
            session.commit()
        return written


#: Process-wide registry — the stream hubs and candle refresh write into it.
registry = LatencyRegistry()


def record_event_time(
    market: str, symbol: str, event_time_ms: object, *, now_ms: float | None = None
) -> None:
    """Record feed latency from an exchange event timestamp (ms since epoch)."""
    try:
        event_ms = float(event_time_ms)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return
    if event_ms <= 0:
        return
    local = now_ms if now_ms is not None else datetime.now(UTC).timestamp() * 1000
    registry.record(market, symbol, "ws", local - event_ms)
