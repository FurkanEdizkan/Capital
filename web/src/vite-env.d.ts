/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the engine API. Empty = same-origin (dev proxy / prod). */
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
