"""Polymarket database models — discovered markets and their AI analyses.

`PredictionMarket` is the local catalogue of Polymarket markets ("bets"),
refreshed from the public Gamma API and curated through a `watched` flag.
`MarketAnalysis` rows are written by the AI bet analysis (polymarket/analysis):
the model's probability estimate for YES against the market's price, and the
edge between them — the platform's evidence trail for every suggestion.
"""

from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

_PRICE = {"max_digits": 24, "decimal_places": 8}


class MarketStatus:
    """Lifecycle states a stored market moves through (string constants)."""

    active = "active"
    closed = "closed"
    resolved = "resolved"


class PredictionMarket(SQLModel, table=True):
    """One Polymarket market, upserted from the Gamma API by `condition_id`."""

    __tablename__ = "prediction_market"

    id: int | None = Field(default=None, primary_key=True)
    condition_id: str = Field(unique=True, index=True, max_length=80)
    question: str = Field(max_length=512)
    slug: str = Field(default="", max_length=256)
    category: str = Field(default="", max_length=64, index=True)
    end_date: datetime | None = Field(default=None, index=True)
    # The binary outcome tokens — `yes`/`no` follow the Gamma ordering, where
    # the first outcome is YES. These are the tradeable venue symbols.
    yes_token_id: str = Field(default="", index=True, max_length=80)
    no_token_id: str = Field(default="", max_length=80)
    outcomes: str = Field(default="[]")  # JSON array of outcome labels
    yes_price: Decimal = Field(default=Decimal(0), **_PRICE)
    volume_24h: Decimal = Field(default=Decimal(0), **_PRICE)
    liquidity: Decimal = Field(default=Decimal(0), **_PRICE)
    status: str = Field(default=MarketStatus.active, max_length=12, index=True)
    resolved_outcome: str = Field(default="", max_length=64)
    # Watched markets get scheduled AI analysis regardless of volume rank.
    watched: bool = Field(default=False, index=True)
    fetched_at: datetime = Field(index=True)


class MarketAnalysis(SQLModel, table=True):
    """One AI pass over a market — estimated probability vs market price."""

    __tablename__ = "market_analysis"

    id: int | None = Field(default=None, primary_key=True)
    condition_id: str = Field(index=True, max_length=80)
    question: str = Field(max_length=512)
    market_price: Decimal = Field(default=Decimal(0), **_PRICE)  # YES price
    est_probability: Decimal = Field(default=Decimal(0), **_PRICE)
    # est_probability - market_price: positive favours YES, negative NO.
    edge: Decimal = Field(default=Decimal(0), **_PRICE)
    recommendation: str = Field(default="hold", max_length=8)  # buy_yes|buy_no|hold
    confidence: Decimal = Field(default=Decimal(0), **_PRICE)
    reasoning: str = Field(default="")
    provider: str = Field(default="", max_length=16)
    model: str = Field(default="", max_length=64)
    created_at: datetime = Field(index=True)
