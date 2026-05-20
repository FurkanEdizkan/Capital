"""Backtest API — run a strategy over historical data and return metrics.

Powers the Backtest page. A run downloads (and caches) the candle range,
replays the strategy through the in-memory backtest runner, and returns the
equity curve, trade log and metrics. Any authenticated operator may run a
backtest (see plan: Authentication & Roles).
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.market import ClientDep
from api.strategies import get_trading_engine
from auth.deps import CurrentUser, SessionDep
from backtest.runner import FeeModel, run_backtest
from marketdata.cache import download_candles, get_candle_range
from strategies.base import BaseStrategy
from trading.engine import TradingEngine

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

TradingDep = Annotated[TradingEngine, Depends(get_trading_engine)]


class BacktestRequest(BaseModel):
    strategy: str
    start: datetime
    end: datetime | None = None
    initial_capital: Decimal = Field(default=Decimal("10000"), gt=0)
    slippage_bps: Decimal = Field(default=Decimal("2"), ge=0)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0)
    funding_rate: Decimal = Field(default=Decimal("0"), ge=0)


class EquityPoint(BaseModel):
    time: datetime
    equity: Decimal


class BacktestTradeRead(BaseModel):
    time: datetime
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    realized_pnl: Decimal


class BacktestMetricsRead(BaseModel):
    total_return_pct: Decimal
    win_rate_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe: Decimal
    trades: int
    wins: int
    losses: int


class BacktestResponse(BaseModel):
    strategy: str
    symbol: str
    interval: str
    initial_capital: Decimal
    final_equity: Decimal
    net_pnl: Decimal
    total_fees: Decimal
    candles: int
    equity_curve: list[EquityPoint]
    trades: list[BacktestTradeRead]
    metrics: BacktestMetricsRead


def _find_strategy(engine: TradingEngine, name: str) -> BaseStrategy:
    for strategy in engine.strategies:
        if strategy.name == name:
            return strategy
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found")


@router.post("/run", response_model=BacktestResponse)
def run(
    body: BacktestRequest,
    _: CurrentUser,
    session: SessionDep,
    engine: TradingDep,
    client: ClientDep,
) -> BacktestResponse:
    """Replay a strategy over the requested date range and return the result."""
    strategy = _find_strategy(engine, body.strategy)

    # Download (and cache) the candle range, then read it back oldest-first.
    download_candles(
        session,
        client,
        market=strategy.market,
        symbol=strategy.symbol,
        interval=strategy.timeframe,
        start=body.start,
        end=body.end,
    )
    candles = get_candle_range(
        session,
        market=strategy.market,
        symbol=strategy.symbol,
        interval=strategy.timeframe,
        start=body.start,
        end=body.end,
    )
    if not candles:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No candle data available for the requested range",
        )

    result = run_backtest(
        strategy,
        candles,
        initial_capital=body.initial_capital,
        fees=FeeModel(
            slippage_bps=body.slippage_bps,
            fee_rate=body.fee_rate,
            funding_rate=body.funding_rate,
        ),
    )
    assert result.metrics is not None  # run_backtest always sets metrics

    return BacktestResponse(
        strategy=strategy.name,
        symbol=strategy.symbol,
        interval=strategy.timeframe,
        initial_capital=result.initial_capital,
        final_equity=result.final_equity,
        net_pnl=result.net_pnl,
        total_fees=result.total_fees,
        candles=len(candles),
        equity_curve=[
            EquityPoint(time=t, equity=e) for t, e in result.equity_curve
        ],
        trades=[
            BacktestTradeRead(
                time=t.time,
                side=t.side,
                quantity=t.quantity,
                price=t.price,
                fee=t.fee,
                realized_pnl=t.realized_pnl,
            )
            for t in result.trades
        ],
        metrics=BacktestMetricsRead(
            total_return_pct=result.metrics.total_return_pct,
            win_rate_pct=result.metrics.win_rate_pct,
            max_drawdown_pct=result.metrics.max_drawdown_pct,
            sharpe=result.metrics.sharpe,
            trades=result.metrics.trades,
            wins=result.metrics.wins,
            losses=result.metrics.losses,
        ),
    )
