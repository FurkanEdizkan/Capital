"""Tests for the Polymarket API — catalogue, watchlist and analyses."""

import json
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from db import get_session
from main import app
from polymarket import service as service_module
from polymarket.service import refresh_markets
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, login
from tests.test_polymarket_analysis import FakeProvider
from tests.test_polymarket_service import FakeGamma, _gamma_market


@pytest.fixture
def pm_client(session: Session, monkeypatch) -> Iterator[TestClient]:
    # The admin refresh endpoint must never hit the real Gamma API in tests.
    monkeypatch.setattr(
        service_module, "_http_fetch", FakeGamma([_gamma_market()])
    )
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(client: TestClient, username: str = "admin") -> dict[str, str]:
    password = ADMIN_PASSWORD if username == "admin" else USER_PASSWORD
    return {"Authorization": f"Bearer {login(client, username, password)}"}


def test_refresh_is_admin_only_for_users(pm_client: TestClient) -> None:
    # "bob" is the seeded non-admin account.
    resp = pm_client.post("/api/polymarket/refresh", headers=_auth(pm_client, "bob"))
    assert resp.status_code == 403


def _seed(session: Session) -> None:
    refresh_markets(session, fetch=FakeGamma([_gamma_market()]))


def test_markets_require_auth(pm_client: TestClient) -> None:
    assert pm_client.get("/api/polymarket/markets").status_code == 401


def test_list_and_search_markets(pm_client: TestClient, session: Session) -> None:
    _seed(session)
    headers = _auth(pm_client)
    resp = pm_client.get("/api/polymarket/markets", headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0]["condition_id"] == "0xCOND"
    none = pm_client.get(
        "/api/polymarket/markets", params={"search": "madrid"}, headers=headers
    )
    assert none.json() == []


def test_watch_round_trip(pm_client: TestClient, session: Session) -> None:
    _seed(session)
    headers = _auth(pm_client)
    resp = pm_client.put(
        "/api/polymarket/markets/0xCOND/watch",
        json={"watched": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["watched"] is True
    listed = pm_client.get(
        "/api/polymarket/markets", params={"watched": True}, headers=headers
    )
    assert [m["condition_id"] for m in listed.json()] == ["0xCOND"]


def test_watch_unknown_market_404(pm_client: TestClient) -> None:
    resp = pm_client.put(
        "/api/polymarket/markets/0xNOPE/watch",
        json={"watched": True},
        headers=_auth(pm_client),
    )
    assert resp.status_code == 404


def test_refresh_updates_the_catalogue(pm_client: TestClient) -> None:
    resp = pm_client.post("/api/polymarket/refresh", headers=_auth(pm_client))
    assert resp.status_code == 200
    assert resp.json() == {"updated": 1}


def test_analyze_now_writes_and_lists(
    pm_client: TestClient, session: Session, monkeypatch
) -> None:
    _seed(session)
    canned = json.dumps(
        {
            "probability": "0.8",
            "recommendation": "buy_yes",
            "confidence": "0.7",
            "reasoning": "news supports it",
        }
    )
    monkeypatch.setattr(
        "api.polymarket.resolve_writer", lambda s: (FakeProvider(canned), None)
    )
    headers = _auth(pm_client)
    resp = pm_client.post(
        "/api/polymarket/markets/0xCOND/analyze", headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation"] == "buy_yes"
    assert Decimal(body["edge"]) == Decimal("0.8") - Decimal("0.62")
    listed = pm_client.get("/api/polymarket/analyses", headers=headers)
    assert len(listed.json()) == 1


def test_analyze_unparseable_is_a_502(
    pm_client: TestClient, session: Session, monkeypatch
) -> None:
    _seed(session)
    monkeypatch.setattr(
        "api.polymarket.resolve_writer", lambda s: (FakeProvider("nonsense"), None)
    )
    resp = pm_client.post(
        "/api/polymarket/markets/0xCOND/analyze", headers=_auth(pm_client)
    )
    assert resp.status_code == 502
