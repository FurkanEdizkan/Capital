"""Venue construction — build a `Venue` from stored, encrypted credentials.

Both routers build venues the same way: the market-data `VenueRouter` and the
order-routing `ExecutorRouter`. Centralising it here keeps them consistent —
one place decides how each venue is wired from its credentials.

Binance market data is public, so a Binance venue is always usable; an
authenticated order client is added only when keys are stored.
"""

import logging
from decimal import Decimal

from binance.client import Client
from sqlmodel import Session

from appsettings.store import TradingMode, get_venue_credentials
from exchange.client import BinanceClient
from venues.base import Venue
from venues.binance import BinanceVenue
from venues.polymarket import PolymarketOrderClient, PolymarketVenue

log = logging.getLogger("capital.venues.factory")

#: Every venue class, keyed by its catalogue name.
_VENUE_CLASSES: dict[str, type[Venue]] = {
    BinanceVenue.name: BinanceVenue,
    PolymarketVenue.name: PolymarketVenue,
}

#: Credential fields Polymarket order signing needs (registry's full set).
_POLYMARKET_ORDER_FIELDS = ("private_key", "api_key", "api_secret", "passphrase")


def venue_fee_rates() -> dict[str, Decimal]:
    """Each venue's representative taker fee rate — for cost visibility."""
    return {name: cls.fee_rate for name, cls in _VENUE_CLASSES.items()}


def build_venue(session: Session, name: str, mode: TradingMode) -> Venue:
    """Construct the `Venue` for `name`, wired with whatever credentials exist.

    `mode` selects sandbox vs. live wiring (Binance Testnet).
    Raises `KeyError` for an unknown venue name — callers handle the fallback.
    """
    creds = get_venue_credentials(session, name)

    if name == "binance":
        if "api_key" in creds and "api_secret" in creds:
            client = Client(
                creds["api_key"],
                creds["api_secret"],
                testnet=mode is TradingMode.testnet,
            )
            return BinanceVenue(client=BinanceClient(client), order_client=client)
        # No keys — public market data only (read-only).
        return BinanceVenue()

    if name == "polymarket":
        # Polymarket has no testnet; `mode` cannot select a sandbox here.
        # Market data is public — the venue is always readable. The signing
        # client is wired only when the full credential set is stored.
        wallet = creds.get("wallet_address", "")
        if all(field in creds for field in _POLYMARKET_ORDER_FIELDS):
            order_client = PolymarketOrderClient.from_credentials(
                private_key=creds["private_key"],
                api_key=creds["api_key"],
                api_secret=creds["api_secret"],
                passphrase=creds["passphrase"],
                wallet_address=wallet,
            )
            return PolymarketVenue(order_client=order_client, wallet_address=wallet)
        return PolymarketVenue(wallet_address=wallet)

    raise KeyError(name)
