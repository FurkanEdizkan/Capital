"""Polymarket API — the market catalogue, watchlist and AI bet analyses.

Powers the Polymarket page: browse/search the discovered markets, pin them to
the watchlist, read the AI's probability estimates, and (admin) trigger an
immediate refresh or a one-off analysis. Suggestions the screener emits ride
the existing AI-signals endpoints (`/api/ai/signals`).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ai.providers import LLMError
from auth.audit import record_audit
from auth.deps import CurrentUser, SessionDep, require_admin
from auth.models import User
from polymarket import analysis, service
from polymarket.models import MarketAnalysis, PredictionMarket
from research.service import resolve_writer

router = APIRouter(prefix="/api/polymarket", tags=["polymarket"])

AdminUser = Annotated[User, Depends(require_admin)]


class WatchUpdate(BaseModel):
    watched: bool


@router.get("/markets", response_model=list[PredictionMarket])
def list_markets(
    _: CurrentUser,
    session: SessionDep,
    watched: bool | None = None,
    status_filter: str | None = "active",
    category: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[PredictionMarket]:
    """Discovered markets, most-traded first — filterable and searchable."""
    return service.list_markets(
        session,
        watched=watched,
        status=status_filter,
        category=category,
        search=search,
        limit=limit,
    )


@router.put("/markets/{condition_id}/watch", response_model=PredictionMarket)
def update_watched(
    condition_id: str,
    body: WatchUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> PredictionMarket:
    """Pin or unpin a market for scheduled AI analysis."""
    row = service.set_watched(session, condition_id, body.watched)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown market")
    record_audit(
        session,
        actor=user.username,
        action="polymarket.watch",
        target=condition_id,
        detail={"watched": body.watched},
    )
    session.refresh(row)  # the audit commit expires the instance
    return row


@router.post("/refresh")
def refresh_markets(_: AdminUser, session: SessionDep) -> dict[str, int]:
    """Pull the latest top markets from the Gamma API now."""
    return {"updated": service.refresh_markets(session)}


@router.get("/analyses", response_model=list[MarketAnalysis])
def list_analyses(
    _: CurrentUser,
    session: SessionDep,
    condition_id: str | None = None,
    limit: int = 50,
) -> list[MarketAnalysis]:
    """Recent AI bet analyses, newest first — optionally for one market."""
    return analysis.list_analyses(session, condition_id=condition_id, limit=limit)


@router.post("/markets/{condition_id}/analyze", response_model=MarketAnalysis)
def analyze_now(
    condition_id: str, user: AdminUser, session: SessionDep
) -> MarketAnalysis:
    """Run one AI analysis for a market immediately (a paid LLM call)."""
    market = service.get_market(session, condition_id)
    if market is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown market")
    try:
        provider, model = resolve_writer(session)
        result = analysis.analyze_market(session, market, provider=provider, model=model)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM call failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"unparseable analysis: {exc}"
        ) from exc
    record_audit(
        session,
        actor=user.username,
        action="polymarket.analyze",
        target=condition_id,
        detail={"recommendation": result.recommendation, "edge": str(result.edge)},
    )
    session.refresh(result)  # the audit commit expires the instance
    return result
