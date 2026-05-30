/**
 * Connections — the asset relationship graph. Select a node to see its edges,
 * ask the AI to suggest new connections, and approve or reject suggestions.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { ConnectionsGraph } from "../components/ConnectionsGraph";
import { GuideButton } from "../components/GuideModal";
import { I } from "../components/icons";
import { Badge, Button, Card, EmptyState, SectionHeader, Toggle } from "../components/ui";
import { useAuth } from "../lib/auth";
import {
  approveEdge,
  deleteEdge,
  fetchGraph,
  type GraphEdge,
  type GraphNode,
  suggestConnections,
} from "../lib/api/connections";

export function Connections() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [includePending, setIncludePending] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const g = await fetchGraph(includePending);
      setNodes(g.nodes);
      setEdges(g.edges);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the graph");
    }
  }, [includePending]);

  useEffect(() => {
    void load();
  }, [load]);

  const selected = useMemo(
    () => nodes.find((n) => n.id === selectedId) ?? null,
    [nodes, selectedId],
  );
  const nodeLabel = useCallback(
    (id?: number | null) => nodes.find((n) => n.id === id)?.label ?? "?",
    [nodes],
  );
  const selectedEdges = useMemo(
    () =>
      edges.filter(
        (e) => e.source_id === selectedId || e.target_id === selectedId,
      ),
    [edges, selectedId],
  );

  const suggest = async () => {
    if (selectedId == null) return;
    setBusy(true);
    try {
      await suggestConnections(selectedId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suggestion failed");
    } finally {
      setBusy(false);
    }
  };

  const onApprove = async (id: number) => {
    await approveEdge(id);
    await load();
  };
  const onDelete = async (id: number) => {
    await deleteEdge(id);
    await load();
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
      <Card padding={0}>
        <SectionHeader
          title={
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              Graph <GuideButton slug="connections" />
            </span>
          }
          subtitle="Assets, products and the relations between them"
          right={
            <Toggle
              checked={includePending}
              onChange={setIncludePending}
              label="Show pending"
            />
          }
        />
        <div style={{ padding: 12 }}>
          {nodes.length === 0 ? (
            <EmptyState
              icon={<I.Connections size={20} />}
              title="No graph yet"
              body="The connections graph is seeded on startup."
            />
          ) : (
            <ConnectionsGraph
              nodes={nodes}
              edges={edges}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </div>
      </Card>

      <Card padding={16} style={{ alignSelf: "start" }}>
        {error && (
          <div style={{ color: "var(--red)", fontSize: 12.5, marginBottom: 8 }}>{error}</div>
        )}
        {selected == null ? (
          <div style={{ color: "var(--text-3)", fontSize: 12.5 }}>
            Select a node to see its connections.
          </div>
        ) : (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ fontSize: 18 }}>{selected.icon}</span>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{selected.label}</div>
            </div>
            <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
              <Badge tone="muted">{selected.kind}</Badge>
              {selected.symbol && <Badge tone="muted">{selected.symbol}</Badge>}
            </div>
            {isAdmin && (
              <Button kind="outline" size="sm" full onClick={suggest} disabled={busy}>
                {busy ? "Asking AI…" : "AI-suggest connections"}
              </Button>
            )}
            <div style={{ marginTop: 14, fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: ".05em" }}>
              Edges
            </div>
            {selectedEdges.length === 0 ? (
              <div style={{ color: "var(--text-4)", fontSize: 12.5, marginTop: 6 }}>None.</div>
            ) : (
              selectedEdges.map((e) => {
                const otherId = e.source_id === selectedId ? e.target_id : e.source_id;
                return (
                  <div
                    key={e.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "8px 0",
                      borderBottom: "1px solid var(--border-soft)",
                    }}
                  >
                    <div style={{ flex: 1, fontSize: 12.5 }}>
                      <span style={{ color: "var(--text-3)" }}>{e.relation}</span>{" "}
                      <span style={{ color: "var(--text)" }}>{nodeLabel(otherId)}</span>
                    </div>
                    {!e.approved && <Badge tone="amber">pending</Badge>}
                    {isAdmin && !e.approved && (
                      <Button kind="soft" size="sm" onClick={() => e.id != null && onApprove(e.id)}>
                        Approve
                      </Button>
                    )}
                    {isAdmin && (
                      <Button kind="ghost" size="sm" onClick={() => e.id != null && onDelete(e.id)}>
                        ✕
                      </Button>
                    )}
                  </div>
                );
              })
            )}
          </>
        )}
      </Card>
    </div>
  );
}
