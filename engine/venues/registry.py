"""Venue registry — the catalogue of venues the platform supports.

Each `Venue` implementation (Binance, Alpaca, Polymarket) is registered here
with its asset class and capabilities. Which venue is *active* — the one the
engine trades through — is a runtime setting (`appsettings.store`), not a
fixed property, so it is not stored on the catalogue entry.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueInfo:
    """Catalogue entry for one supported venue."""

    name: str
    asset_class: str  # crypto | stocks | prediction-markets
    supports_sandbox: bool


AVAILABLE_VENUES: tuple[VenueInfo, ...] = (
    VenueInfo("binance", "crypto", supports_sandbox=True),
    VenueInfo("alpaca", "stocks", supports_sandbox=True),
    VenueInfo("polymarket", "prediction-markets", supports_sandbox=False),
)

#: Venue names that exist — for validating an active-venue change.
VENUE_NAMES: frozenset[str] = frozenset(v.name for v in AVAILABLE_VENUES)


def list_venues() -> list[VenueInfo]:
    """Every venue the platform supports."""
    return list(AVAILABLE_VENUES)
