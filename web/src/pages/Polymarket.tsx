/**
 * Polymarket — browse prediction markets, curate the AI's watchlist and read
 * its bet analyses (estimated probability vs market price = edge).
 *
 * The engine refreshes the catalogue and screens bets on a schedule;
 * suggestions it emits appear as pending AI signals on the Dashboard. Admins
 * can refresh the catalogue or run a one-off analysis from here.
 */
import { useCallback, useEffect, useState } from "react";

import { I } from "../components/icons";
import {
  Badge,
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  Input,
  SectionHeader,
  SegmentedControl,
  Toggle,
} from "../components/ui";
import { useAuth } from "../lib/auth";
import {
  analyzeMarket,
  fetchAnalyses,
  fetchPolymarkets,
  type MarketAnalysis,
  type PredictionMarket,
  refreshPolymarkets,
  setWatched,
} from "../lib/api/polymarket";

const pct = (v?: string | null): string =>
  v == null ? "—" : `${(Number(v) * 100).toFixed(1)}%`;

const money = (v?: string | null): string =>
  v == null ? "—" : `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

const when = (iso?: string | null): string =>
  iso ? iso.slice(0, 16).replace("T", " ") : "—";

function edgeTone(edge: string): "green" | "red" | "muted" {
  const value = Number(edge);
  if (value >= 0.05) return "green";
  if (value <= -0.05) return "red";
  return "muted";
}

function recommendationBadge(rec: string) {
  if (rec === "buy_yes") return <Badge tone="green">BUY YES</Badge>;
  if (rec === "buy_no") return <Badge tone="red">BUY NO</Badge>;
  return <Badge tone="muted">HOLD</Badge>;
}

type Scope = "all" | "watched";

export function Polymarket() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [markets, setMarkets] = useState<PredictionMarket[]>([]);
  const [analyses, setAnalyses] = useState<MarketAnalysis[]>([]);
  const [selected, setSelected] = useState<PredictionMarket | null>(null);
  const [scope, setScope] = useState<Scope>("all");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMarkets(
        await fetchPolymarkets({
          watched: scope === "watched" ? true : undefined,
          search: search.trim() || undefined,
        }),
      );
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load markets");
    }
  }, [scope, search]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    fetchAnalyses(selected?.condition_id)
      .then(setAnalyses)
      .catch(() => setAnalyses([]));
  }, [selected]);

  const refresh = async () => {
    setBusy("refresh");
    try {
      await refreshPolymarkets();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setBusy(null);
    }
  };

  const toggleWatch = async (market: PredictionMarket, watched: boolean) => {
    try {
      const updated = await setWatched(market.condition_id, watched);
      setMarkets((rows) =>
        rows.map((r) => (r.condition_id === updated.condition_id ? updated : r)),
      );
      if (selected?.condition_id === updated.condition_id) setSelected(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update the watchlist");
    }
  };

  const analyze = async (market: PredictionMarket) => {
    setBusy("analyze");
    try {
      const result = await analyzeMarket(market.condition_id);
      setAnalyses((rows) => [result, ...rows]);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setBusy(null);
    }
  };

  const columns: Column<PredictionMarket>[] = [
    {
      key: "question",
      label: "Market",
      wrap: true,
      render: (m) => (
        <span style={{ fontWeight: 500, color: "var(--text)" }}>{m.question}</span>
      ),
    },
    {
      key: "category",
      label: "Category",
      width: 110,
      render: (m) => (m.category ? <Badge tone="muted">{m.category}</Badge> : "—"),
    },
    {
      key: "yes_price",
      label: "YES",
      align: "right",
      width: 80,
      render: (m) => <span style={{ fontFamily: "var(--mono)" }}>{pct(m.yes_price)}</span>,
    },
    {
      key: "volume_24h",
      label: "Volume 24h",
      align: "right",
      width: 110,
      render: (m) => <span style={{ fontFamily: "var(--mono)" }}>{money(m.volume_24h)}</span>,
    },
    {
      key: "end_date",
      label: "Resolves",
      width: 130,
      render: (m) => (
        <span style={{ fontSize: 12, color: "var(--text-3)" }}>{when(m.end_date)}</span>
      ),
    },
    {
      key: "watched",
      label: "Watch",
      align: "center",
      width: 80,
      render: (m) => (
        <span onClick={(e) => e.stopPropagation()}>
          <Toggle
            size="sm"
            checked={!!m.watched}
            onChange={(v) => void toggleWatch(m, v)}
          />
        </span>
      ),
    },
  ];

  const latest = analyses[0];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card padding={0}>
        <SectionHeader
          title="Prediction markets"
          subtitle="Most-traded Polymarket markets — watch one to put it on the AI's schedule"
          right={
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <SegmentedControl
                size="sm"
                options={[
                  { value: "all", label: "All" },
                  { value: "watched", label: "Watchlist" },
                ]}
                value={scope}
                onChange={setScope}
              />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search questions"
                size="sm"
                prefix={<I.Search size={14} />}
              />
              {isAdmin && (
                <Button
                  kind="outline"
                  size="sm"
                  onClick={refresh}
                  disabled={busy === "refresh"}
                >
                  {busy === "refresh" ? "Refreshing…" : "Refresh"}
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
        {markets.length === 0 ? (
          <EmptyState
            icon={<I.Markets size={20} />}
            title="No markets yet"
            body="The engine refreshes the catalogue on a schedule. Admins can trigger a refresh from the button above."
          />
        ) : (
          <DataTable
            columns={columns}
            rows={markets}
            rowKey={(m) => m.condition_id}
            onRowClick={setSelected}
            highlightRow={(m) => m.condition_id === selected?.condition_id}
            dense
          />
        )}
      </Card>

      {selected && (
        <Card padding={0}>
          <SectionHeader
            title={selected.question}
            subtitle={`YES ${pct(selected.yes_price)} · resolves ${when(selected.end_date)} · liquidity ${money(selected.liquidity)}`}
            right={
              isAdmin && (
                <Button
                  kind="primary"
                  size="sm"
                  onClick={() => void analyze(selected)}
                  disabled={busy === "analyze"}
                >
                  {busy === "analyze" ? "Analyzing…" : "Analyze now"}
                </Button>
              )
            }
          />
          {!latest ? (
            <EmptyState
              icon={<I.Research size={20} />}
              title="No AI analysis yet"
              body="Watched markets are analysed on the screening schedule; admins can run one now."
            />
          ) : (
            <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
                {recommendationBadge(latest.recommendation ?? "hold")}
                <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>
                  AI estimate{" "}
                  <b style={{ fontFamily: "var(--mono)" }}>{pct(latest.est_probability)}</b>
                </span>
                <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>
                  market{" "}
                  <b style={{ fontFamily: "var(--mono)" }}>{pct(latest.market_price)}</b>
                </span>
                <Badge tone={edgeTone(latest.edge ?? "0")}>
                  edge {pct(latest.edge)}
                </Badge>
                <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>
                  confidence{" "}
                  <b style={{ fontFamily: "var(--mono)" }}>{pct(latest.confidence)}</b>
                </span>
                <span style={{ fontSize: 11.5, color: "var(--text-4)", marginLeft: "auto" }}>
                  {latest.provider}
                  {latest.model ? ` · ${latest.model}` : ""} · {when(latest.created_at)}
                </span>
              </div>
              {latest.reasoning && (
                <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.55 }}>
                  {latest.reasoning}
                </div>
              )}
              {analyses.length > 1 && (
                <div style={{ borderTop: "1px solid var(--border-soft)", paddingTop: 10 }}>
                  <div style={{ fontSize: 11.5, color: "var(--text-3)", marginBottom: 6 }}>
                    Earlier analyses
                  </div>
                  {analyses.slice(1, 6).map((a) => (
                    <div
                      key={a.id}
                      style={{
                        display: "flex",
                        gap: 12,
                        alignItems: "center",
                        fontSize: 12,
                        color: "var(--text-3)",
                        padding: "3px 0",
                      }}
                    >
                      <span style={{ fontFamily: "var(--mono)", minWidth: 110 }}>
                        {when(a.created_at)}
                      </span>
                      {recommendationBadge(a.recommendation ?? "hold")}
                      <span style={{ fontFamily: "var(--mono)" }}>
                        est {pct(a.est_probability)} / mkt {pct(a.market_price)}
                      </span>
                      <Badge tone={edgeTone(a.edge ?? "0")}>edge {pct(a.edge)}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
