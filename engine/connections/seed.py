"""Curated seed for the connections graph.

`ensure_seed` inserts the bundled `seed.json` nodes/edges idempotently — it is
called on startup and is safe to run every boot: existing labels/edges are left
untouched, so an operator's later edits are never clobbered.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from connections.models import GraphEdge, GraphNode

log = logging.getLogger("capital.connections")

_SEED_PATH = Path(__file__).with_name("seed.json")


def ensure_seed(session: Session) -> None:
    """Insert any missing seed nodes/edges. Idempotent."""
    data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    now = datetime.now(UTC).replace(tzinfo=None)

    label_to_id: dict[str, int] = {}
    for spec in data.get("nodes", []):
        label = spec["label"]
        node = session.exec(
            select(GraphNode).where(GraphNode.label == label)
        ).first()
        if node is None:
            node = GraphNode(
                label=label,
                kind=spec.get("kind", "concept"),
                symbol=spec.get("symbol"),
                icon=spec.get("icon"),
            )
            session.add(node)
            session.commit()
            session.refresh(node)
        label_to_id[label] = node.id  # type: ignore[assignment]

    for spec in data.get("edges", []):
        src = label_to_id.get(spec["source"])
        dst = label_to_id.get(spec["target"])
        relation = spec.get("relation", "related")
        if src is None or dst is None:
            continue
        exists = session.exec(
            select(GraphEdge).where(
                GraphEdge.source_id == src,
                GraphEdge.target_id == dst,
                GraphEdge.relation == relation,
            )
        ).first()
        if exists is None:
            session.add(
                GraphEdge(
                    source_id=src,
                    target_id=dst,
                    relation=relation,
                    origin="seed",
                    approved=True,
                    created_at=now,
                )
            )
    session.commit()
    log.info("connections seed ensured (%d nodes)", len(label_to_id))
