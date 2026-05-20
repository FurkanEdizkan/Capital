/**
 * Typed REST client for the engine API.
 *
 * `openapi-fetch` gives every request/response full type-safety from the
 * generated `schema.d.ts` — itself generated from the engine's OpenAPI
 * document. Change an endpoint in the engine and the web build breaks until
 * the client is updated.
 */
import createClient from "openapi-fetch";

import type { paths } from "./schema";

export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
});

// The bearer token is held module-side; one middleware (registered once)
// attaches it to every request.
let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

api.use({
  onRequest({ request }) {
    if (authToken) request.headers.set("Authorization", `Bearer ${authToken}`);
    return request;
  },
});
