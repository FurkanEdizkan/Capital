"""Tests for Polymarket market discovery — hermetic, fake Gamma fetcher."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from polymarket.models import MarketStatus, PredictionMarket
from polymarket.service import (
    list_markets,
    refresh_markets,
    set_watched,
    sync_resolutions,
)
from trading.models import Position, PositionSide, Trade

_YES = "7132104567925221259462638553270691275033272857194253228963137931245558399"
_NO = "2138298657893457834578934578934578934578934578934578934578934578934578934"


def _gamma_market(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "conditionId": "0xCOND",
        "question": "Will the Fed cut rates in September?",
        "slug": "fed-cut-september",
        "category": "Economy",
        "endDate": "2026-09-30T00:00:00Z",
        # Gamma serialises list fields as stringified JSON.
        "outcomes": '["Yes", "No"]',
        "outcomePrices": '["0.62", "0.38"]',
        "clobTokenIds": f'["{_YES}", "{_NO}"]',
        "volume24hr": 125000.5,
        "liquidityNum": 50000,
        "active": True,
        "closed": False,
    }
    base.update(overrides)
    return base


class FakeGamma:
    """Returns a canned market list and records the params it was asked with."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, path: str, params: dict[str, Any]) -> Any:
        self.calls.append((path, params))
        if "condition_ids" in params:
            return [
                i for i in self.items if i["conditionId"] == params["condition_ids"]
            ]
        return self.items


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, text: str) -> None:
        self.sent.append(text)


def test_refresh_upserts_markets_from_gamma(session: Session) -> None:
    fetch = FakeGamma([_gamma_market()])
    assert refresh_markets(session, fetch=fetch) == 1
    row = session.exec(select(PredictionMarket)).one()
    assert row.condition_id == "0xCOND"
    assert row.question.startswith("Will the Fed")
    assert row.yes_token_id == _YES
    assert row.no_token_id == _NO
    assert row.yes_price == Decimal("0.62")
    assert row.volume_24h == Decimal("125000.5")
    assert row.status == MarketStatus.active
    # Discovery asks for active markets ordered by volume.
    path, params = fetch.calls[0]
    assert path == "/markets"
    assert params["active"] == "true"


def test_refresh_updates_in_place_not_duplicates(session: Session) -> None:
    refresh_markets(session, fetch=FakeGamma([_gamma_market()]))
    refresh_markets(
        session, fetch=FakeGamma([_gamma_market(outcomePrices='["0.70", "0.30"]')])
    )
    rows = session.exec(select(PredictionMarket)).all()
    assert len(rows) == 1
    assert rows[0].yes_price == Decimal("0.70")


def test_refresh_skips_unparseable_rows(session: Session) -> None:
    items = [{"conditionId": ""}, {"question": "no id"}, _gamma_market()]
    assert refresh_markets(session, fetch=FakeGamma(items)) == 1


def test_list_markets_filters_and_search(session: Session) -> None:
    refresh_markets(
        session,
        fetch=FakeGamma(
            [
                _gamma_market(),
                _gamma_market(
                    conditionId="0xOTHER",
                    question="Will Real Madrid win the Champions League?",
                    category="Sports",
                ),
            ]
        ),
    )
    assert len(list_markets(session)) == 2
    assert [m.category for m in list_markets(session, category="Sports")] == ["Sports"]
    assert [m.condition_id for m in list_markets(session, search="madrid")] == ["0xOTHER"]
    set_watched(session, "0xCOND", True)
    assert [m.condition_id for m in list_markets(session, watched=True)] == ["0xCOND"]


def test_set_watched_unknown_market_returns_none(session: Session) -> None:
    assert set_watched(session, "0xNOPE", True) is None


def _open_position(session: Session, *, symbol: str, strategy: str = "Poly AI") -> None:
    session.add(
        Position(
            strategy=strategy,
            market="spot",
            symbol=symbol,
            side=PositionSide.long.value,
            qty=Decimal("100"),
            entry_price=Decimal("0.62"),
            opened_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()


def test_sync_settles_a_won_market(session: Session) -> None:
    refresh_markets(session, fetch=FakeGamma([_gamma_market()]))
    _open_position(session, symbol=_YES)
    resolved = _gamma_market(
        closed=True,
        umaResolutionStatus="resolved",
        outcomePrices='["1", "0"]',
    )
    notifier = FakeNotifier()
    assert sync_resolutions(session, fetch=FakeGamma([resolved]), notifier=notifier) == 1
    market = session.exec(select(PredictionMarket)).one()
    assert market.status == MarketStatus.resolved
    assert market.resolved_outcome == "Yes"
    # The winning tokens settled at 1 USDC — a recorded sell, position flat.
    trade = session.exec(select(Trade)).one()
    assert trade.symbol == _YES
    assert trade.price == Decimal(1)
    assert trade.realized_pnl == Decimal("100") * (Decimal(1) - Decimal("0.62"))
    position = session.exec(select(Position)).one()
    assert position.side == PositionSide.flat.value
    assert notifier.sent and "resolved" in notifier.sent[0]


def test_sync_settles_a_lost_market_at_zero(session: Session) -> None:
    refresh_markets(session, fetch=FakeGamma([_gamma_market()]))
    _open_position(session, symbol=_NO)  # held NO, market resolved YES
    resolved = _gamma_market(
        closed=True,
        umaResolutionStatus="resolved",
        outcomePrices='["1", "0"]',
    )
    sync_resolutions(session, fetch=FakeGamma([resolved]), notifier=FakeNotifier())
    trade = session.exec(select(Trade)).one()
    assert trade.price == Decimal(0)
    assert trade.realized_pnl < 0


def test_sync_skips_unwatched_unheld_markets(session: Session) -> None:
    refresh_markets(session, fetch=FakeGamma([_gamma_market()]))
    fetch = FakeGamma([_gamma_market(closed=True, umaResolutionStatus="resolved")])
    assert sync_resolutions(session, fetch=fetch, notifier=FakeNotifier()) == 0
    assert fetch.calls == []  # nothing watched or held — no lookups at all
