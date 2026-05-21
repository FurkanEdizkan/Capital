"""Watchdog — a heartbeat the engine updates on every tick.

If the heartbeat goes stale the tick loop has stalled or the process has
died; `watchdog_status` reports that, and the situation warrants an **alert**
when it happens while positions are open. The heartbeat is persisted in the
`setting` table, so a check after a restart can still tell that the engine
was down while holding risk.
"""

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlmodel import Session

from appsettings.store import get_setting, set_setting
from trading.portfolio import list_positions

_HEARTBEAT_KEY = "engine_heartbeat"
#: Default staleness threshold — three times the default 60s tick interval.
DEFAULT_MAX_AGE_SECONDS = 180.0


class WatchdogStatus(BaseModel):
    """Engine liveness assessed from the heartbeat and open-position count."""

    alive: bool  # heartbeat is fresh
    stale: bool  # heartbeat missing or older than the threshold
    alert: bool  # stale *and* positions are open — needs attention
    last_beat: datetime | None
    age_seconds: float | None
    open_positions: int


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def record_heartbeat(session: Session) -> None:
    """Mark the engine as alive — called at the end of every trading tick."""
    set_setting(session, _HEARTBEAT_KEY, _now().isoformat())


def last_heartbeat(session: Session) -> datetime | None:
    """The timestamp of the most recent heartbeat, or None if never recorded."""
    raw = get_setting(session, _HEARTBEAT_KEY)
    return datetime.fromisoformat(raw) if raw else None


def watchdog_status(
    session: Session, *, max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS
) -> WatchdogStatus:
    """Assess engine liveness from the heartbeat against `max_age_seconds`."""
    beat = last_heartbeat(session)
    open_count = len(list_positions(session, open_only=True))
    if beat is None:
        return WatchdogStatus(
            alive=False,
            stale=True,
            alert=False,
            last_beat=None,
            age_seconds=None,
            open_positions=open_count,
        )
    age = (_now() - beat).total_seconds()
    stale = age > max_age_seconds
    return WatchdogStatus(
        alive=not stale,
        stale=stale,
        alert=stale and open_count > 0,
        last_beat=beat,
        age_seconds=age,
        open_positions=open_count,
    )
