"""SimExecutor — paper fills against live prices.

Models slippage and a realistic commission, and sizes orders to the symbol's
trading filters, so paper results are not optimistic and the *same* sizing
logic works unchanged once a live executor is plugged in (Phase 5).
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session

from trading.executors.base import (
    DEFAULT_FILTERS,
    BaseExecutor,
    ExecutionError,
    Fill,
    Order,
    SymbolFilters,
)
from trading.models import FillSide, Trade
from trading.portfolio import apply_fill, get_or_create_position

# Binance-like defaults: 0.04% taker fee, ~2 bps slippage.
DEFAULT_FEE_RATE = Decimal("0.0004")
DEFAULT_SLIPPAGE_BPS = Decimal("2")


class SimExecutor(BaseExecutor):
    """Simulated executor — fills on `reference_price` ± slippage."""

    mode = "sim"

    def __init__(
        self,
        *,
        fee_rate: Decimal = DEFAULT_FEE_RATE,
        slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
        filters: dict[str, SymbolFilters] | None = None,
        default_filters: SymbolFilters = DEFAULT_FILTERS,
    ) -> None:
        self.fee_rate = Decimal(fee_rate)
        self.slippage_bps = Decimal(slippage_bps)
        self._filters = filters or {}
        self._default_filters = default_filters

    def filters_for(self, symbol: str) -> SymbolFilters:
        return self._filters.get(symbol, self._default_filters)

    def execute(
        self, session: Session, order: Order, *, reference_price: Decimal
    ) -> Fill:
        ref = Decimal(reference_price)
        filt = self.filters_for(order.symbol)

        qty = filt.round_quantity(order.quantity)
        if qty <= 0:
            raise ExecutionError(
                f"quantity {order.quantity} rounds to zero at step {filt.step_size}"
            )

        # Adverse slippage — buys fill above, sells below the reference price.
        slip = ref * self.slippage_bps / Decimal(10000)
        raw_price = ref + slip if order.side is FillSide.buy else ref - slip
        price = filt.round_price(raw_price)

        notional = qty * price
        if notional < filt.min_notional:
            raise ExecutionError(
                f"notional {notional} below MIN_NOTIONAL {filt.min_notional}"
            )
        fee = notional * self.fee_rate

        # Attribute the fill to the strategy's position (the sub-ledger).
        realized_before = get_or_create_position(
            session, order.strategy, order.market, order.symbol
        ).realized_pnl
        pos = apply_fill(
            session,
            strategy=order.strategy,
            market=order.market,
            symbol=order.symbol,
            side=order.side,
            qty=qty,
            price=price,
            fee=fee,
        )
        realized = pos.realized_pnl - realized_before

        trade = Trade(
            strategy=order.strategy,
            market=order.market,
            symbol=order.symbol,
            side=order.side.value,
            quantity=qty,
            price=price,
            fee=fee,
            realized_pnl=realized,
            mode=self.mode,
            executed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(trade)
        session.commit()
        session.refresh(trade)

        return Fill(
            strategy=order.strategy,
            market=order.market,
            symbol=order.symbol,
            side=order.side,
            quantity=qty,
            price=price,
            fee=fee,
            realized_pnl=realized,
        )
