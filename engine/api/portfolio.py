"""Portfolio API — accounting summary, equity history, positions, trades.

Powers the Dashboard. All endpoints require an authenticated operator.
"""

from decimal import Decimal

from fastapi import APIRouter
from sqlmodel import select

from api.market import StreamsDep
from auth.deps import CurrentUser, SessionDep
from trading.accounting import PortfolioSummary, equity_history, portfolio_summary
from trading.models import EquitySnapshot, Position, Trade
from trading.portfolio import list_positions

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _mark_prices(streams: object) -> dict[str, Decimal]:
    """Build {symbol: price} from the live ticker snapshots."""
    marks: dict[str, Decimal] = {}
    for hub in (streams.spot, streams.futures):  # type: ignore[attr-defined]
        for ticker in hub.snapshot():
            marks[ticker.symbol] = ticker.price
    return marks


@router.get("/summary", response_model=PortfolioSummary)
def summary(_: CurrentUser, session: SessionDep, streams: StreamsDep) -> PortfolioSummary:
    """Aggregate accounting — equity, PnL, fees, allocated vs idle capital."""
    return portfolio_summary(session, _mark_prices(streams))


@router.get("/equity", response_model=list[EquitySnapshot])
def equity(_: CurrentUser, session: SessionDep) -> list[EquitySnapshot]:
    """Equity-curve history, oldest-first."""
    return equity_history(session)


@router.get("/positions", response_model=list[Position])
def positions(_: CurrentUser, session: SessionDep) -> list[Position]:
    """Currently open positions across all strategies."""
    return list_positions(session, open_only=True)


@router.get("/trades", response_model=list[Trade])
def trades(_: CurrentUser, session: SessionDep, limit: int = 50) -> list[Trade]:
    """Most-recent executed trades."""
    rows = session.exec(
        select(Trade).order_by(Trade.executed_at.desc()).limit(limit)  # type: ignore[attr-defined]
    ).all()
    return list(rows)
