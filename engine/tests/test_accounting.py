"""Tests for the accounting layer — PnL, fees, equity snapshots."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session

from trading.accounting import (
    cost_summary,
    equity_history,
    portfolio_summary,
    record_equity_snapshot,
    strategy_summary,
)
from trading.models import Trade
from trading.portfolio import apply_fill, set_allocation

MARK = {"BTCUSDT": Decimal("110")}


def _scenario(session: Session) -> None:
    """alpha: long 0.5 BTC @ entry 100, +10 realized, 1.5 fees."""
    set_allocation(session, "alpha", Decimal("10000"))
    apply_fill(
        session, strategy="alpha", market="spot", symbol="BTCUSDT",
        side="buy", qty=Decimal("1"), price=Decimal("100"), fee=Decimal("1"),
    )
    apply_fill(
        session, strategy="alpha", market="spot", symbol="BTCUSDT",
        side="sell", qty=Decimal("0.5"), price=Decimal("120"), fee=Decimal("0.5"),
    )


def test_strategy_summary(session: Session) -> None:
    _scenario(session)
    s = strategy_summary(session, "alpha", MARK)
    assert s.realized_pnl == Decimal("10")  # (120-100)*0.5
    assert s.unrealized_pnl == Decimal("5")  # (110-100)*0.5
    assert s.fees == Decimal("1.5")
    assert s.net_pnl == Decimal("13.5")  # 10 + 5 - 1.5
    assert s.open_positions == 1


def test_portfolio_summary_aggregates(session: Session) -> None:
    _scenario(session)
    p = portfolio_summary(session, MARK)
    assert p.total_allocated == Decimal("10000")
    assert p.realized_pnl == Decimal("10")
    assert p.unrealized_pnl == Decimal("5")
    assert p.total_fees == Decimal("1.5")
    assert p.net_pnl == Decimal("13.5")
    assert p.equity == Decimal("10013.5")  # allocated + net
    assert p.deployed_capital == Decimal("50")  # 0.5 * entry 100
    assert p.idle_capital == Decimal("9950")
    assert p.open_positions == 1


def test_portfolio_summary_empty(session: Session) -> None:
    p = portfolio_summary(session, {})
    assert p.equity == Decimal("0")
    assert p.net_pnl == Decimal("0")
    assert p.open_positions == 0


def test_record_and_read_equity_history(session: Session) -> None:
    _scenario(session)
    snap = record_equity_snapshot(session, MARK)
    assert snap.equity == Decimal("10013.5")
    record_equity_snapshot(session, MARK)

    history = equity_history(session)
    assert len(history) == 2
    assert all(h.net_pnl == Decimal("13.5") for h in history)


def _trade(session: Session, market: str, qty: str, price: str, fee: str) -> None:
    session.add(
        Trade(
            strategy="s",
            market=market,
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal(qty),
            price=Decimal(price),
            fee=Decimal(fee),
            executed_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()


def test_cost_summary(session: Session) -> None:
    _trade(session, "spot", "1", "100", "0.1")
    _trade(session, "spot", "2", "100", "0.2")
    _trade(session, "futures", "1", "200", "0.08")
    cs = cost_summary(session)
    assert cs.total_fees == Decimal("0.38")
    assert cs.fees_by_market == {"spot": Decimal("0.3"), "futures": Decimal("0.08")}
    assert cs.traded_volume == Decimal("500")  # 100 + 200 + 200
    assert cs.fee_pct_of_volume == Decimal("0.076")  # 0.38 / 500 * 100


def test_cost_summary_empty(session: Session) -> None:
    cs = cost_summary(session)
    assert cs.total_fees == Decimal("0")
    assert cs.fee_pct_of_volume == Decimal("0")
