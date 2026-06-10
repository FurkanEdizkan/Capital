"""Tests for price-feed latency — math, rolling stats, rollups, API."""

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from exchange.client import Market
from marketdata import latency
from marketdata.latency import FeedLatency, LatencyRegistry
from marketdata.stream import TickerHub
from tests.conftest import ADMIN_PASSWORD, login


def test_record_event_time_measures_against_local_clock(monkeypatch) -> None:
    reg = LatencyRegistry()
    monkeypatch.setattr(latency, "registry", reg)
    latency.record_event_time("spot", "BTCUSDT", 1_000_000, now_ms=1_000_450.0)
    (stats,) = reg.stats()
    assert stats.kind == "ws"
    assert stats.current_ms == 450.0
    # Clock skew (event time ahead of us) clamps to zero, never negative.
    latency.record_event_time("spot", "BTCUSDT", 2_000_000, now_ms=1_999_900.0)
    (stats,) = reg.stats()
    assert stats.current_ms == 0.0
    # Garbage event times are ignored.
    latency.record_event_time("spot", "BTCUSDT", None)
    latency.record_event_time("spot", "BTCUSDT", "nope")
    assert reg.stats()[0].samples == 2


def test_rolling_stats_and_degraded_threshold() -> None:
    reg = LatencyRegistry()
    for ms in (100, 200, 300, 400, 10_000):
        reg.record("spot", "BTCUSDT", "ws", ms)
    (stats,) = reg.stats(warn_ms=2000)
    assert stats.p50_ms == 300.0
    assert stats.max_ms == 10_000.0
    assert stats.samples == 5
    assert stats.degraded  # current sample is 10s
    reg.record("spot", "BTCUSDT", "ws", 150)
    (stats,) = reg.stats(warn_ms=20_000)
    assert not stats.degraded


def test_flush_rollups_persists_and_clears(session: Session) -> None:
    reg = LatencyRegistry()
    for ms in (100, 200, 300):
        reg.record("spot", "ETHUSDT", "ws", ms)
    reg.record("spot", "ETHUSDT", "rest", 50)
    assert reg.flush_rollups(session) == 2
    rows = session.exec(select(FeedLatency)).all()
    assert len(rows) == 2
    ws_row = next(r for r in rows if r.kind == "ws")
    assert ws_row.samples == 3
    assert float(ws_row.avg_ms) == 200.0
    # Pending cleared — a second flush writes nothing.
    assert reg.flush_rollups(session) == 0
    # The rolling window survives the flush.
    assert reg.stats()[0].samples > 0


def test_ticker_hub_records_event_latency(monkeypatch) -> None:
    reg = LatencyRegistry()
    monkeypatch.setattr(latency, "registry", reg)
    hub = TickerHub(Market.spot)
    now_ms = datetime.now(UTC).timestamp() * 1000
    hub.handle(
        json.dumps(
            {
                "s": "BTCUSDT",
                "E": now_ms - 250,
                "c": "100",
                "P": "1.5",
                "q": "1000",
            }
        )
    )
    (stats,) = reg.stats()
    assert stats.symbol == "BTCUSDT"
    assert 0 <= stats.current_ms < 5000  # ~250ms plus test overhead


def test_latency_api_reports_feeds(client: TestClient, monkeypatch) -> None:
    reg = LatencyRegistry()
    monkeypatch.setattr("api.market.latency_registry", reg)
    reg.record("spot", "BTCUSDT", "ws", 120)
    reg.record("spot", "BTCUSDT", "rest", 80)
    headers = {"Authorization": f"Bearer {login(client, 'admin', ADMIN_PASSWORD)}"}
    body = client.get("/api/market/latency", headers=headers).json()
    assert body["warn_ms"] == 2000
    assert body["degraded"] is False
    kinds = {f["kind"] for f in body["feeds"]}
    assert kinds == {"ws", "rest"}
    reg.record("spot", "BTCUSDT", "ws", 9000)
    body = client.get("/api/market/latency", headers=headers).json()
    assert body["degraded"] is True
