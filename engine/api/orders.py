"""Orders API — operator-placed manual orders.

The trading engine places orders automatically from strategy signals. This
endpoint lets an admin place a one-off order by hand — to buy and hold a coin,
or to trim a position — outside any strategy.

The placement logic itself lives in `trading.manual_order`; this module only
wires HTTP to it: authenticate, call the service, map its typed errors to HTTP
status codes, and record the audit entry.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.market import get_venue_router
from auth.audit import record_audit
from auth.deps import SessionDep, require_admin
from auth.models import User
from config import settings
from trading.executor_router import ExecutorRouter
from trading.executors.base import ExecutionError, Fill
from trading.manual_order import ManualOrderRequest, OrderBlocked, submit_manual_order
from trading.risk import RiskManager
from trading.venue_router import VenueRouter
from venues.base import VenueError

router = APIRouter(prefix="/api/orders", tags=["orders"])

AdminUser = Annotated[User, Depends(require_admin)]
VenueRouterDep = Annotated[VenueRouter, Depends(get_venue_router)]


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
        result = submit_manual_order(
            session,
            body,
            venues=venues,
            executor_router=_executor_router(),
            risk=RiskManager.from_settings(settings),
        )
    except VenueError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"could not price {body.symbol}: {exc}"
        ) from exc
    except OrderBlocked as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ExecutionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    record_audit(
        session,
        actor=admin.username,
        action="order.manual",
        detail={
            "symbol": body.symbol,
            "side": body.side.value,
            "quantity": str(result.executed_quantity),
            "mode": result.mode,
        },
    )
    return result.fill
