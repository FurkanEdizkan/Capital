"""Tests for retention pruning of candles and equity snapshots."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from marketdata.models import Candle
from ops.retention import prune_all, prune_candles, prune_equity_snapshots
from trading.models import EquitySnapshot

_NOW = datetime.now(UTC).replace(tzinfo=None)


def _candle(session: Session, open_time: datetime) -> None:
    session.add(
        Candle(
            market="spot",
            symbol="BTCUSDT",
            interval="1h",
            open_time=open_time,
            open=Decimal("1"),
            high=Decimal("1"),
            low=Decimal("1"),
            close=Decimal("1"),
            volume=Decimal("1"),
            close_time=open_time + timedelta(minutes=59),
        )
    )
    session.commit()


def _snapshot(session: Session, ts: datetime) -> None:
    session.add(
        EquitySnapshot(
            ts=ts,
            equity=Decimal("1000"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            fees=Decimal("0"),
            net_pnl=Decimal("0"),
        )
    )
    session.commit()


def test_prune_candles_removes_only_old(session: Session) -> None:
    _candle(session, _NOW - timedelta(days=100))  # old
    _candle(session, _NOW - timedelta(days=1))  # recent
    removed = prune_candles(session, older_than_days=90)
    assert removed == 1
    remaining = session.exec(select(Candle)).all()
    assert len(remaining) == 1


def test_prune_candles_disabled_when_zero(session: Session) -> None:
    _candle(session, _NOW - timedelta(days=365))
    assert prune_candles(session, older_than_days=0) == 0
    assert len(session.exec(select(Candle)).all()) == 1


def test_prune_equity_snapshots(session: Session) -> None:
    _snapshot(session, _NOW - timedelta(days=120))
    _snapshot(session, _NOW - timedelta(hours=2))
    removed = prune_equity_snapshots(session, older_than_days=90)
    assert removed == 1
    assert len(session.exec(select(EquitySnapshot)).all()) == 1


def test_prune_all_reports_counts(session: Session) -> None:
    _candle(session, _NOW - timedelta(days=100))
    _snapshot(session, _NOW - timedelta(days=100))
    removed = prune_all(session, candle_days=90, equity_days=90)
    assert removed == {"candles": 1, "equity_snapshots": 1}
