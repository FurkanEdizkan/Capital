"""Tests for the risk manager — sizing caps, SL/TP and the kill switch."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session

from trading.executors.base import Order
from trading.models import EquitySnapshot, FillSide, Position, PositionSide, Trade
from trading.risk import RiskManager


def _flat() -> Position:
    return Position(strategy="S", market="spot", symbol="BTCUSDT")


def _pos(side: PositionSide, qty: str = "1", entry: str = "100") -> Position:
    return Position(
        strategy="S",
        market="spot",
        symbol="BTCUSDT",
        side=side.value,
        qty=Decimal(qty),
        entry_price=Decimal(entry),
    )


def _order(side: FillSide, qty: str) -> Order:
    return Order(strategy="S", market="spot", symbol="BTCUSDT", side=side, quantity=Decimal(qty))


# --- stop-loss / take-profit ----------------------------------------------

def test_stop_loss_closes_a_losing_long() -> None:
    rm = RiskManager(stop_loss_pct=Decimal(5))
    order = rm.stop_order(_pos(PositionSide.long), Decimal("90"))  # −10%
    assert order is not None
    assert order.side is FillSide.sell
    assert order.quantity == Decimal("1")


def test_take_profit_closes_a_winning_long() -> None:
    rm = RiskManager(take_profit_pct=Decimal(5))
    order = rm.stop_order(_pos(PositionSide.long), Decimal("110"))  # +10%
    assert order is not None and order.side is FillSide.sell


def test_stop_loss_closes_a_losing_short_with_a_buy() -> None:
    rm = RiskManager(stop_loss_pct=Decimal(5))
    order = rm.stop_order(_pos(PositionSide.short), Decimal("110"))  # short −10%
    assert order is not None and order.side is FillSide.buy


def test_no_stop_within_the_band() -> None:
    rm = RiskManager(stop_loss_pct=Decimal(5), take_profit_pct=Decimal(5))
    assert rm.stop_order(_pos(PositionSide.long), Decimal("102")) is None  # +2%


def test_no_stop_on_a_flat_position() -> None:
    rm = RiskManager(stop_loss_pct=Decimal(5))
    assert rm.stop_order(_flat(), Decimal("90")) is None


def test_no_stop_when_sl_tp_disabled() -> None:
    rm = RiskManager()  # all limits disabled
    assert rm.stop_order(_pos(PositionSide.long), Decimal("1")) is None


# --- order sizing ----------------------------------------------------------

def test_size_cap_passes_a_small_order() -> None:
    rm = RiskManager(max_position_notional=Decimal("1000"))
    order = _order(FillSide.buy, "5")  # 5 * 100 = 500 < 1000
    assert rm.cap_order_size(order, Decimal("100")) is order


def test_size_cap_clips_a_large_order() -> None:
    rm = RiskManager(max_position_notional=Decimal("1000"))
    clipped = rm.cap_order_size(_order(FillSide.buy, "50"), Decimal("100"))
    assert clipped is not None and clipped.quantity == Decimal("10")


def test_size_cap_disabled_passes_everything() -> None:
    rm = RiskManager()  # max_position_notional == 0
    order = _order(FillSide.buy, "9999")
    assert rm.cap_order_size(order, Decimal("100")) is order


# --- kill switch -----------------------------------------------------------

def _trade(session: Session, realized: str, fee: str = "0", *, days_ago: int = 0) -> None:
    session.add(
        Trade(
            strategy="S",
            market="spot",
            symbol="BTCUSDT",
            side=FillSide.sell.value,
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee=Decimal(fee),
            realized_pnl=Decimal(realized),
            executed_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago),
        )
    )
    session.commit()


def test_daily_loss_only_counts_today(session: Session) -> None:
    _trade(session, realized="-50")
    _trade(session, realized="-1000", days_ago=3)  # old — must be ignored
    rm = RiskManager()
    assert rm.daily_realized_loss(session) == Decimal("-50")


def test_kill_switch_trips_on_daily_loss(session: Session) -> None:
    _trade(session, realized="-80", fee="30")  # net −110
    rm = RiskManager(daily_loss_limit=Decimal("100"))
    assert rm.kill_switch_tripped(session) is not None


def test_kill_switch_quiet_under_the_limit(session: Session) -> None:
    _trade(session, realized="-40")
    rm = RiskManager(daily_loss_limit=Decimal("100"))
    assert rm.kill_switch_tripped(session) is None


def test_kill_switch_trips_on_drawdown(session: Session) -> None:
    base = datetime(2026, 5, 21)
    for i, equity in enumerate(("10000", "12000", "9000")):  # peak 12k → 9k = 25%
        session.add(
            EquitySnapshot(
                ts=base + timedelta(hours=i),
                equity=Decimal(equity),
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                fees=Decimal("0"),
                net_pnl=Decimal("0"),
            )
        )
    session.commit()
    rm = RiskManager(max_drawdown_pct=Decimal("20"))
    assert rm.kill_switch_tripped(session) is not None


def test_review_blocks_new_exposure_when_tripped(session: Session) -> None:
    _trade(session, realized="-200")
    rm = RiskManager(daily_loss_limit=Decimal("100"))
    # A buy from flat increases exposure — blocked.
    assert rm.review(session, _order(FillSide.buy, "1"), _flat(), Decimal("100")) is None


def test_review_allows_closing_when_tripped(session: Session) -> None:
    _trade(session, realized="-200")
    rm = RiskManager(daily_loss_limit=Decimal("100"))
    # A sell that closes a long reduces exposure — always allowed.
    order = _order(FillSide.sell, "1")
    assert rm.review(session, order, _pos(PositionSide.long), Decimal("100")) is order


def test_review_passes_when_not_tripped(session: Session) -> None:
    rm = RiskManager(daily_loss_limit=Decimal("100"))
    order = _order(FillSide.buy, "1")
    assert rm.review(session, order, _flat(), Decimal("100")) is order
