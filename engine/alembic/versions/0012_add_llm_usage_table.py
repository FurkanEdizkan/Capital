"""add llm_usage table for AI cost tracking

Records every LLM completion — provider, model, token counts, estimated
cost and the decision it produced — so AI spend can be shown and capped.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-21 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: str | None = '0011'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'llm_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('strategy', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('estimated_cost_usd', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_llm_usage_provider'), 'llm_usage', ['provider'])
    op.create_index(op.f('ix_llm_usage_model'), 'llm_usage', ['model'])
    op.create_index(op.f('ix_llm_usage_strategy'), 'llm_usage', ['strategy'])
    op.create_index(op.f('ix_llm_usage_created_at'), 'llm_usage', ['created_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_llm_usage_created_at'), table_name='llm_usage')
    op.drop_index(op.f('ix_llm_usage_strategy'), table_name='llm_usage')
    op.drop_index(op.f('ix_llm_usage_model'), table_name='llm_usage')
    op.drop_index(op.f('ix_llm_usage_provider'), table_name='llm_usage')
    op.drop_table('llm_usage')
