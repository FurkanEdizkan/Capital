"""add news_item table for stored RSS headlines

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: str | None = '0012'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'news_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column('url', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=False),
        sa.Column('summary', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=True),
        sa.Column('sentiment', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_news_item_source'), 'news_item', ['source'], unique=False)
    op.create_index(op.f('ix_news_item_url'), 'news_item', ['url'], unique=True)
    op.create_index(op.f('ix_news_item_category'), 'news_item', ['category'], unique=False)
    op.create_index(op.f('ix_news_item_symbol'), 'news_item', ['symbol'], unique=False)
    op.create_index(op.f('ix_news_item_published_at'), 'news_item', ['published_at'], unique=False)
    op.create_index(op.f('ix_news_item_fetched_at'), 'news_item', ['fetched_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_news_item_fetched_at'), table_name='news_item')
    op.drop_index(op.f('ix_news_item_published_at'), table_name='news_item')
    op.drop_index(op.f('ix_news_item_symbol'), table_name='news_item')
    op.drop_index(op.f('ix_news_item_category'), table_name='news_item')
    op.drop_index(op.f('ix_news_item_url'), table_name='news_item')
    op.drop_index(op.f('ix_news_item_source'), table_name='news_item')
    op.drop_table('news_item')
