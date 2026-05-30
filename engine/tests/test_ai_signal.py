"""Tests for AI signals — notify-mode capture and operator confirm/dismiss."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from ai.providers.base import Completion, LLMProvider
from ai.signals import AISignal, SignalStatus
from api.market import get_venue_router
from db import get_session
from exchange.client import Market
from main import app
from strategies.ai_strategy import AIStrategy
from tests.conftest import ADMIN_PASSWORD, login
from trading.engine import TradingEngine
from trading.models import Trade
from trading.portfolio import set_allocation
from trading.venue_router import VenueRouter
from venues.base import Instrument, OrderResult, Venue, VenueCandle


def _venue_candles(n: int = 30) -> list[VenueCandle]:
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(
        hours=n - 1
    )
    return [
        VenueCandle(
            open_time=base + timedelta(hours=i),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=Decimal("10"),
        )
        for i in range(n)
    ]


class FakeVenue(Venue):
    name = "binance"

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        raise NotImplementedError

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        return _venue_candles()

    def price(self, symbol: str) -> Decimal:
        return Decimal("100")

    def place_order(self, request: Any) -> OrderResult:
        raise NotImplementedError

    def positions(self) -> dict[str, Decimal]:
        return {}


class BuyProvider(LLMProvider):
    """LLM that always advises buying with high confidence."""

    name = "fake"

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        return Completion(
            text='{"action": "buy", "confidence": 0.9, "reasoning": "go"}',
            provider=self.name,
            model=model or "m",
            input_tokens=10,
            output_tokens=5,
        )


def test_notify_mode_records_signal_without_executing() -> None:
    """The default (notify) mode captures a signal and does not trade."""
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    factory = lambda: Session(eng)  # noqa: E731
    strat = AIStrategy("AI BTC", "BTCUSDT", market=Market.spot)
    with factory() as s:
        set_allocation(s, strat.name, Decimal("100000"))
    engine = TradingEngine(
        session_factory=factory,
        venue_router=VenueRouter(builder=lambda *_: FakeVenue()),
        strategies=[strat],
        ai_resolver=lambda _s, _n: (BuyProvider(), None),
    )
    engine.tick()
    with factory() as s:
        signals = s.exec(select(AISignal)).all()
        trades = s.exec(select(Trade)).all()
    assert len(signals) == 1
    assert signals[0].action == "buy"
    assert signals[0].status == SignalStatus.pending.value
    assert trades == []  # nothing executed in notify mode


@pytest.fixture
def signal_client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_venue_router] = lambda: VenueRouter(
        builder=lambda *_: FakeVenue()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def _pending(session: Session) -> AISignal:
    sig = AISignal(
        strategy="AI BTC",
        symbol="BTCUSDT",
        market="spot",
        action="buy",
        confidence=Decimal("0.9"),
        reasoning="go",
        reference_price=Decimal("100"),
        quantity=Decimal("0.5"),
        status=SignalStatus.pending.value,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(sig)
    session.commit()
    session.refresh(sig)
    return sig


def test_confirm_executes_signal(signal_client: TestClient, session: Session) -> None:
    sig = _pending(session)
    resp = signal_client.post(
        f"/api/ai/signals/{sig.id}/confirm", headers=_auth(signal_client)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "executed"
    assert len(session.exec(select(Trade)).all()) == 1


def test_confirm_twice_conflicts(signal_client: TestClient, session: Session) -> None:
    sig = _pending(session)
    signal_client.post(f"/api/ai/signals/{sig.id}/confirm", headers=_auth(signal_client))
    again = signal_client.post(
        f"/api/ai/signals/{sig.id}/confirm", headers=_auth(signal_client)
    )
    assert again.status_code == 409


def test_dismiss_signal(signal_client: TestClient, session: Session) -> None:
    sig = _pending(session)
    resp = signal_client.post(
        f"/api/ai/signals/{sig.id}/dismiss", headers=_auth(signal_client)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"
    assert session.exec(select(Trade)).all() == []


def test_list_signals_requires_auth(signal_client: TestClient) -> None:
    assert signal_client.get("/api/ai/signals").status_code == 401
