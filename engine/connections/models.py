"""Connections graph database models — nodes and the edges between them.

A `GraphNode` is an asset, product or concept; a `GraphEdge` is a directed,
labelled relation between two nodes. Curated rows are seeded `approved=True`;
AI-suggested rows arrive `approved=False` and `origin="ai"` until an operator
approves them, so model output never silently enters the graph.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class GraphNode(SQLModel, table=True):
    """A node: an asset, a product, or a concept."""

    __tablename__ = "graph_node"
    __table_args__ = (UniqueConstraint("label", name="uq_graph_node_label"),)

    id: int | None = Field(default=None, primary_key=True)
    label: str = Field(max_length=120, index=True)
    # asset | product | concept
    kind: str = Field(default="concept", max_length=16, index=True)
    # The trading symbol when this node is a tradeable asset (else null).
    symbol: str | None = Field(default=None, max_length=24, index=True)
    # An emoji or short slug used as the node's icon in the UI (optional).
    icon: str | None = Field(default=None, max_length=32)


class GraphEdge(SQLModel, table=True):
    """A directed, labelled relation from one node to another."""

    __tablename__ = "graph_edge"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "target_id", "relation", name="uq_graph_edge"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="graph_node.id", index=True)
    target_id: int = Field(foreign_key="graph_node.id", index=True)
    relation: str = Field(default="related", max_length=40)
    weight: Decimal = Field(default=Decimal(1), max_digits=6, decimal_places=2)
    # seed | ai — where the edge came from.
    origin: str = Field(default="seed", max_length=8, index=True)
    approved: bool = Field(default=True, index=True)
    created_at: datetime | None = Field(default=None)
