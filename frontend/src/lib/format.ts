// Formatting and label helpers shared by every screen. Owner: C.
// One money format, one time format, one hash format (PLAN §11.10 Q5, Q6).
import type { ActionLevel, BomStatus, BuildType, LeftOutReason, ProvenanceType } from "@/lib/types";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const clock = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });
const clockSec = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
const day = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });

export const NOT_QUOTED = "not quoted";

/**
 * The honest label for a mandate signature, or null when it is a real signature over real data.
 * A placeholder cannot be checked; the fixture key is public (format only); a run on mock stores is signed
 * for real with the demo key, but what it signs is simulated.
 */
export function signatureNote(signature: { jws: string; kid: string; alg: string } | null | undefined, simulated: boolean | null | undefined): string | null {
  if (!signature || !signature.jws || signature.alg === "none") return "Not signed";
  if (signature.jws.startsWith("MOCK")) return "Mock signature, not verifiable";
  if (signature.kid === "fixture-key-1") return "Sample signature (public fixture key)";
  return simulated ? "Signed with the demo key · mock data" : null;
}

export function isNum(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** "$74.95"; unknown values read "not quoted", never a guess. */
export function money(v: number | null | undefined): string {
  return isNum(v) ? usd.format(v) : NOT_QUOTED;
}

/** "$160" for budgets and round figures; keeps cents when there are any. */
export function moneyShort(v: number | null | undefined): string {
  if (!isNum(v)) return NOT_QUOTED;
  return Number.isInteger(v) ? usd0.format(v) : usd.format(v);
}

/** "+$4.01" / "−$1.20" */
export function moneyDelta(v: number): string {
  return `${v < 0 ? "−" : "+"}${usd.format(Math.abs(v))}`;
}

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "1:04 PM" */
export function timeOf(iso: string | null | undefined): string {
  const d = parse(iso);
  return d ? clock.format(d) : "time unknown";
}

/** "1:00:12 PM" for the timeline. */
export function timeOfSec(iso: string | null | undefined): string {
  const d = parse(iso);
  return d ? clockSec.format(d) : "";
}

/** "Dec 4" */
export function dayOf(iso: string | null | undefined): string {
  // A bare date ("2026-12-04") is a calendar day, not midnight UTC.
  const d = parse(iso && /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T12:00:00` : iso);
  return d ? day.format(d) : "no date";
}

/** "3 min ago", "just now", "2 h ago"; the clock time once it is over a day old or in the future. */
export function ago(iso: string | null | undefined, now = Date.now()): string {
  const d = parse(iso);
  if (!d) return "time unknown";
  const min = Math.round((now - d.getTime()) / 60000);
  if (min < 0) return `at ${clock.format(d)}`;
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  if (min < 24 * 60) return `${Math.round(min / 60)} h ago`;
  return `${day.format(d)}, ${clock.format(d)}`;
}

export function ageMinutes(iso: string | null | undefined, now = Date.now()): number | null {
  const d = parse(iso);
  return d ? (now - d.getTime()) / 60000 : null;
}

/** "3f9a…c21e" (the sha256: prefix is dropped for display). */
export function shortHash(hash: string | null | undefined, head = 4, tail = 4): string {
  if (!hash) return "no hash";
  const h = hash.replace(/^sha256:/, "");
  return h.length <= head + tail + 1 ? h : `${h.slice(0, head)}…${h.slice(-tail)}`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

export const BUILD_TYPE_LABEL: Record<BuildType, string> = {
  robot_arm: "Robot arm",
  quadcopter: "Quadcopter",
  rc_car: "RC car",
  claw_gripper: "Claw gripper",
  electronics_mcu: "Microcontroller project",
  generic: "Something else",
};

/** Wording fixed in PLAN §3.16. */
export const ACTION_LABEL: Record<ActionLevel, string> = {
  agent_cart: "Agent cart",
  prefilled_cart: "Prefilled cart",
  product_link: "Product link",
};

export const HANDOFF_VERB: Record<ActionLevel, string> = {
  agent_cart: "Open cart",
  prefilled_cart: "Open prefilled cart",
  product_link: "Open product page",
};

export const PROVENANCE_LABEL: Record<ProvenanceType, string> = {
  readme_quote: "Quoted",
  reference_project: "Reference design",
  template_row: "Template",
  photo_region: "Seen in your photo",
  assumption: "Assumed",
};

export const LEFT_OUT_LABEL: Record<LeftOutReason, string> = {
  owned: "you own it",
  removed_by_you: "removed by you",
  print_at_home: "print at home",
  not_found: "not found in your stores",
};

export const STATUS_LABEL: Record<BomStatus, string> = {
  extracted: "Reading",
  resolved: "Searching",
  owned: "Owned",
  offers: "Comparing",
  chosen: "Chosen",
  warning: "Needs your check",
  needs_human: "Needs your check",
  not_found: "Not found",
  skipped: "Left out",
  removed: "Removed",
};

/** Names behind `source_api`, `mock_of` and event providers, e.g. "via SerpAPI". Text only, no logos. */
const SOURCE_NAMES: Record<string, string> = {
  shopify_ucp: "Shopify UCP",
  shopify: "Shopify",
  serpapi: "SerpAPI",
  adafruit: "Adafruit catalog",
  magento: "store catalog",
  digikey: "Digi-Key API",
  cartlinks: "cart link",
  "airbyte.github": "Airbyte",
  airbyte: "Airbyte",
  airbyte_github: "GitHub source",
  github_raw: "GitHub, direct fetch",
  http: "direct fetch",
  keenable: "Keenable",
  exa_airbyte: "Exa via Airbyte",
  claude_web_search: "Claude web search",
  github_search: "GitHub search",
  template: "the template",
  singlestore: "SingleStore",
  sie: "Superlinked SIE",
  cognee: "Cognee",
  amplitude: "Amplitude",
  statsig: "Statsig",
  anthropic: "Claude",
  stripe: "Stripe test mode",
  stripe_test: "Stripe test mode",
  claude: "Claude",
  github: "GitHub",
  huggingface: "Hugging Face",
  mock: "mock data",
};

export function sourceName(key: string | null | undefined): string {
  if (!key) return "source unknown";
  return SOURCE_NAMES[key] ?? SOURCE_NAMES[key.split(":")[0]] ?? key;
}

/** Mock offers stay labelled as mock while still showing which adapter they stand in for. */
export function viaText(sourceApi: string | null | undefined, mockOf?: string | null): string {
  if (sourceApi === "mock") {
    if (mockOf === "mock") return "mock data, simulated store";
    return mockOf ? `mock data, standing in for ${sourceName(mockOf)}` : "mock data";
  }
  return `via ${sourceName(sourceApi)}`;
}

export function reasonCode(code: string): string {
  return code.replace(/_/g, " ");
}

export function hostOf(url: string | null | undefined): string {
  if (!url) return "";
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** "TheRobotStudio/SO-ARM100" from a GitHub URL; the host otherwise. */
export function repoOf(url: string | null | undefined): string {
  if (!url) return "";
  const m = /github\.com\/([^/]+\/[^/#?]+)/.exec(url);
  return m ? m[1] : hostOf(url);
}

const URL_RE = /https?:\/\/[^\s<>"')]+/i;
export function firstUrl(text: string): string | null {
  return URL_RE.exec(text)?.[0] ?? null;
}
