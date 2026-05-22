"""Portfolio API — accounting summary, equity history, positions, trades.

Powers the Dashboard. All endpoints require an authenticated operator.
"""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter
from sqlmodel import select

from ai.usage import spend_since
from api.market import StreamsDep
from auth.deps import CurrentUser, SessionDep
from trading.accounting import (
    CostSummary,
    PortfolioSummary,
    cost_summary,
    equity_history,
    portfolio_summary,
)
from trading.models import EquitySnapshot, Position, Trade
from trading.portfolio import list_positions
from venues.factory import venue_fee_rates

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


class CostsRead(CostSummary):
    """Trading-cost breakdown, the fee-rate reference, and today's LLM spend."""

    venue_fee_rates: dict[str, Decimal]
    llm_spend_today: Decimal  # estimated LLM API spend so far today, in USD


@router.get("/costs", response_model=CostsRead)
def costs(_: CurrentUser, session: SessionDep) -> CostsRead:
    """Cost visibility — trading fees by market, fee rates, and LLM spend."""
    summary = cost_summary(session)
    day_start = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    return CostsRead(
        **summary.model_dump(),
        venue_fee_rates=venue_fee_rates(),
        llm_spend_today=spend_since(session, day_start),
    )
