"""News service — fetch RSS feeds, tag headlines by asset, store and query.

`refresh` downloads each configured feed, parses it with `feedparser`, tags
each entry with an asset symbol when one is recognised, and upserts by URL.
It mirrors `ops.retention.prune_all`'s posture: best-effort, never raising into
the scheduler — a single broken feed is logged and skipped.

The feed list defaults to `DEFAULT_FEEDS` but can be overridden by an operator
via the `news_feeds` setting (a JSON array of `{name, url, category, symbol?}`).
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time

import feedparser
import httpx
from sqlmodel import Session, select

from appsettings.store import get_setting
from news.models import NewsItem

log = logging.getLogger("capital.news")

_NEWS_FEEDS_KEY = "news_feeds"


@dataclass(frozen=True)
class Feed:
    """A configured RSS source. `symbol` pins every entry to one asset."""

    name: str
    url: str
    category: str = "world"
    symbol: str | None = None


#: Free, no-key RSS feeds. Crypto-wide and markets-wide sources; the per-entry
#: symbol tagger picks out specific assets from titles/summaries.
DEFAULT_FEEDS: tuple[Feed, ...] = (
    Feed("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "asset"),
    Feed("Cointelegraph", "https://cointelegraph.com/rss", "asset"),
    Feed("Yahoo Finance", "https://finance.yahoo.com/news/rssindex", "world"),
    Feed(
        "Reuters Business",
        "https://www.reutersagency.com/feed/?best-topics=business-finance",
        "world",
    ),
)

#: Keyword → trading symbol. Lower-cased substrings matched against the
#: headline text. Order matters only for readability; all are scanned.
_SYMBOL_ALIASES: dict[str, str] = {
    "bitcoin": "BTCUSDT",
    "btc": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "ether ": "ETHUSDT",
    "eth ": "ETHUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "xrp": "XRPUSDT",
    "dogecoin": "DOGEUSDT",
    "cardano": "ADAUSDT",
    "tether": "USDT",
    "nvidia": "NVDA",
    "amd ": "AMD",
    "tesla": "TSLA",
    "apple": "AAPL",
    "microsoft": "MSFT",
}

#: Injectable downloader — returns raw feed bytes for a URL. Overridden in tests.
Fetcher = Callable[[str], bytes]


def _http_fetch(url: str) -> bytes:
    """Download a feed over HTTP. Raises on transport/HTTP errors."""
    resp = httpx.get(url, timeout=20.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def _utcnow() -> datetime:
    """Current UTC time, tz-naive — matching the other tables."""
    return datetime.now(UTC).replace(tzinfo=None)


def match_symbol(text: str, default: str | None = None) -> str | None:
    """Recognise an asset symbol in `text`, falling back to `default`."""
    haystack = f" {text.lower()} "
    for alias, symbol in _SYMBOL_ALIASES.items():
        if alias in haystack:
            return symbol
    return default


def _published(entry: object) -> datetime | None:
    """Best-effort published timestamp from a feed entry (tz-naive UTC)."""
    parsed: struct_time | None = getattr(entry, "published_parsed", None) or getattr(
        entry, "updated_parsed", None
    )
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=UTC).replace(tzinfo=None)


def configured_feeds(session: Session) -> list[Feed]:
    """The operator-configured feed list, or the built-in defaults."""
    raw = get_setting(session, _NEWS_FEEDS_KEY)
    if not raw:
        return list(DEFAULT_FEEDS)
    try:
        items = json.loads(raw)
        return [
            Feed(
                name=str(i["name"]),
                url=str(i["url"]),
                category=str(i.get("category", "world")),
                symbol=(str(i["symbol"]) if i.get("symbol") else None),
            )
            for i in items
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        log.warning("invalid news_feeds setting — falling back to defaults")
        return list(DEFAULT_FEEDS)


def parse_feed(content: bytes | str, feed: Feed) -> list[NewsItem]:
    """Parse one feed's raw content into (unsaved) `NewsItem` rows."""
    parsed = feedparser.parse(content)
    now = _utcnow()
    items: list[NewsItem] = []
    for entry in parsed.entries:
        url = getattr(entry, "link", "")
        title = getattr(entry, "title", "")
        if not url or not title:
            continue
        summary = getattr(entry, "summary", "")
        symbol = match_symbol(f"{title} {summary}", feed.symbol)
        items.append(
            NewsItem(
                source=feed.name,
                title=title[:512],
                url=url[:1024],
                summary=summary,
                category=("asset" if symbol else feed.category),
                symbol=symbol,
                published_at=_published(entry),
                fetched_at=now,
            )
        )
    return items


def _upsert(session: Session, item: NewsItem) -> bool:
    """Insert `item` if its URL is new. Returns True when a row was added."""
    existing = session.exec(
        select(NewsItem).where(NewsItem.url == item.url)
    ).first()
    if existing is not None:
        return False
    session.add(item)
    return True


def refresh(
    session: Session,
    *,
    feeds: list[Feed] | None = None,
    fetch: Fetcher = _http_fetch,
) -> int:
    """Fetch every feed and store new headlines. Returns the count added.

    Best-effort: a feed that fails to download or parse is logged and skipped
    so one bad source never aborts the refresh (or the scheduler).
    """
    sources = feeds if feeds is not None else configured_feeds(session)
    added = 0
    for feed in sources:
        try:
            content = fetch(feed.url)
            for item in parse_feed(content, feed):
                if _upsert(session, item):
                    added += 1
        except Exception:  # noqa: BLE001 — one bad feed must not abort refresh
            log.warning("news feed %r failed to refresh", feed.name, exc_info=True)
            continue
    session.commit()
    log.info("news refresh added %d headlines", added)
    return added


def recent(
    session: Session, *, symbol: str | None = None, limit: int = 50
) -> list[NewsItem]:
    """Newest-first headlines, optionally filtered to one asset symbol."""
    stmt = select(NewsItem)
    if symbol:
        stmt = stmt.where(NewsItem.symbol == symbol)
    stmt = stmt.order_by(NewsItem.fetched_at.desc()).limit(limit)  # type: ignore[attr-defined]
    return list(session.exec(stmt).all())
