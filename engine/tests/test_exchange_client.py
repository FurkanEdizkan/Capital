"""Tests for the Binance REST client wrapper — hermetic (no network)."""

from decimal import Decimal
from typing import Any

import pytest
from binance.exceptions import BinanceAPIException

from exchange.client import BinanceClient, Market

_TICKER = {
    "symbol": "BTCUSDT",
    "lastPrice": "68420.55",
    "priceChangePercent": "2.41",
    "quoteVolume": "28400000000",
}
_KLINE = [
    1716163200000, "67000.0", "67500.0", "66800.0", "67320.0", "1234.5",
    1716166799999, "82000000.0", 5000, "600.0", "40000000.0", "0",
]
_MARK = {
    "symbol": "BTCUSDT",
    "lastFundingRate": "0.0001",
    "markPrice": "68421.10",
    "nextFundingTime": 1716192000000,
}
_BOOK = {"bids": [["68400.0", "1.5"]], "asks": [["68440.0", "0.8"]]}


class FakeBinanceLib:
    """Stand-in for `binance.client.Client` returning canned payloads."""

    def get_ticker(self, **kw: Any) -> Any:
        return _TICKER if kw.get("symbol") else [_TICKER]

    futures_ticker = get_ticker

    def get_klines(self, **_: Any) -> list[list[Any]]:
        return [_KLINE]

    futures_klines = get_klines

    def futures_mark_price(self, **_: Any) -> dict[str, Any]:
        return _MARK

    def get_order_book(self, **_: Any) -> dict[str, Any]:
        return _BOOK

    futures_order_book = get_order_book


@pytest.fixture
def bc() -> BinanceClient:
    return BinanceClient(client=FakeBinanceLib())  # type: ignore[arg-type]


def test_get_tickers(bc: BinanceClient) -> None:
    tickers = bc.get_tickers(Market.spot)
    assert len(tickers) == 1
    assert tickers[0].symbol == "BTCUSDT"
    assert tickers[0].price == Decimal("68420.55")


def test_get_ticker_single(bc: BinanceClient) -> None:
    t = bc.get_ticker("BTCUSDT", Market.futures)
    assert t.change_pct_24h == Decimal("2.41")


def test_get_klines(bc: BinanceClient) -> None:
    klines = bc.get_klines("BTCUSDT", "1h", Market.spot, limit=1)
    assert len(klines) == 1
    k = klines[0]
    assert k.open == Decimal("67000.0")
    assert k.close == Decimal("67320.0")
    assert k.open_time.year == 2024


def test_get_funding(bc: BinanceClient) -> None:
    f = bc.get_funding("BTCUSDT")
    assert f.funding_rate == Decimal("0.0001")
    assert f.mark_price == Decimal("68421.10")


def test_get_order_book(bc: BinanceClient) -> None:
    book = bc.get_order_book("BTCUSDT", Market.spot)
    assert book.bids[0].price == Decimal("68400.0")
    assert book.asks[0].qty == Decimal("0.8")


def test_call_retries_on_rate_limit(
    bc: BinanceClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exchange.client.time.sleep", lambda *_: None)
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise BinanceAPIException(None, 429, '{"code":-1003,"msg":"rate limited"}')
        return "ok"

    assert bc._call(flaky) == "ok"
    assert calls["n"] == 3


def test_call_reraises_non_rate_limit(
    bc: BinanceClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("exchange.client.time.sleep", lambda *_: None)

    def bad() -> str:
        raise BinanceAPIException(None, 400, '{"code":-1100,"msg":"bad symbol"}')

    with pytest.raises(BinanceAPIException):
        bc._call(bad)
