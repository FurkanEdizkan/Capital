"""AIStrategy — delegates the trade decision to an LLM each tick.

Every tick the strategy assembles a context pack (recent candles, position,
allocation, price), asks the configured `LLMProvider` for a structured
`Decision`, and turns it into an `Order`. The order still flows through the
engine's allocation enforcement and risk manager — the AI can never bypass
limits or the kill switch.

Each tick is a paid LLM call, so AI strategies are best run on slower
timeframes. An LLM failure is logged and treated as "hold".
"""

import logging

from ai.analyze import build_market_prompt
from ai.providers.base import DecisionAction, LLMError, LLMProvider
from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from trading.executors.base import Order
from trading.models import FillSide, PositionSide

log = logging.getLogger("capital.strategies.ai")


class AIStrategy(BaseStrategy):
    """LLM-driven strategy (long-only, state-based)."""

    kind = "AI"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        provider: LLMProvider,
        market: Market = Market.spot,
        timeframe: str = "1h",
        model: str | None = None,
        lookback: int = 30,
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        self._provider = provider
        self._model = model
        self._lookback = lookback

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        closes = [c.close for c in ctx.candles]
        if len(closes) < 2 or ctx.price <= 0:
            return None

        prompt = build_market_prompt(
            symbol=self.symbol,
            closes=closes,
            position_side=ctx.position.side,
            position_qty=ctx.position.qty,
            allocation=ctx.allocation,
            price=ctx.price,
            lookback=self._lookback,
        )
        try:
            decision = self._provider.decide(prompt, model=self._model)
        except LLMError:
            log.warning("AI strategy %r — LLM call failed, holding", self.name, exc_info=True)
            return None

        log.info(
            "AI strategy %r decided %s (confidence %s)",
            self.name,
            decision.action,
            decision.confidence,
        )
        is_long = ctx.position.side == PositionSide.long.value
        if decision.action is DecisionAction.buy and not is_long and ctx.allocation > 0:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=ctx.allocation / ctx.price,
            )
        if decision.action is DecisionAction.sell and is_long:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.sell,
                quantity=ctx.position.qty,
            )
        return None
