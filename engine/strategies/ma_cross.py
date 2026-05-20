"""Moving-average crossover — the first built-in strategy.

Long-only: when the fast SMA is above the slow SMA the strategy wants to be
long; otherwise flat. It deploys its full capital allocation on entry and
closes the whole position on exit. State-based (not edge-triggered), so it
converges to the desired position even after a missed tick.
"""

from decimal import Decimal

from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from trading.executors.base import Order
from trading.models import FillSide, PositionSide


def _sma(values: list[Decimal], period: int) -> Decimal:
    window = values[-period:]
    return sum(window, Decimal(0)) / Decimal(len(window))


class MACrossStrategy(BaseStrategy):
    """Fast/slow simple-moving-average crossover (long-only)."""

    kind = "MA Cross"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
        fast: int = 9,
        slow: int = 21,
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        if fast >= slow:
            raise ValueError("fast period must be shorter than slow period")
        self.fast = fast
        self.slow = slow

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        closes = [c.close for c in ctx.candles]
        if len(closes) < self.slow:
            return None  # not enough history yet

        fast_ma = _sma(closes, self.fast)
        slow_ma = _sma(closes, self.slow)
        is_long = ctx.position.side == PositionSide.long.value
        want_long = fast_ma > slow_ma

        if want_long and not is_long and ctx.allocation > 0 and ctx.price > 0:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=ctx.allocation / ctx.price,  # deploy the full budget
            )
        if not want_long and is_long:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.sell,
                quantity=ctx.position.qty,  # close the whole position
            )
        return None
