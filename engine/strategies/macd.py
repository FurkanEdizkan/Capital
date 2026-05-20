"""MACD trend-following — long while the MACD line leads its signal line.

Long-only and state-based: the strategy wants to be long whenever the MACD
line is above the signal line, and flat otherwise. It deploys the full
allocation on entry and closes the whole position on exit.
"""

from exchange.client import Market
from strategies.base import BaseStrategy, StrategyContext
from strategies.indicators import macd
from trading.executors.base import Order
from trading.models import FillSide, PositionSide


class MACDStrategy(BaseStrategy):
    """MACD line / signal line trend follower (long-only)."""

    kind = "MACD Trend"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> None:
        super().__init__(name, symbol, market=market, timeframe=timeframe)
        if fast >= slow:
            raise ValueError("fast period must be shorter than slow period")
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def evaluate(self, ctx: StrategyContext) -> Order | None:
        closes = [c.close for c in ctx.candles]
        if len(closes) < self.slow + self.signal:
            return None  # not enough history yet

        macd_line, signal_line, _ = macd(closes, self.fast, self.slow, self.signal)
        is_long = ctx.position.side == PositionSide.long.value
        want_long = macd_line > signal_line

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
