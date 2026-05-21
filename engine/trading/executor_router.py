"""Executor routing — pick the executor for the active venue and mode.

The active venue and the trading mode (Sim / Testnet / Live) are runtime
settings an operator changes from the Settings page. The engine resolves the
executor through an `ExecutorRouter` on every tick, so a change takes effect
without a restart:

- **Sim** — the `SimExecutor` (paper fills); always available, no credentials.
- **Testnet / Live** — a `VenueExecutor` wrapping the active venue, built from
  its stored, encrypted credentials and cached per `(venue, mode)`.

If the active venue's credentials are missing the router falls back to Sim
with a warning — a misconfigured live mode must never halt trading.
"""

import logging

from sqlmodel import Session

from appsettings.store import (
    TradingMode,
    get_active_venue,
    get_mode,
    venue_credentials_configured,
)
from trading.executors.base import BaseExecutor
from trading.executors.sim import SimExecutor
from trading.executors.venue import VenueExecutor
from trading.venue_router import VenueBuilder
from venues.factory import build_venue
from venues.registry import get_venue

log = logging.getLogger("capital.trading.executor_router")


class ExecutorRouter:
    """Resolves the `BaseExecutor` for the active venue and trading mode."""

    def __init__(
        self,
        *,
        sim: BaseExecutor | None = None,
        builder: VenueBuilder = build_venue,
    ) -> None:
        self._sim = sim or SimExecutor()
        self._builder = builder
        # Executors are cached per (venue, mode) — rebuilding each tick would
        # drop the venue's connection and per-symbol setup caches.
        self._cache: dict[tuple[str, TradingMode], BaseExecutor] = {}

    def resolve(self, session: Session) -> BaseExecutor:
        """The executor for the active venue and mode stored in the database."""
        mode = get_mode(session)
        if mode is TradingMode.sim:
            return self._sim

        venue_name = get_active_venue(session)
        cached = self._cache.get((venue_name, mode))
        if cached is not None:
            return cached

        info = get_venue(venue_name)
        required = info.credential_fields if info is not None else ()
        if not venue_credentials_configured(session, venue_name, required):
            log.warning(
                "mode is %s but %s credentials are not configured — "
                "falling back to Sim",
                mode.value,
                venue_name,
            )
            return self._sim

        try:
            venue = self._builder(session, venue_name, mode)
        except KeyError:
            log.warning("venue %r is not wired — falling back to Sim", venue_name)
            return self._sim

        executor = VenueExecutor(venue, mode=mode.value)
        self._cache[(venue_name, mode)] = executor
        log.info(
            "routing orders through the %s executor (%s)", mode.value, venue_name
        )
        return executor
