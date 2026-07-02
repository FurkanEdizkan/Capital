"""Research service — assemble an asset's data pack and write a report.

`build_data_pack` gathers what the platform already knows about a symbol —
recent asset/world/economic headlines, its dependency-graph connections and a
technical snapshot from cached candles. `write_report` hands that pack to the
configured report-writer LLM, which returns the narrative sections as strict
JSON; mechanical and narrative sections are stored together as one
`ResearchReport` row. `run_cycle` does this for every watched symbol on the
scheduler, mirroring `news.service.refresh`'s never-raise posture.
"""

import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlmodel import Session

from ai.providers import LLMProvider, get_provider
from ai.usage import cap_reached, record_usage
from appsettings.store import (
    get_llm_credentials,
    get_research_symbols,
    get_research_writer,
)
from connections import service as connections_service
from exchange.client import Market
from marketdata.cache import get_cached_candles
from news import service as news_service
from research.models import SCHEMA_VERSION, ResearchReport
from strategies.indicators import rsi, sma

log = logging.getLogger("capital.research")

#: Every key a stored report's `sections` JSON carries, in render order.
SECTION_KEYS: tuple[str, ...] = (
    "headlines",
    "market_headlines",
    "connections",
    "technicals",
    "trade_route_effect",
    "technology_review",
    "scenarios_up",
    "scenarios_down",
    "summary",
)

#: The narrative sections the report writer must return.
_NARRATIVE_KEYS: tuple[str, ...] = (
    "trade_route_effect",
    "technology_review",
    "scenarios_up",
    "scenarios_down",
    "summary",
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _utcnow() -> datetime:
    """Current UTC time, tz-naive — matching the other tables."""
    return datetime.now(UTC).replace(tzinfo=None)


def _fmt(value: Decimal) -> str:
    """A Decimal as a compact string — no scientific notation or zero-tail."""
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass
class DataPack:
    """The raw inputs a report is written from — all already stored locally."""

    symbol: str
    headlines: list[str] = field(default_factory=list)
    market_headlines: list[str] = field(default_factory=list)
    connections: list[str] = field(default_factory=list)
    technicals: dict[str, str] = field(default_factory=dict)


def build_data_pack(session: Session, symbol: str) -> DataPack:
    """Assemble everything the platform knows about `symbol` for a report."""
    asset_news = news_service.recent(session, symbol=symbol, limit=15)
    market_news = [
        n
        for n in news_service.recent(session, limit=40)
        if n.category in ("world", "economic")
    ][:10]
    technicals: dict[str, str] = {}
    candles = get_cached_candles(
        session, market=Market.spot, symbol=symbol, interval="1h", limit=200
    )
    if candles:
        closes = [c.close for c in candles]
        technicals["price"] = _fmt(closes[-1])
        if len(closes) >= 15:
            technicals["rsi_14"] = _fmt(rsi(closes, 14))
        if len(closes) >= 20:
            technicals["sma_20"] = _fmt(sma(closes, 20))
        if len(closes) >= 50:
            technicals["sma_50"] = _fmt(sma(closes, 50))
        if len(closes) >= 25:
            prev = closes[-25]
            if prev != 0:
                change = (closes[-1] / prev - Decimal(1)) * Decimal(100)
                technicals["change_24h_pct"] = _fmt(round(change, 2))
    return DataPack(
        symbol=symbol,
        headlines=[n.title for n in asset_news],
        market_headlines=[f"[{n.category}] {n.title}" for n in market_news],
        connections=connections_service.neighbours(session, symbol),
        technicals=technicals,
    )


def build_writer_prompt(pack: DataPack) -> str:
    """The report-writer instruction: data pack in, strict-JSON narrative out."""
    keys = ", ".join(f'"{k}"' for k in _NARRATIVE_KEYS)
    return "\n".join(
        [
            f"You are a market research analyst writing a report on {pack.symbol}.",
            "Use ONLY the data below; do not invent facts.",
            "",
            f"Recent {pack.symbol} headlines:",
            "\n".join(f"- {h}" for h in pack.headlines) or "- (none)",
            "",
            "Recent world & economic headlines:",
            "\n".join(f"- {h}" for h in pack.market_headlines) or "- (none)",
            "",
            f"Known connections/dependencies: {', '.join(pack.connections) or '(none)'}",
            f"Technical snapshot: {json.dumps(pack.technicals)}",
            "",
            "Write the narrative sections of the report:",
            "- trade_route_effect: how trade routes, supply chains and macro"
            " policy in the news could affect this asset (string)",
            "- technology_review: state and trajectory of the asset's"
            " technology and ecosystem (string)",
            "- scenarios_up: plausible upside scenarios (array of strings)",
            "- scenarios_down: plausible downside scenarios (array of strings)",
            "- summary: a balanced 3-5 sentence executive summary (string)",
            "",
            f"Respond ONLY with a JSON object with exactly these keys: {keys}.",
        ]
    )


def _parse_narrative(text: str) -> dict:
    """Extract the narrative-section JSON object from the writer's response."""
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError(f"no JSON object in writer response: {text[:120]!r}")
    raw = json.loads(match.group(0))
    if not isinstance(raw, dict):
        raise ValueError("writer response is not a JSON object")
    narrative: dict = {}
    for key in _NARRATIVE_KEYS:
        value = raw.get(key, [] if key.startswith("scenarios") else "")
        if key.startswith("scenarios"):
            narrative[key] = [str(v) for v in value] if isinstance(value, list) else []
        else:
            narrative[key] = str(value)
    return narrative


def resolve_writer(session: Session) -> tuple[LLMProvider, str | None]:
    """Build the report-writer `(provider, model)` from stored settings."""
    cfg = get_research_writer(session)
    creds = get_llm_credentials(session, cfg["provider"])
    provider = get_provider(
        cfg["provider"], api_key=creds["api_key"], base_url=creds["base_url"]
    )
    return provider, (cfg["model"] or None)


def write_report(
    session: Session,
    symbol: str,
    *,
    provider: LLMProvider,
    model: str | None = None,
    pack: DataPack | None = None,
) -> ResearchReport:
    """Write and store one report for `symbol` using the given writer LLM.

    A writer failure (transport or unparseable JSON) stores a `failed` row
    that still carries the mechanical sections — and never raises.
    """
    pack = pack or build_data_pack(session, symbol)
    sections = {k: v for k, v in asdict(pack).items() if k != "symbol"}
    status, error = "written", ""
    used_model = model or ""
    try:
        completion = provider.complete(build_writer_prompt(pack), model=model)
        used_model = completion.model
        record_usage(
            session,
            provider=completion.provider,
            model=completion.model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            purpose="report",
        )
        sections.update(_parse_narrative(completion.text))
    except Exception as exc:  # noqa: BLE001 — a failed report row beats a crash
        log.warning("report writer failed for %s", symbol, exc_info=True)
        status, error = "failed", str(exc)[:512]
    report = ResearchReport(
        symbol=symbol,
        schema_version=SCHEMA_VERSION,
        status=status,
        sections=json.dumps(sections),
        provider=provider.name,
        model=used_model,
        error=error,
        created_at=_utcnow(),
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def run_cycle(session_factory: Callable[[], Session]) -> int:
    """Write a report for every watched symbol. Returns reports written.

    Best-effort per symbol; stops early once the daily AI spend cap is hit.
    """
    from ai import council  # late import — council pulls in the trading stack

    written = 0
    with session_factory() as session:
        for symbol in get_research_symbols(session):
            if cap_reached(session):
                log.warning("research cycle stopped — AI spend cap reached")
                break
            try:
                provider, model = resolve_writer(session)
                report = write_report(session, symbol, provider=provider, model=model)
                written += report.status == "written"
                if report.status == "written":
                    review = council.review_report(session, report)
                    if review is not None:
                        council.emit_signal(session, report, review)
            except Exception:  # noqa: BLE001 — one symbol must not abort the cycle
                log.exception("research failed for %s", symbol)
    log.info("research cycle wrote %d reports", written)
    return written
