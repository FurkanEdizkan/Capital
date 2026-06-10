"""Strategy Lab API — gain/risk comparison grids and an AI recommendation.

`compare` powers both Lab pivots: pick a strategy type to rank coins, or pick
a coin to rank every type — the grid is the same shape either way. `recommend`
asks the configured LLM to pick (and parameterise) a strategy for a coin, then
backtests that exact configuration over the same range so it ranks alongside
the standard cells.
"""

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from ai.providers import LLMError
from ai.usage import cap_reached, record_usage
from api.ai import ProviderDep
from api.market import ClientDep
from appsettings.store import get_ai_settings
from auth.deps import CurrentUser, SessionDep
from backtest.compare import (
    MAX_DAYS,
    MAX_SYMBOLS,
    MAX_TYPES,
    CompareCell,
    _ensure_candles,
    compare,
    run_cell,
)
from research.models import ResearchReport
from strategies.registry import STRATEGY_TYPES, TIMEFRAMES

log = logging.getLogger("capital.api.lab")

router = APIRouter(prefix="/api/lab", tags=["lab"])

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class CompareRequest(BaseModel):
    """A grid request — either pivot is just a different shape of the same."""

    types: list[str] = Field(default_factory=list, max_length=MAX_TYPES)
    symbols: list[str] = Field(min_length=1, max_length=MAX_SYMBOLS)
    timeframe: str = Field(default="1h", max_length=8)
    days: int = Field(default=90, ge=7, le=MAX_DAYS)
    capital: Decimal = Field(default=Decimal(10000), gt=0)


class CompareCellRead(BaseModel):
    type: str
    symbol: str
    params: dict
    return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe: Decimal
    win_rate_pct: Decimal
    trades: int
    net_pnl: Decimal
    final_equity: Decimal
    equity_sparkline: list[float]
    error: str

    @classmethod
    def from_cell(cls, c: CompareCell) -> "CompareCellRead":
        return cls(**c.__dict__)


class RecommendRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    timeframe: str = Field(default="1h", max_length=8)
    days: int = Field(default=90, ge=7, le=MAX_DAYS)
    capital: Decimal = Field(default=Decimal(10000), gt=0)


class RecommendResponse(BaseModel):
    """The AI's pick, backtested so it ranks alongside the grid cells."""

    strategy_type: str
    params: dict
    reasoning: str
    cell: CompareCellRead


def _validated_types(types: list[str]) -> list[str]:
    chosen = types or list(STRATEGY_TYPES)
    unknown = [t for t in chosen if t not in STRATEGY_TYPES]
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"unknown strategy types: {unknown}"
        )
    return chosen


def _validated_timeframe(timeframe: str) -> str:
    if timeframe not in TIMEFRAMES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"timeframe must be one of {list(TIMEFRAMES)}",
        )
    return timeframe


@router.post("/compare", response_model=list[CompareCellRead])
def compare_grid(
    body: CompareRequest,
    _: CurrentUser,
    session: SessionDep,
    client: ClientDep,
) -> list[CompareCellRead]:
    """Backtest every (type × symbol) cell over the same recent range."""
    cells = compare(
        session,
        client,
        types=_validated_types(body.types),
        symbols=[s.upper() for s in body.symbols],
        timeframe=_validated_timeframe(body.timeframe),
        days=body.days,
        capital=body.capital,
    )
    return [CompareCellRead.from_cell(c) for c in cells]


def _recommend_prompt(session: SessionDep, symbol: str) -> str:
    """The recommendation task: pick a type + params for `symbol`."""
    schema = {
        key: {p.name: f"{p.type} {p.min}..{p.max} (default {p.default})" for p in t.params}
        for key, t in STRATEGY_TYPES.items()
    }
    parts = [
        f"Choose the best-suited trading strategy for {symbol} from these"
        f" types and parameter ranges: {json.dumps(schema)}.",
    ]
    report = session.exec(
        select(ResearchReport)
        .where(ResearchReport.symbol == symbol, ResearchReport.status != "failed")
        .order_by(ResearchReport.created_at.desc())  # type: ignore[attr-defined]
        .limit(1)
    ).first()
    if report is not None:
        summary = report.sections_dict().get("summary", "")
        if summary:
            parts.append(f"Latest research summary for {symbol}: {summary}")
    parts.append(
        'Respond ONLY with a JSON object of the form {"strategy_type": "<key>",'
        ' "params": {…}, "reasoning": "<text>"}.'
    )
    return "\n".join(parts)


@router.post("/recommend", response_model=RecommendResponse)
def recommend(
    body: RecommendRequest,
    _: CurrentUser,
    session: SessionDep,
    client: ClientDep,
    provider: ProviderDep,
) -> RecommendResponse:
    """Ask the configured LLM to pick a strategy for the coin, then backtest it."""
    if cap_reached(session):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "daily AI spend cap reached — try tomorrow"
        )
    symbol = body.symbol.upper()
    timeframe = _validated_timeframe(body.timeframe)
    model = get_ai_settings(session)["model"] or None
    try:
        completion = provider.complete(_recommend_prompt(session, symbol), model=model)
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"AI recommendation failed: {exc}"
        ) from exc
    record_usage(
        session,
        provider=completion.provider,
        model=completion.model,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
    )
    match = _JSON_RE.search(completion.text)
    if not match:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "AI response carried no JSON recommendation"
        )
    try:
        raw = json.loads(match.group(0))
        strategy_type = str(raw["strategy_type"])
        params = raw.get("params") or {}
        reasoning = str(raw.get("reasoning", ""))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "AI recommendation was not parseable"
        ) from exc
    if strategy_type not in STRATEGY_TYPES:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"AI recommended an unknown strategy type: {strategy_type!r}",
        )
    start = datetime.now(UTC) - timedelta(days=body.days)
    candles = _ensure_candles(
        session, client, symbol=symbol, timeframe=timeframe, start=start
    )
    cell = run_cell(
        strategy_type,
        symbol,
        candles,
        timeframe=timeframe,
        capital=body.capital,
        params={k: str(v) for k, v in dict(params).items()},
    )
    return RecommendResponse(
        strategy_type=strategy_type,
        params=cell.params,
        reasoning=reasoning,
        cell=CompareCellRead.from_cell(cell),
    )
