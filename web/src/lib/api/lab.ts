/** Strategy Lab API helpers — comparison grids and the AI recommendation. */
import { api } from "./client";
import type { components } from "./schema";

export type CompareCell = components["schemas"]["CompareCellRead"];
export type Recommendation = components["schemas"]["RecommendResponse"];

function detail(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "detail" in error) {
    return String((error as { detail: unknown }).detail);
  }
  return fallback;
}

export async function compareGrid(body: {
  types?: string[];
  symbols: string[];
  timeframe?: string;
  days?: number;
  capital?: string;
}): Promise<CompareCell[]> {
  const { data, error } = await api.POST("/api/lab/compare", {
    body: {
      types: body.types ?? [],
      symbols: body.symbols,
      timeframe: body.timeframe ?? "1h",
      days: body.days ?? 90,
      capital: body.capital ?? "10000",
    },
  });
  if (error || !data) throw new Error(detail(error, "Comparison failed"));
  return data;
}

export async function recommendStrategy(body: {
  symbol: string;
  timeframe?: string;
  days?: number;
}): Promise<Recommendation> {
  const { data, error } = await api.POST("/api/lab/recommend", {
    body: {
      symbol: body.symbol,
      timeframe: body.timeframe ?? "1h",
      days: body.days ?? 90,
      capital: "10000",
    },
  });
  if (error || !data) throw new Error(detail(error, "Recommendation failed"));
  return data;
}
