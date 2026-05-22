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

from config import settings
from exchange.client import Market
from strategies.ai_strategy import AIStrategy
from strategies.base import BaseStrategy
from strategies.bollinger import BollingerStrategy
from strategies.dca import DCAStrategy
from strategies.loader import load_plugin_strategies
from strategies.ma_cross import MACrossStrategy
from strategies.macd import MACDStrategy
from strategies.rsi import RSIStrategy
from trading.lifecycle import set_enabled
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
        # AI strategies — each resolves its own provider+model per tick.
        # Seeded disabled (an LLM call costs money / needs credentials); the
        # operator picks a model and enables them from the Strategies page.
        AIStrategy("AI Trader BTC", "BTCUSDT", market=Market.spot, timeframe="1h"),
        AIStrategy("AI Trader ETH", "ETHUSDT", market=Market.spot, timeframe="1h"),
    ]


def all_strategies() -> list[BaseStrategy]:
    """Built-in defaults plus any discovered plugin strategies.

    Strategy names key the position sub-ledger and must be unique — a plugin
    that reuses a built-in (or another plugin's) name is logged and dropped.
    """
    combined: list[BaseStrategy] = list(default_strategies())
    seen = {s.name for s in combined}
    for strat in load_plugin_strategies(settings.strategy_plugins_dir):
        if strat.name in seen:
            log.warning("duplicate strategy name %r from plugin — skipping", strat.name)
            continue
        seen.add(strat.name)
        combined.append(strat)
    return combined


def seed_allocations(
    session_factory: Callable[[], Session], strategies: list[BaseStrategy]
) -> None:
    """Give each built-in strategy a starting budget if it has none yet."""
    with session_factory() as session:
        for strat in strategies:
            if get_allocation(session, strat.name) == 0:
                set_allocation(session, strat.name, DEFAULT_ALLOCATION)
                # AI strategies cost money per tick — seed them disabled so
                # the operator opts in after choosing a model.
                if getattr(strat, "kind", "") == "AI":
                    set_enabled(session, strat.name, False)
                log.info("seeded allocation for %r: %s", strat.name, DEFAULT_ALLOCATION)
