"""Tests for BinanceVenue — hermetic, fake market-data and order clients."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from binance.exceptions import BinanceAPIException

from exchange.client import Kline, Market, Ticker
from trading.executors.base import SymbolFilters
from trading.models import FillSide
from venues.base import OrderRequest, OrderType, VenueError
from venues.binance import BinanceVenue


class FakeMarketData:
    """Stand-in for `BinanceClient` — the read side."""

    def get_symbol_filters(self, symbol: str, market: Market) -> SymbolFilters:
        if symbol == "UNKNOWN":
            raise ValueError("unknown symbol")
        return SymbolFilters(
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("10"),
        )

    def get_klines(
        self, symbol: str, interval: str, market: Market, limit: int
    ) -> list[Kline]:
        self.last_klines_market = market
        t = datetime(2026, 1, 1, tzinfo=UTC)
        return [
            Kline(
                open_time=t,
                open=Decimal("100"),
                high=Decimal("105"),
                low=Decimal("95"),
                close=Decimal("102"),
                volume=Decimal("10"),
                close_time=t,
            )
        ]

    def get_ticker(self, symbol: str, market: Market) -> Ticker:
        return Ticker(
            symbol=symbol,
            price=Decimal("100"),
            change_pct_24h=Decimal("0"),
            quote_volume_24h=Decimal("0"),
        )

    def get_futures_positions(self) -> dict[str, Decimal]:
        return {"BTCUSDT": Decimal("0.5")}


class FakeOrderClient:
    """Stand-in for a python-binance order client."""

    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.calls: list[dict[str, Any]] = []
        self.methods: list[str] = []  # method names in call order

    def create_order(self, **kwargs: Any) -> dict[str, Any]:
        self.methods.append("create_order")
        self.calls.append(kwargs)
        if self.reject:
            raise BinanceAPIException(None, 400, '{"code":-2010,"msg":"rejected"}')
        return {
            "orderId": 555,
            "executedQty": "1.0",
            "fills": [{"price": "100", "qty": "1", "commission": "0.1"}],
        }

    def futures_create_order(self, **kwargs: Any) -> dict[str, Any]:
        self.methods.append("futures_create_order")
        self.calls.append(kwargs)
        return {"orderId": 777, "avgPrice": "200", "executedQty": "2"}

    def futures_change_leverage(self, **_: Any) -> dict[str, Any]:
        self.methods.append("futures_change_leverage")
        return {}

    def futures_change_margin_type(self, **_: Any) -> dict[str, Any]:
        self.methods.append("futures_change_margin_type")
        return {}


def _venue(*, futures: bool = False, with_orders: bool = True) -> BinanceVenue:
    return BinanceVenue(
        client=FakeMarketData(),  # type: ignore[arg-type]
        order_client=FakeOrderClient() if with_orders else None,
        market=Market.futures if futures else Market.spot,
    )


def test_instrument_splits_symbol_and_carries_filters() -> None:
    inst = _venue().instrument("BTCUSDT")
    assert inst.base == "BTC"
    assert inst.quote == "USDT"
    assert inst.tick_size == Decimal("0.01")
    assert inst.min_notional == Decimal("10")


def test_instrument_unknown_symbol_raises_venue_error() -> None:
    with pytest.raises(VenueError):
        _venue().instrument("UNKNOWN")


def test_candles_map_to_venue_candles() -> None:
    candles = _venue().candles("BTCUSDT", "1h")
    assert len(candles) == 1
    assert candles[0].close == Decimal("102")


def test_candles_default_to_the_venue_market() -> None:
    venue = _venue(futures=True)
    venue.candles("BTCUSDT", "1h")
    assert venue._client.last_klines_market is Market.futures  # type: ignore[union-attr]


def test_candles_market_override_selects_the_klines_market() -> None:
    venue = _venue()  # spot venue
    venue.candles("BTCUSDT", "1h", market="futures")
    assert venue._client.last_klines_market is Market.futures  # type: ignore[union-attr]


def test_price() -> None:
    assert _venue().price("BTCUSDT") == Decimal("100")


def test_positions_spot_is_empty_futures_reports() -> None:
    assert _venue(futures=False).positions() == {}
    assert _venue(futures=True).positions() == {"BTCUSDT": Decimal("0.5")}


def test_place_spot_order() -> None:
    result = _venue().place_order(
        OrderRequest(symbol="BTCUSDT", side=FillSide.buy, quantity=Decimal("1"))
    )
    assert result.filled_quantity == Decimal("1")
    assert result.price == Decimal("100")
    assert result.fee == Decimal("0.1")
    assert result.order_id == "555"


def test_place_futures_order() -> None:
    result = _venue(futures=True).place_order(
        OrderRequest(symbol="BTCUSDT", side=FillSide.sell, quantity=Decimal("2"))
    )
    assert result.price == Decimal("200")
    assert result.filled_quantity == Decimal("2")
    assert result.order_id == "777"


def test_read_only_venue_rejects_orders() -> None:
    with pytest.raises(VenueError):
        _venue(with_orders=False).place_order(
            OrderRequest(symbol="BTCUSDT", side=FillSide.buy, quantity=Decimal("1"))
        )


def test_limit_orders_are_rejected() -> None:
    with pytest.raises(VenueError):
        _venue().place_order(
            OrderRequest(
                symbol="BTCUSDT",
                side=FillSide.buy,
                quantity=Decimal("1"),
                order_type=OrderType.limit,
                limit_price=Decimal("99"),
            )
        )


def test_exchange_rejection_raises_venue_error() -> None:
    venue = BinanceVenue(
        client=FakeMarketData(),  # type: ignore[arg-type]
        order_client=FakeOrderClient(reject=True),
    )
    with pytest.raises(VenueError):
        venue.place_order(
            OrderRequest(symbol="BTCUSDT", side=FillSide.buy, quantity=Decimal("1"))
        )


def test_client_order_id_is_forwarded_to_binance() -> None:
    venue = _venue()
    venue.place_order(
        OrderRequest(
            symbol="BTCUSDT",
            side=FillSide.buy,
            quantity=Decimal("1"),
            client_order_id="coid-123",
        )
    )
    sent = venue._order_client.calls[0]  # type: ignore[union-attr]
    assert sent["newClientOrderId"] == "coid-123"


def test_order_result_echoes_the_client_order_id() -> None:
    result = _venue().place_order(
        OrderRequest(
            symbol="BTCUSDT",
            side=FillSide.buy,
            quantity=Decimal("1"),
            client_order_id="coid-xyz",
        )
    )
    assert result.client_order_id == "coid-xyz"


def test_order_market_override_selects_the_futures_endpoint() -> None:
    # A spot-default venue places a futures order when the request says so.
    venue = _venue()
    venue.place_order(
        OrderRequest(
            symbol="BTCUSDT",
            side=FillSide.sell,
            quantity=Decimal("1"),
            market="futures",
        )
    )
    assert "futures_create_order" in venue._order_client.methods  # type: ignore[union-attr]


def test_futures_order_configures_leverage_and_margin_once() -> None:
    venue = BinanceVenue(
        client=FakeMarketData(),  # type: ignore[arg-type]
        order_client=FakeOrderClient(),
        market=Market.futures,
        futures_leverage=5,
        futures_margin_type="ISOLATED",
    )
    req = OrderRequest(symbol="BTCUSDT", side=FillSide.buy, quantity=Decimal("1"))
    venue.place_order(req)
    venue.place_order(req)
    methods = venue._order_client.methods  # type: ignore[union-attr]
    assert methods.count("futures_change_leverage") == 1  # cached after the first
    assert "futures_change_margin_type" in methods
