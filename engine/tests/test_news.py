"""Tests for the news service — parsing, symbol tagging, upsert, querying."""

from sqlmodel import Session, select

from news import service
from news.models import NewsItem
from news.service import Feed

_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <item>
    <title>Bitcoin surges past resistance</title>
    <link>https://example.com/btc-1</link>
    <description>BTC rallies hard.</description>
    <pubDate>Tue, 27 May 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Markets steady ahead of data</title>
    <link>https://example.com/markets-1</link>
    <description>General market commentary.</description>
    <pubDate>Tue, 27 May 2026 11:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""

_FEED = Feed("Test", "https://example.com/feed.xml", category="world")


def _fetch(_url: str) -> bytes:
    return _RSS.encode("utf-8")


def test_match_symbol_recognises_known_assets() -> None:
    assert service.match_symbol("Bitcoin is up today") == "BTCUSDT"
    assert service.match_symbol("Nothing relevant here") is None
    assert service.match_symbol("Nothing", default="ETHUSDT") == "ETHUSDT"


def test_parse_feed_tags_asset_news() -> None:
    items = service.parse_feed(_RSS, _FEED)
    assert len(items) == 2
    btc = next(i for i in items if "Bitcoin" in i.title)
    assert btc.symbol == "BTCUSDT"
    assert btc.category == "asset"
    other = next(i for i in items if "Markets" in i.title)
    assert other.symbol is None
    assert other.category == "world"


def test_refresh_inserts_and_dedups(session: Session) -> None:
    added = service.refresh(session, feeds=[_FEED], fetch=_fetch)
    assert added == 2
    # Re-running sees the same URLs and adds nothing.
    again = service.refresh(session, feeds=[_FEED], fetch=_fetch)
    assert again == 0
    assert len(session.exec(select(NewsItem)).all()) == 2


def test_refresh_skips_a_broken_feed(session: Session) -> None:
    def boom(_url: str) -> bytes:
        raise RuntimeError("feed down")

    bad = Feed("Bad", "https://example.com/bad.xml")
    added = service.refresh(
        session,
        feeds=[bad, _FEED],
        fetch=lambda u: boom(u) if "bad" in u else _fetch(u),
    )
    assert added == 2  # the good feed still imported


def test_recent_filters_by_symbol(session: Session) -> None:
    service.refresh(session, feeds=[_FEED], fetch=_fetch)
    btc = service.recent(session, symbol="BTCUSDT")
    assert len(btc) == 1
    assert btc[0].symbol == "BTCUSDT"
    assert len(service.recent(session)) == 2


def test_default_feeds_are_sane() -> None:
    categories = {f.category for f in service.DEFAULT_FEEDS}
    assert categories == {"asset", "world", "economic"}
    names = [f.name for f in service.DEFAULT_FEEDS]
    urls = [f.url for f in service.DEFAULT_FEEDS]
    assert len(names) == len(set(names))
    assert len(urls) == len(set(urls))
    assert all(u.startswith("https://") for u in urls)


def test_parse_feed_keeps_economic_category() -> None:
    economic = Feed("Econ", "https://example.com/econ.xml", category="economic")
    items = service.parse_feed(_RSS, economic)
    general = next(i for i in items if "Markets" in i.title)
    assert general.category == "economic"
    # An entry naming an asset is still tagged to it, overriding the feed.
    btc = next(i for i in items if "Bitcoin" in i.title)
    assert btc.category == "asset"


def test_recent_filters_by_category(session: Session) -> None:
    economic = Feed("Econ", "https://example.com/econ.xml", category="economic")
    service.refresh(session, feeds=[_FEED], fetch=_fetch)
    econ_rss = _RSS.replace("example.com/", "example.com/econ-")
    service.refresh(session, feeds=[economic], fetch=lambda _u: econ_rss.encode())
    assert len(service.recent(session, category="economic")) == 1
    assert len(service.recent(session, category="world")) == 1
    assert len(service.recent(session, category="asset")) == 2
