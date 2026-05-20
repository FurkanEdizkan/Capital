"""Binance WebSocket market-data streams — self-healing, in-memory snapshots.

The engine keeps a live picture of a curated set of symbols by consuming
Binance's per-symbol `@ticker` streams over a single *combined* connection
(spot + futures). If a stream drops it reconnects with exponential backoff,
so the snapshot self-heals.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from decimal import Decimal
from typing import Any

import websockets

from exchange.client import Market, Ticker

log = logging.getLogger("capital.marketdata.stream")

SPOT_BASE = "wss://stream.binance.com:9443/stream?streams="
FUTURES_BASE = "wss://fstream.binance.com/stream?streams="

# Curated symbols streamed live (the Markets page surfaces these). The full
# universe is still available on demand via the REST client.
DEFAULT_SYMBOLS: list[str] = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "AVAXUSDT", "LINKUSDT", "ARBUSDT", "DOGEUSDT", "MATICUSDT",
    "ATOMUSDT", "OPUSDT", "INJUSDT", "SUIUSDT", "APTUSDT",
]

# A connector opens a stream and yields raw text messages.
Connector = Callable[[str], AbstractAsyncContextManager[AsyncIterator[Any]]]


def _default_connector(url: str) -> AbstractAsyncContextManager[AsyncIterator[Any]]:
    return websockets.connect(url, ping_interval=20, close_timeout=5)


def combined_url(base: str, symbols: list[str], suffix: str = "@ticker") -> str:
    """Build a Binance combined-stream URL for the given symbols."""
    return base + "/".join(f"{s.lower()}{suffix}" for s in symbols)


class ReconnectingStream:
    """Consumes a WebSocket URL, re-connecting with exponential backoff."""

    _INITIAL_BACKOFF = 1.0
    _MAX_BACKOFF = 60.0

    def __init__(
        self,
        url: str,
        on_message: Callable[[str | bytes], None],
        *,
        connector: Connector | None = None,
    ) -> None:
        self._url = url
        self._on_message = on_message
        self._connector = connector or _default_connector
        self._running = False

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        """Connect-consume-reconnect loop. Returns when `stop()` is called."""
        self._running = True
        backoff = self._INITIAL_BACKOFF
        while self._running:
            try:
                async with self._connector(self._url) as ws:
                    backoff = self._INITIAL_BACKOFF  # reset after a clean connect
                    async for raw in ws:
                        self._on_message(raw)
                        if not self._running:
                            return
            except Exception as exc:  # noqa: BLE001 — any error → reconnect
                if not self._running:
                    return
                log.warning("stream dropped (%s); reconnect in %.1fs", exc, backoff)
            if not self._running:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._MAX_BACKOFF)


class TickerHub:
    """In-memory snapshot of the latest 24h ticker per symbol for one market."""

    def __init__(self, market: Market) -> None:
        self.market = market
        self._snapshot: dict[str, Ticker] = {}

    def handle(self, raw: str | bytes) -> None:
        """Parse a 24h ticker message — combined-stream, array, or bare."""
        msg = json.loads(raw)
        if isinstance(msg, dict) and "data" in msg:
            msg = msg["data"]  # unwrap the combined-stream envelope
        items = msg if isinstance(msg, list) else [msg]
        for it in items:
            symbol = it.get("s")
            if symbol is None:
                continue
            # 24hrTicker compact keys: c=last, P=change%, q=quote volume.
            self._snapshot[symbol] = Ticker(
                symbol=symbol,
                price=Decimal(str(it["c"])),
                change_pct_24h=Decimal(str(it["P"])),
                quote_volume_24h=Decimal(str(it["q"])),
            )

    def snapshot(self) -> list[Ticker]:
        return list(self._snapshot.values())

    def latest(self, symbol: str) -> Ticker | None:
        return self._snapshot.get(symbol)


class StreamManager:
    """Owns the spot + futures ticker streams and their background tasks."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        *,
        connector: Connector | None = None,
    ) -> None:
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.spot = TickerHub(Market.spot)
        self.futures = TickerHub(Market.futures)
        self._streams = [
            ReconnectingStream(
                combined_url(SPOT_BASE, self.symbols), self.spot.handle, connector=connector
            ),
            ReconnectingStream(
                combined_url(FUTURES_BASE, self.symbols),
                self.futures.handle,
                connector=connector,
            ),
        ]
        self._tasks: list[asyncio.Task[None]] = []

    def hub(self, market: Market) -> TickerHub:
        return self.futures if market is Market.futures else self.spot

    def start(self) -> None:
        self._tasks = [asyncio.create_task(s.run()) for s in self._streams]
        log.info("market-data streams started (%d symbols)", len(self.symbols))

    async def stop(self) -> None:
        for s in self._streams:
            s.stop()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        log.info("market-data streams stopped")
