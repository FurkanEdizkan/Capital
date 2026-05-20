/**
 * Typed REST client for the engine API.
 *
 * `openapi-fetch` gives every request/response full type-safety from the
 * generated `schema.d.ts` — which is itself generated from the engine's
 * OpenAPI document (`web/openapi.json`). The contract is enforced end to end:
 * change an endpoint in the engine and the web build breaks until updated.
 */
import createClient from "openapi-fetch";

import type { paths } from "./schema";

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
});

/** Attach (or clear) the bearer access token used for authenticated calls. */
export function setAuthToken(token: string | null): void {
  api.use({
    onRequest({ request }) {
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  });
}
