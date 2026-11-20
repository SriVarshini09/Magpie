// Receipt helpers (PLAN §3.7, §11.5 E). Owner: D.
// Record grouping for the chain filters, one-line summaries, and the receipt.json download.
import { money, sourceName } from "@/lib/format";
import type { ChainRecord, ProvenanceType, Receipt, RecordKind } from "@/lib/types";

export type ChainFilter = "all" | "mandates" | "refusals" | "decisions" | "cart" | "payment" | "other";

export const FILTER_LABEL: Record<ChainFilter, string> = {
  all: "All",
  mandates: "Mandates",
  refusals: "Refusals",
  decisions: "Decisions",
  cart: "Cart and hand-offs",
  payment: "Test payment",
  other: "Inputs and lookups",
};

const GROUPS: Record<Exclude<ChainFilter, "all">, ReadonlySet<RecordKind>> = {
  mandates: new Set<RecordKind>(["mandate_open", "approval", "mandate_closed", "payment_mandate"]),
  refusals: new Set<RecordKind>(["refusal"]),
  decisions: new Set<RecordKind>(["part_decision", "compat_fix", "plan", "assumption", "extraction_rejected"]),
  cart: new Set<RecordKind>(["cart_edit", "cart_action", "price_refresh", "handoff"]),
  payment: new Set<RecordKind>(["payment_mandate", "payment_hold", "issuing_card", "issuing_authorization", "payment_capture"]),
  other: new Set<RecordKind>(["intake", "source_fetch", "template_load", "reference_search", "photo_parts", "kb_search", "memory_write"]),
};

export function inFilter(rec: ChainRecord, filter: ChainFilter): boolean {
  if (filter === "all") return true;
  const group = GROUPS[filter];
  // A kind nobody listed yet still shows up under "Inputs and lookups", so no record is ever hidden from every filter.
  if (filter === "other") return group.has(rec.kind) || !Object.values(GROUPS).some((g) => g.has(rec.kind));
  return group.has(rec.kind);
}

export function countByFilter(records: ChainRecord[]): Record<ChainFilter, number> {
  const out = { all: records.length, mandates: 0, refusals: 0, decisions: 0, cart: 0, payment: 0, other: 0 } as Record<ChainFilter, number>;
  for (const r of records) {
    for (const f of Object.keys(GROUPS) as Array<Exclude<ChainFilter, "all">>) if (inFilter(r, f)) out[f] += 1;
  }
  return out;
}

export const KIND_LABEL: Partial<Record<RecordKind, string>> = {
  intake: "Request read",
  mandate_open: "Open mandate signed",
  source_fetch: "Source read",
  template_load: "Template loaded",
  reference_search: "Reference search",
  photo_parts: "Parts seen in photo",
  kb_search: "Knowledge-base search",
  part_decision: "Part decision",
  refusal: "Refused",
  extraction_rejected: "Line dropped",
  compat_fix: "Compatibility fix",
  plan: "Plan",
  assumption: "Assumption",
  cart_edit: "Cart edit",
  price_refresh: "Prices refreshed",
  approval: "Approved",
  mandate_closed: "Closed mandate signed",
  cart_action: "Cart action",
  handoff: "Hand-off",
  payment_mandate: "Payment mandate (test)",
  payment_hold: "Test hold",
  issuing_card: "Test card issued",
  issuing_authorization: "Test authorization",
  payment_capture: "Test capture",
  memory_write: "Memory written",
};

export function kindLabel(kind: RecordKind): string {
  return KIND_LABEL[kind] ?? kind.replace(/_/g, " ");
}

type Dict = Record<string, unknown>;

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const obj = (v: unknown): Dict | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as Dict) : null);
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

function joinParts(parts: Array<string | null | undefined | false>): string {
  return parts.filter(Boolean).join(" · ");
}

function answersText(v: unknown): string | null {
  const a = obj(v);
  if (!a) return null;
  const pairs = Object.entries(a).map(([k, val]) => `${k.replace(/_/g, " ")}: ${String(val)}`);
  return pairs.length ? pairs.join(", ") : null;
}

/** One plain sentence per record. Unknown kinds fall back to their scalar fields. */
export function summarize(rec: ChainRecord): string {
  const r = rec as Dict;
  switch (rec.kind) {
    case "intake":
      return joinParts([str(r.build_type)?.replace(/_/g, " "), num(r.confidence) !== null ? `confidence ${num(r.confidence)!.toFixed(2)}` : null, answersText(r.answers)]);
    case "mandate_open":
      return joinParts([str(r.mandate_id), "inputs and limits fixed before any tool call"]);
    case "source_fetch":
      return joinParts([
        str(r.path),
        str(r.commit_sha) ? `commit ${str(r.commit_sha)!.slice(0, 7)}` : null,
        str(r.via) ? `read through ${sourceName(str(r.via))}` : null,
        num(r.bytes) !== null ? `${num(r.bytes)!.toLocaleString("en-US")} bytes` : null,
      ]);
    case "template_load":
      return joinParts([str(r.template_id), str(r.variant) ? `variant ${str(r.variant)}` : null]);
    case "kb_search":
      return joinParts([str(r.query) ? `“${str(r.query)}”` : null, `${arr(r.kb_refs).length} rows cited`]);
    case "reference_search":
      return joinParts([str(r.provider) ? sourceName(str(r.provider)) : null, str(r.query) ? `“${str(r.query)}”` : null, str(r.url)]);
    case "photo_parts":
      return joinParts([str(r.detector), `${arr(r.boxes).length} regions`]);
    case "part_decision": {
      const part = obj(r.part);
      const decision = obj(r.decision);
      return joinParts([
        part ? `${str(part.bom_line_id) ?? ""} ${str(part.raw_name) ?? ""}`.trim() : null,
        decision ? `${arr(decision.chosen).length} offer${arr(decision.chosen).length === 1 ? "" : "s"} chosen` : null,
        `${arr(r.candidates).length} candidates`,
        arr(r.rejected).length ? `${arr(r.rejected).length} rejected` : null,
        arr(r.mandate_checks).length ? `${arr(r.mandate_checks).length} mandate checks` : null,
      ]);
    }
    case "refusal": {
      const ref = obj(r.refusal) ?? r;
      const attempted = obj(ref.attempted);
      return joinParts([
        str(ref.rule)?.replace(/_/g, " "),
        attempted ? joinParts([str(attempted.tool), str(attempted.field), str(attempted.value)]) : null,
        str(ref.triggered_by) ? `triggered by ${str(ref.triggered_by)!.replace(/_/g, " ")}` : null,
      ]);
    }
    case "extraction_rejected":
      return joinParts([str(r.raw_name), str(r.reason)]);
    case "compat_fix":
      return joinParts([str(r.rule_id), str(r.before) && str(r.after) ? `${str(r.before)} → ${str(r.after)}` : null]);
    case "plan":
      return joinParts([str(r.tier) ? `${str(r.tier)} tier` : null, num(r.total_usd) !== null ? money(num(r.total_usd)) : null, str(r.plan_id)]);
    case "assumption":
      return joinParts([str(r.bom_line_id), str(r.action), str(r.statement)]);
    case "cart_edit":
      return joinParts([str(r.op)?.replace(/_/g, " "), str(r.bom_line_id), str(r.by) ? `by ${str(r.by)}` : null]);
    case "price_refresh":
      return `${arr(r.changes).length} price changes`;
    case "approval": {
      const acks = arr(r.acknowledged_warnings).map(String);
      return joinParts([str(r.approved_by) === "ui_button" ? "approved with the button in the UI" : str(r.approved_by), acks.length ? `acknowledged ${acks.join(", ")}` : null]);
    }
    case "mandate_closed":
      return joinParts([num(r.total_usd) !== null ? money(num(r.total_usd)) : null, "cart and hand-offs bound by hash"]);
    case "handoff":
      return joinParts([str(r.store_id), str(r.level)?.replace(/_/g, " "), str(r.state)]);
    case "memory_write":
      return joinParts([str(r.text) ?? str(r.memory_text), str(r.provider) ? `via ${sourceName(str(r.provider))}` : null]);
    default: {
      const scalars = Object.entries(r)
        .filter(([k, v]) => !["run_id", "seq", "ts", "kind", "prev_hash", "hash", "simulated"].includes(k) && (typeof v === "string" || typeof v === "number"))
        .slice(0, 3)
        .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`);
      return scalars.join(" · ");
    }
  }
}

/** The refusal body, whether it is nested under `refusal` (chain records) or flat. */
export function refusalOf(rec: ChainRecord): { rule: string; clause: string; triggered_by: string } | null {
  if (rec.kind !== "refusal") return null;
  const r = rec as Dict;
  const ref = obj(r.refusal) ?? r;
  return { rule: str(ref.rule) ?? "refusal", clause: str(ref.clause) ?? "", triggered_by: str(ref.triggered_by) ?? "" };
}

export const PROVENANCE_ORDER: ProvenanceType[] = ["readme_quote", "reference_project", "template_row", "photo_region", "assumption"];

/** Fallback when the page has no RunState: count the provenance type of every part decision in the chain. */
export function provenanceCountsFromRecords(records: ChainRecord[]): Record<ProvenanceType, number> {
  const out = { readme_quote: 0, reference_project: 0, template_row: 0, photo_region: 0, assumption: 0 } as Record<ProvenanceType, number>;
  for (const rec of records) {
    if (rec.kind !== "part_decision") continue;
    const type = str(obj(obj((rec as Dict).part)?.provenance)?.type) as ProvenanceType | null;
    if (type && type in out) out[type] += 1;
  }
  return out;
}

/** Number of signed mandates in the receipt (open, closed, payment). */
export function signatureCount(receipt: Receipt): number {
  return [receipt.open_mandate?.signature, receipt.closed_mandate?.signature, receipt.payment_mandate?.signature].filter(Boolean).length;
}

/** "eyJhbGciOi…Xk2Q" for a compact JWS. */
export function shortJws(jws: string | null | undefined, head = 10, tail = 6): string {
  if (!jws) return "not signed";
  return jws.length <= head + tail + 1 ? jws : `${jws.slice(0, head)}…${jws.slice(-tail)}`;
}

/** True for the scaffold's placeholder signatures and keys (mock fixtures). */
export function isPlaceholderJws(jws: string | null | undefined): boolean {
  return !jws || jws.startsWith("MOCK");
}

export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
