"""News API — recent headlines and an on-demand refresh.

Headlines are refreshed daily by the engine scheduler; this endpoint serves
them and lets an admin trigger an immediate refresh. `symbol` filters to one
asset's news (used by the Markets side-panel and AI decision prompts).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from auth.deps import CurrentUser, SessionDep, require_admin
from auth.models import User
from news import service
from news.models import NewsItem

router = APIRouter(prefix="/api/news", tags=["news"])

AdminUser = Annotated[User, Depends(require_admin)]


@router.get("", response_model=list[NewsItem])
def list_news(
    _: CurrentUser,
    session: SessionDep,
    symbol: str | None = None,
    limit: int = 50,
) -> list[NewsItem]:
    """Recent headlines, newest first — optionally filtered by `symbol`."""
    return service.recent(session, symbol=symbol, limit=limit)


@router.post("/refresh")
def refresh_news(_: AdminUser, session: SessionDep) -> dict[str, int]:
    """Fetch every configured feed now. Returns the number of new headlines."""
    return {"added": service.refresh(session)}
