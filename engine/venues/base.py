"""Venue abstraction — one interface across every trading venue.

Capital's strategy framework, risk manager, accounting and capital allocator
are venue-agnostic. Each venue — Binance today, then Alpaca / Polymarket / a
futures broker — implements this `Venue` interface, and every venue-specific
assumption stays behind it. See docs/venue-abstraction.md for the design and
the migration plan.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from trading.models import FillSide


class VenueError(Exception):
    """A venue rejected a request or could not fulfil it."""


class OrderType(StrEnum):
    market = "market"
    limit = "limit"


@dataclass(frozen=True)
class Instrument:
    """Tradeable-instrument metadata, normalised across venues.

    Lets the shared order-sizing logic work unchanged whether the instrument
    is a crypto pair, a share, a futures contract or a market outcome.
    """

    symbol: str  # the venue's symbol for the instrument
    base: str  # what is traded — BTC, AAPL, a market-outcome id
    quote: str  # what it is priced in — USDT, USD, USDC
    tick_size: Decimal  # minimum price increment
    size_step: Decimal  # minimum order-size increment
    min_notional: Decimal  # minimum price * size for an order


@dataclass(frozen=True)
class VenueCandle:
    """One OHLCV bar, venue-neutral."""

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class OrderRequest:
    """An intent to trade on a venue."""

    symbol: str
    side: FillSide
    quantity: Decimal
    order_type: OrderType = OrderType.market
    limit_price: Decimal | None = None


@dataclass(frozen=True)
class OrderResult:
    """The outcome of a placed order."""

    symbol: str
    side: FillSide
    filled_quantity: Decimal
    price: Decimal  # average fill price
    fee: Decimal  # venue commission, in the quote currency
    order_id: str  # the venue's order id


class Venue(ABC):
    """A trading venue — market data, instruments and order placement.

    Concrete venues implement every abstract method. `name` identifies the
    venue; `supports_sandbox` says whether a paper/test environment exists
    (Polymarket, for one, has none — see docs/venue-research.md).
    """

    name: str = "base"
    supports_sandbox: bool = False

    @abstractmethod
    def instrument(self, symbol: str) -> Instrument:
        """Trading metadata for `symbol`. Raises `VenueError` if unknown."""

    @abstractmethod
    def candles(
        self, symbol: str, interval: str, limit: int = 200
    ) -> list[VenueCandle]:
        """Recent OHLCV bars for `symbol`, oldest-first."""

    @abstractmethod
    def price(self, symbol: str) -> Decimal:
        """The latest traded price for `symbol`."""

    @abstractmethod
    def place_order(self, request: OrderRequest) -> OrderResult:
        """Submit an order and return its fill.

        Raises `VenueError` if the venue rejects it.
        """

    @abstractmethod
    def positions(self) -> dict[str, Decimal]:
        """Open positions as `{symbol: signed quantity}` — for reconciliation."""
