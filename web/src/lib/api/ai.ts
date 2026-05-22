/** AI API helpers — per-model performance rollup and the decision log. */
import { api } from "./client";
import type { components } from "./schema";

export type ModelUsage = components["schemas"]["ModelUsage"];
export type LlmUsage = components["schemas"]["LLMUsage"];

export async function fetchModelUsage(): Promise<ModelUsage[]> {
  const { data, error } = await api.GET("/api/ai/models");
  if (error || !data) throw new Error("Failed to load model performance");
  return data;
}

export async function fetchDecisionLog(): Promise<LlmUsage[]> {
  const { data, error } = await api.GET("/api/ai/decisions");
  if (error || !data) throw new Error("Failed to load the decision log");
  return data;
}
