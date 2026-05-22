"""Tests for LLM usage tracking — cost estimation and spend records."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session

from ai.usage import (
    LLMUsage,
    estimate_cost,
    model_usage_summary,
    recent_usage,
    record_usage,
    spend_since,
)


def test_estimate_cost_claude() -> None:
    # claude pricing: $3/MTok in, $15/MTok out.
    cost = estimate_cost("claude", "claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == Decimal("18")


def test_estimate_cost_ollama_is_free() -> None:
    # Local Ollama models cost nothing, whatever the token count.
    assert estimate_cost("ollama", "qwen2.5", 5_000_000, 5_000_000) == Decimal("0")


def test_estimate_cost_unknown_model_uses_fallback() -> None:
    # Fallback ($5/$15 per MTok) — over-estimates on purpose.
    cost = estimate_cost("openai", "some-future-model", 1_000_000, 0)
    assert cost == Decimal("5")


def test_record_usage_persists_a_row(session: Session) -> None:
    row = record_usage(
        session,
        provider="claude",
        model="claude-sonnet-4-6",
        input_tokens=2_000_000,
        output_tokens=0,
        strategy="AI BTC",
        action="buy",
        confidence=Decimal("0.7"),
    )
    assert row.id is not None
    assert row.estimated_cost_usd == Decimal("6")  # 2M * $3/MTok
    assert row.strategy == "AI BTC"
    assert row.action == "buy"


def test_spend_since_sums_recent_usage(session: Session) -> None:
    for _ in range(3):
        record_usage(
            session,
            provider="claude",
            model="claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=0,
        )
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    assert spend_since(session, since) == Decimal("9")  # 3 * $3


def test_spend_since_ignores_older_rows(session: Session) -> None:
    old = LLMUsage(
        provider="claude",
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
        estimated_cost_usd=Decimal("3"),
        created_at=datetime(2020, 1, 1),
    )
    session.add(old)
    session.commit()
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    assert spend_since(session, since) == Decimal("0")


def test_model_usage_summary(session: Session) -> None:
    record_usage(
        session, provider="claude", model="claude-x",
        input_tokens=1_000_000, output_tokens=0, action="buy",
    )
    record_usage(
        session, provider="claude", model="claude-x",
        input_tokens=0, output_tokens=0, action="hold",
    )
    record_usage(
        session, provider="ollama", model="qwen",
        input_tokens=100, output_tokens=100, action="sell",
    )
    by = {(m.provider, m.model): m for m in model_usage_summary(session)}
    claude = by[("claude", "claude-x")]
    assert claude.decisions == 2
    assert claude.buys == 1
    assert claude.holds == 1
    assert by[("ollama", "qwen")].total_cost_usd == Decimal("0")  # local = free


def test_recent_usage_returns_recent_rows(session: Session) -> None:
    for i in range(3):
        record_usage(
            session, provider="claude", model=f"m{i}",
            input_tokens=0, output_tokens=0,
        )
    rows = recent_usage(session, limit=2)
    assert len(rows) == 2
