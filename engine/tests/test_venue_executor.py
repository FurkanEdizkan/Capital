"""Tests for the VenueExecutor — hermetic, fake `Venue`."""

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from trading.executors.base import ExecutionError, Order
from trading.executors.venue import VenueExecutor
from trading.models import FillSide, Trade
from venues.base import (
    Instrument,
    OrderRequest,
    OrderResult,
    Venue,
    VenueCandle,
    VenueError,
)


class FakeVenue(Venue):
    """A venue that records the order it was asked to place."""

    name = "binance"

    def __init__(self, *, reject: bool = False, no_fill: bool = False) -> None:
        self.reject = reject
        self.no_fill = no_fill
        self.requests: list[OrderRequest] = []

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        return Instrument(
            symbol=symbol,
            base="BTC",
            quote="USDT",
            tick_size=Decimal("0.01"),
            size_step=Decimal("0.00001"),
            min_notional=Decimal("5"),
        )

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        return []

    def price(self, symbol: str) -> Decimal:
        return Decimal("100")

    def place_order(self, request: OrderRequest) -> OrderResult:
        self.requests.append(request)
        if self.reject:
            raise VenueError("venue rejected")
        return OrderResult(
            symbol=request.symbol,
            side=request.side,
            filled_quantity=Decimal("0") if self.no_fill else request.quantity,
            price=Decimal("101"),
            fee=Decimal("0.1"),
            order_id="venue-555",
            client_order_id=request.client_order_id or "",
        )

    def positions(self) -> dict[str, Decimal]:
        return {}


def _order(market: str = "spot", side: FillSide = FillSide.buy, qty: str = "1") -> Order:
    return Order(
        strategy="S", market=market, symbol="BTCUSDT", side=side, quantity=Decimal(qty)
    )


def test_spot_order_records_a_trade(session: Session) -> None:
    venue = FakeVenue()
    fill = VenueExecutor(venue, mode="live").execute(
        session, _order(qty="0.1"), reference_price=Decimal("100")
    )
    assert fill.price == Decimal("101")
    assert fill.quantity == Decimal("0.1")
    trades = session.exec(select(Trade)).all()
    assert len(trades) == 1
    assert trades[0].mode == "live"


def test_client_order_id_is_sent_and_recorded(session: Session) -> None:
    venue = FakeVenue()
    VenueExecutor(venue, mode="testnet").execute(
        session, _order(qty="0.1"), reference_price=Decimal("100")
    )
    sent = venue.requests[0].client_order_id
    assert sent  # a clientOrderId was passed to the venue
    trade = session.exec(select(Trade)).first()
    assert trade is not None
    assert trade.client_order_id == sent
    assert trade.mode == "testnet"


def test_order_market_is_forwarded_to_the_venue(session: Session) -> None:
    venue = FakeVenue()
    VenueExecutor(venue, mode="live").execute(
        session, _order(market="futures", qty="0.1"), reference_price=Decimal("100")
    )
    assert venue.requests[0].market == "futures"


def test_below_min_notional_is_rejected(session: Session) -> None:
    # qty 0.01 * reference 100 = 1, below the MIN_NOTIONAL of 5.
    executor = VenueExecutor(FakeVenue(), mode="live")
    with pytest.raises(ExecutionError):
        executor.execute(session, _order(qty="0.01"), reference_price=Decimal("100"))


def test_dust_quantity_is_rejected(session: Session) -> None:
    executor = VenueExecutor(FakeVenue(), mode="live")
    with pytest.raises(ExecutionError):
        executor.execute(session, _order(qty="0.000001"), reference_price=Decimal("100"))


def test_venue_rejection_raises_execution_error(session: Session) -> None:
    executor = VenueExecutor(FakeVenue(reject=True), mode="live")
    with pytest.raises(ExecutionError):
        executor.execute(session, _order(qty="0.1"), reference_price=Decimal("100"))


def test_no_fill_raises_execution_error(session: Session) -> None:
    executor = VenueExecutor(FakeVenue(no_fill=True), mode="live")
    with pytest.raises(ExecutionError):
        executor.execute(session, _order(qty="0.1"), reference_price=Decimal("100"))


def test_filters_are_cached_per_symbol(session: Session) -> None:
    venue = FakeVenue()
    executor = VenueExecutor(venue, mode="live")
    executor.execute(session, _order(qty="0.1"), reference_price=Decimal("100"))
    assert ("BTCUSDT", "spot") in executor._filters
