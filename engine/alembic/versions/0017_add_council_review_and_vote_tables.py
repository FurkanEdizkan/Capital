"""add council_review and council_vote tables for the AI council

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0017'
down_revision: str | None = '0016'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'council_review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('verdict', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('weighted_score', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('quorum_met', sa.Boolean(), nullable=False),
        sa.Column('strategy_brief', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['report_id'], ['research_report.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_council_review_report_id'), 'council_review', ['report_id'], unique=False
    )
    op.create_index(
        op.f('ix_council_review_created_at'), 'council_review', ['created_at'], unique=False
    )
    op.create_table(
        'council_vote',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column('reasoning', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(['review_id'], ['council_review.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_council_vote_review_id'), 'council_vote', ['review_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_council_vote_review_id'), table_name='council_vote')
    op.drop_table('council_vote')
    op.drop_index(op.f('ix_council_review_created_at'), table_name='council_review')
    op.drop_index(op.f('ix_council_review_report_id'), table_name='council_review')
    op.drop_table('council_review')
