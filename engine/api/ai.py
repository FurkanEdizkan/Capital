"""AI API — analyze-and-decide, plus per-model usage and the decision log.

An operator (or an agent) submits a free-form task; the configured LLM
returns a structured `Decision`. Executing that decision is a separate,
risk- and role-gated step — this endpoint only advises. The model endpoints
surface what each model did and what it cost.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ai.analyze import analyze
from ai.providers import LLMError, get_provider
from ai.providers.base import Decision, LLMProvider
from ai.signals import AISignal, SignalStatus, recent_signals
from ai.usage import LLMUsage, ModelUsage, model_usage_summary, recent_usage, record_usage
from api.market import get_venue_router
from appsettings.store import get_ai_api_key, get_ai_settings
from auth.deps import CurrentUser, SessionDep, require_admin
from auth.models import User
from config import settings
from trading.executor_router import ExecutorRouter
from trading.executors.base import ExecutionError, Order
from trading.models import FillSide
from trading.portfolio import get_or_create_position
from trading.risk import RiskManager
from trading.venue_router import VenueRouter
from venues.base import VenueError

router = APIRouter(prefix="/api/ai", tags=["ai"])

AdminUser = Annotated[User, Depends(require_admin)]
VenueRouterDep = Annotated[VenueRouter, Depends(get_venue_router)]


def get_llm_provider(session: SessionDep) -> LLMProvider:
    """The LLM provider built from the stored AI settings (overridable)."""
    ai = get_ai_settings(session)
    return get_provider(
        ai["provider"],
        api_key=get_ai_api_key(session),
        base_url=ai["base_url"],
    )


ProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


class AnalyzeRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)


@router.post("/analyze", response_model=Decision)
def analyze_and_decide(
    body: AnalyzeRequest,
    _: CurrentUser,
    session: SessionDep,
    provider: ProviderDep,
) -> Decision:
    """Run a free-form analyze-and-decide task through the configured LLM."""
    model = get_ai_settings(session)["model"] or None
    try:
        decision, completion = analyze(provider, task=body.task, model=model)
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"AI analysis failed: {exc}"
        ) from exc
    record_usage(
        session,
        provider=completion.provider,
        model=completion.model,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        action=decision.action.value,
        confidence=decision.confidence,
    )
    return decision


@router.get("/models", response_model=list[ModelUsage])
def model_performance(_: CurrentUser, session: SessionDep) -> list[ModelUsage]:
    """Per-model rollup — decisions, action mix and total cost for each model."""
    return model_usage_summary(session)


@router.get("/decisions", response_model=list[LLMUsage])
def decision_log(
    _: CurrentUser, session: SessionDep, limit: int = 50
) -> list[LLMUsage]:
    """The recent decision log — what each model decided, newest first."""
    return recent_usage(session, limit=limit)


def _executor_router() -> ExecutorRouter:
    """Overridable in tests; resolves Sim/Testnet/Live per call."""
    return ExecutorRouter()


@router.get("/signals", response_model=list[AISignal])
def list_signals(
    _: CurrentUser, session: SessionDep, status_filter: str | None = None, limit: int = 50
) -> list[AISignal]:
    """Recent AI signals (notify-mode decisions), newest first."""
    return recent_signals(session, status=status_filter, limit=limit)


@router.post("/signals/{signal_id}/confirm", response_model=AISignal)
def confirm_signal(
    signal_id: int,
    _: AdminUser,
    session: SessionDep,
    venues: VenueRouterDep,
) -> AISignal:
    """Execute a pending AI signal through the same risk + executor path.

    Re-prices at confirmation and re-runs the risk gate, so a stale or
    risk-blocked signal cannot slip through. Marks the signal `executed`.
    """
    signal = session.get(AISignal, signal_id)
    if signal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    if signal.status != SignalStatus.pending.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"signal is already {signal.status}"
        )
    try:
        price = venues.resolve(session).price(signal.symbol)
    except VenueError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"could not price {signal.symbol}: {exc}"
        ) from exc

    position = get_or_create_position(
        session, signal.strategy, signal.market, signal.symbol
    )
    order = Order(
        strategy=signal.strategy,
        market=signal.market,
        symbol=signal.symbol,
        side=FillSide(signal.action),
        quantity=signal.quantity,
    )
    reviewed = RiskManager.from_settings(settings).review(
        session, order, position, price
    )
    if reviewed is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "order blocked by the risk manager (size cap or kill switch)",
        )
    executor = _executor_router().resolve(session)
    try:
        executor.execute(session, reviewed, reference_price=price)
    except ExecutionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    signal.status = SignalStatus.executed.value
    session.add(signal)
    session.commit()
    session.refresh(signal)
    return signal


@router.post("/signals/{signal_id}/dismiss", response_model=AISignal)
def dismiss_signal(signal_id: int, _: AdminUser, session: SessionDep) -> AISignal:
    """Dismiss a pending AI signal without executing it."""
    signal = session.get(AISignal, signal_id)
    if signal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "signal not found")
    signal.status = SignalStatus.dismissed.value
    session.add(signal)
    session.commit()
    session.refresh(signal)
    return signal
