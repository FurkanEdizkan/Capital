"""Tests for the position-attribution sub-ledger — the correctness-critical
piece of the trading engine."""

from decimal import Decimal

import pytest
from sqlmodel import Session

from trading.models import PositionSide
from trading.portfolio import (
    apply_fill,
    get_allocation,
    list_allocations,
    list_positions,
    set_allocation,
    unrealized_pnl,
)

S, M, SYM = "MA Cross", "spot", "BTCUSDT"


def _fill(session: Session, side: str, qty: str, price: str, fee: str = "0", strategy: str = S):
    return apply_fill(
        session,
        strategy=strategy,
        market=M,
        symbol=SYM,
        side=side,
        qty=Decimal(qty),
        price=Decimal(price),
        fee=Decimal(fee),
    )


def test_open_long(session: Session) -> None:
    pos = _fill(session, "buy", "1", "100")
    assert pos.side == PositionSide.long.value
    assert pos.qty == Decimal("1")
    assert pos.entry_price == Decimal("100")
    assert pos.realized_pnl == Decimal("0")


def test_increase_long_averages_entry(session: Session) -> None:
    _fill(session, "buy", "1", "100")
    pos = _fill(session, "buy", "1", "200")
    assert pos.qty == Decimal("2")
    assert pos.entry_price == Decimal("150")  # volume-weighted


def test_partial_close_realizes_pnl(session: Session) -> None:
    _fill(session, "buy", "2", "150")
    pos = _fill(session, "sell", "1", "200")
    assert pos.qty == Decimal("1")
    assert pos.entry_price == Decimal("150")  # unchanged on a reduce
    assert pos.realized_pnl == Decimal("50")  # (200-150)*1


def test_full_close_goes_flat(session: Session) -> None:
    _fill(session, "buy", "1", "150")
    pos = _fill(session, "sell", "1", "200")
    assert pos.side == PositionSide.flat.value
    assert pos.qty == Decimal("0")
    assert pos.entry_price == Decimal("0")
    assert pos.realized_pnl == Decimal("50")


def test_flip_long_to_short(session: Session) -> None:
    _fill(session, "buy", "1", "100")
    pos = _fill(session, "sell", "3", "120")
    assert pos.side == PositionSide.short.value
    assert pos.qty == Decimal("2")
    assert pos.entry_price == Decimal("120")  # new short leg at fill price
    assert pos.realized_pnl == Decimal("20")  # (120-100)*1 on the closed long


def test_short_profit_on_cover(session: Session) -> None:
    _fill(session, "sell", "1", "100")  # open short
    pos = _fill(session, "buy", "1", "90")  # cover lower
    assert pos.side == PositionSide.flat.value
    assert pos.realized_pnl == Decimal("10")  # shorted 100, covered 90


def test_fees_accumulate(session: Session) -> None:
    _fill(session, "buy", "1", "100", fee="0.5")
    pos = _fill(session, "sell", "1", "110", fee="0.55")
    assert pos.fees_paid == Decimal("1.05")


def test_strategies_are_isolated(session: Session) -> None:
    _fill(session, "buy", "2", "100", strategy="alpha")
    _fill(session, "sell", "1", "100", strategy="beta")
    alpha = list_positions(session, strategy="alpha")[0]
    beta = list_positions(session, strategy="beta")[0]
    assert alpha.side == PositionSide.long.value and alpha.qty == Decimal("2")
    assert beta.side == PositionSide.short.value and beta.qty == Decimal("1")


def test_negative_qty_rejected(session: Session) -> None:
    with pytest.raises(ValueError):
        _fill(session, "buy", "-1", "100")


def test_unrealized_pnl(session: Session) -> None:
    long_pos = _fill(session, "buy", "2", "100")
    assert unrealized_pnl(long_pos, Decimal("110")) == Decimal("20")
    short_pos = _fill(session, "sell", "2", "100", strategy="s")
    assert unrealized_pnl(short_pos, Decimal("90")) == Decimal("20")


def test_allocations(session: Session) -> None:
    assert get_allocation(session, "alpha") == Decimal("0")
    set_allocation(session, "alpha", Decimal("25000"))
    assert get_allocation(session, "alpha") == Decimal("25000")
    set_allocation(session, "alpha", Decimal("30000"))  # update in place
    assert get_allocation(session, "alpha") == Decimal("30000")
    assert len(list_allocations(session)) == 1
