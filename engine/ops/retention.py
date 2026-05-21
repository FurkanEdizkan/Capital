"""Retention pruning — drop stale rows so the database does not grow forever.

Candles and per-tick equity snapshots accumulate indefinitely on a 24/7
engine. Pruning keeps a configurable window of each. Trades and the audit log
are never pruned — they are the permanent record.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlmodel import Session

from marketdata.models import Candle
from trading.models import EquitySnapshot

log = logging.getLogger("capital.ops.retention")


def _cutoff(days: int) -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)


def prune_candles(session: Session, older_than_days: int) -> int:
    """Delete cached candles older than `older_than_days`. 0 disables it."""
    if older_than_days <= 0:
        return 0
    result = session.exec(  # type: ignore[call-overload]
        delete(Candle).where(Candle.open_time < _cutoff(older_than_days))
    )
    session.commit()
    return result.rowcount or 0


def prune_equity_snapshots(session: Session, older_than_days: int) -> int:
    """Delete equity snapshots older than `older_than_days`. 0 disables it."""
    if older_than_days <= 0:
        return 0
    result = session.exec(  # type: ignore[call-overload]
        delete(EquitySnapshot).where(EquitySnapshot.ts < _cutoff(older_than_days))
    )
    session.commit()
    return result.rowcount or 0


def prune_all(
    session: Session, *, candle_days: int, equity_days: int
) -> dict[str, int]:
    """Prune both tables; return the row counts removed."""
    removed = {
        "candles": prune_candles(session, candle_days),
        "equity_snapshots": prune_equity_snapshots(session, equity_days),
    }
    if any(removed.values()):
        log.info("retention pruned %s", removed)
    return removed
