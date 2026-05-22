"""Tests for the MCP server — tools exercised against the ASGI app."""

from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

import mcp_server
from ai.providers.base import Completion, LLMProvider
from api.ai import get_llm_provider
from auth.api_tokens import create_api_token
from db import get_session
from main import app
from trading.models import FillSide, Trade


class FakeProvider(LLMProvider):
    name = "fake"

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        return Completion(
            text='{"action": "hold", "confidence": 0.5, "reasoning": "wait"}',
            provider=self.name,
            model=model or "fake-model",
            input_tokens=10,
            output_tokens=5,
        )


@pytest.fixture
def mcp_for(session: Session) -> Iterator[Callable[[str], None]]:
    """Yields a factory that points the MCP server at the app as `role`."""
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: FakeProvider()

    def _connect(role: str) -> None:
        _, token = create_api_token(session, f"{role}-agent", role)
        mcp_server.configure(
            TestClient(app, headers={"Authorization": f"Bearer {token}"})
        )

    yield _connect
    app.dependency_overrides.clear()
    mcp_server._http = None  # reset the cached client


def _seed_trade(session: Session) -> None:
    session.add(
        Trade(
            strategy="S",
            market="spot",
            symbol="BTCUSDT",
            side=FillSide.buy.value,
            quantity=Decimal("1"),
            price=Decimal("100"),
            executed_at=datetime(2026, 5, 1),
        )
    )
    session.commit()


def test_read_tool_works_with_a_user_token(
    mcp_for: Callable[[str], None], session: Session
) -> None:
    _seed_trade(session)
    mcp_for("user")
    trades = mcp_server.get_trade_history()
    assert isinstance(trades, list)
    assert len(trades) == 1


def test_analyze_tool_returns_a_decision(mcp_for: Callable[[str], None]) -> None:
    mcp_for("user")
    result = mcp_server.analyze_and_decide("should I buy BTC?")
    assert result["action"] == "hold"


def test_trade_tool_works_with_an_admin_token(mcp_for: Callable[[str], None]) -> None:
    mcp_for("admin")
    result = mcp_server.set_mode("testnet")
    assert result["mode"] == "testnet"


def test_trade_tool_is_forbidden_for_a_user_token(
    mcp_for: Callable[[str], None],
) -> None:
    mcp_for("user")
    # set_mode hits an admin-only endpoint — a user token is rejected.
    result = mcp_server.set_mode("testnet")
    assert "error" in result
    assert "403" in result["error"]
