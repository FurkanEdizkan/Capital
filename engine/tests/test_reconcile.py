"""Tests for reconciliation — engine sub-ledger vs exchange state."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session

from trading.models import FillSide, Position, PositionSide, Trade
from trading.reconcile import (
    engine_positions,
    reconcile_positions,
    reconcile_with_venue,
    untracked_order_ids,
)


class FakeVenue:
    """Stand-in venue exposing only `positions()`."""

    def __init__(self, positions: dict[str, Decimal]) -> None:
        self._positions = positions

    def positions(self) -> dict[str, Decimal]:
        return self._positions


def _position(session: Session, strategy: str, symbol: str, side: PositionSide, qty: str) -> None:
    session.add(
        Position(
            strategy=strategy,
            market="futures",
            symbol=symbol,
            side=side.value,
            qty=Decimal(qty),
            entry_price=Decimal("100"),
        )
    )
    session.commit()


def _trade(session: Session, client_order_id: str | None) -> None:
    session.add(
        Trade(
            strategy="S",
            market="futures",
            symbol="BTCUSDT",
            side=FillSide.buy.value,
            quantity=Decimal("1"),
            price=Decimal("100"),
            client_order_id=client_order_id,
            executed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()


def test_engine_positions_sum_across_strategies(session: Session) -> None:
    _position(session, "A", "BTCUSDT", PositionSide.long, "1")
    _position(session, "B", "BTCUSDT", PositionSide.long, "2")
    _position(session, "C", "BTCUSDT", PositionSide.short, "0.5")
    totals = engine_positions(session)
    assert totals[("futures", "BTCUSDT")] == Decimal("2.5")  # 1 + 2 − 0.5


def test_flat_positions_are_ignored(session: Session) -> None:
    _position(session, "A", "ETHUSDT", PositionSide.flat, "0")
    assert ("futures", "ETHUSDT") not in engine_positions(session)


def test_matching_positions_have_no_discrepancy(session: Session) -> None:
    _position(session, "A", "BTCUSDT", PositionSide.long, "3")
    result = reconcile_positions(session, {("futures", "BTCUSDT"): Decimal("3")})
    assert result == []


def test_drift_is_reported(session: Session) -> None:
    _position(session, "A", "BTCUSDT", PositionSide.long, "3")
    result = reconcile_positions(session, {("futures", "BTCUSDT"): Decimal("5")})
    assert len(result) == 1
    assert result[0].engine_qty == Decimal("3")
    assert result[0].exchange_qty == Decimal("5")
    assert result[0].drift == Decimal("2")


def test_engine_only_position_is_a_discrepancy(session: Session) -> None:
    _position(session, "A", "SOLUSDT", PositionSide.long, "10")
    result = reconcile_positions(session, {})
    assert len(result) == 1
    assert result[0].symbol == "SOLUSDT"
    assert result[0].drift == Decimal("-10")  # exchange has none


def test_exchange_only_position_is_a_discrepancy(session: Session) -> None:
    result = reconcile_positions(session, {("futures", "ETHUSDT"): Decimal("4")})
    assert len(result) == 1
    assert result[0].symbol == "ETHUSDT"
    assert result[0].engine_qty == Decimal("0")


def test_dust_drift_is_within_tolerance(session: Session) -> None:
    _position(session, "A", "BTCUSDT", PositionSide.long, "1")
    result = reconcile_positions(
        session, {("futures", "BTCUSDT"): Decimal("1.0000000001")}
    )
    assert result == []


def test_untracked_order_ids_finds_unrecorded(session: Session) -> None:
    _trade(session, "known-id")
    _trade(session, None)  # a sim trade — no clientOrderId
    result = untracked_order_ids(session, ["known-id", "missing-1", "missing-2"])
    assert result == ["missing-1", "missing-2"]


def test_reconcile_with_venue_attributes_positions_to_a_market(
    session: Session,
) -> None:
    _position(session, "A", "BTCUSDT", PositionSide.long, "2")
    venue = FakeVenue({"BTCUSDT": Decimal("5")})
    result = reconcile_with_venue(session, venue)  # type: ignore[arg-type]
    assert len(result) == 1
    assert result[0].market == "futures"
    assert result[0].drift == Decimal("3")


def test_reconcile_with_venue_no_drift(session: Session) -> None:
    _position(session, "A", "BTCUSDT", PositionSide.long, "2")
    venue = FakeVenue({"BTCUSDT": Decimal("2")})
    assert reconcile_with_venue(session, venue) == []  # type: ignore[arg-type]
