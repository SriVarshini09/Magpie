/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_STATIC_REPLAY?: string;
  /** Public repository URL for the "GitHub" links. The links are hidden when it is not set. */
  readonly VITE_REPO_URL?: string;
  /** MUST start with pk_test_ (PLAN §3.3). */
  readonly VITE_STRIPE_PUBLISHABLE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
