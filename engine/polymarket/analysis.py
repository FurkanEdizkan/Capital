"""AI bet analysis — estimate a market's true probability and find the edge.

For one prediction market the analysis assembles a data pack (the question,
current YES price, time to resolution, volume/liquidity, and news headlines
matched to the question's keywords), asks the configured report-writer LLM to
estimate the probability the market resolves YES, and stores a
`MarketAnalysis` row with the edge — estimate minus market price.

`run_screening_cycle` does this on a schedule for every watched market plus
the top-volume ones, and turns analyses that clear the operator's edge and
confidence bars into pending `AISignal` suggestions (Telegram + dashboard) —
the same confirmation flow AI strategies use. Deliberately slow: one cycle
every few hours; prediction markets move on events, not ticks.
"""

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, col, select

from ai.providers import LLMProvider
from ai.signals import record_signal
from ai.usage import cap_reached, record_usage
from appsettings.store import (
    get_polymarket_edge_threshold,
    get_polymarket_min_confidence,
    get_polymarket_screen_top,
    get_polymarket_stake,
)
from news import service as news_service
from notify.telegram import TelegramNotifier
from polymarket.models import MarketAnalysis, MarketStatus, PredictionMarket
from research.service import resolve_writer

log = logging.getLogger("capital.polymarket.analysis")

#: Strategy label screener suggestions are recorded under — not a real
#: strategy; confirming one books the position under this name.
SCREENER_NAME = "Polymarket Screener"

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

#: Words too common to identify a market's subject in headlines.
_STOPWORDS = frozenset(
    "will the a an of in on at to by for and or be is are was were do does did "
    "before after during above below over under between than then this that "
    "what which who whom when where how why with without from into out up down "
    "win wins won more most less least many much any all no not have has had "
    "it its their there here they he she we you i his her them us our your "
    "yes end year month week day".split()
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def extract_terms(question: str, *, limit: int = 6) -> list[str]:
    """The question's distinctive keywords — what to search the news for."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", question)
    terms: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in _STOPWORDS or lowered in (t.lower() for t in terms):
            continue
        terms.append(word)
        if len(terms) >= limit:
            break
    return terms


def build_market_pack(session: Session, market: PredictionMarket) -> dict[str, Any]:
    """Everything the platform knows about one market, for the bet prompt."""
    matched = news_service.search(session, extract_terms(market.question), limit=10)
    world = [
        n
        for n in news_service.recent(session, limit=40)
        if n.category in ("world", "economic")
    ][:8]
    days_left = None
    if market.end_date is not None:
        days_left = max(0, (market.end_date - _utcnow()).days)
    return {
        "question": market.question,
        "outcomes": json.loads(market.outcomes or "[]"),
        "yes_price": str(market.yes_price),
        "days_to_resolution": days_left,
        "volume_24h": str(market.volume_24h),
        "liquidity": str(market.liquidity),
        "matched_headlines": [n.title for n in matched],
        "world_headlines": [f"[{n.category}] {n.title}" for n in world],
    }


def build_bet_prompt(pack: dict[str, Any]) -> str:
    """The probability-estimation instruction: data pack in, strict JSON out."""
    matched = "\n".join(f"- {h}" for h in pack["matched_headlines"]) or "- (none)"
    world = "\n".join(f"- {h}" for h in pack["world_headlines"]) or "- (none)"
    return "\n".join(
        [
            "You are a careful forecaster evaluating a prediction-market bet.",
            f"Market question: {pack['question']}",
            f"Outcomes: {pack['outcomes']}",
            f"Current market price of YES (the crowd's probability): {pack['yes_price']}",
            f"Days until resolution: {pack['days_to_resolution']}",
            f"24h volume: {pack['volume_24h']} USDC; liquidity: {pack['liquidity']} USDC.",
            "",
            "News headlines matched to this question:",
            matched,
            "",
            "Recent world & economic headlines:",
            world,
            "",
            "Estimate the true probability that this market resolves YES.",
            "Reason from the evidence above and your background knowledge; weigh",
            "base rates and time remaining. Recommend buy_yes only when your",
            "estimate is meaningfully above the market price, buy_no when",
            "meaningfully below, hold otherwise.",
            "",
            "Respond ONLY with a JSON object of the form "
            '{"probability": <0..1>, "recommendation": "buy_yes"|"buy_no"|"hold", '
            '"confidence": <0..1>, "reasoning": "<short text>"}.',
        ]
    )


def _parse_estimate(text: str) -> dict[str, Any]:
    """Extract the probability-estimate JSON from the model's response."""
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError(f"no JSON object in analysis response: {text[:120]!r}")
    raw = json.loads(match.group(0))
    if not isinstance(raw, dict):
        raise ValueError("analysis response is not a JSON object")
    probability = Decimal(str(raw.get("probability", "0")))
    confidence = Decimal(str(raw.get("confidence", "0")))
    recommendation = str(raw.get("recommendation", "hold"))
    if recommendation not in ("buy_yes", "buy_no", "hold"):
        recommendation = "hold"
    if not (0 <= probability <= 1) or not (0 <= confidence <= 1):
        raise ValueError("probability/confidence outside 0..1")
    return {
        "probability": probability,
        "confidence": confidence,
        "recommendation": recommendation,
        "reasoning": str(raw.get("reasoning", ""))[:2000],
    }


def analyze_market(
    session: Session,
    market: PredictionMarket,
    *,
    provider: LLMProvider,
    model: str | None = None,
) -> MarketAnalysis:
    """Run one AI pass over `market` and store the resulting analysis.

    Raises on LLM/parse failure — callers decide whether that aborts (the API
    endpoint surfaces it) or is skipped (the screening cycle logs and moves on).
    """
    pack = build_market_pack(session, market)
    completion = provider.complete(build_bet_prompt(pack), model=model)
    record_usage(
        session,
        provider=completion.provider,
        model=completion.model,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        purpose="polymarket",
    )
    estimate = _parse_estimate(completion.text)
    analysis = MarketAnalysis(
        condition_id=market.condition_id,
        question=market.question,
        market_price=market.yes_price,
        est_probability=estimate["probability"],
        edge=estimate["probability"] - market.yes_price,
        recommendation=estimate["recommendation"],
        confidence=estimate["confidence"],
        reasoning=estimate["reasoning"],
        provider=completion.provider,
        model=completion.model,
        created_at=_utcnow(),
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return analysis


def latest_analysis(
    session: Session, condition_id: str
) -> MarketAnalysis | None:
    """The most recent stored analysis for a market, or None."""
    return session.exec(
        select(MarketAnalysis)
        .where(MarketAnalysis.condition_id == condition_id)
        .order_by(col(MarketAnalysis.created_at).desc())
        .limit(1)
    ).first()


def list_analyses(
    session: Session, *, condition_id: str | None = None, limit: int = 50
) -> list[MarketAnalysis]:
    """Recent analyses, newest first — optionally for one market."""
    stmt = select(MarketAnalysis)
    if condition_id:
        stmt = stmt.where(MarketAnalysis.condition_id == condition_id)
    stmt = stmt.order_by(col(MarketAnalysis.created_at).desc()).limit(limit)
    return list(session.exec(stmt).all())


def _suggest(
    session: Session,
    market: PredictionMarket,
    analysis: MarketAnalysis,
    notifier: TelegramNotifier,
) -> None:
    """Record an `AISignal` suggestion for an analysis that cleared the bars."""
    if analysis.recommendation == "buy_yes":
        token, price = market.yes_token_id, market.yes_price
    else:
        token, price = market.no_token_id, Decimal(1) - market.yes_price
    if not token or price <= 0:
        return
    stake = get_polymarket_stake(session)
    signal = record_signal(
        session,
        strategy=SCREENER_NAME,
        symbol=token,
        venue="polymarket",
        market="spot",
        action="buy",
        confidence=analysis.confidence,
        reasoning=(
            f"{market.question} — {analysis.recommendation} "
            f"(est P(YES) {analysis.est_probability} vs market "
            f"{analysis.market_price}, edge {analysis.edge}). "
            f"{analysis.reasoning}"
        )[:2000],
        reference_price=price,
        quantity=stake / price,
    )
    notifier.send(
        f"Polymarket suggestion — {analysis.recommendation} "
        f"“{market.question[:120]}” at {price} "
        f"(edge {analysis.edge}, confidence {signal.confidence}). "
        f"Confirm on the dashboard to stake {stake} USDC."
    )


def run_screening_cycle(
    session_factory: Callable[[], Session],
    *,
    notifier: TelegramNotifier | None = None,
) -> int:
    """Analyse the watchlist + top-volume markets; suggest where there's edge.

    Returns the number of analyses written. Best-effort per market; stops
    early once the daily AI spend cap is hit — mirrors `research.run_cycle`.
    """
    notifier = notifier or TelegramNotifier()
    written = 0
    with session_factory() as session:
        watched = list_markets_for_screening(session)
        edge_bar = get_polymarket_edge_threshold(session)
        confidence_bar = get_polymarket_min_confidence(session)
        for market in watched:
            if cap_reached(session):
                log.warning("polymarket screening stopped — AI spend cap reached")
                break
            try:
                provider, model = resolve_writer(session)
                analysis = analyze_market(session, market, provider=provider, model=model)
                written += 1
                if (
                    analysis.recommendation != "hold"
                    and abs(analysis.edge) >= edge_bar
                    and analysis.confidence >= confidence_bar
                ):
                    _suggest(session, market, analysis, notifier)
            except Exception:  # noqa: BLE001 — one market must not abort the cycle
                log.exception("bet analysis failed for %s", market.condition_id)
    log.info("polymarket screening wrote %d analyses", written)
    return written


def list_markets_for_screening(session: Session) -> list[PredictionMarket]:
    """Watched markets plus the top-N by volume, deduplicated, active only."""
    top_n = get_polymarket_screen_top(session)
    watched = session.exec(
        select(PredictionMarket).where(
            PredictionMarket.watched == True,  # noqa: E712 — SQL expression
            PredictionMarket.status == MarketStatus.active,
        )
    ).all()
    combined = {m.condition_id: m for m in watched}
    if top_n > 0:
        top = session.exec(
            select(PredictionMarket)
            .where(PredictionMarket.status == MarketStatus.active)
            .order_by(col(PredictionMarket.volume_24h).desc())
            .limit(top_n)
        ).all()
        for market in top:
            combined.setdefault(market.condition_id, market)
    return list(combined.values())
