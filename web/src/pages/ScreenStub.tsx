/**
 * Placeholder screen. Per the build plan ("foundation first, screens per
 * phase"), each feature screen is delivered in its own phase/PR. Until then
 * its route renders this stub so the shell, nav and routing are fully usable.
 */
import type { ReactNode } from "react";
import { Card } from "../components/ui";

export function ScreenStub({
  title,
  phase,
  summary,
  icon,
}: {
  title: string;
  phase: string;
  summary: string;
  icon?: ReactNode;
}) {
  return (
    <Card
      className="grid-bg"
      style={{
        minHeight: 420,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: 40,
      }}
    >
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: 12,
          background: "var(--card-2)",
          border: "1px solid var(--border)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-3)",
          marginBottom: 16,
        }}
      >
        {icon}
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, color: "var(--text)" }}>{title}</div>
      <div
        style={{
          marginTop: 6,
          fontSize: 13,
          color: "var(--text-3)",
          maxWidth: 460,
          lineHeight: 1.6,
        }}
      >
        {summary}
      </div>
      <div
        style={{
          marginTop: 18,
          fontFamily: "var(--mono)",
          fontSize: 11.5,
          color: "#34D399",
          background: "var(--green-bg)",
          border: "1px solid rgba(16,185,129,.30)",
          borderRadius: 999,
          padding: "4px 12px",
          textTransform: "uppercase",
          letterSpacing: ".06em",
        }}
      >
        Ships in {phase}
      </div>
    </Card>
  );
}
