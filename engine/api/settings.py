"""Settings API — trading mode and encrypted Binance credentials.

Admin only. Switching mode is gated: it is blocked while positions are open
(paper and real state must never mix) and switching to **Live** requires an
explicit confirmation flag. See plan: Safety Model.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from appsettings.store import (
    TradingMode,
    binance_keys_configured,
    get_mode,
    set_binance_keys,
    set_mode,
)
from auth.audit import record_audit
from auth.deps import SessionDep, require_admin
from auth.models import User
from trading.portfolio import list_positions

router = APIRouter(prefix="/api/settings", tags=["settings"])

AdminUser = Annotated[User, Depends(require_admin)]


class SettingsRead(BaseModel):
    mode: TradingMode
    binance_keys_configured: bool


class ModeUpdate(BaseModel):
    mode: TradingMode
    confirm: bool = False  # must be true to switch to live trading


class BinanceKeysUpdate(BaseModel):
    api_key: str = Field(min_length=1, max_length=256)
    api_secret: str = Field(min_length=1, max_length=256)


def _read(session: SessionDep) -> SettingsRead:
    return SettingsRead(
        mode=get_mode(session),
        binance_keys_configured=binance_keys_configured(session),
    )


@router.get("", response_model=SettingsRead)
def read_settings(_: AdminUser, session: SessionDep) -> SettingsRead:
    """Current trading mode and whether Binance keys are stored."""
    return _read(session)


@router.put("/mode", response_model=SettingsRead)
def update_mode(
    body: ModeUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Switch the trading mode (Sim / Testnet / Live)."""
    current = get_mode(session)
    if body.mode == current:
        return _read(session)
    # Blocked while positions are open — paper and real state must not mix.
    if list_positions(session, open_only=True):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Close all open positions before switching trading mode",
        )
    if body.mode == TradingMode.live and not body.confirm:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Switching to live trading requires explicit confirmation",
        )
    set_mode(session, body.mode)
    record_audit(
        session,
        actor=admin.username,
        action="settings.mode",
        detail={"from": current.value, "to": body.mode.value},
    )
    return _read(session)


@router.put("/binance-keys", status_code=status.HTTP_204_NO_CONTENT)
def update_binance_keys(
    body: BinanceKeysUpdate, admin: AdminUser, session: SessionDep
) -> None:
    """Store the Binance API credentials (encrypted at rest)."""
    set_binance_keys(session, body.api_key, body.api_secret)
    # The key values themselves are never written to the audit log.
    record_audit(session, actor=admin.username, action="settings.binance_keys")
