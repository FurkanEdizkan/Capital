"""Strategy management API — list, allocate, enable/disable, close.

Powers the Strategies page. Strategies are code-defined (built-in or plugin);
these endpoints manage each strategy's capital allocation, lifecycle state and
open positions. Any authenticated operator may use them — see plan:
Authentication & Roles (managing strategies is allowed for both roles).
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from api.market import StreamsDep
from appsettings.store import (
    LLM_PROVIDERS,
    get_strategy_ai_config,
    set_strategy_ai_config,
)
from auth.audit import record_audit
from auth.deps import CurrentUser, SessionDep
from strategies.base import BaseStrategy
from trading.accounting import strategy_summary
from trading.engine import TradingEngine
from trading.lifecycle import is_enabled, set_enabled
from trading.portfolio import get_allocation, set_allocation

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


def get_trading_engine(request: Request) -> TradingEngine:
    """The trading engine created in the app lifespan."""
    return request.app.state.trading


TradingDep = Annotated[TradingEngine, Depends(get_trading_engine)]


class StrategyRead(BaseModel):
    """A strategy's identity, lifecycle state and accounting summary."""

    name: str
    kind: str
    symbol: str
    market: str
    timeframe: str
    enabled: bool
    allocated: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    open_positions: int
    # The configured LLM provider + model — set only for AI strategies.
    ai_provider: str | None = None
    ai_model: str | None = None


class AllocationUpdate(BaseModel):
    allocated: Decimal = Field(ge=0)


class EnabledUpdate(BaseModel):
    enabled: bool


class AiModelUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=16)
    model: str = Field(default="", max_length=64)


class CloseResult(BaseModel):
    closed: int


def _marks(streams: object) -> dict[str, Decimal]:
    """Build {symbol: price} from the live ticker snapshots."""
    marks: dict[str, Decimal] = {}
    for hub in (streams.spot, streams.futures):  # type: ignore[attr-defined]
        for ticker in hub.snapshot():
            marks[ticker.symbol] = ticker.price
    return marks


def _read(
    session: Session, strategy: BaseStrategy, marks: dict[str, Decimal]
) -> StrategyRead:
    summary = strategy_summary(session, strategy.name, marks)
    ai_provider: str | None = None
    ai_model: str | None = None
    if getattr(strategy, "kind", "") == "AI":
        cfg = get_strategy_ai_config(session, strategy.name)
        ai_provider, ai_model = cfg["provider"], cfg["model"]
    return StrategyRead(
        name=strategy.name,
        kind=strategy.kind,
        symbol=strategy.symbol,
        market=strategy.market.value,
        timeframe=strategy.timeframe,
        enabled=is_enabled(session, strategy.name),
        allocated=summary.allocated,
        realized_pnl=summary.realized_pnl,
        unrealized_pnl=summary.unrealized_pnl,
        fees=summary.fees,
        net_pnl=summary.net_pnl,
        open_positions=summary.open_positions,
        ai_provider=ai_provider,
        ai_model=ai_model,
    )


def _find(engine: TradingEngine, name: str) -> BaseStrategy:
    for strategy in engine.strategies:
        if strategy.name == name:
            return strategy
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found")


@router.get("", response_model=list[StrategyRead])
def list_strategies(
    _: CurrentUser, session: SessionDep, engine: TradingDep, streams: StreamsDep
) -> list[StrategyRead]:
    """Every registered strategy with its allocation, state and PnL."""
    marks = _marks(streams)
    return [_read(session, s, marks) for s in engine.strategies]


@router.patch("/{name}/allocation", response_model=StrategyRead)
def update_allocation(
    name: str,
    body: AllocationUpdate,
    user: CurrentUser,
    session: SessionDep,
    engine: TradingDep,
    streams: StreamsDep,
) -> StrategyRead:
    """Set a strategy's capital budget; the engine caps its exposure to it."""
    strategy = _find(engine, name)
    before = get_allocation(session, name)
    set_allocation(session, name, body.allocated)
    record_audit(
        session,
        actor=user.username,
        action="strategy.allocation",
        target=name,
        detail={"from": str(before), "to": str(body.allocated)},
    )
    return _read(session, strategy, _marks(streams))


@router.patch("/{name}/enabled", response_model=StrategyRead)
def update_enabled(
    name: str,
    body: EnabledUpdate,
    user: CurrentUser,
    session: SessionDep,
    engine: TradingDep,
    streams: StreamsDep,
) -> StrategyRead:
    """Enable or disable a strategy. Disabling stops new entries only."""
    strategy = _find(engine, name)
    before = is_enabled(session, name)
    set_enabled(session, name, body.enabled)
    record_audit(
        session,
        actor=user.username,
        action="strategy.enabled",
        target=name,
        detail={"from": before, "to": body.enabled},
    )
    return _read(session, strategy, _marks(streams))


@router.patch("/{name}/ai-model", response_model=StrategyRead)
def update_ai_model(
    name: str,
    body: AiModelUpdate,
    user: CurrentUser,
    session: SessionDep,
    engine: TradingDep,
    streams: StreamsDep,
) -> StrategyRead:
    """Pin an AI strategy to a provider + model (Claude / OpenAI / Gemini / Ollama)."""
    strategy = _find(engine, name)
    if getattr(strategy, "kind", "") != "AI":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "not an AI strategy"
        )
    if body.provider not in LLM_PROVIDERS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"unknown LLM provider — choose one of {sorted(LLM_PROVIDERS)}",
        )
    set_strategy_ai_config(session, name, provider=body.provider, model=body.model)
    record_audit(
        session,
        actor=user.username,
        action="strategy.ai_model",
        target=name,
        detail={"provider": body.provider, "model": body.model},
    )
    return _read(session, strategy, _marks(streams))


@router.post("/{name}/close", response_model=CloseResult)
def close_strategy(
    name: str, user: CurrentUser, session: SessionDep, engine: TradingDep
) -> CloseResult:
    """Close every open position held by the strategy."""
    _find(engine, name)  # 404 if the strategy is unknown
    closed = engine.flatten(name)
    if closed:
        record_audit(
            session,
            actor=user.username,
            action="strategy.close",
            target=name,
            detail={"closed": closed},
        )
    return CloseResult(closed=closed)
