"""Research report database model — one stored report per asset per run.

A report's `sections` column holds the full schema-formatted content as a
JSON object (see `research.service.SECTION_KEYS`): mechanical sections
(headlines, connections, technicals) assembled from stored data, and
narrative sections written by the configured report-writer LLM. Reports are
insert-only; a new run writes a new row so history is browsable.
"""

import json
from datetime import datetime

from sqlmodel import Field, SQLModel

#: Bumped when the shape of `sections` changes, so old rows stay readable.
SCHEMA_VERSION = 1


class ResearchReport(SQLModel, table=True):
    """One generated research report for an asset."""

    __tablename__ = "research_report"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, max_length=24)
    schema_version: int = Field(default=SCHEMA_VERSION)
    # `written` (narrative complete) or `failed` (writer errored — the
    # mechanical sections are still stored). PR: council adds `reviewed`.
    status: str = Field(default="written", max_length=16, index=True)
    # JSON object — parsed via `sections_dict()`.
    sections: str = Field(default="{}")
    provider: str = Field(default="", max_length=16)
    model: str = Field(default="", max_length=64)
    error: str = Field(default="", max_length=512)
    created_at: datetime = Field(index=True)

    def sections_dict(self) -> dict:
        """The parsed `sections` JSON (empty dict if unreadable)."""
        try:
            parsed = json.loads(self.sections)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
