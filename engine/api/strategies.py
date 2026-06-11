"""Strategy management API — list, allocate, enable/disable, close.

Powers the Strategies page. Strategies are code-defined (built-in or plugin);
these endpoints manage each strategy's capital allocation, lifecycle state and
open positions. Any authenticated operator may use them — see plan:
Authentication & Roles (managing strategies is allowed for both roles).
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import select

from api.market import StreamsDep
from appsettings.store import LLM_PROVIDERS, set_strategy_ai_config
from auth.audit import record_audit
from auth.deps import CurrentUser, SessionDep
from strategies.ai_strategy import AIStrategy
from strategies.base import BaseStrategy
from strategies.builtin import all_strategies_with_instances
from strategies.models import StrategyInstance
from strategies.registry import STRATEGY_TYPES, TIMEFRAMES, build_strategy, coerce_params
from trading.engine import TradingEngine
from trading.lifecycle import is_enabled, set_enabled
from trading.portfolio import (
    get_allocation,
    list_positions,
    set_allocation,
    set_max_loss,
)
from trading.strategy_view import StrategyRead, read_strategy_state

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


def get_trading_engine(request: Request) -> TradingEngine:
    """The trading engine created in the app lifespan."""
    return request.app.state.trading


TradingDep = Annotated[TradingEngine, Depends(get_trading_engine)]


class AllocationUpdate(BaseModel):
    allocated: Decimal = Field(ge=0)
    # Loss cap in quote currency; 0 disables. Omitted = left unchanged.
    max_loss: Decimal | None = Field(default=None, ge=0)


class EnabledUpdate(BaseModel):
    enabled: bool


class AiModelUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=16)
    model: str = Field(default="", max_length=64)


class CloseResult(BaseModel):
    closed: int


class ParamSpecRead(BaseModel):
    name: str
    type: str
    default: str
    min: str
    max: str
    label: str


class StrategyTypeRead(BaseModel):
    """One pickable strategy type and its parameter schema."""

    key: str
    label: str
    params: list[ParamSpecRead]
    timeframes: list[str]
    # The venue the type is pinned to, or null when the operator picks.
    venue: str | None = None


class InstanceCreate(BaseModel):
    """Apply a strategy type to a coin as a new named instance."""

    name: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=32)
    symbol: str = Field(min_length=1, max_length=80)
    venue: str = Field(default="binance", max_length=24)
    market: str = Field(default="spot", pattern="^(spot|futures)$")
    timeframe: str = Field(default="1h", max_length=8)
    params: dict[str, str] = Field(default_factory=dict)
    allocated: Decimal = Field(default=Decimal(10000), ge=0)
    max_loss: Decimal = Field(default=Decimal(0), ge=0)


def _marks(streams: object) -> dict[str, Decimal]:
    """Build {symbol: price} from the live ticker snapshots."""
    marks: dict[str, Decimal] = {}
    for hub in (streams.spot, streams.futures):  # type: ignore[attr-defined]
        for ticker in hub.snapshot():
            marks[ticker.symbol] = ticker.price
    return marks


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
    return [read_strategy_state(session, s, marks) for s in engine.strategies]


@router.get("/types", response_model=list[StrategyTypeRead])
def list_strategy_types(_: CurrentUser) -> list[StrategyTypeRead]:
    """Every pickable strategy type with its typed parameter schema."""
    return [
        StrategyTypeRead(
            key=t.key,
            label=t.label,
            params=[
                ParamSpecRead(
                    name=p.name,
                    type=p.type,
                    default=p.default,
                    min=p.min,
                    max=p.max,
                    label=p.label,
                )
                for p in t.params
            ],
            timeframes=list(TIMEFRAMES),
            venue=t.venue,
        )
        for t in STRATEGY_TYPES.values()
    ]


@router.post("", response_model=StrategyRead, status_code=status.HTTP_201_CREATED)
def create_instance(
    body: InstanceCreate,
    user: CurrentUser,
    session: SessionDep,
    engine: TradingDep,
    streams: StreamsDep,
) -> StrategyRead:
    """Create a strategy instance: any registered type on any chosen coin."""
    name = body.name.strip()
    if any(s.name == name for s in engine.strategies):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"strategy name {name!r} is already in use"
        )
    try:
        # Build first — params, venue and timeframe are validated by the registry.
        built = build_strategy(
            body.type,
            name=name,
            symbol=body.symbol,
            venue=body.venue,
            market=body.market,
            timeframe=body.timeframe,
            params=dict(body.params),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    row = StrategyInstance(
        name=name,
        type=body.type,
        symbol=built.symbol,
        venue=built.venue,  # the registry may pin a type to one venue
        market=body.market,
        timeframe=body.timeframe,
        params=json.dumps(coerce_params(body.type, dict(body.params)), default=str),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(row)
    session.commit()
    set_allocation(session, name, body.allocated)
    if body.max_loss > 0:
        set_max_loss(session, name, body.max_loss)
    engine.replace_strategies(all_strategies_with_instances(session))
    record_audit(
        session,
        actor=user.username,
        action="strategy.create",
        target=name,
        detail={"type": body.type, "symbol": built.symbol, "venue": built.venue},
    )
    strategy = _find(engine, name)
    return read_strategy_state(session, strategy, _marks(streams))


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(
    name: str,
    user: CurrentUser,
    session: SessionDep,
    engine: TradingDep,
) -> None:
    """Delete an instance-backed strategy. Built-ins cannot be deleted.

    Refused while the strategy holds an open position — close it first.
    """
    row = session.exec(
        select(StrategyInstance).where(StrategyInstance.name == name)
    ).first()
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "not an instance-backed strategy (built-ins cannot be deleted)",
        )
    if list_positions(session, strategy=name, open_only=True):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "close the strategy's open positions before deleting it",
        )
    session.delete(row)
    session.commit()
    engine.replace_strategies(all_strategies_with_instances(session))
    record_audit(session, actor=user.username, action="strategy.delete", target=name)


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
    detail = {"from": str(before), "to": str(body.allocated)}
    if body.max_loss is not None:
        set_max_loss(session, name, body.max_loss)
        detail["max_loss"] = str(body.max_loss)
    record_audit(
        session,
        actor=user.username,
        action="strategy.allocation",
        target=name,
        detail=detail,
    )
    return read_strategy_state(session, strategy, _marks(streams))


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
    return read_strategy_state(session, strategy, _marks(streams))


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
    if not isinstance(strategy, AIStrategy):
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
    return read_strategy_state(session, strategy, _marks(streams))


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
