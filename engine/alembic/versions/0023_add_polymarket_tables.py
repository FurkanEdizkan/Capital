"""add prediction_market and market_analysis tables

The Polymarket market catalogue (discovered from the Gamma API, curated via a
`watched` flag) and the AI bet analyses written against it.

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-11 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0023'
down_revision: str | None = '0022'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_PRICE = sa.Numeric(precision=24, scale=8)


def upgrade() -> None:
    op.create_table(
        'prediction_market',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('condition_id', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column('question', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column('slug', sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('yes_token_id', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column('no_token_id', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column('outcomes', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('yes_price', _PRICE, nullable=False),
        sa.Column('volume_24h', _PRICE, nullable=False),
        sa.Column('liquidity', _PRICE, nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
        sa.Column(
            'resolved_outcome', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column('watched', sa.Boolean(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_prediction_market_condition_id'),
        'prediction_market',
        ['condition_id'],
        unique=True,
    )
    op.create_index(
        op.f('ix_prediction_market_category'), 'prediction_market', ['category'], unique=False
    )
    op.create_index(
        op.f('ix_prediction_market_end_date'), 'prediction_market', ['end_date'], unique=False
    )
    op.create_index(
        op.f('ix_prediction_market_yes_token_id'),
        'prediction_market',
        ['yes_token_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_prediction_market_status'), 'prediction_market', ['status'], unique=False
    )
    op.create_index(
        op.f('ix_prediction_market_watched'), 'prediction_market', ['watched'], unique=False
    )
    op.create_index(
        op.f('ix_prediction_market_fetched_at'),
        'prediction_market',
        ['fetched_at'],
        unique=False,
    )

    op.create_table(
        'market_analysis',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('condition_id', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
        sa.Column('question', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column('market_price', _PRICE, nullable=False),
        sa.Column('est_probability', _PRICE, nullable=False),
        sa.Column('edge', _PRICE, nullable=False),
        sa.Column(
            'recommendation', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False
        ),
        sa.Column('confidence', _PRICE, nullable=False),
        sa.Column('reasoning', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_market_analysis_condition_id'),
        'market_analysis',
        ['condition_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_market_analysis_created_at'), 'market_analysis', ['created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_market_analysis_created_at'), table_name='market_analysis')
    op.drop_index(op.f('ix_market_analysis_condition_id'), table_name='market_analysis')
    op.drop_table('market_analysis')
    for index in (
        'ix_prediction_market_fetched_at',
        'ix_prediction_market_watched',
        'ix_prediction_market_status',
        'ix_prediction_market_yes_token_id',
        'ix_prediction_market_end_date',
        'ix_prediction_market_category',
        'ix_prediction_market_condition_id',
    ):
        op.drop_index(op.f(index), table_name='prediction_market')
    op.drop_table('prediction_market')
