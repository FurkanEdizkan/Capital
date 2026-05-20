"""Dollar-cost averaging — accumulate a position in fixed tranches.

Each tick the strategy buys one tranche (a fixed fraction of its allocation)
until the position's market value reaches the allocation; then it idles. It
never sells — exiting a DCA position is a manual decision.
"""

from decimal import Decimal

from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from trading.executors.base import Order
from trading.models import FillSide


class DCAStrategy(BaseStrategy):
    """Dollar-cost-averaging accumulator (buy-only)."""

    kind = "DCA Accumulate"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
        tranche: Decimal = Decimal("0.1"),
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        if not 0 < tranche <= 1:
            raise ValueError("tranche must be in (0, 1]")
        self.tranche = tranche

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        if ctx.allocation <= 0 or ctx.price <= 0:
            return None

        deployed = ctx.position.qty * ctx.price
        remaining = ctx.allocation - deployed
        # Stop once all-but-dust of the budget is deployed.
        if remaining <= ctx.allocation / Decimal(1000):
            return None

        spend = min(self.tranche * ctx.allocation, remaining)
        return Order(
            strategy=self.name,
            market=self.market.value,
            symbol=self.symbol,
            side=FillSide.buy,
            quantity=spend / ctx.price,
        )
