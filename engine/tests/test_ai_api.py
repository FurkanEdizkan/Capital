"""Tests for the AI analyze-and-decide API."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from ai.providers.base import Completion, LLMError, LLMProvider
from api.ai import get_llm_provider
from db import get_session
from main import app
from tests.conftest import ADMIN_PASSWORD, login


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, text: str = "", *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        if self._raises:
            raise LLMError("provider unavailable")
        return Completion(
            text=self._text,
            provider=self.name,
            model=model or "fake-model",
            input_tokens=12,
            output_tokens=8,
        )


def _client(session: Session, provider: LLMProvider) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_llm_provider] = lambda: provider
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def ok_client(session: Session) -> Iterator[TestClient]:
    yield from _client(
        session,
        FakeProvider('{"action": "buy", "confidence": 0.75, "reasoning": "momentum"}'),
    )


@pytest.fixture
def failing_client(session: Session) -> Iterator[TestClient]:
    yield from _client(session, FakeProvider(raises=True))


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def test_analyze_requires_auth(ok_client: TestClient) -> None:
    assert ok_client.post("/api/ai/analyze", json={"task": "review BTC"}).status_code == 401


def test_analyze_returns_a_decision(ok_client: TestClient) -> None:
    resp = ok_client.post(
        "/api/ai/analyze", json={"task": "review my BTC position"}, headers=_auth(ok_client)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "buy"
    assert body["reasoning"] == "momentum"


def test_analyze_rejects_empty_task(ok_client: TestClient) -> None:
    resp = ok_client.post("/api/ai/analyze", json={"task": ""}, headers=_auth(ok_client))
    assert resp.status_code == 422


def test_analyze_records_llm_usage(ok_client: TestClient, session: Session) -> None:
    from sqlmodel import select

    from ai.usage import LLMUsage

    ok_client.post(
        "/api/ai/analyze",
        json={"task": "review my BTC position"},
        headers=_auth(ok_client),
    )
    rows = session.exec(select(LLMUsage)).all()
    assert len(rows) == 1
    assert rows[0].input_tokens == 12
    assert rows[0].action == "buy"


def test_llm_failure_returns_502(failing_client: TestClient) -> None:
    resp = failing_client.post(
        "/api/ai/analyze", json={"task": "review BTC"}, headers=_auth(failing_client)
    )
    assert resp.status_code == 502
