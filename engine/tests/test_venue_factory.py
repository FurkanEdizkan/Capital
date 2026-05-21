"""Tests for venue construction — build_venue from stored credentials."""

import pytest
from sqlmodel import Session

from appsettings.store import TradingMode, set_venue_credentials
from venues.alpaca import AlpacaVenue
from venues.binance import BinanceVenue
from venues.factory import build_venue
from venues.polymarket import PolymarketVenue


def test_binance_without_credentials_is_read_only(session: Session) -> None:
    venue = build_venue(session, "binance", TradingMode.sim)
    assert isinstance(venue, BinanceVenue)
    assert venue._order_client is None  # no keys → market data only


def test_alpaca_uses_paper_for_non_live_modes(session: Session) -> None:
    set_venue_credentials(session, "alpaca", {"api_key": "k", "api_secret": "s"})
    venue = build_venue(session, "alpaca", TradingMode.testnet)
    assert isinstance(venue, AlpacaVenue)
    assert venue._trading.startswith("https://paper-api")


def test_alpaca_uses_live_for_live_mode(session: Session) -> None:
    set_venue_credentials(session, "alpaca", {"api_key": "k", "api_secret": "s"})
    venue = build_venue(session, "alpaca", TradingMode.live)
    assert isinstance(venue, AlpacaVenue)
    assert venue._trading == "https://api.alpaca.markets"


def test_polymarket_is_read_only(session: Session) -> None:
    # Order placement needs a wallet-signing client that is not yet wired.
    venue = build_venue(session, "polymarket", TradingMode.live)
    assert isinstance(venue, PolymarketVenue)
    assert venue._order_client is None


def test_unknown_venue_raises_key_error(session: Session) -> None:
    with pytest.raises(KeyError):
        build_venue(session, "nasdaq", TradingMode.sim)
