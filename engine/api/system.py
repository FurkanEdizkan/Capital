"""System status API — the engine watchdog/heartbeat.

Lets the dashboard (and external monitors) see whether the trading loop is
still ticking. See plan: Phase 6 / watchdog.
"""

from fastapi import APIRouter

from auth.deps import CurrentUser, SessionDep
from ops.watchdog import WatchdogStatus, watchdog_status

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/watchdog", response_model=WatchdogStatus)
def get_watchdog(_: CurrentUser, session: SessionDep) -> WatchdogStatus:
    """Engine liveness — heartbeat age and whether an alert is warranted."""
    return watchdog_status(session)
