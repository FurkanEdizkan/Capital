"""Built-in strategies registered with the engine on startup.

Phase 3 ships five strategy types — MA crossover, RSI mean-reversion, MACD
trend, Bollinger breakout and DCA — each ready to run on a default symbol.
UI-driven configuration of additional instances arrives with the Strategies
page; this stays the out-of-the-box default set.
"""

import logging
from collections.abc import Callable
from decimal import Decimal

from sqlmodel import Session

from exchange.client import Market
from strategies.base import BaseStrategy
from strategies.bollinger import BollingerStrategy
from strategies.dca import DCAStrategy
from strategies.ma_cross import MACrossStrategy
from strategies.macd import MACDStrategy
from strategies.rsi import RSIStrategy
from trading.portfolio import get_allocation, set_allocation

log = logging.getLogger("capital.strategies")

#: Default paper-trading budget seeded for each built-in strategy (sim USDT).
DEFAULT_ALLOCATION = Decimal("10000")


def default_strategies() -> list[BaseStrategy]:
    return [
        MACrossStrategy("MA Cross BTC", "BTCUSDT", market=Market.spot, timeframe="1h"),
        MACrossStrategy("MA Cross ETH", "ETHUSDT", market=Market.spot, timeframe="1h"),
        RSIStrategy("RSI Reversion BTC", "BTCUSDT", market=Market.spot, timeframe="1h"),
        MACDStrategy("MACD Trend ETH", "ETHUSDT", market=Market.spot, timeframe="1h"),
        BollingerStrategy("Bollinger Breakout BTC", "BTCUSDT", market=Market.spot, timeframe="1h"),
        DCAStrategy("DCA Accumulate BTC", "BTCUSDT", market=Market.spot, timeframe="1h"),
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
