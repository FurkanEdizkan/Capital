"""Tests for the AI council — consensus, fan-out, signal emission."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from ai import council
from ai.providers.base import Completion, LLMError, LLMProvider
from ai.signals import AISignal
from ai.usage import LLMUsage
from appsettings.store import set_ai_spend_cap, set_strategy_action_mode
from marketdata.models import Candle
from research.models import ResearchReport
from trading.models import Trade
from trading.portfolio import set_allocation
from trading.venue_router import VenueRouter
from venues.base import Instrument, OrderResult, Venue, VenueCandle


class VotingProvider(LLMProvider):
    """A council member with a fixed vote (or a failure)."""

    name = "fake"

    def __init__(
        self, action: str = "buy", confidence: str = "0.9", *, raises: bool = False
    ) -> None:
        self._action = action
        self._confidence = confidence
        self._raises = raises

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        if self._raises:
            raise LLMError("member down")
        text = json.dumps(
            {
                "action": self._action,
                "confidence": self._confidence,
                "reasoning": f"vote {self._action}",
            }
        )
        return Completion(
            text=text,
            provider=self.name,
            model=model or "fake-model",
            input_tokens=10,
            output_tokens=5,
        )


def _vote(action: str, confidence: str) -> council.CouncilVote:
    return council.CouncilVote(
        review_id=0, provider="p", action=action, confidence=Decimal(confidence)
    )


def _report(session: Session, symbol: str = "BTCUSDT") -> ResearchReport:
    report = ResearchReport(
        symbol=symbol,
        status="written",
        sections=json.dumps({"summary": "constructive"}),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


_MEMBERS = [
    {"provider": "claude", "model": "m1"},
    {"provider": "openai", "model": "m2"},
    {"provider": "gemini", "model": "m3"},
]


def test_consensus_weighted_majority() -> None:
    votes = [_vote("buy", "0.9"), _vote("buy", "0.6"), _vote("sell", "0.5")]
    verdict, score, met = council.consensus(votes, Decimal("0.5"))
    assert verdict == "buy"
    assert met
    assert score == Decimal("1.5") / Decimal("2.0")


def test_consensus_below_quorum_falls_back_to_hold() -> None:
    votes = [_vote("buy", "0.5"), _vote("sell", "0.5"), _vote("hold", "0.4")]
    verdict, _score, met = council.consensus(votes, Decimal("0.6"))
    assert verdict == "hold"
    assert not met


def test_consensus_ignores_abstains() -> None:
    votes = [_vote("abstain", "0"), _vote("buy", "0.7")]
    verdict, score, met = council.consensus(votes, Decimal("0.5"))
    assert (verdict, met) == ("buy", True)
    assert score == Decimal(1)
    # All abstain → hold without quorum.
    verdict, score, met = council.consensus([_vote("abstain", "0")], Decimal("0.5"))
    assert (verdict, score, met) == ("hold", Decimal(0), False)


def test_review_report_fans_out_and_stores_votes(session: Session) -> None:
    report = _report(session)
    providers: list[LLMProvider] = [
        VotingProvider("buy", "0.9"),
        VotingProvider("buy", "0.8"),
        VotingProvider(raises=True),
    ]
    review = council.review_report(
        session, report, members=_MEMBERS, providers=providers
    )
    assert review is not None
    assert review.verdict == "buy"
    assert review.quorum_met
    assert "buy" in review.strategy_brief
    votes = session.exec(select(council.CouncilVote)).all()
    assert len(votes) == 3
    assert sum(v.action == "abstain" for v in votes) == 1
    # Two successful members were costed; the failed one was not.
    assert len(session.exec(select(LLMUsage)).all()) == 2
    session.refresh(report)
    assert report.status == "reviewed"


def test_review_report_without_members_is_skipped(session: Session) -> None:
    assert council.review_report(session, _report(session)) is None


def test_review_report_respects_spend_cap(session: Session) -> None:
    set_ai_spend_cap(session, Decimal("0.000001"))
    session.add(
        LLMUsage(
            provider="openai",
            model="gpt-4",
            estimated_cost_usd=Decimal(1),
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()
    review = council.review_report(
        session,
        _report(session),
        members=_MEMBERS,
        providers=[VotingProvider() for _ in _MEMBERS],
    )
    assert review is None


def _seed_price(session: Session, symbol: str = "BTCUSDT") -> None:
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    session.add(
        Candle(
            market="spot",
            symbol=symbol,
            interval="1h",
            open_time=now,
            open=Decimal(100),
            high=Decimal(100),
            low=Decimal(100),
            close=Decimal(100),
            volume=Decimal(1),
            close_time=now,
        )
    )
    session.commit()


def _review(report: ResearchReport, verdict: str = "buy") -> council.CouncilReview:
    return council.CouncilReview(
        report_id=report.id or 0,
        verdict=verdict,
        weighted_score=Decimal("0.8"),
        quorum_met=verdict != "hold",
        strategy_brief=f"Council verdict: {verdict}.",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )


def test_emit_signal_records_pending_signal_in_notify_mode(
    session: Session,
) -> None:
    _seed_price(session)
    set_allocation(session, "AI Trader BTC", Decimal(1000))
    report = _report(session)
    signal = council.emit_signal(session, report, _review(report, "buy"))
    assert signal is not None
    assert signal.status == "pending"
    assert signal.strategy == "AI Trader BTC"
    assert signal.quantity == Decimal(1000) / Decimal(100)
    assert session.exec(select(Trade)).all() == []  # notify mode: not executed


def test_emit_signal_skips_hold_and_unknown_symbols(session: Session) -> None:
    report = _report(session)
    assert council.emit_signal(session, report, _review(report, "hold")) is None
    other = _report(session, symbol="NOSUCHUSDT")
    assert council.emit_signal(session, other, _review(other, "buy")) is None
    # Sell with no long position does not apply.
    _seed_price(session)
    assert council.emit_signal(session, report, _review(report, "sell")) is None


class FakeVenue(Venue):
    name = "binance"

    def instrument(self, symbol: str, *, market: str | None = None) -> Instrument:
        raise NotImplementedError

    def candles(
        self, symbol: str, interval: str, limit: int = 200, *, market: str | None = None
    ) -> list[VenueCandle]:
        return []

    def price(self, symbol: str) -> Decimal:
        return Decimal(100)

    def place_order(self, request: Any) -> OrderResult:
        raise NotImplementedError

    def positions(self) -> dict[str, Decimal]:
        return {}


def test_emit_signal_auto_mode_executes_through_sim(session: Session) -> None:
    _seed_price(session)
    set_allocation(session, "AI Trader BTC", Decimal(1000))
    set_strategy_action_mode(session, "AI Trader BTC", "auto")
    report = _report(session)
    venues = VenueRouter(builder=lambda _s, _n, _m: FakeVenue())
    signal = council.emit_signal(session, report, _review(report, "buy"), venues=venues)
    assert signal is not None
    assert signal.status == "executed"
    trades = session.exec(select(Trade)).all()
    assert len(trades) == 1
    assert trades[0].strategy == "AI Trader BTC"


def test_emit_signal_auto_mode_failure_leaves_signal_pending(
    session: Session,
) -> None:
    _seed_price(session)
    set_allocation(session, "AI Trader BTC", Decimal(1000))
    set_strategy_action_mode(session, "AI Trader BTC", "auto")
    report = _report(session)

    class DownVenue(FakeVenue):
        def price(self, symbol: str) -> Decimal:
            raise RuntimeError("venue down")

    venues = VenueRouter(builder=lambda _s, _n, _m: DownVenue())
    signal = council.emit_signal(session, report, _review(report, "buy"), venues=venues)
    assert signal is not None
    assert signal.status == "pending"
    assert session.exec(select(AISignal)).all()[0].status == "pending"
