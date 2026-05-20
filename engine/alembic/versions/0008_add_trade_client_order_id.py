"""add client_order_id to trade

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-21 02:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Nullable — trades placed before live trading have no exchange order id.
    op.add_column(
        'trade',
        sa.Column(
            'client_order_id',
            sqlmodel.sql.sqltypes.AutoString(length=40),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('trade', 'client_order_id')
