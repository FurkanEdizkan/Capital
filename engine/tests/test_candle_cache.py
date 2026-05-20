"""Tests for the candle cache — refresh, dedup, ordered reads."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlmodel import Session

from exchange.client import Kline, Market
from marketdata.cache import (
    download_candles,
    get_cached_candles,
    get_candle_range,
    refresh_candles,
)


def _klines(n: int, start_hour: int = 0) -> list[Kline]:
    base = datetime(2024, 5, 20, tzinfo=UTC)
    out = []
    for i in range(start_hour, start_hour + n):
        t = base + timedelta(hours=i)
        out.append(
            Kline(
                open_time=t,
                open=Decimal("100"),
                high=Decimal("110"),
                low=Decimal("90"),
                close=Decimal("105") + Decimal(i),
                volume=Decimal("1000"),
                close_time=t + timedelta(minutes=59),
            )
        )
    return out


class FakeClient:
    def __init__(self, klines: list[Kline]) -> None:
        self._k = klines

    def get_klines(self, *_: Any, **__: Any) -> list[Kline]:
        return self._k

    def get_historical_klines(self, *_: Any, **__: Any) -> list[Kline]:
        return self._k


def test_refresh_stores_and_returns_ordered(session: Session) -> None:
    client = FakeClient(_klines(10))
    candles = refresh_candles(
        session, client, market=Market.spot, symbol="BTCUSDT", interval="1h"  # type: ignore[arg-type]
    )
    assert len(candles) == 10
    # oldest-first
    times = [c.open_time for c in candles]
    assert times == sorted(times)
    assert candles[0].symbol == "BTCUSDT"


def test_refresh_is_idempotent(session: Session) -> None:
    client = FakeClient(_klines(10))
    refresh_candles(session, client, market=Market.spot, symbol="ETHUSDT", interval="1h")  # type: ignore[arg-type]
    refresh_candles(session, client, market=Market.spot, symbol="ETHUSDT", interval="1h")  # type: ignore[arg-type]
    cached = get_cached_candles(session, market=Market.spot, symbol="ETHUSDT", interval="1h")
    assert len(cached) == 10  # no duplicates


def test_refresh_appends_new_bars(session: Session) -> None:
    refresh_candles(
        session, FakeClient(_klines(5)), market=Market.spot, symbol="SOLUSDT", interval="1h"  # type: ignore[arg-type]
    )
    # A later fetch overlaps the first 5 and adds 5 more.
    refresh_candles(
        session, FakeClient(_klines(10)), market=Market.spot, symbol="SOLUSDT", interval="1h"  # type: ignore[arg-type]
    )
    cached = get_cached_candles(session, market=Market.spot, symbol="SOLUSDT", interval="1h")
    assert len(cached) == 10


_START = datetime(2024, 5, 20, tzinfo=UTC)


def test_download_caches_history(session: Session) -> None:
    n = download_candles(
        session,
        FakeClient(_klines(8)),  # type: ignore[arg-type]
        market=Market.spot,
        symbol="BTCUSDT",
        interval="1h",
        start=_START,
    )
    assert n == 8
    cached = get_cached_candles(session, market=Market.spot, symbol="BTCUSDT", interval="1h")
    assert len(cached) == 8


def test_download_is_idempotent(session: Session) -> None:
    client = FakeClient(_klines(8))
    download_candles(
        session, client, market=Market.spot, symbol="ETHUSDT", interval="1h", start=_START  # type: ignore[arg-type]
    )
    again = download_candles(
        session, client, market=Market.spot, symbol="ETHUSDT", interval="1h", start=_START  # type: ignore[arg-type]
    )
    assert again == 0  # every candle was already cached


def test_get_candle_range_filters_by_time(session: Session) -> None:
    download_candles(
        session,
        FakeClient(_klines(10)),  # type: ignore[arg-type]
        market=Market.spot,
        symbol="SOLUSDT",
        interval="1h",
        start=_START,
    )
    rows = get_candle_range(
        session,
        market=Market.spot,
        symbol="SOLUSDT",
        interval="1h",
        start=_START + timedelta(hours=3),
        end=_START + timedelta(hours=6),
    )
    assert len(rows) == 4  # hours 3, 4, 5, 6 inclusive
    assert [r.open_time for r in rows] == sorted(r.open_time for r in rows)


def test_markets_are_isolated(session: Session) -> None:
    refresh_candles(
        session, FakeClient(_klines(3)), market=Market.spot, symbol="BTCUSDT", interval="1h"  # type: ignore[arg-type]
    )
    refresh_candles(
        session, FakeClient(_klines(7)), market=Market.futures, symbol="BTCUSDT", interval="1h"  # type: ignore[arg-type]
    )
    spot = get_cached_candles(session, market=Market.spot, symbol="BTCUSDT", interval="1h")
    futures = get_cached_candles(session, market=Market.futures, symbol="BTCUSDT", interval="1h")
    assert len(spot) == 3
    assert len(futures) == 7
