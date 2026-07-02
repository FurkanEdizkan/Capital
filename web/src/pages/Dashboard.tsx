/**
 * Dashboard — portfolio overview: equity, PnL net of fees, open positions and
 * recent bot activity. Consumes the portfolio API; refreshes periodically.
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EquityChart } from "../components/EquityChart";
import { I } from "../components/icons";
import {
  Badge,
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  SectionHeader,
  SideBadge,
  Skeleton,
  StatTile,
} from "../components/ui";
import { useAuth } from "../lib/auth";
import { fmt } from "../lib/format";
import {
  type AiSignal,
  confirmSignal,
  dismissSignal,
  fetchSignals,
} from "../lib/api/ai";
import {
  type Costs,
  type EquitySnapshot,
  fetchCosts,
  fetchEquity,
  fetchPositions,
  fetchSummary,
  fetchTrades,
  type PortfolioSummary,
  type Position,
  type Trade,
} from "../lib/api/portfolio";
import { type FeedLatency, fetchFeedLatency } from "../lib/api/market";

const REFRESH_MS = 15_000;

function LatencyChip({ latency }: { latency: FeedLatency | null }) {
  if (!latency || latency.feeds.length === 0) return null;
  const ws = latency.feeds.filter((f) => f.kind === "ws");
  const current = Math.max(...(ws.length ? ws : latency.feeds).map((f) => f.current_ms));
  const p95 = Math.max(...(ws.length ? ws : latency.feeds).map((f) => f.p95_ms));
  const color = latency.degraded
    ? "var(--red)"
    : current < 500
      ? "var(--green)"
      : "var(--amber)";
  const label =
    current >= 1000 ? `${(current / 1000).toFixed(1)} s` : `${Math.round(current)} ms`;
  return (
    <span
      title={`Price-feed latency — current ${Math.round(current)} ms, p95 ${Math.round(
        p95,
      )} ms (degraded above ${latency.warn_ms} ms)`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11.5,
        color: "var(--text-3)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "2px 10px",
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: color,
          display: "inline-block",
        }}
      />
      feed {label}
      {latency.degraded ? " · degraded" : ""}
    </span>
  );
}

/** Relative "updated Xs ago" stamp; turns red and pulses once data is stale. */
function FreshnessStamp({ at, stale }: { at: number | null; stale: boolean }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  if (at == null) return null;
  const secs = Math.max(0, Math.round((Date.now() - at) / 1000));
  const rel =
    secs < 60 ? `${secs}s` : secs < 3600 ? `${Math.floor(secs / 60)}m` : `${Math.floor(secs / 3600)}h`;
  return (
    <span
      title={`Last successful refresh: ${new Date(at).toLocaleTimeString()}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11.5,
        color: stale ? "var(--red)" : "var(--text-3)",
      }}
    >
      <span
        className={stale ? "pulse-red" : ""}
        style={{
          width: 7,
          height: 7,
          borderRadius: "50%",
          background: stale ? "var(--red)" : "var(--green)",
          display: "inline-block",
        }}
      />
      {stale ? `stale · last updated ${rel} ago` : `updated ${rel} ago`}
    </span>
  );
}

/** Placeholder rows shown in a table body until the first fetch resolves. */
function RowsSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div style={{ padding: "10px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={14} />
      ))}
    </div>
  );
}

export function Dashboard() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [equity, setEquity] = useState<EquitySnapshot[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [costs, setCosts] = useState<Costs | null>(null);
  const [signals, setSignals] = useState<AiSignal[]>([]);
  const [latency, setLatency] = useState<FeedLatency | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Freshness tracking — a monitor tool must never present frozen data as live.
  const [loaded, setLoaded] = useState(false);
  const [lastLoadedAt, setLastLoadedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, e, p, t, c, sig] = await Promise.all([
        fetchSummary(),
        fetchEquity(),
        fetchPositions(),
        fetchTrades(),
        fetchCosts(),
        fetchSignals("pending"),
      ]);
      setSummary(s);
      setEquity(e);
      setPositions(p);
      setTrades(t);
      setCosts(c);
      setSignals(sig);
      fetchFeedLatency().then(setLatency).catch(() => setLatency(null));
      setError(null);
      setLoaded(true);
      setLastLoadedAt(Date.now());
    } catch (err) {
      // Keep the last-known data on screen, but surface that it's stale
      // (see the degraded banner below) rather than silently freezing it.
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  if (error && !summary) {
    return <EmptyState icon={<I.Warn />} title="Couldn't load the dashboard" body={error} />;
  }

  const net = summary ? Number(summary.net_pnl) : 0;
  const idle = summary ? Number(summary.idle_capital) : 0;

  const positionCols: Column<Position>[] = [
    { key: "strategy", label: "Strategy" },
    { key: "symbol", label: "Symbol" },
    { key: "side", label: "Side", render: (r) => <SideBadge side={r.side} /> },
    { key: "qty", label: "Size", align: "right", render: (r) => <span className="num">{fmt(Number(r.qty), 4)}</span> },
    {
      key: "entry_price",
      label: "Entry",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.entry_price), 2)}</span>,
    },
    {
      key: "realized_pnl",
      label: "Realized PnL",
      align: "right",
      render: (r) => <PnlText value={Number(r.realized_pnl)} />,
    },
  ];

  const tradeCols: Column<Trade>[] = [
    {
      key: "executed_at",
      label: "Time",
      render: (r) => <span className="num">{r.executed_at.slice(11, 19)}</span>,
    },
    { key: "strategy", label: "Strategy" },
    { key: "symbol", label: "Symbol" },
    { key: "side", label: "Side", render: (r) => <SideBadge side={r.side} /> },
    { key: "quantity", label: "Size", align: "right", render: (r) => <span className="num">{fmt(Number(r.quantity), 4)}</span> },
    {
      key: "price",
      label: "Price",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.price), 2)}</span>,
    },
    {
      key: "fee",
      label: "Fee",
      align: "right",
      render: (r) => <span className="num">${fmt(Number(r.fee), 4)}</span>,
    },
  ];

  const stale = Boolean(error && summary);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          minHeight: 22,
        }}
      >
        <FreshnessStamp at={lastLoadedAt} stale={stale} />
        {latency && latency.feeds.length > 0 && <LatencyChip latency={latency} />}
      </div>

      {stale && (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 12px",
            fontSize: 12.5,
            color: "var(--text-2)",
            background: "var(--red-bg)",
            border: "1px solid rgba(239, 68, 68, 0.30)",
            borderRadius: "var(--radius)",
          }}
        >
          <span style={{ color: "var(--red)", display: "inline-flex" }}>
            <I.Warn />
          </span>
          <span style={{ flex: 1 }}>
            Showing last-known data — the latest refresh failed. {error}
          </span>
          <Button kind="ghost" size="sm" onClick={() => void load()}>
            Retry
          </Button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <StatTile
          label="Portfolio Value"
          value={
            summary ? `$${fmt(Number(summary.equity))}` : <Skeleton width={110} height={26} />
          }
        />
        <StatTile
          label="Net PnL (after fees)"
          value={
            summary ? (
              `${net >= 0 ? "+" : "−"}$${fmt(Math.abs(net))}`
            ) : (
              <Skeleton width={110} height={26} />
            )
          }
          subTone={net >= 0 ? "green" : "red"}
          sub={summary ? `${summary.open_positions} open positions` : undefined}
          trend={summary ? (net >= 0 ? "up" : "down") : undefined}
        />
        <StatTile
          label="Total Fees Paid"
          value={
            summary ? `$${fmt(Number(summary.total_fees))}` : <Skeleton width={90} height={26} />
          }
        />
        <StatTile
          label="Allocated Capital"
          value={
            summary ? (
              `$${fmt(Number(summary.total_allocated))}`
            ) : (
              <Skeleton width={110} height={26} />
            )
          }
          sub={summary ? `$${fmt(idle)} idle` : undefined}
        />
      </div>

      <Card>
        <SectionHeader title="Equity curve" subtitle="Snapshot per engine tick" />
        <div style={{ padding: 14 }}>
          {loaded ? (
            <EquityChart
              points={equity.map((s) => ({ time: s.ts, value: Number(s.equity) }))}
            />
          ) : (
            <Skeleton height={220} radius={8} />
          )}
        </div>
      </Card>

      {signals.length > 0 && <SignalsCard signals={signals} onChange={load} />}

      {costs && <CostsCard costs={costs} />}

      <Card>
        <SectionHeader
          title="Open positions"
          subtitle={loaded ? `${positions.length} held` : "—"}
        />
        {!loaded ? (
          <RowsSkeleton rows={3} />
        ) : positions.length === 0 ? (
          <EmptyState icon={<I.Dashboard />} title="No open positions" body="Strategies open positions as their signals fire." />
        ) : (
          <DataTable columns={positionCols} rows={positions} rowKey={(r) => r.id ?? r.symbol} dense />
        )}
      </Card>

      <Card>
        <SectionHeader title="Recent activity" subtitle="Latest executed trades" />
        {!loaded ? (
          <RowsSkeleton rows={4} />
        ) : trades.length === 0 ? (
          <EmptyState icon={<I.History />} title="No trades yet" body="The bot's trades will appear here." />
        ) : (
          <DataTable columns={tradeCols} rows={trades} rowKey={(r) => r.id ?? r.executed_at} dense />
        )}
      </Card>
    </div>
  );
}

/** Pending AI signals (notify mode) — confirm to execute, or dismiss. */
function SignalsCard({ signals, onChange }: { signals: AiSignal[]; onChange: () => void }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [busy, setBusy] = useState<number | null>(null);
  const [armed, setArmed] = useState<number | null>(null); // signal whose Confirm is armed
  const [failed, setFailed] = useState<{ id: number; msg: string } | null>(null);

  const act = async (
    id: number,
    fn: (id: number) => Promise<unknown>,
    verb: string,
  ) => {
    setBusy(id);
    setFailed(null);
    try {
      await fn(id);
      setArmed(null);
      await onChange();
    } catch (err) {
      // A real-money action must never fail silently — surface it in-row.
      setFailed({ id, msg: err instanceof Error ? err.message : `Failed to ${verb} signal` });
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card>
      <SectionHeader
        title="Pending AI signals"
        subtitle={`${signals.length} awaiting confirmation`}
      />
      <div style={{ display: "flex", flexDirection: "column" }}>
        {signals.map((s) => (
          <div key={s.id} style={{ borderTop: "1px solid var(--border-soft)" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 16px",
              }}
            >
              <SideBadge side={s.action} />
              <div style={{ fontSize: 13 }}>
                <span style={{ fontWeight: 600 }}>{s.symbol}</span>{" "}
                <span style={{ color: "var(--text-3)" }}>· {s.strategy}</span>
              </div>
              <Badge tone="muted">conf {fmt(Number(s.confidence) * 100, 0)}%</Badge>
              <span
                style={{
                  flex: 1,
                  fontSize: 12,
                  color: "var(--text-2)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={s.reasoning ?? ""}
              >
                {s.reasoning}
              </span>
              {isAdmin && s.id != null ? (
                armed === s.id ? (
                  <>
                    <Button
                      kind="primary"
                      size="sm"
                      disabled={busy === s.id}
                      onClick={() => void act(s.id!, confirmSignal, "confirm")}
                    >
                      {busy === s.id ? "Executing…" : "Execute trade"}
                    </Button>
                    <Button
                      kind="ghost"
                      size="sm"
                      disabled={busy === s.id}
                      onClick={() => setArmed(null)}
                    >
                      Cancel
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      kind="default"
                      size="sm"
                      disabled={busy != null}
                      onClick={() => {
                        setFailed(null);
                        setArmed(s.id!);
                      }}
                    >
                      Confirm…
                    </Button>
                    <Button
                      kind="ghost"
                      size="sm"
                      disabled={busy != null}
                      onClick={() => void act(s.id!, dismissSignal, "dismiss")}
                    >
                      Dismiss
                    </Button>
                  </>
                )
              ) : null}
            </div>
            {/* Arming reveals the size/notional + full rationale, so the operator
                commits capital on complete information — not a truncated one-liner. */}
            {armed === s.id && (
              <div style={{ padding: "0 16px 10px", display: "flex", flexDirection: "column", gap: 6 }}>
                <div className="num" style={{ fontSize: 12.5, color: "var(--text)" }}>
                  {s.action.toUpperCase()} {fmt(Number(s.quantity), 4)} {s.symbol}
                  {Number(s.reference_price) > 0 && (
                    <span style={{ color: "var(--text-3)" }}>
                      {" "}@ ${fmt(Number(s.reference_price), 2)}
                    </span>
                  )}
                  {Number(s.quantity) > 0 && Number(s.reference_price) > 0 && (
                    <span style={{ color: "var(--text-2)" }}>
                      {" "}≈ ${fmt(Number(s.quantity) * Number(s.reference_price), 2)}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 12, lineHeight: 1.5, color: "var(--text-2)" }}>
                  <span style={{ color: "var(--text-3)" }}>
                    Executing commits real capital. Rationale:{" "}
                  </span>
                  {s.reasoning || "—"}
                </div>
              </div>
            )}
            {failed && failed.id === s.id && (
              <div
                role="alert"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "0 16px 10px",
                  fontSize: 12,
                  color: "var(--red)",
                }}
              >
                <I.Warn />
                <span>{failed.msg}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function PnlText({ value }: { value: number }) {
  const color = value > 0 ? "#34D399" : value < 0 ? "#F87171" : "var(--text-2)";
  return (
    <span className="num" style={{ color }}>
      {value >= 0 ? "+" : "−"}${fmt(Math.abs(value))}
    </span>
  );
}

/** Trading-cost visibility — fees by market and the per-venue fee-rate table. */
function CostsCard({ costs }: { costs: Costs }) {
  const pct = Number(costs.fee_pct_of_volume);
  const byMarket = Object.entries(costs.fees_by_market);
  const rates = Object.entries(costs.venue_fee_rates);
  const rowStyle = {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 12.5,
    padding: "3px 0",
  } as const;
  return (
    <Card>
      <SectionHeader
        title="Trading costs"
        subtitle={`$${fmt(Number(costs.total_fees), 2)} in fees · ${fmt(
          pct,
          3,
        )}% of $${fmt(Number(costs.traded_volume), 0)} traded · $${fmt(
          Number(costs.llm_spend_today),
          2,
        )} LLM spend today`}
        right={
          <Link to="/costs" style={{ fontSize: 12, color: "var(--text-2)" }}>
            View costs →
          </Link>
        }
      />
      <div
        style={{
          padding: 14,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 24,
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4 }}>
            FEES BY MARKET
          </div>
          {byMarket.length === 0 ? (
            <span style={{ fontSize: 12.5, color: "var(--text-3)" }}>No fees yet</span>
          ) : (
            byMarket.map(([market, fee]) => (
              <div key={market} style={rowStyle}>
                <span style={{ textTransform: "capitalize" }}>{market}</span>
                <span className="num">${fmt(Number(fee), 4)}</span>
              </div>
            ))
          )}
        </div>
        <div>
          <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4 }}>
            VENUE FEE RATES
          </div>
          {rates.map(([venue, rate]) => (
            <div key={venue} style={rowStyle}>
              <span style={{ textTransform: "capitalize" }}>{venue}</span>
              <span className="num">{fmt(Number(rate) * 100, 3)}%</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
