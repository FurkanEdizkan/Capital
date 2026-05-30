/**
 * News — world and per-asset headlines, refreshed daily by the engine.
 * Filter by symbol to see only one asset's news; admins can refresh on demand.
 */
import { useCallback, useEffect, useState } from "react";

import { GuideButton } from "../components/GuideModal";
import { I } from "../components/icons";
import { Badge, Button, Card, EmptyState, Input, SectionHeader } from "../components/ui";
import { useAuth } from "../lib/auth";
import { fetchNews, type NewsItem, refreshNews } from "../lib/api/news";

const when = (iso?: string | null): string =>
  iso ? iso.slice(0, 16).replace("T", " ") : "";

export function News() {
  const { user } = useAuth();
  const [items, setItems] = useState<NewsItem[]>([]);
  const [symbol, setSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setItems(await fetchNews(symbol.trim() || undefined));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load news");
    }
  }, [symbol]);

  useEffect(() => {
    void load();
  }, [load]);

  const refresh = async () => {
    setBusy(true);
    try {
      await refreshNews();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card padding={0}>
      <SectionHeader
        title={
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            Headlines <GuideButton slug="news" />
          </span>
        }
        subtitle="World news and per-asset coverage"
        right={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="Filter symbol (e.g. BTCUSDT)"
              size="sm"
              prefix={<I.Search size={14} />}
            />
            {user?.role === "admin" && (
              <Button kind="outline" size="sm" onClick={refresh} disabled={busy}>
                {busy ? "Refreshing…" : "Refresh"}
              </Button>
            )}
          </div>
        }
      />
      {error && (
        <div style={{ padding: "10px 16px", color: "var(--red)", fontSize: 12.5 }}>
          {error}
        </div>
      )}
      {items.length === 0 ? (
        <EmptyState
          icon={<I.News size={20} />}
          title="No headlines yet"
          body="News is refreshed daily. Admins can trigger a refresh from the button above."
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {items.map((n) => (
            <a
              key={n.id}
              href={n.url}
              target="_blank"
              rel="noreferrer"
              style={{
                display: "block",
                padding: "12px 16px",
                borderTop: "1px solid var(--border-soft)",
              }}
            >
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                {n.symbol && <Badge tone="muted">{n.symbol}</Badge>}
                <span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{n.source}</span>
                <span style={{ fontSize: 11.5, color: "var(--text-4)", marginLeft: "auto" }}>
                  {when(n.published_at)}
                </span>
              </div>
              <div style={{ fontSize: 13.5, color: "var(--text)", fontWeight: 500 }}>
                {n.title}
              </div>
            </a>
          ))}
        </div>
      )}
    </Card>
  );
}
