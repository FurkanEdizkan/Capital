"""AI council — several models review a research report and vote.

The report is fanned out to every configured council member in parallel; each
returns a structured `Decision` vote. A confidence-weighted majority produces
the unified verdict: an action's score is the sum of its votes' confidences
over the sum of all confidences, and the top action wins only when its score
reaches the quorum — otherwise the verdict is a safe `hold`. A member that
fails is recorded as an abstain and never aborts the review.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Field, Session, SQLModel, select

from ai.providers import LLMProvider, get_provider
from ai.providers.base import Completion, parse_decision
from ai.signals import AISignal, execute_signal, record_signal
from ai.usage import cap_reached, record_usage
from appsettings.store import (
    get_llm_credentials,
    get_setting,
    get_strategy_action_mode,
    set_setting,
)
from marketdata.cache import get_cached_candles
from research.models import ResearchReport
from strategies.ai_strategy import AIStrategy
from strategies.builtin import all_strategies
from trading.models import PositionSide
from trading.portfolio import get_allocation, get_or_create_position
from trading.venue_router import VenueRouter

log = logging.getLogger("capital.ai.council")

_AMT = {"max_digits": 28, "decimal_places": 10}

_MEMBERS_KEY = "council_members"
_QUORUM_KEY = "council_quorum"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class CouncilReview(SQLModel, table=True):
    """One council pass over a report — the unified verdict."""

    __tablename__ = "council_review"

    id: int | None = Field(default=None, primary_key=True)
    report_id: int = Field(index=True, foreign_key="research_report.id")
    verdict: str = Field(max_length=8)  # buy | sell | hold
    weighted_score: Decimal = Field(default=Decimal(0), **_AMT)
    quorum_met: bool = Field(default=False)
    # A short synthesis of the winning side's reasoning.
    strategy_brief: str = Field(default="")
    created_at: datetime = Field(index=True)


class CouncilVote(SQLModel, table=True):
    """One member's vote on a review. `abstain` records a failed member."""

    __tablename__ = "council_vote"

    id: int | None = Field(default=None, primary_key=True)
    review_id: int = Field(index=True, foreign_key="council_review.id")
    provider: str = Field(max_length=16)
    model: str = Field(default="", max_length=64)
    action: str = Field(max_length=8)  # buy | sell | hold | abstain
    confidence: Decimal = Field(default=Decimal(0), **_AMT)
    reasoning: str = Field(default="")


# -- settings -------------------------------------------------------------------


def get_council_members(session: Session) -> list[dict[str, str]]:
    """The configured members — `[{provider, model}, …]`; empty disables."""
    raw = get_setting(session, _MEMBERS_KEY)
    if not raw:
        return []
    try:
        items = json.loads(raw)
        return [
            {"provider": str(i["provider"]), "model": str(i.get("model", ""))}
            for i in items
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("invalid council_members setting — council disabled")
        return []


def set_council_members(session: Session, members: list[dict[str, str]]) -> None:
    """Store the council member list."""
    set_setting(session, _MEMBERS_KEY, json.dumps(members))


def get_council_quorum(session: Session) -> Decimal:
    """The weighted-score threshold a verdict must reach (default 0.5)."""
    raw = get_setting(session, _QUORUM_KEY)
    try:
        value = Decimal(raw) if raw else Decimal("0.5")
    except ArithmeticError:
        return Decimal("0.5")
    return value if Decimal(0) < value <= Decimal(1) else Decimal("0.5")


def set_council_quorum(session: Session, quorum: Decimal) -> None:
    """Set the council quorum (a fraction of total confidence, 0–1]."""
    set_setting(session, _QUORUM_KEY, str(quorum))


# -- consensus ------------------------------------------------------------------


def consensus(
    votes: list[CouncilVote], quorum: Decimal
) -> tuple[str, Decimal, bool]:
    """Confidence-weighted majority over the cast (non-abstain) votes.

    Returns `(verdict, weighted_score, quorum_met)`. With no votes — or a top
    score below the quorum — the verdict falls back to `hold`.
    """
    cast = [v for v in votes if v.action in ("buy", "sell", "hold")]
    total = sum((v.confidence for v in cast), Decimal(0))
    if total <= 0:
        return "hold", Decimal(0), False
    scores: dict[str, Decimal] = {}
    for vote in cast:
        scores[vote.action] = scores.get(vote.action, Decimal(0)) + vote.confidence
    top_action = max(scores, key=lambda a: scores[a])
    top_score = scores[top_action] / total
    if top_score >= quorum:
        return top_action, top_score, True
    return "hold", top_score, False


def _brief(verdict: str, score: Decimal, votes: list[CouncilVote]) -> str:
    """Synthesize the winning side's reasoning into a short strategy brief."""
    reasons = [
        v.reasoning.strip()
        for v in votes
        if v.action == verdict and v.reasoning.strip()
    ]
    head = f"Council verdict: {verdict} (weighted score {score:.0%})."
    return " ".join([head, *reasons[:3]])[:1000]


# -- review ---------------------------------------------------------------------


def render_report(report: ResearchReport) -> str:
    """The report's sections as the text put before each council member."""
    s = report.sections_dict()
    lines = [f"Research report for {report.symbol}:"]
    for key in (
        "summary",
        "technicals",
        "trade_route_effect",
        "technology_review",
        "scenarios_up",
        "scenarios_down",
        "headlines",
        "market_headlines",
        "connections",
    ):
        value = s.get(key)
        if not value:
            continue
        if isinstance(value, list):
            body = "\n".join(f"- {item}" for item in value)
            lines.append(f"{key}:\n{body}")
        elif isinstance(value, dict):
            lines.append(f"{key}: {json.dumps(value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n\n".join(lines)


def build_vote_prompt(report: ResearchReport) -> str:
    """Instruction for one member: read the report, return a Decision."""
    return (
        f"{render_report(report)}\n\n"
        f"You are one member of a trading council voting on {report.symbol}. "
        "Based ONLY on this report, decide whether to buy, sell or hold. "
        'Respond ONLY with a JSON object of the form {"action": '
        '"buy"|"sell"|"hold", "confidence": <0..1>, "reasoning": "<text>"}.'
    )


def _vote(
    member: dict[str, str], provider: LLMProvider, prompt: str
) -> tuple[CouncilVote, Completion | None]:
    """One member's vote — abstains (never raises) on any failure."""
    model = member.get("model") or None
    try:
        completion = provider.complete(prompt, model=model)
        decision = parse_decision(completion.text)
        vote = CouncilVote(
            review_id=0,  # set after the review row exists
            provider=member["provider"],
            model=completion.model,
            action=decision.action.value,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
        )
        return vote, completion
    except Exception:  # noqa: BLE001 — a failed member abstains
        log.warning("council member %s failed", member["provider"], exc_info=True)
        return (
            CouncilVote(
                review_id=0,
                provider=member["provider"],
                model=member.get("model", ""),
                action="abstain",
            ),
            None,
        )


def review_report(
    session: Session,
    report: ResearchReport,
    members: list[dict[str, str]] | None = None,
    *,
    providers: list[LLMProvider] | None = None,
) -> CouncilReview | None:
    """Fan `report` out to the council and store the verdict + votes.

    Returns None when no members are configured or the spend cap is reached.
    `providers` overrides member resolution in tests.
    """
    members = members if members is not None else get_council_members(session)
    if not members:
        return None
    if cap_reached(session):
        log.warning("council skipped for report %s — AI spend cap reached", report.id)
        return None
    if providers is None:
        providers = []
        for member in members:
            creds = get_llm_credentials(session, member["provider"])
            providers.append(
                get_provider(
                    member["provider"],
                    api_key=creds["api_key"],
                    base_url=creds["base_url"],
                )
            )
    prompt = build_vote_prompt(report)
    # Providers' complete() calls are synchronous — fan out on threads. The
    # session is only touched back on this thread, after all members return.
    with ThreadPoolExecutor(max_workers=max(1, len(members))) as pool:
        results = list(
            pool.map(
                lambda pair: _vote(pair[0], pair[1], prompt),
                zip(members, providers, strict=True),
            )
        )
    votes = [vote for vote, _ in results]
    for vote, completion in results:
        if completion is not None:
            record_usage(
                session,
                provider=completion.provider,
                model=completion.model,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                action=vote.action,
                confidence=vote.confidence,
            )
    verdict, score, quorum_met = consensus(votes, get_council_quorum(session))
    review = CouncilReview(
        report_id=report.id or 0,
        verdict=verdict,
        weighted_score=score,
        quorum_met=quorum_met,
        strategy_brief=_brief(verdict, score, votes),
        created_at=_utcnow(),
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    for vote in votes:
        vote.review_id = review.id or 0
        session.add(vote)
    if report.status == "written":
        report.status = "reviewed"
        session.add(report)
    session.commit()
    session.refresh(review)
    return review


def latest_review(
    session: Session, report_id: int
) -> tuple[CouncilReview, list[CouncilVote]] | None:
    """The newest review for a report, with its votes."""
    review = session.exec(
        select(CouncilReview)
        .where(CouncilReview.report_id == report_id)
        .order_by(CouncilReview.created_at.desc())  # type: ignore[attr-defined]
        .limit(1)
    ).first()
    if review is None:
        return None
    votes = list(
        session.exec(
            select(CouncilVote).where(CouncilVote.review_id == review.id)
        ).all()
    )
    return review, votes


def emit_signal(
    session: Session,
    report: ResearchReport,
    review: CouncilReview,
    *,
    venues: VenueRouter | None = None,
) -> AISignal | None:
    """Turn a non-hold council verdict into an `AISignal` for the symbol.

    The signal is recorded for the symbol's AI strategy (skipped with a log
    when none exists). In `auto` action mode it is executed immediately
    through the shared risk + executor path; a blocked or failed execution
    leaves the signal pending for the operator.
    """
    if review.verdict == "hold" or not review.quorum_met:
        return None
    strat = next(
        (
            s
            for s in all_strategies()
            if isinstance(s, AIStrategy) and s.symbol == report.symbol
        ),
        None,
    )
    if strat is None:
        log.info("no AI strategy for %s — council verdict not traded", report.symbol)
        return None
    candles = get_cached_candles(
        session, market=strat.market, symbol=strat.symbol, interval=strat.timeframe, limit=1
    )
    if not candles:
        log.info("no cached price for %s — council verdict not traded", report.symbol)
        return None
    price = candles[-1].close
    position = get_or_create_position(
        session, strat.name, strat.market.value, strat.symbol
    )
    is_long = position.side == PositionSide.long.value
    if review.verdict == "buy" and not is_long:
        allocation = get_allocation(session, strat.name)
        if allocation <= 0 or price <= 0:
            return None
        quantity = allocation / price
    elif review.verdict == "sell" and is_long:
        quantity = position.qty
    else:
        return None  # verdict does not apply to the current position
    signal = record_signal(
        session,
        strategy=strat.name,
        symbol=strat.symbol,
        market=strat.market.value,
        action=review.verdict,
        confidence=review.weighted_score,
        reasoning=review.strategy_brief,
        reference_price=price,
        quantity=quantity,
    )
    if get_strategy_action_mode(session, strat.name) == "auto":
        try:
            execute_signal(session, signal, venues or VenueRouter.default())
        except Exception:  # noqa: BLE001 — leave the signal pending on failure
            log.warning(
                "auto-execution of council signal %s failed — left pending",
                signal.id,
                exc_info=True,
            )
    return signal
