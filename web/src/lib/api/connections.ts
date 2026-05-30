/** Connections API helpers — the relationship graph and its curation. */
import { api } from "./client";
import type { components } from "./schema";

export type GraphNode = components["schemas"]["GraphNode"];
export type GraphEdge = components["schemas"]["GraphEdge"];
export type GraphView = components["schemas"]["GraphView"];

export async function fetchGraph(includePending = false): Promise<GraphView> {
  const { data, error } = await api.GET("/api/connections/graph", {
    params: { query: { include_pending: includePending } },
  });
  if (error || !data) throw new Error("Failed to load the connections graph");
  return data;
}

export async function suggestConnections(nodeId: number): Promise<GraphEdge[]> {
  const { data, error } = await api.POST("/api/connections/suggest/{node_id}", {
    params: { path: { node_id: nodeId } },
  });
  if (error || !data) throw new Error("AI suggestion failed");
  return data;
}

export async function approveEdge(edgeId: number): Promise<GraphEdge> {
  const { data, error } = await api.POST("/api/connections/edges/{edge_id}/approve", {
    params: { path: { edge_id: edgeId } },
  });
  if (error || !data) throw new Error("Failed to approve the edge");
  return data;
}

export async function deleteEdge(edgeId: number): Promise<void> {
  const { error } = await api.DELETE("/api/connections/edges/{edge_id}", {
    params: { path: { edge_id: edgeId } },
  });
  if (error) throw new Error("Failed to delete the edge");
}

export async function createNode(opts: {
  label: string;
  kind?: string;
  symbol?: string | null;
  icon?: string | null;
}): Promise<GraphNode> {
  const { data, error } = await api.POST("/api/connections/nodes", {
    body: { kind: "concept", ...opts },
  });
  if (error || !data) throw new Error("Failed to create the node");
  return data;
}
