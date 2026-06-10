/**
 * Costs — every AI-model call (and any future paid API) with its estimated
 * cost, attributed to what spent it: strategy ticks, research reports,
 * council votes, analyze tasks and Lab recommendations.
 */
import { useCallback, useEffect, useState } from "react";

import { I } from "../components/icons";
import {
  Badge,
  Card,
  type Column,
  DataTable,
  EmptyState,
  SectionHeader,
  SegmentedControl,
  StatTile,
} from "../components/ui";
import { fmt } from "../lib/format";
import {
  type CostsSummary,
  fetchCostsLedger,
  fetchCostsSummary,
  type LedgerPage,
} from "../lib/api/costs";

const PURPOSES = ["all", "strategy", "analyze", "report", "council", "recommend"];

const usd = (v: string | number) => `$${fmt(Number(v), 2)}`;

type Bucket = CostsSummary["by_model"][number];
type Entry = LedgerPage["entries"][number];

function DailyBars({ days }: { days: Bucket[] }) {
  if (days.length === 0) {
    return <span style={{ fontSize: 12.5, color: "var(--text-4)" }}>No spend yet.</span>;
  }
  const max = Math.max(...days.map((d) => Number(d.cost_usd))) || 1;
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 72 }}>
      {days.map((d) => (
        <div
          key={d.key}
          title={`${d.key} — ${usd(d.cost_usd)} (${d.calls} calls)`}
          style={{
            width: 14,
            height: Math.max(3, (Number(d.cost_usd) / max) * 68),
            background: "var(--green-bg)",
            border: "1px solid rgba(16,185,129,.35)",
            borderRadius: 2,
          }}
        />
      ))}
    </div>
  );
}

function BucketTable({ rows, label }: { rows: Bucket[]; label: string }) {
  const cols: Column<Bucket>[] = [
    { key: "key", label, render: (r) => <span className="num">{r.key}</span> },
    { key: "calls", label: "Calls", align: "right" },
    {
      key: "tokens",
      label: "Tokens in / out",
      align: "right",
      render: (r) => (
        <span className="num">
          {fmt(r.input_tokens, 0)} / {fmt(r.output_tokens, 0)}
        </span>
      ),
    },
    {
      key: "cost_usd",
      label: "Cost",
      align: "right",
      render: (r) => <span className="num">{usd(r.cost_usd)}</span>,
    },
  ];
  return <DataTable columns={cols} rows={rows} rowKey={(r) => r.key} dense />;
}

export function Costs() {
  const [summary, setSummary] = useState<CostsSummary | null>(null);
  const [ledger, setLedger] = useState<LedgerPage | null>(null);
  const [purpose, setPurpose] = useState("all");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const PAGE = 50;

  const load = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([
        fetchCostsSummary(),
        fetchCostsLedger(PAGE, offset, purpose === "all" ? undefined : purpose),
      ]);
      setSummary(s);
      setLedger(l);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load costs");
    }
  }, [offset, purpose]);

  useEffect(() => {
    void load();
  }, [load]);

  const cap = Number(summary?.daily_cap_usd ?? 0);
  const today = Number(summary?.today_usd ?? 0);

  const ledgerCols: Column<Entry>[] = [
    {
      key: "created_at",
      label: "When",
      render: (r) => (
        <span className="num" style={{ fontSize: 11.5 }}>
          {r.created_at.slice(0, 16).replace("T", " ")}
        </span>
      ),
    },
    {
      key: "purpose",
      label: "Purpose",
      render: (r) => <Badge tone="muted">{r.purpose}</Badge>,
    },
    {
      key: "model",
      label: "Model",
      render: (r) => (
        <span className="num" style={{ fontSize: 11.5 }}>
          {r.provider}/{r.model}
        </span>
      ),
    },
    {
      key: "strategy",
      label: "Strategy",
      render: (r) => r.strategy ?? <span style={{ color: "var(--text-4)" }}>—</span>,
    },
    {
      key: "tokens",
      label: "Tokens",
      align: "right",
      render: (r) => (
        <span className="num">
          {fmt(r.input_tokens, 0)} / {fmt(r.output_tokens, 0)}
        </span>
      ),
    },
    {
      key: "action",
      label: "Decision",
      render: (r) =>
        r.action ? (
          <Badge tone={r.action === "buy" ? "green" : r.action === "sell" ? "red" : "muted"}>
            {r.action}
          </Badge>
        ) : (
          <span style={{ color: "var(--text-4)" }}>—</span>
        ),
    },
    {
      key: "cost_usd",
      label: "Cost",
      align: "right",
      render: (r) => <span className="num">{usd(r.cost_usd)}</span>,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {error && <div style={{ color: "var(--red)", fontSize: 12.5 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        <StatTile
          label={cap > 0 ? `Today (cap ${usd(cap)})` : "Today"}
          value={usd(today)}
          subTone={cap > 0 && today >= cap ? "red" : undefined}
          sub={
            cap > 0
              ? `${Math.min(100, Math.round((today / cap) * 100))}% of the daily cap`
              : "no daily cap set"
          }
        />
        <StatTile label="Last 7 days" value={usd(summary?.last_7d_usd ?? 0)} />
        <StatTile label="Last 30 days" value={usd(summary?.last_30d_usd ?? 0)} />
      </div>

      {cap > 0 && (
        <Card>
          <div style={{ padding: "12px 16px" }}>
            <div
              style={{
                height: 8,
                borderRadius: 4,
                background: "var(--card-2)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, (today / cap) * 100)}%`,
                  height: "100%",
                  background: today >= cap ? "var(--red)" : "var(--green)",
                  transition: "width 300ms",
                }}
              />
            </div>
            <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 6 }}>
              AI strategies, reports and council votes pause once the cap is
              reached; it resets at midnight UTC. Configure it in Settings.
            </div>
          </div>
        </Card>
      )}

      <Card>
        <SectionHeader title="Daily spend" subtitle="Last 30 days, estimated US$" />
        <div style={{ padding: "12px 16px" }}>
          <DailyBars days={summary?.by_day ?? []} />
        </div>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Card padding={0}>
          <SectionHeader title="By model" subtitle="Who was asked" />
          {summary && summary.by_model.length > 0 ? (
            <BucketTable rows={summary.by_model} label="Model" />
          ) : (
            <EmptyState icon={<I.Bell size={18} />} title="No usage yet" body="" />
          )}
        </Card>
        <Card padding={0}>
          <SectionHeader title="By purpose" subtitle="What spent it" />
          {summary && summary.by_purpose.length > 0 ? (
            <BucketTable rows={summary.by_purpose} label="Purpose" />
          ) : (
            <EmptyState icon={<I.Bell size={18} />} title="No usage yet" body="" />
          )}
        </Card>
      </div>

      <Card padding={0}>
        <SectionHeader
          title="Call ledger"
          subtitle={`Every paid call, newest first${
            ledger ? ` · ${ledger.total} total` : ""
          }`}
          right={
            <SegmentedControl
              size="sm"
              options={PURPOSES.map((p) => ({ value: p, label: p }))}
              value={purpose}
              onChange={(p) => {
                setPurpose(p);
                setOffset(0);
              }}
            />
          }
        />
        {ledger && ledger.entries.length > 0 ? (
          <>
            <DataTable
              columns={ledgerCols}
              rows={ledger.entries}
              rowKey={(r) => String(r.id)}
              dense
            />
            {ledger.total > PAGE && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "8px 16px",
                  fontSize: 12,
                  color: "var(--text-3)",
                }}
              >
                <button
                  onClick={() => setOffset(Math.max(0, offset - PAGE))}
                  disabled={offset === 0}
                  style={pagerStyle}
                >
                  ← Newer
                </button>
                <span>
                  {offset + 1}–{Math.min(offset + PAGE, ledger.total)} of {ledger.total}
                </span>
                <button
                  onClick={() => setOffset(offset + PAGE)}
                  disabled={offset + PAGE >= ledger.total}
                  style={pagerStyle}
                >
                  Older →
                </button>
              </div>
            )}
          </>
        ) : (
          <EmptyState
            icon={<I.History size={20} />}
            title="No paid calls yet"
            body="AI usage appears here the moment a model is called — strategy ticks, reports, council votes, analyze tasks and Lab picks."
          />
        )}
      </Card>
    </div>
  );
}

const pagerStyle = {
  background: "none",
  border: "none",
  color: "var(--text-2)",
  cursor: "pointer",
  fontSize: 12,
} as const;
