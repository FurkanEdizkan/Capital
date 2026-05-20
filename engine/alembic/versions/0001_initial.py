"""initial baseline

Revision ID: 0001
Revises:
Create Date: 2026-05-20

The baseline revision. It creates no tables — it exists so every later phase's
migration has a parent and `alembic upgrade head` is meaningful from an empty
database. Phase 0 auth (issue #3) adds the first real tables.
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
