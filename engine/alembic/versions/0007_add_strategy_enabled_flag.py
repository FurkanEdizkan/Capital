"""add enabled flag to strategy_allocation

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-21 02:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Existing strategies default to enabled. server_default keeps the NOT NULL
    # column valid for rows created before this migration.
    op.add_column(
        'strategy_allocation',
        sa.Column(
            'enabled', sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade() -> None:
    op.drop_column('strategy_allocation', 'enabled')
