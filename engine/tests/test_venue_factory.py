"""Tests for venue construction — build_venue from stored credentials."""

import pytest
from sqlmodel import Session

from appsettings.store import TradingMode
from venues.binance import BinanceVenue
from venues.factory import build_venue


def test_binance_without_credentials_is_read_only(session: Session) -> None:
    venue = build_venue(session, "binance", TradingMode.sim)
    assert isinstance(venue, BinanceVenue)
    assert venue._order_client is None  # no keys → market data only


def test_unknown_venue_raises_key_error(session: Session) -> None:
    with pytest.raises(KeyError):
        build_venue(session, "nasdaq", TradingMode.sim)
