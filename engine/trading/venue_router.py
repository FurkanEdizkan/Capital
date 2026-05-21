"""Venue routing — resolve the market-data `Venue` for the active setting.

The active venue is a runtime setting (`appsettings.store`). The trading
engine resolves its `Venue` through a `VenueRouter` each tick, so switching
the venue from the Settings page takes effect without a restart. A venue the
operator selects but which is not wired (e.g. no credentials) falls back to
the default with a warning, so the engine never stalls on a misconfiguration.
"""

import logging

from sqlmodel import Session

from appsettings.store import get_active_venue
from venues.base import Venue
from venues.binance import BinanceVenue

log = logging.getLogger("capital.trading.venue_router")


class VenueRouter:
    """Resolves the `Venue` named by the active-venue setting."""

    def __init__(self, venues: dict[str, Venue], *, default: str = "binance") -> None:
        if default not in venues:
            raise ValueError(f"default venue {default!r} must be in the venue map")
        self._venues = venues
        self._default = default

    @classmethod
    def default(cls) -> "VenueRouter":
        """A router with Binance wired — the engine's out-of-the-box venue."""
        return cls({"binance": BinanceVenue()})

    def resolve(self, session: Session) -> Venue:
        """The `Venue` for the active-venue setting, or the default."""
        name = get_active_venue(session)
        venue = self._venues.get(name)
        if venue is None:
            log.warning(
                "active venue %r is not wired — falling back to %s",
                name,
                self._default,
            )
            return self._venues[self._default]
        return venue
