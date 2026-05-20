"""Strategy framework — `BaseStrategy` and the per-tick context.

A strategy is evaluated once per engine tick. It sees recent candles, its own
position and capital allocation, and the latest price, and may return an
`Order`. The engine routes that order through risk checks to an executor — the
strategy never knows whether it is running in Sim, Testnet or Live.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from exchange.client import Market
from marketdata.models import Candle
from trading.executors.base import Order
from trading.models import Position


@dataclass
class StrategyContext:
    """Everything a strategy sees on one tick."""

    candles: list[Candle]  # recent candles, oldest-first, for the strategy's timeframe
    position: Position  # the strategy's current position in its symbol
    allocation: Decimal  # capital budget assigned to the strategy
    price: Decimal  # latest reference price


class BaseStrategy(ABC):
    """Abstract trading strategy.

    Subclasses implement `evaluate`. Each strategy trades a single symbol on a
    declared candle timeframe (Phase 2 scope; multi-symbol strategies compose
    several instances).
    """

    #: Strategy type label (e.g. "MA Cross") — set by subclasses.
    kind: str = "base"

    def __init__(
        self,
        name: str,
        symbol: str,
        *,
        market: Market = Market.spot,
        timeframe: str = "1h",
    ) -> None:
        self.name = name
        self.symbol = symbol
        self.market = market
        self.timeframe = timeframe

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> Order | None:
        """Return an `Order` to execute this tick, or `None` to do nothing."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r} {self.symbol} {self.timeframe}>"
