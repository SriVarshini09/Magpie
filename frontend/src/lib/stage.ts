// What a part looks like in any view (3D mesh, diagram node, kit token, tray chip, photo box).
// One function decides the colour for the three colour modes, so every view agrees (PLAN §11.6 E1).
import type { ColourMode } from "@/lib/store";
import type { ActionLevel, BOMLine, BomStatus, PartCategory, RunState } from "@/lib/types";

export type StageLine = {
  id: string;
  name: string;
  qty: number;
  status: BomStatus;
  category: PartCategory | null;
  lineKind: BOMLine["line_kind"];
  storeId: string | null;
  storeName: string | null;
  level: ActionLevel | null;
  /** Sum of the chosen offers for this line; null when nothing is chosen. */
  price: number | null;
  seenAt: string | null;
  simulated: boolean;
  openAssumption: boolean;
  /** A compatibility rule failed for this line. */
  failed: boolean;
  ownedNote: string | null;
};

export type StageData = {
  lines: Map<string, StageLine>;
  /** store_id -> palette slot 1..8, in cart order. */
  storeSlot: Map<string, number>;
  storeNames: Map<string, string>;
};

const PENDING: BomStatus[] = ["extracted", "resolved", "offers"];

export function isPending(status: BomStatus): boolean {
  return PENDING.includes(status);
}

export function buildStageData(run: RunState): StageData {
  const lines = new Map<string, StageLine>();
  const storeSlot = new Map<string, number>();
  const storeNames = new Map<string, string>();
  const failedIds = new Set(run.checks.filter((c) => c.result === "fail").flatMap((c) => c.bom_line_ids));
  // Cart order first (the active plan), then any store only seen on a line.
  for (const id of run.plans[run.active_tier]?.stores ?? []) if (!storeSlot.has(id)) storeSlot.set(id, (storeSlot.size % 8) + 1);
  for (const line of run.bom) {
    const chosen = line.chosen ?? [];
    for (const c of chosen) {
      if (!storeSlot.has(c.store_id)) storeSlot.set(c.store_id, (storeSlot.size % 8) + 1);
      storeNames.set(c.store_id, c.store_name);
    }
    const first = chosen[0];
    lines.set(line.bom_line_id, {
      id: line.bom_line_id,
      name: line.raw_name,
      qty: line.qty,
      status: line.status,
      category: line.category ?? null,
      lineKind: line.line_kind,
      storeId: first?.store_id ?? null,
      storeName: first?.store_name ?? null,
      level: first?.action_level ?? null,
      price: chosen.length ? chosen.reduce((sum, c) => sum + c.price * c.packs, 0) : null,
      seenAt: first?.seen_at ?? null,
      simulated: chosen.some((c) => c.simulated),
      openAssumption: line.provenance.type === "assumption" && !line.provenance.confirmed_by_user,
      failed: failedIds.has(line.bom_line_id),
      ownedNote: line.owned_note ?? null,
    });
  }
  return { lines, storeSlot, storeNames };
}

/** CSS custom property names; resolved to colours by `token()` for three.js and used as var() in the DOM. */
export type Paint = {
  /** A token name such as "--b2c-warn", or null for the part's own material colour. */
  token: string | null;
  /** Owned, left out or not in this mode's legend: drawn at 35% opacity. */
  ghost: boolean;
};

export const LEVEL_TOKEN: Record<ActionLevel, string> = {
  // "Ink" on the dark stage is drawn in the stage's light text colour so it stays visible.
  agent_cart: "--b2c-stage-text",
  prefilled_cart: "--b2c-brand",
  product_link: "--b2c-level-product-link",
};

export function paintFor(line: StageLine | undefined, mode: ColourMode, data: StageData): Paint {
  if (!line) return { token: null, ghost: false };
  if (mode === "store") {
    const slot = line.storeId ? data.storeSlot.get(line.storeId) : undefined;
    return slot ? { token: `--b2c-store-${slot}`, ghost: false } : { token: "--b2c-mat-ghost", ghost: true };
  }
  if (mode === "checkout") {
    return line.level ? { token: LEVEL_TOKEN[line.level], ghost: false } : { token: "--b2c-mat-ghost", ghost: true };
  }
  // Status (default)
  if (line.failed) return { token: "--b2c-fail", ghost: false };
  if (line.openAssumption || line.status === "warning" || line.status === "needs_human") return { token: "--b2c-warn", ghost: false };
  if (line.status === "owned" || line.status === "removed") return { token: "--b2c-mat-ghost", ghost: true };
  if (line.status === "skipped") return line.category === "printed" ? { token: "--b2c-mat-printed", ghost: false } : { token: "--b2c-mat-ghost", ghost: true };
  if (line.status === "not_found") return { token: "--b2c-mat-ghost", ghost: true };
  return { token: null, ghost: false };
}

const cache = new Map<string, string>();
/** Reads a design token as a colour string three.js understands. */
export function token(name: string): string {
  const hit = cache.get(name);
  if (hit) return hit;
  const value = typeof window === "undefined" ? "" : getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const colour = value || "#71717a";
  if (value) cache.set(name, colour);
  return colour;
}

/** "motor 2 of 4" */
export function instanceLabel(name: string, index: number, total: number): string {
  return total > 1 ? `${name} ${index + 1} of ${total}` : name;
}
