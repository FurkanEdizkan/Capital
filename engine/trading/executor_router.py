"""Executor routing — pick the executor for the active trading mode.

The trading mode (Sim / Testnet / Live) is a runtime setting an operator
changes from the Settings page. The engine resolves the executor through an
`ExecutorRouter` on every tick, so a mode switch takes effect without a
restart:

- **Sim** — the `SimExecutor` (paper fills); always available, no keys.
- **Testnet / Live** — a `VenueExecutor` wrapping a `Venue` built lazily from
  the stored, encrypted Binance keys and cached per mode. The venue places the
  actual orders; the executor only sizes, validates and records them.

If keys are missing the router falls back to Sim with a warning — a
misconfigured live mode must never halt trading.
"""

import logging
from collections.abc import Callable

from binance.client import Client
from sqlmodel import Session

from appsettings.store import TradingMode, get_binance_keys, get_mode
from exchange.client import BinanceClient
from trading.executors.base import BaseExecutor
from trading.executors.sim import SimExecutor
from trading.executors.venue import VenueExecutor
from venues.base import Venue
from venues.binance import BinanceVenue

log = logging.getLogger("capital.trading.executor_router")

#: Builds an order-capable `Venue`: `(api_key, api_secret, testnet) -> Venue`.
VenueFactory = Callable[[str, str, bool], Venue]


def _default_venue_factory(api_key: str, api_secret: str, testnet: bool) -> Venue:
    """Build a Binance venue with an authenticated order client."""
    client = Client(api_key, api_secret, testnet=testnet)
    return BinanceVenue(client=BinanceClient(client), order_client=client)


class ExecutorRouter:
    """Resolves the `BaseExecutor` for the current trading mode."""

    def __init__(
        self,
        *,
        sim: BaseExecutor | None = None,
        venue_factory: VenueFactory = _default_venue_factory,
    ) -> None:
        self._sim = sim or SimExecutor()
        self._venue_factory = venue_factory
        # Testnet/Live executors are cached per mode — rebuilding each tick
        # would drop the venue's futures setup cache and re-ping it.
        self._cache: dict[TradingMode, BaseExecutor] = {}

    def resolve(self, session: Session) -> BaseExecutor:
        """The executor for the mode stored in `session`'s database."""
        mode = get_mode(session)
        if mode is TradingMode.sim:
            return self._sim
        if mode in self._cache:
            return self._cache[mode]

        keys = get_binance_keys(session)
        if keys is None:
            log.warning(
                "trading mode is %s but Binance keys are not configured — "
                "falling back to Sim",
                mode.value,
            )
            return self._sim

        api_key, api_secret = keys
        venue = self._venue_factory(api_key, api_secret, mode is TradingMode.testnet)
        executor = VenueExecutor(venue, mode=mode.value)
        self._cache[mode] = executor
        log.info("routing orders through the %s executor (%s)", mode.value, venue.name)
        return executor
