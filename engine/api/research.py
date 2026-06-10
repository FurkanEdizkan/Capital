"""Research API — stored reports and an on-demand research run.

Reports are written on the engine scheduler; this router serves them (list +
full detail) and lets an admin trigger a run immediately — for one symbol or
the whole watched list.
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from ai.providers import LLMError
from appsettings.store import get_research_symbols
from auth.deps import CurrentUser, SessionDep, require_admin
from auth.models import User
from research import service
from research.models import ResearchReport

log = logging.getLogger("capital.api.research")

router = APIRouter(prefix="/api/research", tags=["research"])

AdminUser = Annotated[User, Depends(require_admin)]


class ResearchReportRead(BaseModel):
    """One report — `sections` is the parsed schema-formatted content."""

    id: int
    symbol: str
    schema_version: int
    status: str
    provider: str
    model: str
    error: str
    created_at: datetime
    sections: dict

    @classmethod
    def from_row(cls, row: ResearchReport) -> "ResearchReportRead":
        return cls(
            id=row.id or 0,
            symbol=row.symbol,
            schema_version=row.schema_version,
            status=row.status,
            provider=row.provider,
            model=row.model,
            error=row.error,
            created_at=row.created_at,
            sections=row.sections_dict(),
        )


class ResearchRun(BaseModel):
    """Manual trigger — one symbol, or blank for every watched symbol."""

    symbol: str = Field(default="", max_length=24)


@router.get("", response_model=list[ResearchReportRead])
def list_reports(
    _: CurrentUser,
    session: SessionDep,
    symbol: str | None = None,
    limit: int = 50,
) -> list[ResearchReportRead]:
    """Recent reports, newest first — optionally filtered by `symbol`."""
    stmt = select(ResearchReport)
    if symbol:
        stmt = stmt.where(ResearchReport.symbol == symbol.upper())
    stmt = stmt.order_by(ResearchReport.created_at.desc()).limit(  # type: ignore[attr-defined]
        min(max(limit, 1), 200)
    )
    return [ResearchReportRead.from_row(r) for r in session.exec(stmt).all()]


@router.get("/{report_id}", response_model=ResearchReportRead)
def get_report(
    report_id: int, _: CurrentUser, session: SessionDep
) -> ResearchReportRead:
    """One report with its full sections."""
    row = session.get(ResearchReport, report_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    return ResearchReportRead.from_row(row)


@router.post("/run", response_model=list[ResearchReportRead])
def run_research(
    body: ResearchRun, _: AdminUser, session: SessionDep
) -> list[ResearchReportRead]:
    """Write a report now — for `symbol`, or every watched symbol when blank."""
    symbols = [body.symbol.upper()] if body.symbol else get_research_symbols(session)
    try:
        provider, model = service.resolve_writer(session)
    except LLMError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    reports: list[ResearchReportRead] = []
    for sym in symbols:
        row = service.write_report(session, sym, provider=provider, model=model)
        reports.append(ResearchReportRead.from_row(row))
    return reports
