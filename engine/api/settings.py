"""Settings API — trading mode and encrypted Binance credentials.

Admin only. Switching mode is gated: it is blocked while positions are open
(paper and real state must never mix) and switching to **Live** requires an
explicit confirmation flag. See plan: Safety Model.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ai.usage import spend_since
from appsettings.store import (
    AI_ACTION_MODES,
    LLM_PROVIDERS,
    TradingMode,
    ai_key_configured,
    binance_keys_configured,
    get_active_venue,
    get_ai_action_mode,
    get_ai_settings,
    get_ai_spend_cap,
    get_mode,
    llm_provider_configured,
    set_ai_action_mode,
    set_ai_settings,
    set_ai_spend_cap,
    set_binance_keys,
    set_llm_credentials,
    set_mode,
    set_venue_credentials,
    venue_credentials_configured,
)
from auth.audit import record_audit
from auth.deps import SessionDep, require_admin
from auth.models import User
from trading.portfolio import list_positions
from venues.registry import AVAILABLE_VENUES, get_venue

router = APIRouter(prefix="/api/settings", tags=["settings"])

AdminUser = Annotated[User, Depends(require_admin)]


def _day_start() -> datetime:
    """Start of the current UTC day, tz-naive (matches stored timestamps)."""
    return datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )


class SettingsRead(BaseModel):
    mode: TradingMode
    binance_keys_configured: bool
    # Per-venue: whether every declared credential field is stored.
    venue_credentials_configured: dict[str, bool]
    ai_provider: str
    ai_model: str
    ai_base_url: str
    ai_key_configured: bool
    ai_spend_cap: Decimal  # daily LLM spend cap in USD (0 = unlimited)
    ai_spend_today: Decimal  # LLM spend so far today, in USD
    # How AI decisions are applied globally: `notify` (default) or `auto`.
    ai_action_mode: str
    # Per-LLM-provider: whether it is usable (Ollama always; others need a key).
    llm_providers_configured: dict[str, bool]


class VenueCredentialsUpdate(BaseModel):
    """A venue's credential fields — names validated against the catalogue."""

    fields: dict[str, str] = Field(min_length=1)


class ModeUpdate(BaseModel):
    mode: TradingMode
    confirm: bool = False  # must be true to switch to live trading


class BinanceKeysUpdate(BaseModel):
    api_key: str = Field(min_length=1, max_length=256)
    api_secret: str = Field(min_length=1, max_length=256)


class AiSpendCapUpdate(BaseModel):
    cap: Decimal = Field(ge=0)  # daily LLM spend cap in USD; 0 = unlimited


class LlmCredentialsUpdate(BaseModel):
    """One LLM provider's credentials — both fields optional."""

    api_key: str = Field(default="", max_length=256)
    base_url: str = Field(default="", max_length=256)


class AiSettingsUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=32)
    model: str = Field(default="", max_length=64)
    base_url: str = Field(default="", max_length=256)
    # Optional — the stored key is kept when this is omitted/blank.
    api_key: str = Field(default="", max_length=256)


class AiActionModeUpdate(BaseModel):
    mode: str = Field(description="notify | auto")


def _read(session: SessionDep) -> SettingsRead:
    ai = get_ai_settings(session)
    return SettingsRead(
        mode=get_mode(session),
        binance_keys_configured=binance_keys_configured(session),
        venue_credentials_configured={
            v.name: venue_credentials_configured(session, v.name, v.credential_fields)
            for v in AVAILABLE_VENUES
        },
        ai_provider=ai["provider"],
        ai_model=ai["model"],
        ai_base_url=ai["base_url"],
        ai_key_configured=ai_key_configured(session),
        ai_spend_cap=get_ai_spend_cap(session),
        ai_spend_today=spend_since(session, _day_start()),
        ai_action_mode=get_ai_action_mode(session),
        llm_providers_configured={
            p: llm_provider_configured(session, p) for p in LLM_PROVIDERS
        },
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
    # The active venue must have a sandbox to enter Testnet mode.
    if body.mode is TradingMode.testnet:
        venue = get_venue(get_active_venue(session))
        if venue is not None and not venue.supports_sandbox:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"the active venue ({venue.name}) has no testnet — "
                "use Sim or Live",
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


@router.put("/venue-credentials/{venue}", status_code=status.HTTP_204_NO_CONTENT)
def update_venue_credentials(
    venue: str,
    body: VenueCredentialsUpdate,
    admin: AdminUser,
    session: SessionDep,
) -> None:
    """Store a venue's credentials (encrypted at rest).

    The submitted field names must exactly match the venue's declared
    `credential_fields`, and every value must be non-empty.
    """
    info = get_venue(venue)
    if info is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown venue {venue!r}")
    if set(body.fields) != set(info.credential_fields):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{venue} expects exactly these credential fields: "
            f"{sorted(info.credential_fields)}",
        )
    if any(not value.strip() for value in body.fields.values()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "credential values must not be empty"
        )
    set_venue_credentials(session, venue, body.fields)
    # Only the venue name is audited — never the credential values.
    record_audit(
        session,
        actor=admin.username,
        action="settings.venue_credentials",
        detail={"venue": venue},
    )


@router.put("/llm-credentials/{provider}", response_model=SettingsRead)
def update_llm_credentials(
    provider: str,
    body: LlmCredentialsUpdate,
    admin: AdminUser,
    session: SessionDep,
) -> SettingsRead:
    """Store one LLM provider's API key and/or base URL (encrypted at rest)."""
    if provider not in LLM_PROVIDERS:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"unknown LLM provider {provider!r}"
        )
    set_llm_credentials(
        session,
        provider,
        api_key=body.api_key or None,
        base_url=body.base_url if body.base_url else None,
    )
    # The key value itself is never written to the audit log.
    record_audit(
        session,
        actor=admin.username,
        action="settings.llm_credentials",
        detail={"provider": provider},
    )
    return _read(session)


@router.put("/ai-spend-cap", response_model=SettingsRead)
def update_ai_spend_cap(
    body: AiSpendCapUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Set the daily LLM spend cap — AI strategies pause once it is reached."""
    set_ai_spend_cap(session, body.cap)
    record_audit(
        session,
        actor=admin.username,
        action="settings.ai_spend_cap",
        detail={"cap": str(body.cap)},
    )
    return _read(session)


@router.put("/ai", response_model=SettingsRead)
def update_ai_settings(
    body: AiSettingsUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Configure the AI provider. The API key is encrypted at rest."""
    set_ai_settings(
        session,
        provider=body.provider,
        model=body.model,
        base_url=body.base_url,
        api_key=body.api_key or None,
    )
    record_audit(
        session,
        actor=admin.username,
        action="settings.ai",
        detail={"provider": body.provider, "model": body.model},
    )
    return _read(session)


@router.put("/ai-action-mode", response_model=SettingsRead)
def update_ai_action_mode(
    body: AiActionModeUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Set how AI decisions are applied: `notify` (confirm) or `auto`."""
    if body.mode not in AI_ACTION_MODES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"mode must be one of {list(AI_ACTION_MODES)}",
        )
    set_ai_action_mode(session, body.mode)
    record_audit(
        session,
        actor=admin.username,
        action="settings.ai_action_mode",
        detail={"mode": body.mode},
    )
    return _read(session)
