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
from ai.providers.base import (
    Completion,
    Decision,
    DecisionAction,
    LLMError,
    LLMProvider,
    parse_decision,
)
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
        provider: LLMProvider | None = None,
        market: Market = Market.spot,
        timeframe: str = "1h",
        model: str | None = None,
        lookback: int = 30,
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        # The provider + model are resolved per tick from the strategy's
        # stored config — the engine calls `set_ai_config` before each tick,
        # so different AI strategies can run on different models.
        self._provider = provider
        self._model = model
        self._lookback = lookback
        # The most recent LLM call's usage + decision — read by the engine
        # after each tick to record an `LLMUsage` row. Reset every evaluate().
        self.last_usage: Completion | None = None
        self.last_decision: Decision | None = None

    def set_ai_config(self, provider: LLMProvider, model: str | None) -> None:
        """Point the strategy at a provider + model for the coming tick."""
        self._provider = provider
        self._model = model

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        self.last_usage = None
        self.last_decision = None
        if self._provider is None:  # no model configured — nothing to ask
            return None
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
            completion = self._provider.complete(prompt, model=self._model)
            decision = parse_decision(completion.text)
        except LLMError:
            log.warning("AI strategy %r — LLM call failed, holding", self.name, exc_info=True)
            return None
        # Surface usage + decision for the engine to record (cost tracking).
        self.last_usage = completion
        self.last_decision = decision

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
