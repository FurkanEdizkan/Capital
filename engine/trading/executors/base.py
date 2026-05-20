"""Executor interface — Sim / Testnet / Live all implement `BaseExecutor`.

A strategy emits an `Order`; an executor turns it into a `Fill`. Because every
executor shares this interface, a strategy never knows (or cares) which is
active — see plan: Architecture / Executors.
"""

from abc import ABC, abstractmethod
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from pydantic import BaseModel
from sqlmodel import Session

from trading.models import FillSide


class ExecutionError(Exception):
    """An order could not be executed (below MIN_NOTIONAL, rounds to zero, …)."""


class SymbolFilters(BaseModel):
    """Binance trading rules for one symbol — orders must satisfy these."""

    tick_size: Decimal = Decimal("0.01")  # price increment
    step_size: Decimal = Decimal("0.00001")  # quantity increment (LOT_SIZE)
    min_notional: Decimal = Decimal("5")  # minimum price * quantity

    def round_price(self, price: Decimal) -> Decimal:
        return (Decimal(price) / self.tick_size).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        ) * self.tick_size

    def round_quantity(self, qty: Decimal) -> Decimal:
        # Floor to the lot step — never round a quantity up.
        return (Decimal(qty) / self.step_size).quantize(
            Decimal(1), rounding=ROUND_DOWN
        ) * self.step_size


DEFAULT_FILTERS = SymbolFilters()


class Order(BaseModel):
    """A strategy's intent to trade."""

    strategy: str
    market: str
    symbol: str
    side: FillSide
    quantity: Decimal


class Fill(BaseModel):
    """The result of executing an `Order`."""

    strategy: str
    market: str
    symbol: str
    side: FillSide
    quantity: Decimal
    price: Decimal
    fee: Decimal
    realized_pnl: Decimal


class BaseExecutor(ABC):
    """Common executor interface."""

    mode: str = "base"

    @abstractmethod
    def execute(
        self, session: Session, order: Order, *, reference_price: Decimal
    ) -> Fill:
        """Execute `order` and return the resulting `Fill`.

        `reference_price` is the current market price the executor prices
        against (mark price / candle close / ticker).
        """
        raise NotImplementedError
