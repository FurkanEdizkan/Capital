"""Tests for the connections graph — seed, query, neighbours, AI suggest."""

from sqlmodel import Session, select

from ai.providers.base import Completion, LLMProvider
from connections import service
from connections.models import GraphEdge, GraphNode
from connections.seed import ensure_seed


class FakeProvider(LLMProvider):
    """Returns a canned JSON array of suggested connections."""

    name = "fake"

    def __init__(self, text: str) -> None:
        self._text = text

    def complete(self, prompt: str, *, model: str | None = None) -> Completion:
        return Completion(
            text=self._text,
            provider=self.name,
            model=model or "fake-model",
            input_tokens=10,
            output_tokens=5,
        )


def test_ensure_seed_is_idempotent(session: Session) -> None:
    ensure_seed(session)
    nodes_first = len(session.exec(select(GraphNode)).all())
    edges_first = len(session.exec(select(GraphEdge)).all())
    assert nodes_first > 0 and edges_first > 0
    ensure_seed(session)  # second run adds nothing
    assert len(session.exec(select(GraphNode)).all()) == nodes_first
    assert len(session.exec(select(GraphEdge)).all()) == edges_first


def test_graph_excludes_pending_by_default(session: Session) -> None:
    ensure_seed(session)
    nodes, edges = service.graph(session)
    assert all(e.approved for e in edges)
    assert any(n.symbol == "BTCUSDT" for n in nodes)


def test_neighbours_returns_related_labels(session: Session) -> None:
    ensure_seed(session)
    labels = service.neighbours(session, "NVDA")
    assert "GPU chip" in labels


def test_suggest_inserts_unapproved_edges(session: Session) -> None:
    ensure_seed(session)
    node = session.exec(
        select(GraphNode).where(GraphNode.symbol == "BTCUSDT")
    ).first()
    provider = FakeProvider(
        '[{"label": "Mining hardware", "kind": "product", "relation": "secured_by"}]'
    )
    created = service.suggest(session, node.id, provider=provider)
    assert len(created) == 1
    assert created[0].origin == "ai"
    assert created[0].approved is False
    # The pending edge is hidden until approved.
    _, approved_edges = service.graph(session)
    assert all(e.id != created[0].id for e in approved_edges)
    # Approve it and it joins the graph.
    service.approve(session, created[0].id)
    _, approved_edges = service.graph(session)
    assert any(e.id == created[0].id for e in approved_edges)


def test_delete_edge(session: Session) -> None:
    ensure_seed(session)
    edge = session.exec(select(GraphEdge)).first()
    assert service.delete_edge(session, edge.id) is True
    assert service.delete_edge(session, edge.id) is False
