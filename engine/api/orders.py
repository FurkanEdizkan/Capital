"""Orders API — operator-placed manual orders.

The trading engine places orders automatically from strategy signals. This
endpoint lets an admin place a one-off order by hand — to buy and hold a coin,
or to trim a position — outside any strategy.

A manual order is attributed to the reserved `"manual"` pseudo-strategy so the
sub-ledger keeps it separate from strategy positions. It is routed through the
same executor (Sim / Testnet / Live) and the same risk manager (position-size
cap + daily-loss kill switch) as a strategy order — the operator cannot bypass
the kill switch. It is *not* subject to per-strategy capital allocation, which
partitions budget among strategies and does not apply to a direct action.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.market import get_venue_router
from auth.audit import record_audit
from auth.deps import SessionDep, require_admin
from auth.models import User
from config import settings
from trading.executor_router import ExecutorRouter
from trading.executors.base import ExecutionError, Fill, Order
from trading.models import FillSide
from trading.portfolio import get_or_create_position
from trading.risk import RiskManager
from trading.venue_router import VenueRouter
from venues.base import VenueError

router = APIRouter(prefix="/api/orders", tags=["orders"])

AdminUser = Annotated[User, Depends(require_admin)]
VenueRouterDep = Annotated[VenueRouter, Depends(get_venue_router)]

#: Manual orders are attributed to this reserved pseudo-strategy.
MANUAL_STRATEGY = "manual"


class ManualOrderRequest(BaseModel):
    symbol: str = Field(min_length=3, max_length=24)
    side: FillSide
    quantity: Decimal = Field(gt=0)
    market: str = "spot"


def _executor_router() -> ExecutorRouter:
    """Overridable in tests; a fresh router resolves Sim/Testnet/Live per call."""
    return ExecutorRouter()


@router.post("/manual", response_model=Fill)
def place_manual_order(
    body: ManualOrderRequest,
    admin: AdminUser,
    session: SessionDep,
    venues: VenueRouterDep,
) -> Fill:
    """Place a one-off order, risk-checked and recorded as `manual`."""
    try:
        price = venues.resolve(session).price(body.symbol)
    except VenueError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"could not price {body.symbol}: {exc}"
        ) from exc

    position = get_or_create_position(
        session, MANUAL_STRATEGY, body.market, body.symbol
    )
    order = Order(
        strategy=MANUAL_STRATEGY,
        market=body.market,
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
    )
    # Same risk gate as a strategy order — sizing cap + kill switch.
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
        fill = executor.execute(session, reviewed, reference_price=price)
    except ExecutionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    record_audit(
        session,
        actor=admin.username,
        action="order.manual",
        detail={
            "symbol": body.symbol,
            "side": body.side.value,
            "quantity": str(reviewed.quantity),
            "mode": executor.mode,
        },
    )
    return fill
