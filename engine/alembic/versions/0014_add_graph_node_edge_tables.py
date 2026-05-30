"""add graph_node and graph_edge tables for the connections graph

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-30 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: str | None = '0013'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'graph_node',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=True),
        sa.Column('icon', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('label', name='uq_graph_node_label'),
    )
    op.create_index(op.f('ix_graph_node_label'), 'graph_node', ['label'], unique=False)
    op.create_index(op.f('ix_graph_node_kind'), 'graph_node', ['kind'], unique=False)
    op.create_index(op.f('ix_graph_node_symbol'), 'graph_node', ['symbol'], unique=False)

    op.create_table(
        'graph_edge',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('relation', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column('weight', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
        sa.Column('approved', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['graph_node.id']),
        sa.ForeignKeyConstraint(['target_id'], ['graph_node.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_id', 'target_id', 'relation', name='uq_graph_edge'),
    )
    op.create_index(op.f('ix_graph_edge_source_id'), 'graph_edge', ['source_id'], unique=False)
    op.create_index(op.f('ix_graph_edge_target_id'), 'graph_edge', ['target_id'], unique=False)
    op.create_index(op.f('ix_graph_edge_origin'), 'graph_edge', ['origin'], unique=False)
    op.create_index(op.f('ix_graph_edge_approved'), 'graph_edge', ['approved'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_graph_edge_approved'), table_name='graph_edge')
    op.drop_index(op.f('ix_graph_edge_origin'), table_name='graph_edge')
    op.drop_index(op.f('ix_graph_edge_target_id'), table_name='graph_edge')
    op.drop_index(op.f('ix_graph_edge_source_id'), table_name='graph_edge')
    op.drop_table('graph_edge')
    op.drop_index(op.f('ix_graph_node_symbol'), table_name='graph_node')
    op.drop_index(op.f('ix_graph_node_kind'), table_name='graph_node')
    op.drop_index(op.f('ix_graph_node_label'), table_name='graph_node')
    op.drop_table('graph_node')
