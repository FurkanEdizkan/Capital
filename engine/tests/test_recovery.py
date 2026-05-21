"""Tests for boot state recovery — startup reconciliation."""

from decimal import Decimal

from sqlmodel import Session

from appsettings.store import TradingMode, set_mode
from ops.recovery import recover_on_boot
from trading.models import Position, PositionSide


class FakeVenue:
    """Stand-in venue exposing only `positions()` — what reconciliation calls."""

    def __init__(
        self, positions: dict[str, Decimal] | None = None, *, raises: bool = False
    ) -> None:
        self._positions = positions or {}
        self._raises = raises

    def positions(self) -> dict[str, Decimal]:
        if self._raises:
            raise RuntimeError("venue unreachable")
        return self._positions


def _position(session: Session, symbol: str, qty: str) -> None:
    session.add(
        Position(
            strategy="S",
            market="futures",
            symbol=symbol,
            side=PositionSide.long.value,
            qty=Decimal(qty),
            entry_price=Decimal("100"),
        )
    )
    session.commit()


def test_sim_mode_skips_reconciliation(session: Session) -> None:
    # Default mode is sim — recovery is a no-op even with positions.
    _position(session, "BTCUSDT", "1")
    assert recover_on_boot(session) == []


def test_live_mode_without_keys_is_a_noop(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    assert recover_on_boot(session) == []  # no keys configured → nothing to do


def test_matching_positions_report_no_drift(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    _position(session, "BTCUSDT", "2")
    result = recover_on_boot(session, venue=FakeVenue({"BTCUSDT": Decimal("2")}))  # type: ignore[arg-type]
    assert result == []


def test_drift_is_detected(session: Session) -> None:
    set_mode(session, TradingMode.live)
    _position(session, "BTCUSDT", "2")
    result = recover_on_boot(session, venue=FakeVenue({"BTCUSDT": Decimal("3")}))  # type: ignore[arg-type]
    assert len(result) == 1
    assert result[0].drift == Decimal("1")


def test_reconciliation_failure_does_not_raise(session: Session) -> None:
    set_mode(session, TradingMode.testnet)
    # A venue that raises must not propagate — startup continues.
    assert recover_on_boot(session, venue=FakeVenue(raises=True)) == []  # type: ignore[arg-type]
