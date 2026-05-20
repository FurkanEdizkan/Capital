"""Tests for the Binance WebSocket streams — hermetic (faked connections)."""

import asyncio
import json
from decimal import Decimal
from typing import Any

import pytest

from exchange.client import Market
from marketdata.stream import ReconnectingStream, StreamManager, TickerHub

_TICKER_MSG = json.dumps(
    [
        {"s": "BTCUSDT", "c": "68000.0", "P": "1.5", "q": "1000000"},
        {"s": "ETHUSDT", "c": "3400.0", "P": "-0.8", "q": "500000"},
    ]
)


# --- TickerHub --------------------------------------------------------------

def test_ticker_hub_parses_array() -> None:
    hub = TickerHub(Market.spot)
    hub.handle(_TICKER_MSG)
    snap = {t.symbol: t for t in hub.snapshot()}
    assert snap["BTCUSDT"].price == Decimal("68000.0")
    assert snap["ETHUSDT"].change_pct_24h == Decimal("-0.8")
    assert hub.latest("BTCUSDT") is not None
    assert hub.latest("NOPEUSDT") is None


def test_ticker_hub_updates_in_place() -> None:
    hub = TickerHub(Market.spot)
    hub.handle(json.dumps([{"s": "BTCUSDT", "c": "1", "P": "0", "q": "0"}]))
    hub.handle(json.dumps([{"s": "BTCUSDT", "c": "2", "P": "0", "q": "0"}]))
    assert len(hub.snapshot()) == 1
    assert hub.latest("BTCUSDT").price == Decimal("2")  # type: ignore[union-attr]


# --- fake WebSocket ---------------------------------------------------------

class _FakeWS:
    def __init__(self, messages: list[str], fail: bool = False) -> None:
        self._messages = messages
        self._fail = fail

    async def __aenter__(self) -> "_FakeWS":
        if self._fail:
            raise ConnectionError("simulated drop")
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    def __aiter__(self) -> Any:
        return self._gen()

    async def _gen(self) -> Any:
        for m in self._messages:
            yield m


# --- ReconnectingStream -----------------------------------------------------

def test_stream_delivers_messages() -> None:
    received: list[str] = []
    stream: ReconnectingStream

    def on_msg(m: str | bytes) -> None:
        received.append(m if isinstance(m, str) else m.decode())
        if len(received) == 2:
            stream.stop()

    stream = ReconnectingStream(
        "ws://test", on_msg, connector=lambda _: _FakeWS(["a", "b"])
    )
    asyncio.run(stream.run())
    assert received == ["a", "b"]


def test_stream_reconnects_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(*_: Any) -> None:
        return None

    monkeypatch.setattr("marketdata.stream.asyncio.sleep", _no_sleep)

    calls = {"n": 0}
    received: list[str] = []
    stream: ReconnectingStream

    def connector(_: str) -> _FakeWS:
        calls["n"] += 1
        # First connection fails; the second succeeds.
        return _FakeWS(["ok"], fail=calls["n"] == 1)

    def on_msg(m: str | bytes) -> None:
        received.append(str(m))
        stream.stop()

    stream = ReconnectingStream("ws://test", on_msg, connector=connector)
    asyncio.run(stream.run())
    assert received == ["ok"]
    assert calls["n"] == 2  # reconnected once


def test_stream_manager_has_both_markets() -> None:
    mgr = StreamManager(connector=lambda _: _FakeWS([]))
    assert mgr.hub(Market.spot) is mgr.spot
    assert mgr.hub(Market.futures) is mgr.futures
