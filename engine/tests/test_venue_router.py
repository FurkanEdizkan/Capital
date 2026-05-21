"""Tests for the venue router — active-venue resolution."""

from decimal import Decimal
from typing import Any

from sqlmodel import Session

from appsettings.store import set_active_venue
from trading.venue_router import VenueRouter
from venues.base import Instrument, OrderResult, Venue, VenueCandle


class _FakeVenue(Venue):
    def __init__(self, name: str) -> None:
        self.name = name

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        raise NotImplementedError

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        return []

    def price(self, symbol: str) -> Decimal:
        return Decimal("1")

    def place_order(self, request: Any) -> OrderResult:
        raise NotImplementedError

    def positions(self) -> dict[str, Decimal]:
        return {}


def _builder(venues: dict[str, _FakeVenue]):
    """A venue builder over a fixed map — raises KeyError for unknown names."""

    def build(session: Session, name: str, mode: Any) -> Venue:
        return venues[name]

    return build


def test_resolves_the_default_venue(session: Session) -> None:
    binance = _FakeVenue("binance")
    # The active-venue setting defaults to binance.
    router = VenueRouter(builder=_builder({"binance": binance}))
    assert router.resolve(session) is binance


def test_resolves_the_active_venue(session: Session) -> None:
    binance, alpaca = _FakeVenue("binance"), _FakeVenue("alpaca")
    router = VenueRouter(builder=_builder({"binance": binance, "alpaca": alpaca}))
    set_active_venue(session, "alpaca")
    assert router.resolve(session) is alpaca


def test_unwired_active_venue_falls_back_to_default(session: Session) -> None:
    binance = _FakeVenue("binance")
    # The builder only knows binance — an unknown active venue raises KeyError.
    router = VenueRouter(builder=_builder({"binance": binance}))
    set_active_venue(session, "polymarket")
    assert router.resolve(session) is binance


def test_default_factory_resolves_binance(session: Session) -> None:
    # The production router builds a real Binance venue out of the box.
    assert VenueRouter.default().resolve(session).name == "binance"
