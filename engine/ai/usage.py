"""LLM usage tracking — per-call token counts and estimated cost.

Every AI completion (a strategy tick or an analyze request) writes one
`LLMUsage` row, so spend can be shown, capped, and attributed to a model.

Costs are **estimates** — token prices change and vary by tier. The fallback
rate deliberately over-estimates so a spend cap errs on the safe side. Local
Ollama models are free, so they are priced at zero.
"""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, select


def _utcnow() -> datetime:
    """Current UTC time, tz-naive — matching how the other tables store time."""
    return datetime.now(UTC).replace(tzinfo=None)

_AMT = {"max_digits": 28, "decimal_places": 10}

#: (input, output) US$ per million tokens, by model-name prefix. Estimates.
_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "claude": (Decimal("3"), Decimal("15")),
    "gpt-4o": (Decimal("2.5"), Decimal("10")),
    "gpt-4": (Decimal("10"), Decimal("30")),
    "gpt-3.5": (Decimal("0.5"), Decimal("1.5")),
    "o1": (Decimal("15"), Decimal("60")),
    "gemini": (Decimal("0.10"), Decimal("0.40")),
    "deepseek": (Decimal("0.30"), Decimal("1.20")),
}
#: Conservative fallback when no prefix matches — over-estimates on purpose.
_FALLBACK = (Decimal("5"), Decimal("15"))
_PER_MTOK = Decimal("1000000")


class LLMUsage(SQLModel, table=True):
    """One recorded LLM completion — tokens, estimated cost, and the decision."""

    __tablename__ = "llm_usage"

    id: int | None = Field(default=None, primary_key=True)
    provider: str = Field(index=True, max_length=16)
    model: str = Field(index=True, max_length=64)
    strategy: str | None = Field(default=None, index=True, max_length=64)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    estimated_cost_usd: Decimal = Field(default=Decimal(0), **_AMT)
    # The decision this call produced, when it produced one (null for a
    # call that failed to parse or for non-decision uses).
    action: str | None = Field(default=None, max_length=8)
    confidence: Decimal | None = Field(default=None, **_AMT)
    created_at: datetime = Field(index=True)


def estimate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> Decimal:
    """Estimate the US$ cost of one completion. Local Ollama models are free."""
    if provider.strip().lower() == "ollama":
        return Decimal(0)
    name = model.strip().lower()
    rate_in, rate_out = next(
        (rates for prefix, rates in _PRICING.items() if name.startswith(prefix)),
        _FALLBACK,
    )
    return (
        Decimal(input_tokens) * rate_in + Decimal(output_tokens) * rate_out
    ) / _PER_MTOK


def record_usage(
    session: Session,
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    strategy: str | None = None,
    action: str | None = None,
    confidence: Decimal | None = None,
) -> LLMUsage:
    """Insert one `LLMUsage` row, computing the estimated cost."""
    row = LLMUsage(
        provider=provider,
        model=model,
        strategy=strategy,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost(
            provider, model, input_tokens, output_tokens
        ),
        action=action,
        confidence=confidence,
        created_at=_utcnow(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def spend_since(session: Session, since: datetime) -> Decimal:
    """Total estimated LLM spend since `since` (tz-naive UTC)."""
    rows = session.exec(
        select(LLMUsage.estimated_cost_usd).where(LLMUsage.created_at >= since)
    ).all()
    return sum(rows, Decimal(0))


class ModelUsage(BaseModel):
    """Per-model rollup of LLM activity — 'what each model did'."""

    provider: str
    model: str
    decisions: int
    buys: int
    sells: int
    holds: int
    total_cost_usd: Decimal


def model_usage_summary(session: Session) -> list[ModelUsage]:
    """Aggregate every recorded LLM call by `(provider, model)`."""
    by_key: dict[tuple[str, str], ModelUsage] = {}
    for row in session.exec(select(LLMUsage)).all():
        key = (row.provider, row.model)
        cur = by_key.get(key) or ModelUsage(
            provider=row.provider,
            model=row.model,
            decisions=0,
            buys=0,
            sells=0,
            holds=0,
            total_cost_usd=Decimal(0),
        )
        by_key[key] = ModelUsage(
            provider=row.provider,
            model=row.model,
            decisions=cur.decisions + 1,
            buys=cur.buys + (row.action == "buy"),
            sells=cur.sells + (row.action == "sell"),
            holds=cur.holds + (row.action == "hold"),
            total_cost_usd=cur.total_cost_usd + row.estimated_cost_usd,
        )
    return [by_key[k] for k in sorted(by_key)]


def recent_usage(session: Session, limit: int = 50) -> list[LLMUsage]:
    """The most recent LLM calls — the decision log, newest first."""
    return list(
        session.exec(
            select(LLMUsage)
            .order_by(LLMUsage.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        ).all()
    )
