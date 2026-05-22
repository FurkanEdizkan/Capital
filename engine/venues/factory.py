"""Venue construction — build a `Venue` from stored, encrypted credentials.

Both routers build venues the same way: the market-data `VenueRouter` and the
order-routing `ExecutorRouter`. Centralising it here keeps them consistent —
one place decides how each venue is wired from its credentials.

Binance market data is public, so a Binance venue is always usable; an
authenticated order client is added only when keys are stored. Alpaca needs
its key/secret for both data and orders. Polymarket order placement needs a
wallet-signing client that is not yet wired, so it is built read-only.
"""

import logging
from decimal import Decimal

from binance.client import Client
from sqlmodel import Session

from appsettings.store import TradingMode, get_venue_credentials
from exchange.client import BinanceClient
from venues.alpaca import AlpacaVenue
from venues.base import Venue
from venues.binance import BinanceVenue
from venues.binance_alpha import BinanceAlphaVenue
from venues.polymarket import PolymarketVenue

log = logging.getLogger("capital.venues.factory")

#: Every venue class, keyed by its catalogue name.
_VENUE_CLASSES: dict[str, type[Venue]] = {
    BinanceVenue.name: BinanceVenue,
    AlpacaVenue.name: AlpacaVenue,
    PolymarketVenue.name: PolymarketVenue,
    BinanceAlphaVenue.name: BinanceAlphaVenue,
}


def venue_fee_rates() -> dict[str, Decimal]:
    """Each venue's representative taker fee rate — for cost visibility."""
    return {name: cls.fee_rate for name, cls in _VENUE_CLASSES.items()}


def build_venue(session: Session, name: str, mode: TradingMode) -> Venue:
    """Construct the `Venue` for `name`, wired with whatever credentials exist.

    `mode` selects sandbox vs. live wiring (Binance Testnet, Alpaca paper).
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

    if name == "alpaca":
        # Alpaca's paper environment maps to Capital's non-live modes.
        return AlpacaVenue(
            api_key=creds.get("api_key", ""),
            api_secret=creds.get("api_secret", ""),
            paper=mode is not TradingMode.live,
        )

    if name == "polymarket":
        # Order placement needs a wallet-signing client (py-clob-client),
        # which is not yet wired — so this venue is read-only: place_order
        # raises VenueError. Market data works without credentials.
        return PolymarketVenue(wallet_address=creds.get("wallet_address", ""))

    if name == "binance-alpha":
        # Tokenized stocks — read-only public market data (no order API yet).
        return BinanceAlphaVenue()

    raise KeyError(name)
