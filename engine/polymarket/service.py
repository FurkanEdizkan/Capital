"""Polymarket market discovery — fetch, store and curate prediction markets.

`refresh_markets` pulls the most-traded active markets from Polymarket's
public Gamma API (no credentials) and upserts them by `condition_id` — the
local catalogue the dashboard browses and the AI analyses. `sync_resolutions`
re-checks watched/held markets and, when one resolves, books the settlement
(winning tokens redeem at 1 USDC, losing at 0) into the position sub-ledger
and alerts the operator.

It mirrors `news.service.refresh`'s posture: an injectable fetcher for
hermetic tests, and a single broken row is logged and skipped.
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlmodel import Session, col, select

from appsettings.store import get_mode
from notify.telegram import TelegramNotifier
from polymarket.models import MarketStatus, PredictionMarket
from trading.executors.base import Order
from trading.models import FillSide, Position, PositionSide
from trading.portfolio import record_fill

log = logging.getLogger("capital.polymarket")

_GAMMA_API = "https://gamma-api.polymarket.com"

#: Injectable Gamma fetcher — returns the parsed JSON for a path + params.
Fetcher = Callable[[str, dict[str, Any]], Any]


def _http_fetch(path: str, params: dict[str, Any]) -> Any:
    """Query the Gamma API over HTTP. Raises on transport/HTTP errors."""
    resp = httpx.get(f"{_GAMMA_API}{path}", params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _utcnow() -> datetime:
    """Current UTC time, tz-naive — matching the other tables."""
    return datetime.now(UTC).replace(tzinfo=None)


def _decimal(value: Any) -> Decimal:
    """A best-effort Decimal — Gamma numbers arrive as floats or strings."""
    try:
        return Decimal(str(value)) if value not in (None, "") else Decimal(0)
    except InvalidOperation:
        return Decimal(0)


def _str_list(value: Any) -> list[str]:
    """Gamma returns list fields as stringified JSON; tolerate real lists."""
    if isinstance(value, list):
        return [str(v) for v in value]
    try:
        parsed = json.loads(value or "[]")
        return [str(v) for v in parsed] if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _end_date(value: Any) -> datetime | None:
    """Parse Gamma's ISO-8601 end date to tz-naive UTC; None when absent."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _status_of(item: dict[str, Any]) -> str:
    """A Gamma market's lifecycle status, from its `closed`/resolution flags."""
    resolution = str(item.get("umaResolutionStatus", "") or "")
    if resolution.startswith("resolved"):
        return MarketStatus.resolved
    if item.get("closed"):
        return MarketStatus.closed
    return MarketStatus.active


def _resolved_outcome(item: dict[str, Any]) -> str:
    """The winning outcome label of a resolved market — the price-1 outcome."""
    outcomes = _str_list(item.get("outcomes"))
    prices = _str_list(item.get("outcomePrices"))
    for label, price in zip(outcomes, prices, strict=False):
        if _decimal(price) == 1:
            return label
    return ""


def _apply(row: PredictionMarket, item: dict[str, Any]) -> PredictionMarket:
    """Copy a Gamma market payload onto a (new or existing) catalogue row."""
    tokens = _str_list(item.get("clobTokenIds"))
    prices = _str_list(item.get("outcomePrices"))
    row.question = str(item.get("question", ""))[:512]
    row.slug = str(item.get("slug", ""))[:256]
    row.category = str(item.get("category", "") or "")[:64]
    row.end_date = _end_date(item.get("endDate"))
    row.yes_token_id = tokens[0] if tokens else ""
    row.no_token_id = tokens[1] if len(tokens) > 1 else ""
    row.outcomes = json.dumps(_str_list(item.get("outcomes")))
    row.yes_price = _decimal(prices[0]) if prices else Decimal(0)
    row.volume_24h = _decimal(item.get("volume24hr"))
    row.liquidity = _decimal(item.get("liquidityNum") or item.get("liquidity"))
    row.status = _status_of(item)
    if row.status == MarketStatus.resolved:
        row.resolved_outcome = _resolved_outcome(item)
    row.fetched_at = _utcnow()
    return row


def get_market(session: Session, condition_id: str) -> PredictionMarket | None:
    """The stored market for `condition_id`, or None."""
    return session.exec(
        select(PredictionMarket).where(PredictionMarket.condition_id == condition_id)
    ).first()


def refresh_markets(
    session: Session, *, fetch: Fetcher | None = None, limit: int = 200
) -> int:
    """Pull the most-traded active markets from Gamma and upsert the catalogue.

    Returns the number of rows added or updated. A market payload that fails
    to parse is logged and skipped — one bad row never aborts the refresh.
    """
    fetch = fetch or _http_fetch
    items = fetch(
        "/markets",
        {
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
            "limit": limit,
        },
    )
    written = 0
    for item in items or []:
        try:
            condition_id = str(item.get("conditionId", ""))
            if not condition_id or not item.get("question"):
                continue
            row = get_market(session, condition_id) or PredictionMarket(
                condition_id=condition_id, question="", fetched_at=_utcnow()
            )
            session.add(_apply(row, item))
            written += 1
        except Exception:  # noqa: BLE001 — one bad market must not abort refresh
            log.warning("failed to parse a Gamma market payload", exc_info=True)
            continue
    session.commit()
    log.info("polymarket refresh upserted %d markets", written)
    return written


def list_markets(
    session: Session,
    *,
    watched: bool | None = None,
    status: str | None = MarketStatus.active,
    category: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[PredictionMarket]:
    """Catalogue rows, most-traded first, with optional filters."""
    stmt = select(PredictionMarket)
    if watched is not None:
        stmt = stmt.where(PredictionMarket.watched == watched)
    if status:
        stmt = stmt.where(PredictionMarket.status == status)
    if category:
        stmt = stmt.where(PredictionMarket.category == category)
    if search:
        stmt = stmt.where(col(PredictionMarket.question).ilike(f"%{search}%"))
    stmt = stmt.order_by(col(PredictionMarket.volume_24h).desc()).limit(limit)
    return list(session.exec(stmt).all())


def set_watched(
    session: Session, condition_id: str, watched: bool
) -> PredictionMarket | None:
    """Pin or unpin a market for scheduled AI analysis. None if unknown."""
    row = get_market(session, condition_id)
    if row is None:
        return None
    row.watched = watched
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _open_positions_on(session: Session, token_ids: list[str]) -> list[Position]:
    """Open positions held on any of the given outcome tokens."""
    if not token_ids:
        return []
    return list(
        session.exec(
            select(Position).where(
                col(Position.symbol).in_(token_ids),
                Position.side != PositionSide.flat.value,
                Position.qty > 0,
            )
        ).all()
    )


def _settle_positions(
    session: Session, market: PredictionMarket, notifier: TelegramNotifier
) -> None:
    """Book the settlement of every open position on a resolved market.

    A winning outcome token redeems at 1 USDC, a losing one at 0. Settlement
    is a redemption, not an order, so the fill is recorded directly into the
    sub-ledger (no executor sizing, slippage or fees).
    """
    outcomes = _str_list(market.outcomes)
    winner_token = ""
    if market.resolved_outcome in outcomes:
        index = outcomes.index(market.resolved_outcome)
        if index == 0:
            winner_token = market.yes_token_id
        elif index == 1:
            winner_token = market.no_token_id
    mode = get_mode(session).value
    for pos in _open_positions_on(
        session, [t for t in (market.yes_token_id, market.no_token_id) if t]
    ):
        settle_price = Decimal(1) if pos.symbol == winner_token else Decimal(0)
        side = FillSide.sell if pos.side == PositionSide.long.value else FillSide.buy
        order = Order(
            strategy=pos.strategy,
            market=pos.market,
            symbol=pos.symbol,
            side=side,
            quantity=pos.qty,
        )
        record_fill(
            session, mode=mode, order=order, qty=pos.qty, price=settle_price, fee=Decimal(0)
        )
        log.info(
            "settled %r position on %s at %s (market resolved %s)",
            pos.strategy,
            pos.symbol,
            settle_price,
            market.resolved_outcome or "unknown",
        )
        notifier.send(
            f"Polymarket resolved — {market.question[:120]}: "
            f"{market.resolved_outcome or 'resolved'}; settled {pos.strategy}'s "
            f"{pos.qty} tokens at {settle_price} USDC."
            + (
                " Live tokens may still need redemption on polymarket.com."
                if mode == "live"
                else ""
            )
        )


def sync_resolutions(
    session: Session,
    *,
    fetch: Fetcher | None = None,
    notifier: TelegramNotifier | None = None,
) -> int:
    """Re-check open watched/held markets; settle and alert on resolution.

    Returns the number of markets that moved to `resolved`. Best-effort per
    market — one failed lookup never aborts the sync.
    """
    fetch = fetch or _http_fetch
    notifier = notifier or TelegramNotifier()
    candidates = session.exec(
        select(PredictionMarket).where(
            PredictionMarket.status != MarketStatus.resolved
        )
    ).all()
    resolved = 0
    for market in candidates:
        held = _open_positions_on(
            session, [t for t in (market.yes_token_id, market.no_token_id) if t]
        )
        if not market.watched and not held:
            continue
        try:
            items = fetch("/markets", {"condition_ids": market.condition_id})
            if not items:
                continue
            _apply(market, items[0])
            session.add(market)
            if market.status == MarketStatus.resolved:
                _settle_positions(session, market, notifier)
                resolved += 1
            session.commit()
        except Exception:  # noqa: BLE001 — one market must not abort the sync
            log.warning(
                "resolution sync failed for %s", market.condition_id, exc_info=True
            )
            continue
    if resolved:
        log.info("polymarket resolution sync settled %d markets", resolved)
    return resolved
