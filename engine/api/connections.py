"""Connections API — the relationship graph and its curation.

Read the graph for the Connections page; ask the configured LLM to suggest
related entities for a node (admin); approve or delete edges. AI-suggested
edges arrive `approved=False` and are excluded from the default graph view
until an operator approves them.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ai.providers import LLMError, get_provider
from ai.providers.base import LLMProvider
from appsettings.store import get_ai_api_key, get_ai_settings
from auth.deps import CurrentUser, SessionDep, require_admin
from auth.models import User
from connections import service
from connections.models import GraphEdge, GraphNode

router = APIRouter(prefix="/api/connections", tags=["connections"])

AdminUser = Annotated[User, Depends(require_admin)]


def get_llm_provider(session: SessionDep) -> LLMProvider:
    """The LLM provider built from the stored AI settings."""
    ai = get_ai_settings(session)
    return get_provider(
        ai["provider"], api_key=get_ai_api_key(session), base_url=ai["base_url"]
    )


ProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]


class GraphView(BaseModel):
    """The connections graph — nodes and the edges between them."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NodeCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    kind: str = "concept"
    symbol: str | None = None
    icon: str | None = None


@router.get("/graph", response_model=GraphView)
def get_graph(
    _: CurrentUser, session: SessionDep, include_pending: bool = False
) -> GraphView:
    """The full graph. Pending (AI-suggested) edges are opt-in."""
    nodes, edges = service.graph(session, include_pending=include_pending)
    return GraphView(nodes=nodes, edges=edges)


@router.post("/nodes", response_model=GraphNode)
def create_node(
    body: NodeCreate, _: AdminUser, session: SessionDep
) -> GraphNode:
    """Create a node (or return the existing one with the same label)."""
    return service.create_node(
        session, label=body.label, kind=body.kind, symbol=body.symbol, icon=body.icon
    )


@router.post("/suggest/{node_id}", response_model=list[GraphEdge])
def suggest_connections(
    node_id: int, _: AdminUser, session: SessionDep, provider: ProviderDep
) -> list[GraphEdge]:
    """Ask the LLM to suggest related entities for a node (stored pending)."""
    model = get_ai_settings(session)["model"] or None
    try:
        return service.suggest(session, node_id, provider=provider, model=model)
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"suggestion failed: {exc}"
        ) from exc


@router.post("/edges/{edge_id}/approve", response_model=GraphEdge)
def approve_edge(edge_id: int, _: AdminUser, session: SessionDep) -> GraphEdge:
    """Approve a pending edge so it joins the graph."""
    edge = service.approve(session, edge_id)
    if edge is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edge not found")
    return edge


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edge(edge_id: int, _: AdminUser, session: SessionDep) -> None:
    """Delete an edge (reject a suggestion or prune a curated link)."""
    if not service.delete_edge(session, edge_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "edge not found")
