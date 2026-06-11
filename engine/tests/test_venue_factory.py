"""Tests for venue construction — build_venue from stored credentials."""

import pytest
from sqlmodel import Session

from appsettings.store import TradingMode, set_venue_credentials
from venues.binance import BinanceVenue
from venues.factory import build_venue
from venues.polymarket import PolymarketVenue


def test_binance_without_credentials_is_read_only(session: Session) -> None:
    venue = build_venue(session, "binance", TradingMode.sim)
    assert isinstance(venue, BinanceVenue)
    assert venue._order_client is None  # no keys → market data only


def test_polymarket_without_credentials_is_read_only(session: Session) -> None:
    venue = build_venue(session, "polymarket", TradingMode.live)
    assert isinstance(venue, PolymarketVenue)
    assert venue._order_client is None  # no signing client → market data only


def test_polymarket_partial_credentials_stay_read_only(session: Session) -> None:
    # A wallet address alone enables position reads, never order signing.
    set_venue_credentials(session, "polymarket", {"wallet_address": "0xAB"})
    venue = build_venue(session, "polymarket", TradingMode.live)
    assert isinstance(venue, PolymarketVenue)
    assert venue._order_client is None
    assert venue._wallet_address == "0xAB"


def test_unknown_venue_raises_key_error(session: Session) -> None:
    with pytest.raises(KeyError):
        build_venue(session, "nasdaq", TradingMode.sim)
