"""Stale-data safeguard — detect when the market feed has gone stale.

A closed candle's `open_time` naturally lags "now" by up to one interval. If
the newest candle is older than that by a healthy margin, the feed has
stalled or disconnected — the engine freezes trading rather than acting on
frozen prices, and resumes automatically once fresh data arrives.
"""

from datetime import UTC, datetime

from marketdata.models import Candle

_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86_400, "w": 604_800}


def interval_seconds(interval: str) -> int:
    """Convert a Binance kline interval (`1m`, `1h`, `1d`, …) to seconds."""
    interval = interval.strip()
    if not interval or not interval[:-1].isdigit():
        raise ValueError(f"unrecognised interval: {interval!r}")
    count, unit = int(interval[:-1]), interval[-1]
    if unit == "M":  # calendar month — approximated as 30 days
        return count * 30 * 86_400
    if unit not in _UNIT_SECONDS:
        raise ValueError(f"unrecognised interval unit: {unit!r}")
    return count * _UNIT_SECONDS[unit]


def feed_is_stale(
    latest: Candle,
    interval: str,
    *,
    max_intervals: float = 2.0,
    now: datetime | None = None,
) -> bool:
    """Whether the newest candle is too old for trading to be safe.

    The newest *closed* candle already lags "now" by up to one interval, so
    staleness is measured generously at `max_intervals` intervals.
    """
    reference = now or datetime.now(UTC).replace(tzinfo=None)
    age = (reference - latest.open_time).total_seconds()
    return age > max_intervals * interval_seconds(interval)
