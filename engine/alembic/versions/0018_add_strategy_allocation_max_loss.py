"""add max_loss column to strategy_allocation for the per-strategy loss cap

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0018'
down_revision: str | None = '0017'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'strategy_allocation',
        sa.Column(
            'max_loss',
            sa.Numeric(precision=28, scale=10),
            nullable=False,
            server_default='0',
        ),
    )


def downgrade() -> None:
    op.drop_column('strategy_allocation', 'max_loss')
