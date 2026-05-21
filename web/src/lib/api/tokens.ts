/** API-token management helpers — list, create, revoke. */
import { api } from "./client";
import type { components } from "./schema";

export type ApiToken = components["schemas"]["ApiTokenRead"];
export type ApiTokenCreated = components["schemas"]["ApiTokenCreated"];

export async function fetchTokens(): Promise<ApiToken[]> {
  const { data, error } = await api.GET("/api/tokens");
  if (error || !data) throw new Error("Failed to load API tokens");
  return data;
}

export async function createToken(name: string, role: string): Promise<ApiTokenCreated> {
  const { data, error } = await api.POST("/api/tokens", {
    body: { name, role: role as "admin" | "user" },
  });
  if (error || !data) throw new Error("Failed to create API token");
  return data;
}

export async function revokeToken(id: number): Promise<void> {
  const { error } = await api.DELETE("/api/tokens/{token_id}", {
    params: { path: { token_id: id } },
  });
  if (error) throw new Error("Failed to revoke API token");
}
