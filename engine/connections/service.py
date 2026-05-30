"""Connections graph service — read the graph, suggest edges, curate them.

`graph` returns the nodes and edges (approved-only by default). `neighbours`
returns a symbol's directly-related node labels — the AI decision prompt folds
these in. `suggest` asks the configured LLM for related entities and stores
them unapproved; `approve`/`delete` and `create_node` curate the result.
"""

import json
import logging
import re
from datetime import UTC, datetime

from sqlmodel import Session, select

from ai.providers.base import LLMError, LLMProvider
from ai.usage import record_usage
from connections.models import GraphEdge, GraphNode

log = logging.getLogger("capital.connections")

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def graph(
    session: Session, *, include_pending: bool = False
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """All nodes and edges. Pending (AI-suggested) edges are opt-in."""
    nodes = list(session.exec(select(GraphNode)).all())
    edge_stmt = select(GraphEdge)
    if not include_pending:
        edge_stmt = edge_stmt.where(GraphEdge.approved == True)  # noqa: E712
    edges = list(session.exec(edge_stmt).all())
    return nodes, edges


def neighbours(session: Session, symbol: str, *, limit: int = 12) -> list[str]:
    """Labels of nodes directly related to the asset `symbol` (approved edges).

    Used to enrich the AI decision prompt — e.g. for ``NVDA`` this surfaces
    ``GPU chip`` and ``AI compute``. Returns at most `limit` labels.
    """
    node = session.exec(
        select(GraphNode).where(GraphNode.symbol == symbol)
    ).first()
    if node is None:
        return []
    edges = session.exec(
        select(GraphEdge).where(
            GraphEdge.approved == True,  # noqa: E712
            (GraphEdge.source_id == node.id) | (GraphEdge.target_id == node.id),
        )
    ).all()
    other_ids = {
        (e.target_id if e.source_id == node.id else e.source_id) for e in edges
    }
    labels: list[str] = []
    for nid in other_ids:
        other = session.get(GraphNode, nid)
        if other is not None:
            labels.append(other.label)
        if len(labels) >= limit:
            break
    return labels


def _get_or_create_node(session: Session, label: str, kind: str) -> GraphNode:
    """Find a node by label or create a concept/product node for it."""
    node = session.exec(
        select(GraphNode).where(GraphNode.label == label)
    ).first()
    if node is None:
        node = GraphNode(label=label[:120], kind=kind)
        session.add(node)
        session.commit()
        session.refresh(node)
    return node


def create_node(
    session: Session,
    *,
    label: str,
    kind: str = "concept",
    symbol: str | None = None,
    icon: str | None = None,
) -> GraphNode:
    """Create (or return the existing) node for `label`."""
    node = session.exec(
        select(GraphNode).where(GraphNode.label == label)
    ).first()
    if node is not None:
        return node
    node = GraphNode(label=label[:120], kind=kind, symbol=symbol, icon=icon)
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


def approve(session: Session, edge_id: int) -> GraphEdge | None:
    """Mark a pending edge approved. Returns the edge, or None if missing."""
    edge = session.get(GraphEdge, edge_id)
    if edge is None:
        return None
    edge.approved = True
    session.add(edge)
    session.commit()
    session.refresh(edge)
    return edge


def delete_edge(session: Session, edge_id: int) -> bool:
    """Delete an edge. Returns True when a row was removed."""
    edge = session.get(GraphEdge, edge_id)
    if edge is None:
        return False
    session.delete(edge)
    session.commit()
    return True


_SUGGEST_INSTRUCTION = (
    "List up to 6 entities (companies, products, concepts or assets) closely "
    "related to the subject. Respond ONLY with a JSON array of objects of the "
    'form [{"label": "<name>", "kind": "asset"|"product"|"concept", '
    '"relation": "<short relation, e.g. supplies, competes_with, pegged_to>"}].'
)


def suggest(
    session: Session,
    node_id: int,
    *,
    provider: LLMProvider,
    model: str | None = None,
) -> list[GraphEdge]:
    """Ask the LLM for entities related to a node; store them unapproved.

    Returns the newly-created (pending) edges. Raises `LLMError` if the call
    fails or returns nothing parseable.
    """
    node = session.get(GraphNode, node_id)
    if node is None:
        raise LLMError(f"unknown node id {node_id}")

    prompt = (
        f"Subject: {node.label}"
        + (f" (asset symbol {node.symbol})" if node.symbol else "")
        + f".\n{_SUGGEST_INSTRUCTION}"
    )
    completion = provider.complete(prompt, model=model)
    record_usage(
        session,
        provider=completion.provider,
        model=completion.model,
        input_tokens=completion.input_tokens,
        output_tokens=completion.output_tokens,
        strategy="connections.suggest",
    )

    match = _JSON_ARRAY_RE.search(completion.text)
    if not match:
        raise LLMError("no JSON array in suggestion response")
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"could not parse suggestions: {exc}") from exc

    created: list[GraphEdge] = []
    now = _utcnow()
    for item in raw:
        label = str(item.get("label", "")).strip()
        if not label or label.lower() == node.label.lower():
            continue
        kind = str(item.get("kind", "concept"))
        relation = str(item.get("relation", "related"))[:40]
        other = _get_or_create_node(session, label, kind)
        exists = session.exec(
            select(GraphEdge).where(
                GraphEdge.source_id == node.id,
                GraphEdge.target_id == other.id,
                GraphEdge.relation == relation,
            )
        ).first()
        if exists is not None:
            continue
        edge = GraphEdge(
            source_id=node.id,  # type: ignore[arg-type]
            target_id=other.id,  # type: ignore[arg-type]
            relation=relation,
            origin="ai",
            approved=False,
            created_at=now,
        )
        session.add(edge)
        created.append(edge)
    session.commit()
    for edge in created:
        session.refresh(edge)
    return created
