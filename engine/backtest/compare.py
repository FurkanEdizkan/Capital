"""Strategy Lab comparison — ad-hoc backtest grids over types × symbols.

Each cell of the grid instantiates a registry type (default params unless
overridden), replays it over the shared candle range with `run_backtest`, and
collects the gain/risk metrics the Lab screen ranks by. Candles are
downloaded once per symbol and cached, so re-running a grid is cheap. A cell
that fails (no data, bad params) carries its error instead of aborting the
grid.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session

from backtest.runner import run_backtest
from exchange.client import BinanceClient, Market
from marketdata.cache import download_candles, get_candle_range
from marketdata.models import Candle
from strategies.registry import build_strategy

log = logging.getLogger("capital.backtest.compare")

#: Grid bounds — keep an interactive request interactive.
MAX_SYMBOLS = 8
MAX_TYPES = 6
MAX_DAYS = 365

#: Points kept of each cell's equity curve (sparkline resolution).
_SPARK_POINTS = 40


@dataclass
class CompareCell:
    """One (strategy type × symbol) backtest, ranked by the Lab screen."""

    type: str
    symbol: str
    params: dict
    return_pct: Decimal = Decimal(0)
    max_drawdown_pct: Decimal = Decimal(0)
    sharpe: Decimal = Decimal(0)
    win_rate_pct: Decimal = Decimal(0)
    trades: int = 0
    net_pnl: Decimal = Decimal(0)
    final_equity: Decimal = Decimal(0)
    equity_sparkline: list[float] = field(default_factory=list)
    error: str = ""


def _sparkline(curve: list[tuple[datetime, Decimal]]) -> list[float]:
    """Downsample an equity curve to a fixed-size float sparkline."""
    if not curve:
        return []
    if len(curve) <= _SPARK_POINTS:
        return [float(eq) for _, eq in curve]
    step = (len(curve) - 1) / (_SPARK_POINTS - 1)
    return [float(curve[round(i * step)][1]) for i in range(_SPARK_POINTS)]


def _ensure_candles(
    session: Session,
    client: BinanceClient,
    *,
    symbol: str,
    timeframe: str,
    start: datetime,
) -> list[Candle]:
    """Candles for the range — downloaded once, then served from the cache."""
    try:
        download_candles(
            session,
            client,
            market=Market.spot,
            symbol=symbol,
            interval=timeframe,
            start=start,
        )
    except Exception:  # noqa: BLE001 — cached data may still cover the range
        log.warning("candle download failed for %s — using cache", symbol)
    return get_candle_range(
        session, market=Market.spot, symbol=symbol, interval=timeframe, start=start
    )


def run_cell(
    cell_type: str,
    symbol: str,
    candles: list[Candle],
    *,
    timeframe: str,
    capital: Decimal,
    params: dict | None = None,
) -> CompareCell:
    """Backtest one (type × symbol) cell. Failures land in `cell.error`."""
    cell = CompareCell(type=cell_type, symbol=symbol, params=dict(params or {}))
    if not candles:
        cell.error = "no candle data for the range"
        return cell
    try:
        strategy = build_strategy(
            cell_type,
            name=f"lab:{cell_type}:{symbol}",
            symbol=symbol,
            timeframe=timeframe,
            params=params or {},
        )
        result = run_backtest(strategy, candles, initial_capital=capital)
    except ValueError as exc:
        cell.error = str(exc)
        return cell
    metrics = result.metrics
    if metrics is not None:
        cell.return_pct = metrics.total_return_pct
        cell.max_drawdown_pct = metrics.max_drawdown_pct
        cell.sharpe = metrics.sharpe
        cell.win_rate_pct = metrics.win_rate_pct
        cell.trades = metrics.trades
    cell.net_pnl = result.net_pnl
    cell.final_equity = result.final_equity
    cell.equity_sparkline = _sparkline(result.equity_curve)
    return cell


def compare(
    session: Session,
    client: BinanceClient,
    *,
    types: list[str],
    symbols: list[str],
    timeframe: str = "1h",
    days: int = 90,
    capital: Decimal = Decimal(10000),
) -> list[CompareCell]:
    """Backtest every (type × symbol) cell over the same range.

    Inputs are bounded (`MAX_TYPES` × `MAX_SYMBOLS`, `MAX_DAYS`) by the API
    layer. Candles are fetched once per symbol; cells run sequentially.
    """
    start = datetime.now(UTC) - timedelta(days=days)
    cells: list[CompareCell] = []
    for symbol in symbols:
        candles = _ensure_candles(
            session, client, symbol=symbol, timeframe=timeframe, start=start
        )
        for cell_type in types:
            cells.append(
                run_cell(
                    cell_type,
                    symbol,
                    candles,
                    timeframe=timeframe,
                    capital=capital,
                )
            )
    return cells
