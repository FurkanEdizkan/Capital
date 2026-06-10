"""add feed_latency table for price-feed latency rollups

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0021'
down_revision: str | None = '0020'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'feed_latency',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('market', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
        sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('samples', sa.Integer(), nullable=False),
        sa.Column('avg_ms', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('p95_ms', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('max_ms', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_feed_latency_market'), 'feed_latency', ['market'], unique=False)
    op.create_index(op.f('ix_feed_latency_symbol'), 'feed_latency', ['symbol'], unique=False)
    op.create_index(
        op.f('ix_feed_latency_recorded_at'), 'feed_latency', ['recorded_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_feed_latency_recorded_at'), table_name='feed_latency')
    op.drop_index(op.f('ix_feed_latency_symbol'), table_name='feed_latency')
    op.drop_index(op.f('ix_feed_latency_market'), table_name='feed_latency')
    op.drop_table('feed_latency')
