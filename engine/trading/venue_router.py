"""Venue routing — resolve the market-data `Venue` for the active setting.

The active venue is a runtime setting (`appsettings.store`). The trading
engine resolves its `Venue` through a `VenueRouter` each tick, so switching
the venue from the Settings page takes effect without a restart. The venue is
built fresh from stored credentials via `venues.factory.build_venue`; an
unknown venue name falls back to the default with a warning, so the engine
never stalls on a misconfiguration.
"""

import logging
from collections.abc import Callable

from sqlmodel import Session

from appsettings.store import get_active_venue, get_mode
from venues.base import Venue
from venues.factory import build_venue

log = logging.getLogger("capital.trading.venue_router")

#: Builds a `Venue`: `(session, name, mode) -> Venue`. Raises KeyError if the
#: name is unknown. `venues.factory.build_venue` is the production builder;
#: tests inject a fake.
VenueBuilder = Callable[..., Venue]


class VenueRouter:
    """Resolves the market-data `Venue` named by the active-venue setting."""

    def __init__(
        self, *, builder: VenueBuilder = build_venue, default: str = "binance"
    ) -> None:
        self._builder = builder
        self._default = default

    @classmethod
    def default(cls) -> "VenueRouter":
        """The engine's out-of-the-box router (Binance default)."""
        return cls()

    def resolve(self, session: Session) -> Venue:
        """Build the `Venue` for the active-venue setting, or the default."""
        name = get_active_venue(session)
        mode = get_mode(session)
        try:
            return self._builder(session, name, mode)
        except KeyError:
            log.warning(
                "active venue %r is not wired — falling back to %s",
                name,
                self._default,
            )
            return self._builder(session, self._default, mode)
