"""News database model — one stored headline.

Rows are insert-only and deduplicated on `url`: re-fetching a feed re-sees the
same links, so an upsert keyed on the URL keeps the table free of duplicates.
A headline is tagged `world` or `asset`; `symbol` carries the recognised asset
(e.g. ``BTCUSDT``) when one was matched, else null.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel


class NewsItem(SQLModel, table=True):
    """A single news headline pulled from an RSS feed."""

    __tablename__ = "news_item"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(max_length=64, index=True)
    title: str = Field(max_length=512)
    url: str = Field(unique=True, index=True, max_length=1024)
    summary: str = Field(default="")
    # `world` (general) or `asset` (tagged to a specific symbol).
    category: str = Field(default="world", max_length=16, index=True)
    symbol: str | None = Field(default=None, max_length=24, index=True)
    sentiment: str | None = Field(default=None, max_length=16)
    # When the feed published the item (best-effort; null when absent).
    published_at: datetime | None = Field(default=None, index=True)
    fetched_at: datetime = Field(index=True)
