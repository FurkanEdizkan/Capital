"""Tests for the SimExecutor — slippage, fees, filter sizing, attribution."""

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from trading.executors.base import ExecutionError, Order, SymbolFilters
from trading.executors.sim import SimExecutor
from trading.models import FillSide, Trade
from trading.portfolio import list_positions

FILTERS = {
    "BTCUSDT": SymbolFilters(
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("10"),
    )
}


def _order(side: FillSide, qty: str, symbol: str = "BTCUSDT") -> Order:
    return Order(
        strategy="MA Cross",
        market="spot",
        symbol=symbol,
        side=side,
        quantity=Decimal(qty),
    )


def test_buy_slips_above_reference(session: Session) -> None:
    ex = SimExecutor(slippage_bps=Decimal("10"), fee_rate=Decimal("0"), filters=FILTERS)
    fill = ex.execute(session, _order(FillSide.buy, "1"), reference_price=Decimal("100"))
    assert fill.price == Decimal("100.10")  # 100 + 10bps


def test_sell_slips_below_reference(session: Session) -> None:
    ex = SimExecutor(slippage_bps=Decimal("10"), fee_rate=Decimal("0"), filters=FILTERS)
    fill = ex.execute(session, _order(FillSide.sell, "1"), reference_price=Decimal("100"))
    assert fill.price == Decimal("99.90")


def test_fee_is_notional_times_rate(session: Session) -> None:
    ex = SimExecutor(slippage_bps=Decimal("0"), fee_rate=Decimal("0.0004"), filters=FILTERS)
    fill = ex.execute(session, _order(FillSide.buy, "2"), reference_price=Decimal("100"))
    assert fill.fee == Decimal("2") * Decimal("100") * Decimal("0.0004")


def test_quantity_rounded_to_step(session: Session) -> None:
    ex = SimExecutor(slippage_bps=Decimal("0"), fee_rate=Decimal("0"), filters=FILTERS)
    fill = ex.execute(session, _order(FillSide.buy, "1.23456"), reference_price=Decimal("100"))
    assert fill.quantity == Decimal("1.234")  # floored to 0.001 step


def test_below_min_notional_rejected(session: Session) -> None:
    ex = SimExecutor(filters=FILTERS)
    with pytest.raises(ExecutionError, match="MIN_NOTIONAL"):
        ex.execute(session, _order(FillSide.buy, "0.05"), reference_price=Decimal("100"))


def test_quantity_rounding_to_zero_rejected(session: Session) -> None:
    ex = SimExecutor(filters=FILTERS)
    with pytest.raises(ExecutionError, match="rounds to zero"):
        ex.execute(session, _order(FillSide.buy, "0.0001"), reference_price=Decimal("100"))


def test_trade_recorded_and_position_updated(session: Session) -> None:
    ex = SimExecutor(slippage_bps=Decimal("0"), fee_rate=Decimal("0"), filters=FILTERS)
    ex.execute(session, _order(FillSide.buy, "1"), reference_price=Decimal("100"))

    trades = session.exec(select(Trade)).all()
    assert len(trades) == 1
    assert trades[0].mode == "sim"

    positions = list_positions(session, strategy="MA Cross", open_only=True)
    assert len(positions) == 1
    assert positions[0].qty == Decimal("1.000")


def test_realized_pnl_booked_on_close(session: Session) -> None:
    ex = SimExecutor(slippage_bps=Decimal("0"), fee_rate=Decimal("0"), filters=FILTERS)
    ex.execute(session, _order(FillSide.buy, "1"), reference_price=Decimal("100"))
    closing = ex.execute(session, _order(FillSide.sell, "1"), reference_price=Decimal("110"))
    assert closing.realized_pnl == Decimal("10")  # bought 100, sold 110
