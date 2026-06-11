"""per-strategy venue routing — venue columns + wide symbols for token ids

Polymarket outcome-token ids are ~77-character numeric strings; every column
that stores a tradeable symbol widens from 24 to 80. `strategy_instance` and
`ai_signal` gain a `venue` column so strategies (and their signals) on
different venues run side by side.

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0022'
down_revision: str | None = '0021'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_VENUE = sqlmodel.sql.sqltypes.AutoString(length=24)
_WIDE = sqlmodel.sql.sqltypes.AutoString(length=80)
_NARROW = sqlmodel.sql.sqltypes.AutoString(length=24)

#: Every (table, column) that stores a tradeable symbol.
_SYMBOL_COLUMNS = (
    ('position', 'symbol'),
    ('trade', 'symbol'),
    ('candle', 'symbol'),
    ('feed_latency', 'symbol'),
    ('strategy_instance', 'symbol'),
    ('ai_signal', 'symbol'),
)


def upgrade() -> None:
    for table, column in _SYMBOL_COLUMNS:
        op.alter_column(table, column, type_=_WIDE, existing_nullable=False)
    op.add_column(
        'strategy_instance',
        sa.Column('venue', _VENUE, nullable=False, server_default='binance'),
    )
    op.add_column(
        'ai_signal',
        sa.Column('venue', _VENUE, nullable=False, server_default='binance'),
    )


def downgrade() -> None:
    op.drop_column('ai_signal', 'venue')
    op.drop_column('strategy_instance', 'venue')
    for table, column in _SYMBOL_COLUMNS:
        op.alter_column(table, column, type_=_NARROW, existing_nullable=False)
