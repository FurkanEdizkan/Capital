/** Orders API — operator-placed manual orders. */
import { api } from "./client";
import type { components } from "./schema";

export type Fill = components["schemas"]["Fill"];
export type OrderSide = components["schemas"]["FillSide"];

export async function placeManualOrder(
  symbol: string,
  side: OrderSide,
  quantity: string,
  market = "spot",
): Promise<Fill> {
  const { data, error } = await api.POST("/api/orders/manual", {
    body: { symbol, side, quantity, market },
  });
  if (error || !data) {
    const detail =
      error && typeof error === "object" && "detail" in error
        ? String((error as { detail: unknown }).detail)
        : "Failed to place order";
    throw new Error(detail);
  }
  return data;
}
