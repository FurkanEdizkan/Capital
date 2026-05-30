import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Engine origin for the dev proxy. Defaults to localhost for running Vite
// directly on the host; in Docker it's set to the compose service (engine:8000).
const engineTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // In dev the engine API is proxied so the web app talks to one origin.
    proxy: {
      "/api": { target: engineTarget, changeOrigin: true },
      "/ws": { target: engineTarget.replace(/^http/, "ws"), ws: true },
    },
  },
});
