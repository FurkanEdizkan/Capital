"""Tests for the venue router — active-venue resolution."""

from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import Session

from appsettings.store import set_active_venue
from trading.venue_router import VenueRouter
from venues.base import Instrument, OrderResult, Venue, VenueCandle


class _FakeVenue(Venue):
    def __init__(self, name: str) -> None:
        self.name = name

    def instrument(self, symbol: str) -> Instrument:
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


def test_resolves_the_default_venue(session: Session) -> None:
    binance = _FakeVenue("binance")
    # The active-venue setting defaults to binance.
    assert VenueRouter({"binance": binance}).resolve(session) is binance


def test_resolves_the_active_venue(session: Session) -> None:
    binance, alpaca = _FakeVenue("binance"), _FakeVenue("alpaca")
    router = VenueRouter({"binance": binance, "alpaca": alpaca})
    set_active_venue(session, "alpaca")
    assert router.resolve(session) is alpaca


def test_unwired_active_venue_falls_back_to_default(session: Session) -> None:
    binance = _FakeVenue("binance")
    router = VenueRouter({"binance": binance})
    set_active_venue(session, "polymarket")  # selected but not wired
    assert router.resolve(session) is binance


def test_default_must_be_in_the_venue_map() -> None:
    with pytest.raises(ValueError):
        VenueRouter({"alpaca": _FakeVenue("alpaca")})  # default "binance" absent


def test_default_factory_wires_binance(session: Session) -> None:
    assert VenueRouter.default().resolve(session).name == "binance"
