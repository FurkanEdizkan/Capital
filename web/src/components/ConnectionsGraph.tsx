/**
 * Connections graph — a force-directed SVG view of nodes and edges.
 *
 * The layout is computed once per data change with d3-force (run to a settled
 * state, then frozen — no animation), so the render is a plain static SVG.
 * Approved edges are solid; pending AI suggestions are dashed. Clicking a node
 * selects it (the page panel then offers AI-suggest and per-edge curation).
 */
import { useMemo } from "react";
import {
  forceCenter,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";

import type { GraphEdge, GraphNode } from "../lib/api/connections";

const WIDTH = 720;
const HEIGHT = 460;

type SimNode = GraphNode & SimulationNodeDatum;
type SimLink = SimulationLinkDatum<SimNode> & { edge: GraphEdge };

export function ConnectionsGraph({
  nodes,
  edges,
  selectedId,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const layout = useMemo(() => {
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }));
    const byId = new Map(simNodes.map((n) => [n.id, n]));
    const simLinks: SimLink[] = edges
      .filter((e) => byId.has(e.source_id) && byId.has(e.target_id))
      .map((e) => ({ source: e.source_id!, target: e.target_id!, edge: e }));

    const sim = forceSimulation(simNodes)
      .force(
        "link",
        forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id as number)
          .distance(90)
          .strength(0.4),
      )
      .force("charge", forceManyBody().strength(-260))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .stop();
    sim.tick(320); // settle synchronously, then freeze
    return { simNodes, simLinks };
  }, [nodes, edges]);

  const clamp = (v: number, max: number) => Math.max(18, Math.min(max - 18, v));

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      style={{ display: "block", background: "var(--surface)", borderRadius: 8 }}
    >
      {layout.simLinks.map((l) => {
        const s = l.source as SimNode;
        const t = l.target as SimNode;
        const pending = !l.edge.approved;
        return (
          <g key={l.edge.id}>
            <line
              x1={clamp(s.x ?? 0, WIDTH)}
              y1={clamp(s.y ?? 0, HEIGHT)}
              x2={clamp(t.x ?? 0, WIDTH)}
              y2={clamp(t.y ?? 0, HEIGHT)}
              stroke={pending ? "var(--text-4)" : "var(--border)"}
              strokeWidth={1.2}
              strokeDasharray={pending ? "4 3" : undefined}
            />
          </g>
        );
      })}
      {layout.simNodes.map((n) => {
        const x = clamp(n.x ?? 0, WIDTH);
        const y = clamp(n.y ?? 0, HEIGHT);
        const isAsset = n.kind === "asset";
        const isSelected = n.id === selectedId;
        return (
          <g
            key={n.id}
            transform={`translate(${x},${y})`}
            style={{ cursor: "pointer" }}
            onClick={() => n.id != null && onSelect(n.id)}
          >
            <circle
              r={isAsset ? 18 : 14}
              fill={isAsset ? "var(--card-2)" : "var(--surface)"}
              stroke={isSelected ? "var(--text)" : "var(--border)"}
              strokeWidth={isSelected ? 2 : 1.2}
            />
            {n.icon && (
              <text textAnchor="middle" dy="0.35em" fontSize="13">
                {n.icon}
              </text>
            )}
            <text
              textAnchor="middle"
              y={isAsset ? 32 : 28}
              fontSize="10.5"
              fill="var(--text-2)"
            >
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
