"""Venue registry — the catalogue of venues the platform supports.

Each `Venue` implementation (Binance, Alpaca, Polymarket, Binance Alpha) is
registered here with its asset class and capabilities. Which venue is *active*
— the one the engine trades through — is a runtime setting
(`appsettings.store`), not a fixed property, so it is not stored on the
catalogue entry.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueInfo:
    """Catalogue entry for one supported venue."""

    name: str
    asset_class: str  # crypto | stocks | prediction-markets | tokenized-stocks
    supports_sandbox: bool
    #: Credential field names the venue needs to place orders. Stored
    #: encrypted, per-venue, in `appsettings` (see store.set_venue_credentials).
    credential_fields: tuple[str, ...]


AVAILABLE_VENUES: tuple[VenueInfo, ...] = (
    VenueInfo(
        "binance", "crypto", supports_sandbox=True,
        credential_fields=("api_key", "api_secret"),
    ),
    VenueInfo(
        "alpaca", "stocks", supports_sandbox=True,
        credential_fields=("api_key", "api_secret"),
    ),
    VenueInfo(
        "polymarket", "prediction-markets", supports_sandbox=False,
        credential_fields=("wallet_private_key", "wallet_address"),
    ),
    VenueInfo(
        # Binance Alpha tokenized stocks (Ondo) — read-only market data; no
        # confirmed order API yet, so no credentials and no sandbox.
        "binance-alpha", "tokenized-stocks", supports_sandbox=False,
        credential_fields=(),
    ),
)

#: Venue names that exist — for validating an active-venue change.
VENUE_NAMES: frozenset[str] = frozenset(v.name for v in AVAILABLE_VENUES)


def list_venues() -> list[VenueInfo]:
    """Every venue the platform supports."""
    return list(AVAILABLE_VENUES)


def get_venue(name: str) -> VenueInfo | None:
    """The catalogue entry for `name`, or None if the venue is unknown."""
    return next((v for v in AVAILABLE_VENUES if v.name == name), None)
