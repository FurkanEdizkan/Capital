/** News API helpers — recent headlines and an on-demand refresh. */
import { api } from "./client";
import type { components } from "./schema";

export type NewsItem = components["schemas"]["NewsItem"];

export async function fetchNews(symbol?: string, limit = 50): Promise<NewsItem[]> {
  const { data, error } = await api.GET("/api/news", {
    params: { query: { symbol, limit } },
  });
  if (error || !data) throw new Error("Failed to load news");
  return data;
}

export async function refreshNews(): Promise<number> {
  const { data, error } = await api.POST("/api/news/refresh");
  if (error || !data) throw new Error("Failed to refresh news");
  return data.added;
}
