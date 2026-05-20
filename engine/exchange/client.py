"""Binance REST client wrapper — spot & USDⓈ-M futures market data.

Phase 1 is read-only public market data, so no API key is required. The
wrapper normalises Binance's raw payloads into typed models (Decimal money,
UTC datetimes) and retries transient rate-limit errors with backoff.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, TypeVar

from binance.client import Client
from binance.exceptions import BinanceAPIException
from pydantic import BaseModel

T = TypeVar("T")

_MAX_RETRIES = 3
_BACKOFF_SECONDS = 1.5


class Market(StrEnum):
    spot = "spot"
    futures = "futures"


class Ticker(BaseModel):
    symbol: str
    price: Decimal
    change_pct_24h: Decimal
    quote_volume_24h: Decimal


class Kline(BaseModel):
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime


class FundingRate(BaseModel):
    symbol: str
    funding_rate: Decimal
    mark_price: Decimal
    next_funding_time: datetime


class OrderBookLevel(BaseModel):
    price: Decimal
    qty: Decimal


class OrderBook(BaseModel):
    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]


def _ms_to_dt(ms: int | str) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)


def _levels(side: list[list[Any]]) -> list[OrderBookLevel]:
    return [OrderBookLevel(price=Decimal(str(p)), qty=Decimal(str(q))) for p, q in side]


class BinanceClient:
    """Typed wrapper over `python-binance` for market data."""

    def __init__(self, client: Client | None = None) -> None:
        # Injectable for tests; defaults to a real keyless public client.
        self._c = client if client is not None else Client()

    # -- rate-limit-aware call -------------------------------------------
    def _call(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        for attempt in range(_MAX_RETRIES):
            try:
                return fn(*args, **kwargs)
            except BinanceAPIException as exc:
                rate_limited = exc.status_code == 429 or exc.code == -1003
                if not rate_limited or attempt == _MAX_RETRIES - 1:
                    raise
                time.sleep(_BACKOFF_SECONDS * (attempt + 1))
        raise RuntimeError("unreachable")

    # -- tickers ----------------------------------------------------------
    @staticmethod
    def _parse_ticker(raw: dict[str, Any]) -> Ticker:
        return Ticker(
            symbol=raw["symbol"],
            price=Decimal(str(raw["lastPrice"])),
            change_pct_24h=Decimal(str(raw["priceChangePercent"])),
            quote_volume_24h=Decimal(str(raw["quoteVolume"])),
        )

    def get_tickers(self, market: Market = Market.spot) -> list[Ticker]:
        """24h rolling ticker for every symbol on the given market."""
        fn = self._c.futures_ticker if market is Market.futures else self._c.get_ticker
        raw = self._call(fn)
        return [self._parse_ticker(r) for r in raw]

    def get_ticker(self, symbol: str, market: Market = Market.spot) -> Ticker:
        fn = self._c.futures_ticker if market is Market.futures else self._c.get_ticker
        raw = self._call(fn, symbol=symbol)
        if isinstance(raw, list):  # futures_ticker may return a list
            raw = raw[0]
        return self._parse_ticker(raw)

    # -- klines -----------------------------------------------------------
    def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        market: Market = Market.spot,
        limit: int = 200,
    ) -> list[Kline]:
        fn = self._c.futures_klines if market is Market.futures else self._c.get_klines
        raw = self._call(fn, symbol=symbol, interval=interval, limit=limit)
        return [
            Kline(
                open_time=_ms_to_dt(k[0]),
                open=Decimal(str(k[1])),
                high=Decimal(str(k[2])),
                low=Decimal(str(k[3])),
                close=Decimal(str(k[4])),
                volume=Decimal(str(k[5])),
                close_time=_ms_to_dt(k[6]),
            )
            for k in raw
        ]

    # -- funding (futures only) ------------------------------------------
    def get_funding(self, symbol: str) -> FundingRate:
        raw = self._call(self._c.futures_mark_price, symbol=symbol)
        if isinstance(raw, list):
            raw = raw[0]
        return FundingRate(
            symbol=raw["symbol"],
            funding_rate=Decimal(str(raw["lastFundingRate"])),
            mark_price=Decimal(str(raw["markPrice"])),
            next_funding_time=_ms_to_dt(raw["nextFundingTime"]),
        )

    # -- order book -------------------------------------------------------
    def get_order_book(
        self, symbol: str, market: Market = Market.spot, limit: int = 20
    ) -> OrderBook:
        fn = (
            self._c.futures_order_book
            if market is Market.futures
            else self._c.get_order_book
        )
        raw = self._call(fn, symbol=symbol, limit=limit)
        return OrderBook(
            symbol=symbol,
            bids=_levels(raw["bids"]),
            asks=_levels(raw["asks"]),
        )
