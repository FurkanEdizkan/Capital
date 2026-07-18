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

from ai.council import (
    get_council_members,
    get_council_quorum,
    set_council_members,
    set_council_quorum,
)
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
    get_news_interval_hours,
    get_polymarket_edge_threshold,
    get_polymarket_min_confidence,
    get_polymarket_refresh_hours,
    get_polymarket_research_hours,
    get_polymarket_screen_top,
    get_polymarket_stake,
    get_research_interval_hours,
    get_research_symbols,
    get_research_writer,
    get_risk_daily_loss_limit,
    get_risk_max_drawdown_pct,
    get_risk_max_position_notional,
    get_risk_stop_loss_pct,
    get_risk_take_profit_pct,
    llm_provider_configured,
    set_ai_action_mode,
    set_ai_settings,
    set_ai_spend_cap,
    set_binance_keys,
    set_llm_credentials,
    set_mode,
    set_news_interval_hours,
    set_polymarket_edge_threshold,
    set_polymarket_min_confidence,
    set_polymarket_refresh_hours,
    set_polymarket_research_hours,
    set_polymarket_screen_top,
    set_polymarket_stake,
    set_research_interval_hours,
    set_research_symbols,
    set_research_writer,
    set_risk_daily_loss_limit,
    set_risk_max_drawdown_pct,
    set_risk_max_position_notional,
    set_risk_stop_loss_pct,
    set_risk_take_profit_pct,
    set_venue_credentials,
    venue_credentials_configured,
)
from auth.audit import record_audit
from auth.deps import SessionDep, require_admin
from auth.models import User
from config import settings as _env_settings
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
    # Research reports: watched symbols, cycle interval and the writer LLM.
    research_symbols: list[str]
    research_interval_hours: int
    research_writer_provider: str
    research_writer_model: str
    # News refresh interval in hours; null keeps the default daily schedule.
    news_interval_hours: int | None
    # AI council: the models that vote on each report, and the quorum a
    # verdict must reach. An empty member list disables the council.
    council_members: list[dict[str, str]]
    council_quorum: Decimal
    # Polymarket: catalogue refresh + AI screening cadence, and the edge /
    # confidence bar a screener suggestion must clear.
    polymarket_refresh_hours: int
    polymarket_research_hours: int
    polymarket_edge_threshold: Decimal
    polymarket_min_confidence: Decimal
    polymarket_screen_top: int
    polymarket_stake: Decimal
    # Global risk limits (0 = disabled). Enforced by trading/risk.py each tick.
    risk_stop_loss_pct: Decimal
    risk_take_profit_pct: Decimal
    risk_max_drawdown_pct: Decimal
    risk_daily_loss_limit: Decimal
    risk_max_position_notional: Decimal


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


class CouncilMember(BaseModel):
    provider: str = Field(min_length=1, max_length=32)
    model: str = Field(default="", max_length=64)


class CouncilSettingsUpdate(BaseModel):
    """Council configuration — an empty member list disables the council."""

    members: list[CouncilMember] = Field(max_length=8)
    quorum: Decimal = Field(default=Decimal("0.5"), gt=0, le=1)


class ResearchSettingsUpdate(BaseModel):
    """Research configuration — watched symbols, interval and writer LLM."""

    symbols: list[str] = Field(min_length=1, max_length=20)
    interval_hours: int = Field(default=12, ge=1, le=168)
    writer_provider: str = Field(min_length=1, max_length=32)
    writer_model: str = Field(default="", max_length=64)
    # None keeps the default daily news schedule.
    news_interval_hours: int | None = Field(default=None, ge=1, le=48)


class PolymarketSettingsUpdate(BaseModel):
    """Polymarket configuration — discovery/screening cadence and bars."""

    refresh_hours: int = Field(default=6, ge=1, le=48)
    research_hours: int = Field(default=6, ge=1, le=168)
    edge_threshold: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
    min_confidence: Decimal = Field(default=Decimal("0.6"), ge=0, le=1)
    screen_top: int = Field(default=10, ge=0, le=50)
    stake: Decimal = Field(default=Decimal("100"), gt=0)


class RiskSettingsUpdate(BaseModel):
    """Global risk limits in percent (SL/TP/drawdown) or quote currency
    (loss limit, notional). 0 disables a limit."""

    stop_loss_pct: Decimal = Field(ge=0, le=100)
    take_profit_pct: Decimal = Field(ge=0, le=100)
    max_drawdown_pct: Decimal = Field(ge=0, le=100)
    daily_loss_limit: Decimal = Field(ge=0)
    max_position_notional: Decimal = Field(ge=0)


def _read(session: SessionDep) -> SettingsRead:
    ai = get_ai_settings(session)
    writer = get_research_writer(session)
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
        research_symbols=get_research_symbols(session),
        research_interval_hours=get_research_interval_hours(session),
        research_writer_provider=writer["provider"],
        research_writer_model=writer["model"],
        news_interval_hours=get_news_interval_hours(session),
        council_members=get_council_members(session),
        council_quorum=get_council_quorum(session),
        polymarket_refresh_hours=get_polymarket_refresh_hours(session),
        polymarket_research_hours=get_polymarket_research_hours(session),
        polymarket_edge_threshold=get_polymarket_edge_threshold(session),
        polymarket_min_confidence=get_polymarket_min_confidence(session),
        polymarket_screen_top=get_polymarket_screen_top(session),
        polymarket_stake=get_polymarket_stake(session),
        risk_stop_loss_pct=get_risk_stop_loss_pct(
            session, _env_settings.risk_stop_loss_pct
        ),
        risk_take_profit_pct=get_risk_take_profit_pct(
            session, _env_settings.risk_take_profit_pct
        ),
        risk_max_drawdown_pct=get_risk_max_drawdown_pct(
            session, _env_settings.risk_max_drawdown_pct
        ),
        risk_daily_loss_limit=get_risk_daily_loss_limit(
            session, _env_settings.risk_daily_loss_limit
        ),
        risk_max_position_notional=get_risk_max_position_notional(
            session, _env_settings.risk_max_position_notional
        ),
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


@router.put("/research", response_model=SettingsRead)
def update_research_settings(
    body: ResearchSettingsUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Configure research reports and the news refresh interval.

    Scheduler-interval changes take effect on the next engine restart.
    """
    if body.writer_provider not in LLM_PROVIDERS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"writer_provider must be one of {list(LLM_PROVIDERS)}",
        )
    symbols = [s.strip().upper() for s in body.symbols if s.strip()]
    if not symbols:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "at least one symbol is required"
        )
    set_research_symbols(session, symbols)
    set_research_interval_hours(session, body.interval_hours)
    set_research_writer(
        session, provider=body.writer_provider, model=body.writer_model
    )
    set_news_interval_hours(session, body.news_interval_hours)
    record_audit(
        session,
        actor=admin.username,
        action="settings.research",
        detail={
            "symbols": symbols,
            "interval_hours": body.interval_hours,
            "writer": f"{body.writer_provider}:{body.writer_model}",
        },
    )
    return _read(session)


@router.put("/polymarket", response_model=SettingsRead)
def update_polymarket_settings(
    body: PolymarketSettingsUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Configure Polymarket discovery and AI bet screening.

    Scheduler-interval changes take effect on the next engine restart.
    """
    set_polymarket_refresh_hours(session, body.refresh_hours)
    set_polymarket_research_hours(session, body.research_hours)
    set_polymarket_edge_threshold(session, body.edge_threshold)
    set_polymarket_min_confidence(session, body.min_confidence)
    set_polymarket_screen_top(session, body.screen_top)
    set_polymarket_stake(session, body.stake)
    record_audit(
        session,
        actor=admin.username,
        action="settings.polymarket",
        detail={
            "refresh_hours": body.refresh_hours,
            "research_hours": body.research_hours,
            "edge_threshold": str(body.edge_threshold),
            "min_confidence": str(body.min_confidence),
            "screen_top": body.screen_top,
            "stake": str(body.stake),
        },
    )
    return _read(session)


@router.put("/risk", response_model=SettingsRead)
def update_risk_settings(
    body: RiskSettingsUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Set the global risk limits (0 disables a limit).

    Changes apply on the next engine tick — a stop-loss you enable may
    immediately close an already-losing position.
    """
    set_risk_stop_loss_pct(session, body.stop_loss_pct)
    set_risk_take_profit_pct(session, body.take_profit_pct)
    set_risk_max_drawdown_pct(session, body.max_drawdown_pct)
    set_risk_daily_loss_limit(session, body.daily_loss_limit)
    set_risk_max_position_notional(session, body.max_position_notional)
    record_audit(
        session,
        actor=admin.username,
        action="settings.risk",
        detail={
            "stop_loss_pct": str(body.stop_loss_pct),
            "take_profit_pct": str(body.take_profit_pct),
            "max_drawdown_pct": str(body.max_drawdown_pct),
            "daily_loss_limit": str(body.daily_loss_limit),
            "max_position_notional": str(body.max_position_notional),
        },
    )
    return _read(session)


@router.put("/council", response_model=SettingsRead)
def update_council_settings(
    body: CouncilSettingsUpdate, admin: AdminUser, session: SessionDep
) -> SettingsRead:
    """Configure the AI council members and quorum."""
    for member in body.members:
        if member.provider not in LLM_PROVIDERS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"council provider must be one of {list(LLM_PROVIDERS)}",
            )
    set_council_members(
        session,
        [{"provider": m.provider, "model": m.model} for m in body.members],
    )
    set_council_quorum(session, body.quorum)
    record_audit(
        session,
        actor=admin.username,
        action="settings.council",
        detail={
            "members": [f"{m.provider}:{m.model}" for m in body.members],
            "quorum": str(body.quorum),
        },
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
