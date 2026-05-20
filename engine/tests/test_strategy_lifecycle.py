"""Tests for strategy lifecycle — enable/disable and safe deletion."""

from decimal import Decimal

import pytest
from sqlmodel import Session, select

from trading.lifecycle import (
    StrategyLifecycleError,
    delete_strategy,
    is_enabled,
    set_enabled,
)
from trading.models import Position, PositionSide, StrategyAllocation
from trading.portfolio import set_allocation


def _open_position(session: Session, strategy: str) -> None:
    session.add(
        Position(
            strategy=strategy,
            market="spot",
            symbol="BTCUSDT",
            side=PositionSide.long.value,
            qty=Decimal("1"),
            entry_price=Decimal("100"),
        )
    )
    session.commit()


def test_unknown_strategy_defaults_to_enabled(session: Session) -> None:
    assert is_enabled(session, "Never Seen") is True


def test_set_enabled_toggles_state(session: Session) -> None:
    set_allocation(session, "S", Decimal("1000"))
    set_enabled(session, "S", False)
    assert is_enabled(session, "S") is False
    set_enabled(session, "S", True)
    assert is_enabled(session, "S") is True


def test_set_enabled_creates_row_when_missing(session: Session) -> None:
    set_enabled(session, "Fresh", False)
    assert is_enabled(session, "Fresh") is False


def test_delete_strategy_removes_config_and_positions(session: Session) -> None:
    set_allocation(session, "S", Decimal("1000"))
    session.add(Position(strategy="S", market="spot", symbol="BTCUSDT"))  # flat
    session.commit()

    delete_strategy(session, "S")

    assert session.exec(
        select(StrategyAllocation).where(StrategyAllocation.strategy == "S")
    ).first() is None
    assert session.exec(select(Position).where(Position.strategy == "S")).first() is None


def test_delete_strategy_blocked_while_position_open(session: Session) -> None:
    set_allocation(session, "S", Decimal("1000"))
    _open_position(session, "S")

    with pytest.raises(StrategyLifecycleError):
        delete_strategy(session, "S")

    # The strategy and its position must survive the rejected delete.
    assert session.exec(
        select(StrategyAllocation).where(StrategyAllocation.strategy == "S")
    ).first() is not None
