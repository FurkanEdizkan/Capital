"""Example strategy plugin — a template, not loaded.

Copy this file to `my_strategy.py` (any name **not** starting with `_`) in
this directory. The engine imports every such file on startup and calls its
`build()` function to obtain ready-to-run strategy instances.

A plugin may either subclass `BaseStrategy` with its own logic, or simply
return configured instances of the built-in strategy types.
"""

from decimal import Decimal

from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from trading.executors.base import Order
from trading.models import FillSide, PositionSide


class BuyTheDipStrategy(BaseStrategy):
    """Toy custom strategy: buy after a fixed percentage drop, never sell."""

    kind = "Example Buy-the-Dip"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
        drop_pct: Decimal = Decimal("5"),
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        self.drop_pct = drop_pct

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        closes = [c.close for c in ctx.candles]
        if len(closes) < 2 or ctx.allocation <= 0 or ctx.price <= 0:
            return None
        is_long = ctx.position.side == PositionSide.long.value
        drop = (closes[-2] - closes[-1]) / closes[-2] * Decimal(100)
        if drop >= self.drop_pct and not is_long:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=ctx.allocation / ctx.price,
            )
        return None


def build() -> list[BaseStrategy]:
    """Entrypoint — return the strategy instances this plugin contributes."""
    return [BuyTheDipStrategy("Example Dip Buyer", "BTCUSDT")]
