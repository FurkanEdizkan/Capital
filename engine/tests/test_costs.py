"""Tests for cost tracking — purpose attribution, summary, ledger."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from ai.usage import record_usage
from tests.conftest import ADMIN_PASSWORD, login


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def _seed_usage(session: Session) -> None:
    # Two purposes, two models; one old row outside the 30-day window.
    record_usage(
        session,
        provider="claude",
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
        purpose="strategy",
        strategy="AI Trader BTC",
    )  # $3 at the claude input rate
    record_usage(
        session,
        provider="openai",
        model="gpt-4o",
        input_tokens=0,
        output_tokens=1_000_000,
        purpose="council",
    )  # $10 at the gpt-4o output rate
    old = record_usage(
        session,
        provider="openai",
        model="gpt-4o",
        input_tokens=1_000_000,
        output_tokens=0,
        purpose="report",
    )
    old.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=45)
    session.add(old)
    session.commit()


def test_record_usage_carries_purpose(session: Session) -> None:
    row = record_usage(
        session,
        provider="claude",
        model="m",
        input_tokens=1,
        output_tokens=1,
        purpose="recommend",
    )
    assert row.purpose == "recommend"
    # The default keeps old call sites meaningful.
    default = record_usage(
        session, provider="claude", model="m", input_tokens=1, output_tokens=1
    )
    assert default.purpose == "analyze"


def test_costs_summary_aggregates(client: TestClient, session: Session) -> None:
    _seed_usage(session)
    body = client.get("/api/costs/summary", headers=_auth(client)).json()
    assert Decimal(str(body["today_usd"])) == Decimal("13")
    assert Decimal(str(body["last_30d_usd"])) == Decimal("13")  # old row excluded
    by_purpose = {b["key"]: b for b in body["by_purpose"]}
    assert set(by_purpose) == {"strategy", "council"}
    assert Decimal(str(by_purpose["council"]["cost_usd"])) == Decimal("10")
    by_model = {b["key"]: b for b in body["by_model"]}
    assert by_model["claude/claude-sonnet-4-6"]["calls"] == 1
    assert len(body["by_day"]) == 1


def test_costs_ledger_pages_and_filters(
    client: TestClient, session: Session
) -> None:
    _seed_usage(session)
    headers = _auth(client)
    page = client.get("/api/costs/ledger?limit=2", headers=headers).json()
    assert page["total"] == 3
    assert len(page["entries"]) == 2
    # Newest first.
    assert page["entries"][0]["purpose"] in ("strategy", "council")
    rest = client.get("/api/costs/ledger?limit=2&offset=2", headers=headers).json()
    assert len(rest["entries"]) == 1
    council_only = client.get(
        "/api/costs/ledger?purpose=council", headers=headers
    ).json()
    assert council_only["total"] == 1
    assert council_only["entries"][0]["model"] == "gpt-4o"
