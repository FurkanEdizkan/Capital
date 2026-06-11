/** Polymarket API helpers — market catalogue, watchlist and AI bet analyses. */
import { api } from "./client";
import type { components } from "./schema";

export type PredictionMarket = components["schemas"]["PredictionMarket"];
export type MarketAnalysis = components["schemas"]["MarketAnalysis"];

export async function fetchPolymarkets(opts?: {
  watched?: boolean;
  search?: string;
  category?: string;
  statusFilter?: string;
  limit?: number;
}): Promise<PredictionMarket[]> {
  const { data, error } = await api.GET("/api/polymarket/markets", {
    params: {
      query: {
        watched: opts?.watched,
        search: opts?.search,
        category: opts?.category,
        status_filter: opts?.statusFilter,
        limit: opts?.limit,
      },
    },
  });
  if (error || !data) throw new Error("Failed to load Polymarket markets");
  return data;
}

export async function setWatched(
  conditionId: string,
  watched: boolean,
): Promise<PredictionMarket> {
  const { data, error } = await api.PUT(
    "/api/polymarket/markets/{condition_id}/watch",
    {
      params: { path: { condition_id: conditionId } },
      body: { watched },
    },
  );
  if (error || !data) throw new Error("Failed to update the watchlist");
  return data;
}

export async function refreshPolymarkets(): Promise<number> {
  const { data, error } = await api.POST("/api/polymarket/refresh");
  if (error || !data) throw new Error("Failed to refresh markets");
  return data.updated;
}

export async function fetchAnalyses(
  conditionId?: string,
  limit = 50,
): Promise<MarketAnalysis[]> {
  const { data, error } = await api.GET("/api/polymarket/analyses", {
    params: { query: { condition_id: conditionId, limit } },
  });
  if (error || !data) throw new Error("Failed to load analyses");
  return data;
}

export async function analyzeMarket(
  conditionId: string,
): Promise<MarketAnalysis> {
  const { data, error } = await api.POST(
    "/api/polymarket/markets/{condition_id}/analyze",
    { params: { path: { condition_id: conditionId } } },
  );
  if (error || !data) throw new Error("Analysis failed — check the AI settings");
  return data;
}
