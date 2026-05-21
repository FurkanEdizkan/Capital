/** History API helpers — transaction log, audit log and CSV export. */
import { api, getAuthToken } from "./client";
import type { components } from "./schema";

export type Trade = components["schemas"]["Trade"];
export type AuditLog = components["schemas"]["AuditLog"];

export async function fetchHistoryTrades(start?: string, end?: string): Promise<Trade[]> {
  const { data, error } = await api.GET("/api/history/trades", {
    params: { query: { start, end } },
  });
  if (error || !data) throw new Error("Failed to load transaction history");
  return data;
}

export async function fetchAuditLog(): Promise<AuditLog[]> {
  const { data, error } = await api.GET("/api/history/audit");
  if (error || !data) throw new Error("Failed to load the audit log");
  return data;
}

/** Fetch the trade-log CSV (with auth) and trigger a browser download. */
export async function downloadTradesCsv(start?: string, end?: string): Promise<void> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  const resp = await fetch(`${base}/api/history/trades.csv?${params.toString()}`, {
    headers: { Authorization: `Bearer ${getAuthToken() ?? ""}` },
  });
  if (!resp.ok) throw new Error("CSV export failed");
  const url = URL.createObjectURL(await resp.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = "capital-trades.csv";
  link.click();
  URL.revokeObjectURL(url);
}
