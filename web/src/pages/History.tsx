/**
 * History & Logs — the full transaction log, the config audit trail, and a
 * CSV export of trades (filterable by date range) for tax & reporting.
 */
import { useCallback, useEffect, useState } from "react";

import { I } from "../components/icons";
import { VenueBadge } from "../components/VenueBadge";
import {
  Button,
  Card,
  type Column,
  DataTable,
  EmptyState,
  Input,
  Money,
  SectionHeader,
  SideBadge,
} from "../components/ui";
import { fmt } from "../lib/format";
import {
  type AuditLog,
  downloadTradesCsv,
  fetchAuditLog,
  fetchHistoryTrades,
  type Trade,
} from "../lib/api/history";

export function History() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [audit, setAudit] = useState<AuditLog[]>([]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([
        fetchHistoryTrades(
          start ? `${start}T00:00:00` : undefined,
          end ? `${end}T23:59:59` : undefined,
        ),
        fetchAuditLog(),
      ]);
      setTrades(t);
      setAudit(a);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load history");
    }
  }, [start, end]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportCsv = async () => {
    setBusy(true);
    try {
      await downloadTradesCsv(
        start ? `${start}T00:00:00` : undefined,
        end ? `${end}T23:59:59` : undefined,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "CSV export failed");
    } finally {
      setBusy(false);
    }
  };

  const tradeCols: Column<Trade>[] = [
    {
      key: "executed_at",
      label: "Time",
      render: (r) => <span className="num">{r.executed_at.slice(0, 19).replace("T", " ")}</span>,
    },
    { key: "strategy", label: "Strategy" },
    { key: "symbol", label: "Symbol" },
    { key: "side", label: "Side", render: (r) => <SideBadge side={r.side} /> },
    {
      key: "quantity",
      label: "Size",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.quantity), 4)}</span>,
    },
    {
      key: "price",
      label: "Price",
      align: "right",
      render: (r) => <span className="num">{fmt(Number(r.price), 2)}</span>,
    },
    { key: "fee", label: "Fee", align: "right", render: (r) => <Money value={Number(r.fee)} /> },
    {
      key: "realized_pnl",
      label: "Realized PnL",
      align: "right",
      render: (r) => <Money value={Number(r.realized_pnl)} signed />,
    },
    { key: "mode", label: "Mode" },
  ];

  const auditCols: Column<AuditLog>[] = [
    {
      key: "created_at",
      label: "Time",
      render: (r) => (
        <span className="num">{(r.created_at ?? "").slice(0, 19).replace("T", " ")}</span>
      ),
    },
    { key: "actor", label: "Actor" },
    { key: "action", label: "Action" },
    { key: "target", label: "Target", render: (r) => r.target ?? "—" },
    {
      key: "detail",
      label: "Detail",
      render: (r) => (
        <span style={{ color: "var(--text-2)", fontSize: 11 }}>{r.detail ?? ""}</span>
      ),
    },
  ];

  if (error && trades.length === 0 && audit.length === 0) {
    return <EmptyState icon={<I.Warn />} title="Couldn't load history" body={error} />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Card>
        <SectionHeader
          title="Filter & export"
          subtitle="Filter the transaction log by date range, or export it as CSV."
          right={<VenueBadge />}
        />
        <div
          style={{
            padding: 14,
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            alignItems: "flex-end",
          }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 11, color: "var(--text-2)" }}>From</span>
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 11, color: "var(--text-2)" }}>To</span>
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </label>
          <Button kind="primary" disabled={busy} onClick={() => void exportCsv()}>
            Export CSV
          </Button>
        </div>
      </Card>

      <Card>
        <SectionHeader title="Transaction log" subtitle={`${trades.length} trades`} />
        {trades.length === 0 ? (
          <EmptyState icon={<I.History />} title="No trades" body="No trades in this range." />
        ) : (
          <DataTable
            columns={tradeCols}
            rows={trades}
            rowKey={(r) => r.id ?? `${r.executed_at}-${r.symbol}`}
            dense
          />
        )}
      </Card>

      <Card>
        <SectionHeader title="Audit log" subtitle="Every config-changing action" />
        {audit.length === 0 ? (
          <EmptyState
            icon={<I.Settings />}
            title="No audit entries"
            body="Configuration changes are recorded here."
          />
        ) : (
          <DataTable
            columns={auditCols}
            rows={audit}
            rowKey={(r) => r.id ?? `${r.created_at}-${r.action}`}
            dense
          />
        )}
      </Card>
    </div>
  );
}
