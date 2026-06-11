"""Tests for AI bet analysis — fake provider, hermetic edge/signal logic."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from ai.providers.base import Completion, LLMError, LLMProvider
from ai.signals import AISignal
from ai.usage import LLMUsage
from appsettings.store import set_ai_spend_cap
from news.models import NewsItem
from polymarket import analysis
from polymarket.analysis import (
    SCREENER_NAME,
    analyze_market,
    build_bet_prompt,
    build_market_pack,
    extract_terms,
    latest_analysis,
    run_screening_cycle,
)
from polymarket.models import PredictionMarket
from polymarket.service import refresh_markets, set_watched
from tests.test_polymarket_service import _NO, _YES, FakeGamma, _gamma_market


class FakeProvider(LLMProvider):
    """LLM provider returning a canned response (or raising)."""

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


def _estimate(probability: str, recommendation: str, confidence: str) -> str:
    return json.dumps(
        {
            "probability": probability,
            "recommendation": recommendation,
            "confidence": confidence,
            "reasoning": "rates look sticky",
        }
    )


def _seed_market(session: Session) -> PredictionMarket:
    refresh_markets(session, fetch=FakeGamma([_gamma_market()]))
    return session.exec(select(PredictionMarket)).one()


def _headline(title: str, category: str = "economic") -> NewsItem:
    return NewsItem(
        source="t",
        title=title,
        url=f"https://example.com/{abs(hash(title))}",
        category=category,
        fetched_at=datetime.now(UTC).replace(tzinfo=None),
    )


def test_extract_terms_keeps_distinctive_words() -> None:
    terms = extract_terms("Will the Fed cut rates in September?")
    assert "Fed" in terms and "rates" in terms and "September" in terms
    assert "Will" not in terms and "the" not in terms


def test_market_pack_matches_news_to_the_question(session: Session) -> None:
    market = _seed_market(session)
    session.add(_headline("Fed signals patience on rates"))
    session.add(_headline("Madrid beats Arsenal", category="world"))
    session.commit()
    pack = build_market_pack(session, market)
    assert Decimal(pack["yes_price"]) == Decimal("0.62")
    assert any("Fed" in h for h in pack["matched_headlines"])
    assert not any("Madrid" in h for h in pack["matched_headlines"])
    prompt = build_bet_prompt(pack)
    assert "Fed signals patience" in prompt
    assert "resolves YES" in prompt


def test_analyze_market_stores_the_edge_and_usage(session: Session) -> None:
    market = _seed_market(session)
    provider = FakeProvider(_estimate("0.75", "buy_yes", "0.8"))
    result = analyze_market(session, market, provider=provider)
    assert result.est_probability == Decimal("0.75")
    assert result.edge == Decimal("0.75") - Decimal("0.62")
    assert result.recommendation == "buy_yes"
    assert latest_analysis(session, market.condition_id).id == result.id
    usage = session.exec(select(LLMUsage)).one()
    assert usage.purpose == "polymarket"


def test_analyze_market_rejects_garbage(session: Session) -> None:
    market = _seed_market(session)
    with pytest.raises(ValueError):
        analyze_market(session, market, provider=FakeProvider("not json"))
    with pytest.raises(ValueError):
        analyze_market(
            session, market, provider=FakeProvider(_estimate("7", "buy_yes", "0.5"))
        )


def test_screening_suggests_when_edge_clears_the_bars(
    session: Session, monkeypatch
) -> None:
    market = _seed_market(session)
    set_watched(session, market.condition_id, True)
    monkeypatch.setattr(
        analysis,
        "resolve_writer",
        lambda s: (FakeProvider(_estimate("0.80", "buy_yes", "0.9")), None),
    )
    written = run_screening_cycle(lambda: session)
    assert written == 1
    signal = session.exec(select(AISignal)).one()
    assert signal.strategy == SCREENER_NAME
    assert signal.venue == "polymarket"
    assert signal.symbol == _YES
    assert signal.action == "buy"
    # Stake (default 100 USDC) at the YES price of 0.62 (column is 8 dp).
    expected = (Decimal("100") / Decimal("0.62")).quantize(Decimal("1e-8"))
    assert signal.quantity == expected


def test_screening_buy_no_targets_the_no_token(session: Session, monkeypatch) -> None:
    market = _seed_market(session)
    set_watched(session, market.condition_id, True)
    monkeypatch.setattr(
        analysis,
        "resolve_writer",
        lambda s: (FakeProvider(_estimate("0.40", "buy_no", "0.9")), None),
    )
    run_screening_cycle(lambda: session)
    signal = session.exec(select(AISignal)).one()
    assert signal.symbol == _NO
    assert signal.reference_price == Decimal(1) - Decimal("0.62")


def test_screening_holds_below_the_bars(session: Session, monkeypatch) -> None:
    market = _seed_market(session)
    set_watched(session, market.condition_id, True)
    # Edge 0.02 is under the default 0.05 threshold — analysed, not suggested.
    monkeypatch.setattr(
        analysis,
        "resolve_writer",
        lambda s: (FakeProvider(_estimate("0.64", "buy_yes", "0.9")), None),
    )
    assert run_screening_cycle(lambda: session) == 1
    assert session.exec(select(AISignal)).all() == []


def test_screening_stops_at_the_spend_cap(session: Session, monkeypatch) -> None:
    market = _seed_market(session)
    set_watched(session, market.condition_id, True)
    set_ai_spend_cap(session, Decimal("0.0000001"))
    provider = FakeProvider(_estimate("0.80", "buy_yes", "0.9"))
    monkeypatch.setattr(analysis, "resolve_writer", lambda s: (provider, None))
    # Cap is already exhausted by a prior recorded call.
    from ai.usage import record_usage

    record_usage(
        session,
        provider="fake",
        model="fake-model",
        input_tokens=10_000_000,
        output_tokens=10_000_000,
        purpose="polymarket",
    )
    assert run_screening_cycle(lambda: session) == 0


def test_screening_includes_top_volume_markets(session: Session, monkeypatch) -> None:
    # Nothing watched — the screener still analyses the top-volume markets.
    _seed_market(session)
    monkeypatch.setattr(
        analysis,
        "resolve_writer",
        lambda s: (FakeProvider(_estimate("0.64", "buy_yes", "0.5")), None),
    )
    assert run_screening_cycle(lambda: session) == 1
