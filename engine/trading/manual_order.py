"""Manual order placement — the domain unit behind the operator's manual-order
endpoint.

The trading engine places orders automatically from strategy signals. An
operator can also place a one-off order by hand; this module owns that flow as a
single unit (price → risk-check → execute → result) so the API layer only wires
HTTP to it. A manual order is attributed to the reserved `"manual"`
pseudo-strategy and routed through the same risk manager (size cap + daily-loss
kill switch) and executor (Sim / Testnet / Live) as a strategy order.
"""

from decimal import Decimal

from pydantic import BaseModel, Field
from sqlmodel import Session

from trading.executor_router import ExecutorRouter
from trading.executors.base import Fill, Order
from trading.models import FillSide
from trading.portfolio import get_or_create_position
from trading.risk import RiskManager
from trading.venue_router import VenueRouter

#: Manual orders are attributed to this reserved pseudo-strategy.
MANUAL_STRATEGY = "manual"


# Input contract — the order an operator wants placed. (No docstring: it would
# surface into the OpenAPI schema as a description and pull web/ generated types
# into this change.)
class ManualOrderRequest(BaseModel):
    symbol: str = Field(min_length=3, max_length=24)
    side: FillSide
    quantity: Decimal = Field(gt=0)
    market: str = "spot"


class ManualOrderResult(BaseModel):
    """Output contract — the fill plus the bits the caller needs to audit it."""

    fill: Fill
    executed_quantity: Decimal
    mode: str


class OrderBlocked(Exception):
    """The risk manager rejected the order (size cap or kill switch)."""


def submit_manual_order(
    session: Session,
    req: ManualOrderRequest,
    *,
    venues: VenueRouter,
    executor_router: ExecutorRouter,
    risk: RiskManager,
) -> ManualOrderResult:
    """Price, risk-check, execute and report one operator order.

    `session`, `venues`, `executor_router` and `risk` are injected dependencies;
    `req` is the sole data input. Raises `venues.base.VenueError` if the symbol
    cannot be priced, `OrderBlocked` if the risk manager rejects it, and
    `executors.base.ExecutionError` if the executor fails — each a documented
    typed error the caller maps to a response.
    """
    price = venues.resolve(session).price(req.symbol)
    position = get_or_create_position(session, MANUAL_STRATEGY, req.market, req.symbol)
    order = Order(
        strategy=MANUAL_STRATEGY,
        market=req.market,
        symbol=req.symbol,
        side=req.side,
        quantity=req.quantity,
    )
    # Same risk gate as a strategy order — sizing cap + kill switch.
    reviewed = risk.review(session, order, position, price)
    if reviewed is None:
        raise OrderBlocked("order blocked by the risk manager (size cap or kill switch)")

    executor = executor_router.resolve(session)
    fill = executor.execute(session, reviewed, reference_price=price)
    return ManualOrderResult(
        fill=fill, executed_quantity=reviewed.quantity, mode=executor.mode
    )
