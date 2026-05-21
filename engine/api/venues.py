"""Venues API — the catalogue of supported trading venues.

Read-only: lists every venue the platform supports and which one the engine
currently trades through. Any authenticated operator may read it.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from auth.deps import CurrentUser
from venues.registry import list_venues

router = APIRouter(prefix="/api/venues", tags=["venues"])


class VenueRead(BaseModel):
    name: str
    asset_class: str
    supports_sandbox: bool
    active: bool


@router.get("", response_model=list[VenueRead])
def get_venues(_: CurrentUser) -> list[VenueRead]:
    """Every supported venue, with its asset class and capabilities."""
    return [
        VenueRead(
            name=v.name,
            asset_class=v.asset_class,
            supports_sandbox=v.supports_sandbox,
            active=v.active,
        )
        for v in list_venues()
    ]
