"""add ai_signal table for notify-mode AI decisions

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-30 00:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: str | None = '0014'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'ai_signal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
        sa.Column('market', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('reasoning', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('reference_price', sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_signal_strategy'), 'ai_signal', ['strategy'], unique=False)
    op.create_index(op.f('ix_ai_signal_symbol'), 'ai_signal', ['symbol'], unique=False)
    op.create_index(op.f('ix_ai_signal_status'), 'ai_signal', ['status'], unique=False)
    op.create_index(op.f('ix_ai_signal_created_at'), 'ai_signal', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_signal_created_at'), table_name='ai_signal')
    op.drop_index(op.f('ix_ai_signal_status'), table_name='ai_signal')
    op.drop_index(op.f('ix_ai_signal_symbol'), table_name='ai_signal')
    op.drop_index(op.f('ix_ai_signal_strategy'), table_name='ai_signal')
    op.drop_table('ai_signal')
