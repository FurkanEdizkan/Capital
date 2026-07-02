"""add purpose column to llm_usage for cost attribution

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0020'
down_revision: str | None = '0019'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'llm_usage',
        sa.Column(
            'purpose',
            sqlmodel.sql.sqltypes.AutoString(length=16),
            nullable=False,
            server_default='analyze',
        ),
    )
    op.create_index(op.f('ix_llm_usage_purpose'), 'llm_usage', ['purpose'], unique=False)
    # Backfill: rows tied to a strategy were per-tick decisions; the rest were
    # one-off analyze calls (the only two purposes that existed before this).
    op.execute("UPDATE llm_usage SET purpose = 'strategy' WHERE strategy IS NOT NULL")


def downgrade() -> None:
    op.drop_index(op.f('ix_llm_usage_purpose'), table_name='llm_usage')
    op.drop_column('llm_usage', 'purpose')
