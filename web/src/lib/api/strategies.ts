/** Strategies API helpers — list, allocate, enable/disable, close. */
import { api } from "./client";
import type { components } from "./schema";

export type Strategy = components["schemas"]["StrategyRead"];

export async function fetchStrategies(): Promise<Strategy[]> {
  const { data, error } = await api.GET("/api/strategies");
  if (error || !data) throw new Error("Failed to load strategies");
  return data;
}

export async function updateAllocation(
  name: string,
  allocated: string,
  maxLoss?: string,
): Promise<Strategy> {
  const { data, error } = await api.PATCH("/api/strategies/{name}/allocation", {
    params: { path: { name } },
    body: { allocated, max_loss: maxLoss ?? null },
  });
  if (error || !data) throw new Error("Failed to update allocation");
  return data;
}

export async function updateEnabled(name: string, enabled: boolean): Promise<Strategy> {
  const { data, error } = await api.PATCH("/api/strategies/{name}/enabled", {
    params: { path: { name } },
    body: { enabled },
  });
  if (error || !data) throw new Error("Failed to update strategy state");
  return data;
}

export async function closeStrategy(name: string): Promise<number> {
  const { data, error } = await api.POST("/api/strategies/{name}/close", {
    params: { path: { name } },
  });
  if (error || !data) throw new Error("Failed to close strategy positions");
  return data.closed;
}

export async function updateAiModel(
  name: string,
  provider: string,
  model: string,
): Promise<Strategy> {
  const { data, error } = await api.PATCH("/api/strategies/{name}/ai-model", {
    params: { path: { name } },
    body: { provider, model },
  });
  if (error || !data) {
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "Failed to set the AI model";
    throw new Error(detail);
  }
  return data;
}

export type StrategyType = components["schemas"]["StrategyTypeRead"];

export async function fetchStrategyTypes(): Promise<StrategyType[]> {
  const { data, error } = await api.GET("/api/strategies/types");
  if (error || !data) throw new Error("Failed to load strategy types");
  return data;
}

export async function createStrategy(body: {
  name: string;
  type: string;
  symbol: string;
  market?: string;
  timeframe?: string;
  params?: Record<string, string>;
  allocated?: string;
  max_loss?: string;
}): Promise<Strategy> {
  const { data, error } = await api.POST("/api/strategies", {
    body: {
      ...body,
      market: body.market ?? "spot",
      timeframe: body.timeframe ?? "1h",
      allocated: body.allocated ?? "10000",
      max_loss: body.max_loss ?? "0",
    },
  });
  if (error || !data) {
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "Failed to create strategy";
    throw new Error(detail);
  }
  return data;
}

export async function deleteStrategy(name: string): Promise<void> {
  const { error } = await api.DELETE("/api/strategies/{name}", {
    params: { path: { name } },
  });
  if (error) {
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "Failed to delete strategy";
    throw new Error(detail);
  }
}
