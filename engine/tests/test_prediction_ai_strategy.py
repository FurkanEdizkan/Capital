"""Tests for PredictionAIStrategy — hermetic, seeded analyses + fake LLM."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from polymarket.models import MarketAnalysis
from polymarket.service import refresh_markets
from strategies.base import StrategyContext
from strategies.prediction_ai import PredictionAIStrategy
from strategies.registry import build_strategy
from tests.test_polymarket_analysis import FakeProvider, _estimate
from tests.test_polymarket_service import _NO, _YES, FakeGamma, _gamma_market
from trading.models import FillSide, Position, PositionSide


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_market(session: Session) -> None:
    refresh_markets(session, fetch=FakeGamma([_gamma_market()]))


def _analysis(
    session: Session,
    *,
    probability: str,
    confidence: str = "0.9",
    age_hours: int = 0,
) -> MarketAnalysis:
    row = MarketAnalysis(
        condition_id="0xCOND",
        question="Will the Fed cut rates in September?",
        market_price=Decimal("0.62"),
        est_probability=Decimal(probability),
        edge=Decimal(probability) - Decimal("0.62"),
        recommendation="buy_yes",
        confidence=Decimal(confidence),
        created_at=_utcnow() - timedelta(hours=age_hours),
    )
    session.add(row)
    session.commit()
    return row


def _ctx(position: Position, price: str = "0.62") -> StrategyContext:
    return StrategyContext(
        candles=[],
        position=position,
        allocation=Decimal("1000"),
        price=Decimal(price),
    )


def _flat(symbol: str = _YES) -> Position:
    return Position(strategy="P", market="spot", symbol=symbol)


def _long(symbol: str = _YES) -> Position:
    return Position(
        strategy="P",
        market="spot",
        symbol=symbol,
        side=PositionSide.long.value,
        qty=Decimal("100"),
        entry_price=Decimal("0.62"),
    )


def _strategy(session: Session, symbol: str = _YES) -> PredictionAIStrategy:
    strat = PredictionAIStrategy("Pred", symbol)
    strat.bind(session)
    return strat


def test_registry_pins_the_type_to_polymarket() -> None:
    strat = build_strategy("prediction_ai", name="p", symbol=_YES)
    assert isinstance(strat, PredictionAIStrategy)
    assert strat.venue == "polymarket"
    assert strat.symbol == _YES  # token ids are never uppercased


def test_buys_yes_on_fresh_edge(session: Session) -> None:
    _seed_market(session)
    _analysis(session, probability="0.75")  # edge +0.13 on YES
    strat = _strategy(session)
    order = strat.evaluate(_ctx(_flat()))
    assert order is not None and order.side is FillSide.buy
    assert order.quantity == Decimal("1000") / Decimal("0.62")
    assert strat.last_decision is not None
    assert strat.last_decision.action.value == "buy"
    assert strat.last_usage is None  # no inline LLM call was needed


def test_no_token_mirrors_the_edge(session: Session) -> None:
    _seed_market(session)
    _analysis(session, probability="0.40")  # YES edge -0.22 → NO edge +0.22
    order = _strategy(session, symbol=_NO).evaluate(_ctx(_flat(_NO), price="0.38"))
    assert order is not None and order.side is FillSide.buy
    # And the YES token holder would be told nothing (flat, negative edge).
    assert _strategy(session).evaluate(_ctx(_flat())) is None


def test_holds_under_the_edge_or_confidence_bar(session: Session) -> None:
    _seed_market(session)
    _analysis(session, probability="0.64")  # edge 0.02 < default 0.05
    assert _strategy(session).evaluate(_ctx(_flat())) is None


def test_sells_when_the_edge_is_gone(session: Session) -> None:
    _seed_market(session)
    _analysis(session, probability="0.60")  # edge negative — exit
    order = _strategy(session).evaluate(_ctx(_long()))
    assert order is not None and order.side is FillSide.sell
    assert order.quantity == Decimal("100")


def test_keeps_holding_while_edge_is_positive(session: Session) -> None:
    _seed_market(session)
    _analysis(session, probability="0.66")  # edge +0.04 — keep the position
    assert _strategy(session).evaluate(_ctx(_long())) is None


def test_stale_analysis_triggers_a_reanalysis(session: Session) -> None:
    _seed_market(session)
    _analysis(session, probability="0.60", age_hours=12)  # stale (default 6h)
    strat = _strategy(session)
    strat.set_ai_config(FakeProvider(_estimate("0.80", "buy_yes", "0.9")), None)
    order = strat.evaluate(_ctx(_flat()))
    assert order is not None and order.side is FillSide.buy
    # The inline analysis was stored for the dashboard and future ticks.
    rows = session.exec(select(MarketAnalysis)).all()
    assert len(rows) == 2


def test_stale_analysis_without_a_model_uses_last_known(session: Session) -> None:
    _seed_market(session)
    _analysis(session, probability="0.80", age_hours=12)
    strat = _strategy(session)  # no provider configured
    order = strat.evaluate(_ctx(_flat()))
    assert order is not None and order.side is FillSide.buy


def test_unknown_token_does_nothing(session: Session) -> None:
    _seed_market(session)
    assert _strategy(session, symbol="999").evaluate(_ctx(_flat("999"))) is None


def test_closed_market_is_not_traded(session: Session) -> None:
    refresh_markets(session, fetch=FakeGamma([_gamma_market(closed=True)]))
    _analysis(session, probability="0.80")
    assert _strategy(session).evaluate(_ctx(_flat())) is None
