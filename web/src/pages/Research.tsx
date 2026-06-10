/**
 * Research — scheduled, schema-formatted research reports per watched asset.
 * Click a report to expand its sections; admins can trigger a run on demand.
 */
import { useCallback, useEffect, useState } from "react";

import { GuideButton } from "../components/GuideModal";
import { I } from "../components/icons";
import { Badge, Button, Card, EmptyState, Input, SectionHeader } from "../components/ui";
import { useAuth } from "../lib/auth";
import {
  type CouncilReview,
  fetchReports,
  fetchReview,
  type ResearchReport,
  rerunReview,
  runResearch,
} from "../lib/api/research";

const when = (iso?: string | null): string =>
  iso ? iso.slice(0, 16).replace("T", " ") : "";

const sectionTitle: Record<string, string> = {
  summary: "Summary",
  technicals: "Technical snapshot",
  headlines: "Asset headlines",
  market_headlines: "World & economic headlines",
  connections: "Connections",
  trade_route_effect: "Trade routes & macro effects",
  technology_review: "Technology review",
  scenarios_up: "Possible ups",
  scenarios_down: "Possible downs",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: 0.5,
          color: "var(--text-3)",
          marginBottom: 4,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function Bullets({ items, tone }: { items: string[]; tone?: "up" | "down" }) {
  if (!items.length) {
    return <span style={{ fontSize: 12.5, color: "var(--text-4)" }}>—</span>;
  }
  const color =
    tone === "up" ? "var(--green)" : tone === "down" ? "var(--red)" : "var(--text-2)";
  return (
    <ul style={{ margin: 0, paddingLeft: 18 }}>
      {items.map((s, i) => (
        <li key={i} style={{ fontSize: 13, color, marginBottom: 2 }}>
          <span style={{ color: "var(--text-2)" }}>{s}</span>
        </li>
      ))}
    </ul>
  );
}

function Paragraph({ text }: { text: string }) {
  return (
    <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: "var(--text-2)" }}>
      {text || "—"}
    </p>
  );
}

function CouncilPanel({ report }: { report: ResearchReport }) {
  const { user } = useAuth();
  const [review, setReview] = useState<CouncilReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReview(report.id)
      .then(setReview)
      .catch(() => setReview(null));
  }, [report.id]);

  const rerun = async () => {
    setBusy(true);
    setError(null);
    try {
      setReview(await rerunReview(report.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Council review failed");
    } finally {
      setBusy(false);
    }
  };

  const verdictTone = (v: string): "green" | "red" | "muted" =>
    v === "buy" ? "green" : v === "sell" ? "red" : "muted";

  return (
    <Section title="Council review">
      {review ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Badge tone={verdictTone(review.verdict)} size="lg">
              {review.verdict}
            </Badge>
            <span style={{ fontSize: 12.5, color: "var(--text-3)" }}>
              weighted score {(Number(review.weighted_score) * 100).toFixed(0)}%
              {review.quorum_met ? " · quorum met" : " · below quorum"}
            </span>
          </div>
          <Paragraph text={review.strategy_brief} />
          <table style={{ borderCollapse: "collapse", fontSize: 12.5 }}>
            <tbody>
              {review.votes.map((v, i) => (
                <tr key={i} style={{ borderTop: "1px solid var(--border-soft)" }}>
                  <td style={{ padding: "4px 10px 4px 0", color: "var(--text-2)" }}>
                    {v.provider}
                    {v.model ? ` / ${v.model}` : ""}
                  </td>
                  <td style={{ padding: "4px 10px 4px 0" }}>
                    <Badge tone={v.action === "abstain" ? "muted" : verdictTone(v.action)}>
                      {v.action}
                    </Badge>
                  </td>
                  <td style={{ padding: "4px 10px 4px 0", color: "var(--text-3)" }}>
                    {v.action === "abstain"
                      ? "—"
                      : `${(Number(v.confidence) * 100).toFixed(0)}%`}
                  </td>
                  <td style={{ padding: "4px 0", color: "var(--text-3)" }}>
                    {v.reasoning}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <span style={{ fontSize: 12.5, color: "var(--text-4)" }}>
          No council review yet — configure council members in Settings.
        </span>
      )}
      {error && (
        <div style={{ color: "var(--red)", fontSize: 12.5, marginTop: 6 }}>{error}</div>
      )}
      {user?.role === "admin" && (
        <div style={{ marginTop: 8 }}>
          <Button kind="outline" size="sm" onClick={rerun} disabled={busy}>
            {busy ? "Voting…" : review ? "Re-run council" : "Run council"}
          </Button>
        </div>
      )}
    </Section>
  );
}

function ReportDetail({ report }: { report: ResearchReport }) {
  const s = report.sections as Record<string, unknown>;
  const str = (k: string): string => (typeof s[k] === "string" ? (s[k] as string) : "");
  const list = (k: string): string[] => (Array.isArray(s[k]) ? (s[k] as string[]) : []);
  const technicals =
    s.technicals && typeof s.technicals === "object"
      ? (s.technicals as Record<string, string>)
      : {};
  return (
    <div style={{ padding: "12px 16px", background: "var(--card-2)" }}>
      {report.status === "failed" && (
        <div style={{ color: "var(--red)", fontSize: 12.5, marginBottom: 10 }}>
          Writer failed: {report.error || "unknown error"} — mechanical sections only.
        </div>
      )}
      <Section title={sectionTitle.summary}>
        <Paragraph text={str("summary")} />
      </Section>
      <CouncilPanel report={report} />
      {Object.keys(technicals).length > 0 && (
        <Section title={sectionTitle.technicals}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {Object.entries(technicals).map(([k, v]) => (
              <Badge key={k} tone="muted">
                {k}: {v}
              </Badge>
            ))}
          </div>
        </Section>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Section title={sectionTitle.scenarios_up}>
          <Bullets items={list("scenarios_up")} tone="up" />
        </Section>
        <Section title={sectionTitle.scenarios_down}>
          <Bullets items={list("scenarios_down")} tone="down" />
        </Section>
      </div>
      <Section title={sectionTitle.trade_route_effect}>
        <Paragraph text={str("trade_route_effect")} />
      </Section>
      <Section title={sectionTitle.technology_review}>
        <Paragraph text={str("technology_review")} />
      </Section>
      <Section title={sectionTitle.headlines}>
        <Bullets items={list("headlines")} />
      </Section>
      <Section title={sectionTitle.market_headlines}>
        <Bullets items={list("market_headlines")} />
      </Section>
      {list("connections").length > 0 && (
        <Section title={sectionTitle.connections}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {list("connections").map((c) => (
              <Badge key={c} tone="muted">
                {c}
              </Badge>
            ))}
          </div>
        </Section>
      )}
      <div style={{ fontSize: 11.5, color: "var(--text-4)" }}>
        Written by {report.provider || "?"}
        {report.model ? ` / ${report.model}` : ""} · schema v{report.schema_version}
      </div>
    </div>
  );
}

export function Research() {
  const { user } = useAuth();
  const [reports, setReports] = useState<ResearchReport[]>([]);
  const [symbol, setSymbol] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setReports(await fetchReports(symbol.trim() || undefined));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load reports");
    }
  }, [symbol]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async () => {
    setBusy(true);
    try {
      await runResearch(symbol.trim());
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Research run failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card padding={0}>
      <SectionHeader
        title={
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            Reports <GuideButton slug="research" />
          </span>
        }
        subtitle="News, connections, technicals and AI-written analysis per asset"
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
              <Button kind="outline" size="sm" onClick={run} disabled={busy}>
                {busy ? "Writing…" : "Run now"}
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
      {reports.length === 0 ? (
        <EmptyState
          icon={<I.Research size={20} />}
          title="No reports yet"
          body="Reports are written on a schedule for every watched symbol. Admins can run one now, or configure symbols in Settings."
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {reports.map((r) => {
            const summary =
              typeof (r.sections as Record<string, unknown>).summary === "string"
                ? ((r.sections as Record<string, unknown>).summary as string)
                : "";
            const open = openId === r.id;
            return (
              <div key={r.id} style={{ borderTop: "1px solid var(--border-soft)" }}>
                <button
                  onClick={() => setOpenId(open ? null : r.id)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    padding: "12px 16px",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      gap: 8,
                      alignItems: "center",
                      marginBottom: 4,
                    }}
                  >
                    <Badge tone="muted">{r.symbol}</Badge>
                    <Badge tone={r.status === "written" ? "green" : "red"}>
                      {r.status}
                    </Badge>
                    <span style={{ fontSize: 11.5, color: "var(--text-4)", marginLeft: "auto" }}>
                      {when(r.created_at)}
                    </span>
                  </div>
                  <div style={{ fontSize: 13.5, color: "var(--text)", fontWeight: 500 }}>
                    {summary || "(no summary)"}
                  </div>
                </button>
                {open && <ReportDetail report={r} />}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
