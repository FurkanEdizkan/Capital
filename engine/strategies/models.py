"""Strategy instance database model — operator-created strategy rows.

Built-in strategies are code-defined; an operator can additionally apply any
registered strategy type to any coin from the UI. Each such instance is one
row here, rebuilt into a live strategy object on engine start (and on
create/delete through the API).
"""

import json
from datetime import datetime

from sqlmodel import Field, SQLModel


class StrategyInstance(SQLModel, table=True):
    """One operator-created strategy: a type applied to a symbol."""

    __tablename__ = "strategy_instance"

    id: int | None = Field(default=None, primary_key=True)
    # Strategy names key the position sub-ledger — unique across built-ins,
    # plugins and instances (collisions are rejected at create time).
    name: str = Field(unique=True, index=True, max_length=64)
    type: str = Field(index=True, max_length=32)
    symbol: str = Field(index=True, max_length=24)
    market: str = Field(default="spot", max_length=8)
    timeframe: str = Field(default="1h", max_length=8)
    # JSON object of constructor params (registry-validated at create time).
    params: str = Field(default="{}")
    created_at: datetime = Field(index=True)

    def params_dict(self) -> dict:
        """The parsed params JSON (empty dict if unreadable)."""
        try:
            parsed = json.loads(self.params)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
