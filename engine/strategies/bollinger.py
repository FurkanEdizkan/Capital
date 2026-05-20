"""Bollinger-band breakout — ride a move that closes above the upper band.

Long-only with hysteresis: enter long when the latest close breaks above the
upper band, close when it falls back below the middle band, and hold in
between. State-based, so it converges to the desired position after a missed
tick.
"""

from decimal import Decimal

from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from strategies.indicators import bollinger
from trading.executors.base import Order
from trading.models import FillSide, PositionSide


class BollingerStrategy(BaseStrategy):
    """Bollinger-band breakout (long-only)."""

    kind = "Bollinger Breakout"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
        period: int = 20,
        num_std: Decimal = Decimal(2),
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        if period <= 1 or num_std <= 0:
            raise ValueError("require period > 1 and num_std > 0")
        self.period = period
        self.num_std = num_std

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        closes = [c.close for c in ctx.candles]
        if len(closes) < self.period:
            return None  # not enough history yet

        lower, mid, upper = bollinger(closes, self.period, self.num_std)
        last = closes[-1]
        is_long = ctx.position.side == PositionSide.long.value

        if last > upper and not is_long and ctx.allocation > 0 and ctx.price > 0:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.buy,
                quantity=ctx.allocation / ctx.price,  # deploy the full budget
            )
        if last < mid and is_long:
            return Order(
                strategy=self.name,
                market=self.market.value,
                symbol=self.symbol,
                side=FillSide.sell,
                quantity=ctx.position.qty,  # close the whole position
            )
        return None
