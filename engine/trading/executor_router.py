"""Executor routing — pick the executor for the active trading mode.

The trading mode (Sim / Testnet / Live) is a runtime setting an operator
changes from the Settings page. The engine resolves the executor through an
`ExecutorRouter` on every tick, so a mode switch takes effect without a
restart:

- **Sim** — the `SimExecutor` (paper fills); always available, no keys.
- **Testnet / Live** — a `TestnetExecutor` / `LiveExecutor` built lazily from
  the stored, encrypted Binance keys and cached per mode.

If keys are missing the router falls back to Sim with a warning — a
misconfigured live mode must never halt trading.
"""

import logging
from collections.abc import Callable
from typing import Any

from binance.client import Client
from sqlmodel import Session

from appsettings.store import TradingMode, get_binance_keys, get_mode
from trading.executors.base import BaseExecutor
from trading.executors.live import LiveExecutor
from trading.executors.sim import SimExecutor
from trading.executors.testnet import TestnetExecutor

log = logging.getLogger("capital.trading.executor_router")

#: Builds a python-binance client: `(api_key, api_secret, testnet) -> Client`.
ClientFactory = Callable[[str, str, bool], Any]


def _default_client_factory(api_key: str, api_secret: str, testnet: bool) -> Client:
    return Client(api_key, api_secret, testnet=testnet)


class ExecutorRouter:
    """Resolves the `BaseExecutor` for the current trading mode."""

    def __init__(
        self,
        *,
        sim: BaseExecutor | None = None,
        client_factory: ClientFactory = _default_client_factory,
    ) -> None:
        self._sim = sim or SimExecutor()
        self._client_factory = client_factory
        # Testnet/Live executors are cached per mode — rebuilding each tick
        # would drop the futures leverage/margin setup cache and re-ping it.
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
        client = self._client_factory(api_key, api_secret, mode is TradingMode.testnet)
        executor: BaseExecutor = (
            TestnetExecutor(client)
            if mode is TradingMode.testnet
            else LiveExecutor(client)
        )
        self._cache[mode] = executor
        log.info("routing orders through the %s executor", mode.value)
        return executor
