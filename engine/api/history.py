"""History API — transaction log, audit log and CSV export.

Powers the History & Logs page. Any authenticated operator may read history
(see plan: Authentication & Roles).
"""

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Response
from sqlmodel import select
from sqlmodel.sql.expression import SelectOfScalar

from auth.deps import CurrentUser, SessionDep
from auth.models import AuditLog
from trading.models import Trade

router = APIRouter(prefix="/api/history", tags=["history"])

_CSV_COLUMNS = [
    "executed_at",
    "strategy",
    "market",
    "symbol",
    "side",
    "quantity",
    "price",
    "fee",
    "realized_pnl",
    "mode",
]


def _trade_query(
    start: datetime | None, end: datetime | None, limit: int
) -> SelectOfScalar[Trade]:
    query = select(Trade)
    if start is not None:
        query = query.where(Trade.executed_at >= start)
    if end is not None:
        query = query.where(Trade.executed_at <= end)
    return query.order_by(Trade.executed_at.desc()).limit(limit)  # type: ignore[attr-defined]


@router.get("/trades", response_model=list[Trade])
def trades(
    _: CurrentUser,
    session: SessionDep,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> list[Trade]:
    """The transaction log, newest-first, optionally filtered by date range."""
    return list(session.exec(_trade_query(start, end, limit)).all())


@router.get("/audit", response_model=list[AuditLog])
def audit(_: CurrentUser, session: SessionDep, limit: int = 200) -> list[AuditLog]:
    """The audit log of config-changing actions, newest-first."""
    rows = session.exec(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)  # type: ignore[attr-defined]
    ).all()
    return list(rows)


@router.get("/trades.csv")
def trades_csv(
    _: CurrentUser,
    session: SessionDep,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Response:
    """The transaction log as a CSV download (oldest-first) for tax/reporting."""
    rows = list(session.exec(_trade_query(start, end, 100_000)).all())
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)
    for trade in reversed(rows):  # export oldest-first
        writer.writerow(
            [
                trade.executed_at.isoformat(),
                trade.strategy,
                trade.market,
                trade.symbol,
                trade.side,
                trade.quantity,
                trade.price,
                trade.fee,
                trade.realized_pnl,
                trade.mode,
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=capital-trades.csv"},
    )
