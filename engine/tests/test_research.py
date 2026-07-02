"""Tests for research reports — data pack, writer, cycle, API."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from ai.providers.base import Completion, LLMError, LLMProvider
from ai.usage import LLMUsage
from appsettings.store import set_ai_spend_cap, set_research_symbols
from connections import service as connections_service
from marketdata.models import Candle
from news.models import NewsItem
from research import service
from research.models import ResearchReport
from tests.conftest import ADMIN_PASSWORD, login


class FakeProvider(LLMProvider):
    """LLM provider returning a canned response (or raising)."""

    name = "fake"

    def __init__(self, text: str = "", *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        if self._raises:
            raise LLMError("provider unavailable")
        return Completion(
            text=self._text,
            provider=self.name,
            model=model or "fake-model",
            input_tokens=12,
            output_tokens=8,
        )


_NARRATIVE = json.dumps(
    {
        "trade_route_effect": "Tariff news may slow mining hardware imports.",
        "technology_review": "Network upgrades continue on schedule.",
        "scenarios_up": ["ETF inflows accelerate"],
        "scenarios_down": ["Regulatory crackdown"],
        "summary": "Constructive but volatile.",
    }
)


def _seed_news(session: Session) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    rows = [
        NewsItem(
            source="Test",
            title="Bitcoin climbs on ETF inflows",
            url="https://example.com/btc-news",
            category="asset",
            symbol="BTCUSDT",
            fetched_at=now,
        ),
        NewsItem(
            source="Econ",
            title="Fed holds rates steady",
            url="https://example.com/fed",
            category="economic",
            fetched_at=now,
        ),
        NewsItem(
            source="World",
            title="Trade talks resume",
            url="https://example.com/trade",
            category="world",
            fetched_at=now,
        ),
    ]
    for r in rows:
        session.add(r)
    session.commit()


def _seed_candles(session: Session, n: int = 60) -> None:
    base = datetime(2026, 6, 1, tzinfo=UTC).replace(tzinfo=None)
    for i in range(n):
        price = Decimal(100 + i)
        session.add(
            Candle(
                market="spot",
                symbol="BTCUSDT",
                interval="1h",
                open_time=base + timedelta(hours=i),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=Decimal(1),
                close_time=base + timedelta(hours=i + 1),
            )
        )
    session.commit()


def test_build_data_pack_assembles_stored_inputs(session: Session) -> None:
    _seed_news(session)
    _seed_candles(session)
    connections_service.create_node(
        session, label="BTC", kind="asset", symbol="BTCUSDT"
    )
    pack = service.build_data_pack(session, "BTCUSDT")
    assert pack.headlines == ["Bitcoin climbs on ETF inflows"]
    assert len(pack.market_headlines) == 2
    assert any("Fed holds" in h for h in pack.market_headlines)
    assert pack.technicals["price"] == "159"  # trailing zeros normalised away
    assert "rsi_14" in pack.technicals
    assert "sma_50" in pack.technicals


def test_write_report_stores_sections_and_usage(session: Session) -> None:
    _seed_news(session)
    report = service.write_report(
        session, "BTCUSDT", provider=FakeProvider(_NARRATIVE)
    )
    assert report.status == "written"
    sections = report.sections_dict()
    assert sections["summary"] == "Constructive but volatile."
    assert sections["scenarios_up"] == ["ETF inflows accelerate"]
    assert sections["headlines"] == ["Bitcoin climbs on ETF inflows"]
    usage = session.exec(select(LLMUsage)).all()
    assert len(usage) == 1
    assert usage[0].provider == "fake"


def test_write_report_failure_stores_failed_row(session: Session) -> None:
    report = service.write_report(
        session, "BTCUSDT", provider=FakeProvider(raises=True)
    )
    assert report.status == "failed"
    assert "provider unavailable" in report.error
    # The mechanical sections survive even when the writer fails.
    assert "headlines" in report.sections_dict()

    bad_json = service.write_report(
        session, "BTCUSDT", provider=FakeProvider("not json at all")
    )
    assert bad_json.status == "failed"


def test_run_cycle_respects_spend_cap(session: Session, monkeypatch) -> None:
    set_research_symbols(session, ["BTCUSDT"])
    set_ai_spend_cap(session, Decimal("0.000001"))
    session.add(
        LLMUsage(
            provider="openai",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=1000,
            estimated_cost_usd=Decimal("1"),
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    session.commit()
    monkeypatch.setattr(
        service, "resolve_writer", lambda s: (FakeProvider(_NARRATIVE), None)
    )
    written = service.run_cycle(lambda: session)
    assert written == 0
    assert session.exec(select(ResearchReport)).all() == []


def test_run_cycle_writes_each_watched_symbol(
    session: Session, monkeypatch
) -> None:
    set_research_symbols(session, ["BTCUSDT", "ETHUSDT"])
    monkeypatch.setattr(
        service, "resolve_writer", lambda s: (FakeProvider(_NARRATIVE), None)
    )
    written = service.run_cycle(lambda: session)
    assert written == 2
    symbols = {r.symbol for r in session.exec(select(ResearchReport)).all()}
    assert symbols == {"BTCUSDT", "ETHUSDT"}


def _login(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}


def test_research_api_run_list_detail(
    client: TestClient, session: Session, monkeypatch
) -> None:
    from api import research as research_api

    _seed_news(session)
    monkeypatch.setattr(
        research_api.service,
        "resolve_writer",
        lambda s: (FakeProvider(_NARRATIVE), None),
    )
    headers = _login(client)
    resp = client.post(
        "/api/research/run", json={"symbol": "BTCUSDT"}, headers=headers
    )
    assert resp.status_code == 200
    (report,) = resp.json()
    assert report["status"] == "written"
    assert report["sections"]["summary"] == "Constructive but volatile."

    listed = client.get("/api/research?symbol=BTCUSDT", headers=headers).json()
    assert len(listed) == 1
    detail = client.get(f"/api/research/{report['id']}", headers=headers).json()
    assert detail["symbol"] == "BTCUSDT"
    assert client.get("/api/research/9999", headers=headers).status_code == 404


def test_research_settings_round_trip(client: TestClient) -> None:
    headers = _login(client)
    resp = client.put(
        "/api/settings/research",
        json={
            "symbols": ["solusdt", "BTCUSDT"],
            "interval_hours": 6,
            "writer_provider": "ollama",
            "writer_model": "llama3",
            "news_interval_hours": 4,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["research_symbols"] == ["SOLUSDT", "BTCUSDT"]
    assert body["research_interval_hours"] == 6
    assert body["research_writer_provider"] == "ollama"
    assert body["news_interval_hours"] == 4

    bad = client.put(
        "/api/settings/research",
        json={"symbols": ["BTCUSDT"], "writer_provider": "nonsense"},
        headers=headers,
    )
    assert bad.status_code == 400


def test_council_settings_round_trip(client: TestClient) -> None:
    headers = _login(client)
    resp = client.put(
        "/api/settings/council",
        json={
            "members": [
                {"provider": "claude", "model": "claude-sonnet-4-6"},
                {"provider": "ollama", "model": "llama3"},
            ],
            "quorum": "0.6",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["council_members"]) == 2
    assert body["council_members"][0]["provider"] == "claude"
    assert Decimal(str(body["council_quorum"])) == Decimal("0.6")

    bad = client.put(
        "/api/settings/council",
        json={"members": [{"provider": "nonsense"}]},
        headers=headers,
    )
    assert bad.status_code == 400


def test_council_review_api(
    client: TestClient, session: Session, monkeypatch
) -> None:
    from ai import council
    from tests.test_council import VotingProvider

    headers = _login(client)
    client.put(
        "/api/settings/council",
        json={"members": [{"provider": "claude", "model": "m"}], "quorum": "0.5"},
        headers=headers,
    )
    monkeypatch.setattr(
        research_api_module().service,
        "resolve_writer",
        lambda s: (FakeProvider(_NARRATIVE), None),
    )
    monkeypatch.setattr(
        council, "get_provider", lambda name, **_kw: VotingProvider("buy", "0.9")
    )
    (report,) = client.post(
        "/api/research/run", json={"symbol": "BTCUSDT"}, headers=headers
    ).json()

    no_review = client.get(f"/api/research/{report['id']}/review", headers=headers)
    assert no_review.status_code == 404

    resp = client.post(f"/api/research/{report['id']}/review", headers=headers)
    assert resp.status_code == 200
    review = resp.json()
    assert review["verdict"] == "buy"
    assert review["quorum_met"] is True
    assert len(review["votes"]) == 1

    fetched = client.get(
        f"/api/research/{report['id']}/review", headers=headers
    ).json()
    assert fetched["id"] == review["id"]


def research_api_module():
    from api import research as research_api

    return research_api
