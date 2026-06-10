"""Costs API — what the platform spends, attributed to what spent it.

Aggregates every recorded usage row (today LLM calls are the only paid
usage — Binance and the RSS feeds are free) into headline totals, per-model /
per-purpose / per-day breakdowns and a paginated per-call ledger. Named
`costs`, not `llm`, on purpose: a future paid service (keyed news API, paid
market data) reports into the same summary by writing usage rows with its
own provider and purpose.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import select

from ai.usage import LLMUsage
from appsettings.store import get_ai_spend_cap
from auth.deps import CurrentUser, SessionDep

router = APIRouter(prefix="/api/costs", tags=["costs"])


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class CostBucket(BaseModel):
    """One aggregation bucket — by model, purpose or day."""

    key: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class CostsSummary(BaseModel):
    """Headline spend + the breakdowns the Costs screen renders."""

    today_usd: Decimal
    last_7d_usd: Decimal
    last_30d_usd: Decimal
    daily_cap_usd: Decimal  # 0 = unlimited
    by_model: list[CostBucket]
    by_purpose: list[CostBucket]
    by_day: list[CostBucket]  # last 30 days, oldest first


class LedgerEntry(BaseModel):
    """One paid call, newest first."""

    id: int
    created_at: datetime
    provider: str
    model: str
    purpose: str
    strategy: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    action: str | None
    confidence: Decimal | None


class LedgerPage(BaseModel):
    total: int
    entries: list[LedgerEntry]


def _bucketise(
    rows: list[LLMUsage], key_of: Callable[[LLMUsage], str]
) -> list[CostBucket]:
    buckets: dict[str, CostBucket] = {}
    for row in rows:
        key = key_of(row)
        cur = buckets.get(key)
        if cur is None:
            buckets[key] = CostBucket(
                key=key,
                calls=1,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                cost_usd=row.estimated_cost_usd,
            )
        else:
            buckets[key] = CostBucket(
                key=key,
                calls=cur.calls + 1,
                input_tokens=cur.input_tokens + row.input_tokens,
                output_tokens=cur.output_tokens + row.output_tokens,
                cost_usd=cur.cost_usd + row.estimated_cost_usd,
            )
    return [buckets[k] for k in sorted(buckets)]


@router.get("/summary", response_model=CostsSummary)
def costs_summary(_: CurrentUser, session: SessionDep) -> CostsSummary:
    """Spend totals and breakdowns over the last 30 days."""
    now = datetime.now(UTC).replace(tzinfo=None)
    month_ago = now - timedelta(days=30)
    rows = list(
        session.exec(select(LLMUsage).where(LLMUsage.created_at >= month_ago)).all()
    )
    day0 = _day_start(now)
    week_ago = now - timedelta(days=7)
    return CostsSummary(
        today_usd=sum(
            (r.estimated_cost_usd for r in rows if r.created_at >= day0), Decimal(0)
        ),
        last_7d_usd=sum(
            (r.estimated_cost_usd for r in rows if r.created_at >= week_ago),
            Decimal(0),
        ),
        last_30d_usd=sum((r.estimated_cost_usd for r in rows), Decimal(0)),
        daily_cap_usd=get_ai_spend_cap(session),
        by_model=_bucketise(rows, lambda r: f"{r.provider}/{r.model}"),
        by_purpose=_bucketise(rows, lambda r: r.purpose),
        by_day=_bucketise(rows, lambda r: r.created_at.date().isoformat()),
    )


@router.get("/ledger", response_model=LedgerPage)
def costs_ledger(
    _: CurrentUser,
    session: SessionDep,
    limit: int = 50,
    offset: int = 0,
    purpose: str | None = None,
) -> LedgerPage:
    """The per-call ledger, newest first — filterable by purpose."""
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    base = select(LLMUsage)
    if purpose:
        base = base.where(LLMUsage.purpose == purpose)
    all_ids = session.exec(base).all()
    rows = session.exec(
        base.order_by(LLMUsage.created_at.desc())  # type: ignore[attr-defined]
        .offset(offset)
        .limit(limit)
    ).all()
    return LedgerPage(
        total=len(all_ids),
        entries=[
            LedgerEntry(
                id=r.id or 0,
                created_at=r.created_at,
                provider=r.provider,
                model=r.model,
                purpose=r.purpose,
                strategy=r.strategy,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                cost_usd=r.estimated_cost_usd,
                action=r.action,
                confidence=r.confidence,
            )
            for r in rows
        ],
    )
