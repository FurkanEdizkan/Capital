/** Strategies API helpers — list, allocate, enable/disable, close. */
import { api } from "./client";
import type { components } from "./schema";

export type Strategy = components["schemas"]["StrategyRead"];

export async function fetchStrategies(): Promise<Strategy[]> {
  const { data, error } = await api.GET("/api/strategies");
  if (error || !data) throw new Error("Failed to load strategies");
  return data;
}

export async function updateAllocation(name: string, allocated: string): Promise<Strategy> {
  const { data, error } = await api.PATCH("/api/strategies/{name}/allocation", {
    params: { path: { name } },
    body: { allocated },
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
