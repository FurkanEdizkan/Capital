"""add research_report table for scheduled asset research

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0016'
down_revision: str | None = '0015'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'research_report',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('sections', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('error', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_research_report_symbol'), 'research_report', ['symbol'], unique=False
    )
    op.create_index(
        op.f('ix_research_report_status'), 'research_report', ['status'], unique=False
    )
    op.create_index(
        op.f('ix_research_report_created_at'),
        'research_report',
        ['created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_research_report_created_at'), table_name='research_report')
    op.drop_index(op.f('ix_research_report_status'), table_name='research_report')
    op.drop_index(op.f('ix_research_report_symbol'), table_name='research_report')
    op.drop_table('research_report')
