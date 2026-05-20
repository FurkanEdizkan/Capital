"""RSI mean-reversion — buy oversold, sell overbought.

Long-only with hysteresis: enter long when RSI falls to/below the oversold
threshold, close when RSI rises to/above the overbought threshold, and hold
the current state in between. State-based like `MACrossStrategy`, so it
converges to the desired position even after a missed tick.
"""

from decimal import Decimal

from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from strategies.indicators import rsi
from trading.executors.base import Order
from trading.models import FillSide, PositionSide


class RSIStrategy(BaseStrategy):
    """RSI mean-reversion (long-only)."""

    kind = "RSI Reversion"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
        period: int = 14,
        oversold: Decimal = Decimal(30),
        overbought: Decimal = Decimal(70),
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        if not 0 < oversold < overbought < 100:
            raise ValueError("require 0 < oversold < overbought < 100")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        closes = [c.close for c in ctx.candles]
        if len(closes) < self.period + 1:
            return None  # not enough history yet

        value = rsi(closes, self.period)
        is_long = ctx.position.side == PositionSide.long.value

        if value <= self.oversold and not is_long and ctx.allocation > 0 and ctx.price > 0:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=ctx.allocation / ctx.price,  # deploy the full budget
            )
        if value >= self.overbought and is_long:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.sell,
                quantity=ctx.position.qty,  # close the whole position
            )
        return None
