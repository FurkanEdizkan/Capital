"""add strategy_instance table for operator-created strategies

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0019'
down_revision: str | None = '0018'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'strategy_instance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
        sa.Column('market', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('timeframe', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('params', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_strategy_instance_name'), 'strategy_instance', ['name'], unique=True)
    op.create_index(op.f('ix_strategy_instance_type'), 'strategy_instance', ['type'], unique=False)
    op.create_index(op.f('ix_strategy_instance_symbol'), 'strategy_instance', ['symbol'], unique=False)
    op.create_index(
        op.f('ix_strategy_instance_created_at'), 'strategy_instance', ['created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_strategy_instance_created_at'), table_name='strategy_instance')
    op.drop_index(op.f('ix_strategy_instance_symbol'), table_name='strategy_instance')
    op.drop_index(op.f('ix_strategy_instance_type'), table_name='strategy_instance')
    op.drop_index(op.f('ix_strategy_instance_name'), table_name='strategy_instance')
    op.drop_table('strategy_instance')
