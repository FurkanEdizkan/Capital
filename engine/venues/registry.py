"""Venue registry — the catalogue of venues the platform supports.

Each `Venue` implementation (Binance, Alpaca, Polymarket) is registered here
with its asset class and capabilities. The UI lists this catalogue; `active`
marks the venue the trading engine currently routes through.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueInfo:
    """Catalogue entry for one supported venue."""

    name: str
    asset_class: str  # crypto | stocks | prediction-markets
    supports_sandbox: bool
    active: bool  # whether the trading engine currently routes through it


# Binance is the engine's live trading venue today. Alpaca and Polymarket are
# integrated as `Venue` implementations and become routable once the engine's
# data + execution paths are rewired through the `Venue` interface.
AVAILABLE_VENUES: tuple[VenueInfo, ...] = (
    VenueInfo("binance", "crypto", supports_sandbox=True, active=True),
    VenueInfo("alpaca", "stocks", supports_sandbox=True, active=False),
    VenueInfo("polymarket", "prediction-markets", supports_sandbox=False, active=False),
)


def list_venues() -> list[VenueInfo]:
    """Every venue the platform supports."""
    return list(AVAILABLE_VENUES)
