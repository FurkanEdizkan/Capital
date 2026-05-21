"""Tests for BinanceAlphaVenue — hermetic, fake Alpha market-data API."""

from decimal import Decimal
from typing import Any

import pytest

from trading.models import FillSide
from venues.base import OrderRequest, VenueError
from venues.binance_alpha import BinanceAlphaVenue


class _Resp:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        return self._payload


def _ok(data: Any) -> _Resp:
    return _Resp({"code": "000000", "success": True, "data": data})


_KLINES = [
    # [openTime, open, high, low, close, volume, closeTime, ...]
    ["1700000000000", "10.0", "11.0", "9.5", "10.5", "100", "1700003599999",
     "0", "0", "0", "0", "0"],
]

_TICKER = {"lastPrice": "10.5", "priceChangePercent": "2.0"}

_EXCHANGE_INFO = [
    {
        "symbol": "ALPHA_175USDT",
        "baseAsset": "ALPHA_175",
        "quoteAsset": "USDT",
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
            {"filterType": "LOT_SIZE", "stepSize": "0.001"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
        ],
    }
]


class FakeHttp:
    """Routes Alpha endpoints by URL path; raises configurable failures."""

    def __init__(self, *, status: int = 200, success: bool = True) -> None:
        self._status = status
        self._success = success

    def get(self, url: str, params: dict[str, Any] | None = None) -> _Resp:
        if self._status >= 400:
            return _Resp({}, status=self._status)
        if not self._success:
            return _Resp({"success": False, "message": "boom", "code": "1"})
        if "klines" in url:
            return _ok(_KLINES)
        if "ticker" in url:
            return _ok(_TICKER)
        if "get-exchange-info" in url:
            return _ok(_EXCHANGE_INFO)
        return _ok(None)


def _venue(**kw: Any) -> BinanceAlphaVenue:
    return BinanceAlphaVenue(http=FakeHttp(**kw))


def test_candles_parse_the_12_element_arrays() -> None:
    candles = _venue().candles("ALPHA_175USDT", "1h")
    assert len(candles) == 1
    assert candles[0].open == Decimal("10.0")
    assert candles[0].close == Decimal("10.5")
    assert candles[0].volume == Decimal("100")


def test_price_reads_last_price() -> None:
    assert _venue().price("ALPHA_175USDT") == Decimal("10.5")


def test_instrument_parses_filters() -> None:
    inst = _venue().instrument("ALPHA_175USDT")
    assert inst.base == "ALPHA_175"
    assert inst.quote == "USDT"
    assert inst.tick_size == Decimal("0.01")
    assert inst.size_step == Decimal("0.001")
    assert inst.min_notional == Decimal("5")


def test_instrument_unknown_symbol_raises() -> None:
    with pytest.raises(VenueError):
        _venue().instrument("ALPHA_999USDT")


def test_place_order_is_read_only() -> None:
    with pytest.raises(VenueError):
        _venue().place_order(
            OrderRequest(symbol="ALPHA_175USDT", side=FillSide.buy, quantity=Decimal("1"))
        )


def test_positions_are_empty() -> None:
    assert _venue().positions() == {}


def test_http_error_raises_venue_error() -> None:
    with pytest.raises(VenueError):
        _venue(status=503).price("ALPHA_175USDT")


def test_unsuccessful_envelope_raises_venue_error() -> None:
    with pytest.raises(VenueError):
        _venue(success=False).price("ALPHA_175USDT")
