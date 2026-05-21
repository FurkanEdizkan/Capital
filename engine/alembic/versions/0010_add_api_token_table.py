"""add api_token table

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-21 06:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'api_token',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('token_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_api_token_token_hash'), 'api_token', ['token_hash'], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_api_token_token_hash'), table_name='api_token')
    op.drop_table('api_token')
