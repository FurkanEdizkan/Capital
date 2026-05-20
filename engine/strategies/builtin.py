"""Built-in strategies registered with the engine on startup.

Phase 2 ships one strategy type (MA crossover) on two symbols. Phase 3 adds
more strategy types and UI-driven configuration; this stays the default set.
"""

import logging
from collections.abc import Callable
from decimal import Decimal

from sqlmodel import Session

from exchange.client import Market
from strategies.base import BaseStrategy
from strategies.ma_cross import MACrossStrategy
from trading.portfolio import get_allocation, set_allocation

log = logging.getLogger("capital.strategies")

#: Default paper-trading budget seeded for each built-in strategy (sim USDT).
DEFAULT_ALLOCATION = Decimal("10000")


def default_strategies() -> list[BaseStrategy]:
    return [
        MACrossStrategy("MA Cross BTC", "BTCUSDT", market=Market.spot, timeframe="1h"),
        MACrossStrategy("MA Cross ETH", "ETHUSDT", market=Market.spot, timeframe="1h"),
    ]


def seed_allocations(
    session_factory: Callable[[], Session], strategies: list[BaseStrategy]
) -> None:
    """Give each built-in strategy a starting budget if it has none yet."""
    with session_factory() as session:
        for strat in strategies:
            if get_allocation(session, strat.name) == 0:
                set_allocation(session, strat.name, DEFAULT_ALLOCATION)
                log.info("seeded allocation for %r: %s", strat.name, DEFAULT_ALLOCATION)
