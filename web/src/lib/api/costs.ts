/** Costs API helpers — spend summary and the per-call ledger. */
import { api } from "./client";
import type { components } from "./schema";

export type CostsSummary = components["schemas"]["CostsSummary"];
export type LedgerPage = components["schemas"]["LedgerPage"];

export async function fetchCostsSummary(): Promise<CostsSummary> {
  const { data, error } = await api.GET("/api/costs/summary");
  if (error || !data) throw new Error("Failed to load costs summary");
  return data;
}

export async function fetchCostsLedger(
  limit = 50,
  offset = 0,
  purpose?: string,
): Promise<LedgerPage> {
  const { data, error } = await api.GET("/api/costs/ledger", {
    params: { query: { limit, offset, purpose } },
  });
  if (error || !data) throw new Error("Failed to load costs ledger");
  return data;
}
