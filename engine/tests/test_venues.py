"""Tests for the Venue abstraction interface."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trading.models import FillSide
from venues.base import (
    Instrument,
    OrderRequest,
    OrderResult,
    OrderType,
    Venue,
    VenueCandle,
)


class _FakeVenue(Venue):
    """A minimal concrete venue — proves the interface is implementable."""

    name = "fake"
    supports_sandbox = True

    def instrument(self, symbol: str) -> Instrument:
        return Instrument(
            symbol=symbol,
            base="BTC",
            quote="USDT",
            tick_size=Decimal("0.01"),
            size_step=Decimal("0.001"),
            min_notional=Decimal("10"),
        )

    def candles(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[VenueCandle]:
        return [
            VenueCandle(
                open_time=datetime(2026, 1, 1, tzinfo=UTC),
                open=Decimal("1"),
                high=Decimal("1"),
                low=Decimal("1"),
                close=Decimal("1"),
                volume=Decimal("1"),
            )
        ]

    def price(self, symbol: str) -> Decimal:
        return Decimal("100")

    def place_order(self, request: OrderRequest) -> OrderResult:
        return OrderResult(
            symbol=request.symbol,
            side=request.side,
            filled_quantity=request.quantity,
            price=Decimal("100"),
            fee=Decimal("0.1"),
            order_id="order-1",
        )

    def positions(self) -> dict[str, Decimal]:
        return {"BTCUSDT": Decimal("1")}


def test_venue_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        Venue()  # type: ignore[abstract] — the ABC is not concrete


def test_concrete_venue_satisfies_the_interface() -> None:
    venue = _FakeVenue()
    assert venue.name == "fake"
    assert venue.supports_sandbox is True
    assert venue.instrument("BTCUSDT").min_notional == Decimal("10")
    assert len(venue.candles("BTCUSDT", "1h")) == 1
    assert venue.price("BTCUSDT") == Decimal("100")
    assert venue.positions() == {"BTCUSDT": Decimal("1")}


def test_order_request_defaults_to_market() -> None:
    request = OrderRequest(symbol="BTCUSDT", side=FillSide.buy, quantity=Decimal("2"))
    assert request.order_type is OrderType.market
    assert request.limit_price is None


def test_place_order_returns_a_fill() -> None:
    result = _FakeVenue().place_order(
        OrderRequest(symbol="BTCUSDT", side=FillSide.buy, quantity=Decimal("2"))
    )
    assert result.filled_quantity == Decimal("2")
    assert result.fee == Decimal("0.1")
    assert result.order_id == "order-1"


def test_instrument_is_immutable() -> None:
    instrument = Instrument(
        symbol="X",
        base="X",
        quote="USD",
        tick_size=Decimal("0.01"),
        size_step=Decimal("1"),
        min_notional=Decimal("1"),
    )
    with pytest.raises(FrozenInstanceError):
        instrument.symbol = "Y"  # type: ignore[misc] — frozen dataclass
