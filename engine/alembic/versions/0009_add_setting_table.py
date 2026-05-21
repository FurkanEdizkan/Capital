"""add setting table for runtime mode and encrypted credentials

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-21 03:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'setting',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('value', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_secret', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_setting_key'), 'setting', ['key'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_setting_key'), table_name='setting')
    op.drop_table('setting')
