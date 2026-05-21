"""Venues API — the supported-venue catalogue and the active venue.

`GET` lists every venue and marks the active one. `PUT /active` changes the
active venue (admin only) — blocked while positions are open, the same guard
as a trading-mode switch.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from appsettings.store import (
    TradingMode,
    get_active_venue,
    get_mode,
    set_active_venue,
)
from auth.audit import record_audit
from auth.deps import CurrentUser, SessionDep, require_admin
from auth.models import User
from trading.portfolio import list_positions
from venues.registry import VENUE_NAMES, get_venue, list_venues

router = APIRouter(prefix="/api/venues", tags=["venues"])

AdminUser = Annotated[User, Depends(require_admin)]


class VenueRead(BaseModel):
    name: str
    asset_class: str
    supports_sandbox: bool
    active: bool
    #: Credential field names the venue needs to place orders — drives the
    #: per-venue credential form on the Settings page.
    credential_fields: list[str]


class ActiveVenueUpdate(BaseModel):
    venue: str


def _read(session: SessionDep) -> list[VenueRead]:
    active = get_active_venue(session)
    return [
        VenueRead(
            name=v.name,
            asset_class=v.asset_class,
            supports_sandbox=v.supports_sandbox,
            active=v.name == active,
            credential_fields=list(v.credential_fields),
        )
        for v in list_venues()
    ]


@router.get("", response_model=list[VenueRead])
def get_venues(_: CurrentUser, session: SessionDep) -> list[VenueRead]:
    """Every supported venue, with the active one flagged."""
    return _read(session)


@router.put("/active", response_model=list[VenueRead])
def set_active(
    body: ActiveVenueUpdate, admin: AdminUser, session: SessionDep
) -> list[VenueRead]:
    """Change the active trading venue."""
    if body.venue not in VENUE_NAMES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown venue: {body.venue}")
    current = get_active_venue(session)
    if body.venue != current and list_positions(session, open_only=True):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Close all open positions before switching venue",
        )
    # A venue with no sandbox cannot be used in Testnet mode.
    info = get_venue(body.venue)
    if (
        get_mode(session) is TradingMode.testnet
        and info is not None
        and not info.supports_sandbox
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{body.venue} has no testnet — switch to Sim or Live before "
            "selecting it",
        )
    set_active_venue(session, body.venue)
    record_audit(
        session,
        actor=admin.username,
        action="venue.active",
        detail={"from": current, "to": body.venue},
    )
    return _read(session)
