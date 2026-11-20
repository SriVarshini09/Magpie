// "Every store" (PLAN §11.6 core 1): one row per offer. Order: chosen, alternatives (with "+$4.01 vs. chosen"),
// then a collapsed Rejected (n) group (grey: reason and rerank score) and a Refused (n) group (red tint: the
// mandate clause). Unknown shipping, ETA and rating read "not quoted". Every row shows its action-level badge.
// The same table is the Swap dialog on the cart (§12.3).
import { ChevronRight, ExternalLink, ShieldX, Star } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Money } from "@/components/common/Money";
import { ToneBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { hostOf, money, moneyDelta, NOT_QUOTED, plural, timeOf, viaText } from "@/lib/format";
import type { OfferRow, PanelRefusal, SpecRead } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ActionBadge } from "./ActionBadge";

const STOCK: Record<OfferRow["stock"], string> = { in_stock: "In stock", out_of_stock: "Out of stock", unknown: "Stock not quoted" };

/** Mock offers point at the reserved mock.invalid host: there is no store page to open. */
export function StoreLink({ url, children = "View at store", className }: { url: string; children?: ReactNode; className?: string }) {
  if (hostOf(url).endsWith("mock.invalid")) {
    return <span className={cn("text-caption text-test", className)} title="Mock data has no real store page.">No store page (mock)</span>;
  }
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={cn("inline-flex items-center gap-1 text-caption font-medium text-brand hover:text-brand-hover", className)}>
      {children}
      <ExternalLink className="size-3" strokeWidth={1.75} aria-hidden />
    </a>
  );
}

function Facts({ offer }: { offer: OfferRow }) {
  const quoted = "text-secondary-text";
  const missing = "text-muted-foreground";
  return (
    <p className="flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-caption">
      <span className={offer.shipping_usd == null ? missing : quoted}>Shipping {offer.shipping_usd == null ? NOT_QUOTED : offer.shipping_usd === 0 ? "free" : money(offer.shipping_usd)}</span>
      <span className={offer.eta_text ? quoted : missing}>ETA {offer.eta_text ?? NOT_QUOTED}</span>
      <span className={offer.stock === "in_stock" ? quoted : offer.stock === "out_of_stock" ? "text-fail" : missing}>{STOCK[offer.stock] ?? STOCK.unknown}</span>
      {offer.rating != null ? (
        <span className={cn("inline-flex items-center gap-0.5", quoted)}>
          <Star className="size-3" strokeWidth={1.75} aria-hidden />
          {offer.rating.toFixed(1)}
          {offer.reviews != null ? ` (${offer.reviews})` : ""}
        </span>
      ) : (
        <span className={missing}>Rating {NOT_QUOTED}</span>
      )}
    </p>
  );
}

const SPEC_UNIT: Record<string, (v: string) => string> = {
  cells: (v) => `${v}S`,
  capacity_mah: (v) => `${v} mAh`,
  current_a: (v) => `${v}A`,
  voltage_v: (v) => `${v}V`,
  kv: (v) => `${v}KV`,
  prop_in: (v) => `${v}-inch`,
  connector: (v) => v.replace(/^BARREL-/, "barrel "),
};
const SPEC_NAME: Record<string, string> = {
  mount_mm: "stack mounting pattern", stator: "motor stator size", prop_in: "prop size", cells: "battery cells", capacity_mah: "battery capacity",
  connector: "connector", current_a: "current rating", voltage_v: "voltage", kv: "motor KV",
};

/** Specs read from the listing text and judged by the compatibility rules. Live: SIE extract. Mock services: a
 *  local pattern reader, shown violet and dashed as "Mock SIE" (never as SIE). */
function SpecReads({ reads }: { reads: SpecRead[] }) {
  const seen = new Set<string>();
  const chips = reads.filter((r) => {
    const key = `${r.attr}:${r.value}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (!chips.length) return null;
  const mock = chips.some((r) => r.simulated || r.provider !== "sie");
  return (
    <p className="flex flex-wrap items-center gap-1 text-caption text-muted-foreground" data-testid="spec-reads" data-provider={mock ? "mock" : "sie"}>
      <span className={mock ? "font-medium text-test" : undefined} title={mock ? "Mock data: a local pattern reader stands in for Superlinked SIE extract. The compatibility rules judge these values." : "Read from the listing text by Superlinked SIE extract. The compatibility rules judge these values."}>
        {mock ? "Mock SIE read:" : "Read by SIE:"}
      </span>
      {chips.map((r) => (
        <span
          key={`${r.attr}:${r.value}`}
          title={`${SPEC_NAME[r.attr] ?? r.attr}: “${r.text}” in the ${r.field}${r.score != null ? `, score ${r.score.toFixed(2)}` : ""}${mock ? " (mock reader)" : ""}`}
          className={cn("tabular rounded-sm border px-1 py-px", mock ? "border-dashed border-test bg-test-tint text-test" : "border-border bg-surface text-secondary-text")}
        >
          {(SPEC_UNIT[r.attr] ?? ((v: string) => v))(r.value)}
        </span>
      ))}
    </p>
  );
}

function Row({ offer, qty, onUse, busy }: { offer: OfferRow; qty: number; onUse?: (offer: OfferRow) => void; busy?: boolean }) {
  const tone = offer.status === "refused" ? "bg-fail-tint" : offer.status === "rejected" ? "bg-muted/60" : offer.status === "chosen" ? "bg-brand-tint/50" : "bg-surface";
  const packs = `${offer.packs_needed} × ${offer.units_per_pack > 1 ? `${offer.units_per_pack}-pack` : "single"} at ${money(offer.price_usd)}`;
  return (
    <li className={cn("space-y-1.5 border-b border-border px-3 py-2.5 last:border-b-0", tone)} data-status={offer.status}>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-1.5 text-small font-medium text-foreground">
            {offer.store_name}
            {offer.seller_name ? <span className="font-normal text-muted-foreground">sold by {offer.seller_name}</span> : null}
            <ActionBadge level={offer.action_level} reason={offer.downgrade_reason} />
          </p>
          <p className={cn("truncate text-caption", offer.status === "rejected" || offer.status === "refused" ? "text-muted-foreground" : "text-secondary-text")} title={offer.title}>
            {offer.title}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-small">
            <Money value={offer.line_usd} seenAt={offer.seen_at} source={offer.source_api} mockOf={offer.mock_of} simulated={offer.simulated} className={cn("font-semibold", (offer.status === "rejected" || offer.status === "refused") && "text-muted-foreground")} />
          </p>
          <p className="tabular text-caption text-muted-foreground">
            {offer.status === "chosen" ? "chosen" : offer.status === "alternative" && offer.vs_chosen_usd != null ? `${moneyDelta(offer.vs_chosen_usd)} vs. chosen` : `for ${qty}`}
          </p>
        </div>
      </div>

      {offer.status === "rejected" ? (
        <p className="text-caption text-secondary-text">
          Rejected: {offer.reason ?? "no reason recorded"}
          {offer.rerank_score != null ? <span className="tabular text-muted-foreground"> · rerank {offer.rerank_score.toFixed(2)}</span> : null}
        </p>
      ) : offer.status === "refused" ? (
        <p className="flex items-start gap-1.5 text-caption text-fail">
          <ShieldX className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
          <span>
            {offer.reason?.startsWith("constraints.data_sharing")
              ? "Refused: this listing asked for your contact details. Its text is treated as data, and nothing is bought from it."
              : `Refused: ${offer.store_name} isn’t in your mandate.`}{" "}
            Clause <code className="rounded-sm bg-surface px-1 font-mono text-foreground">{offer.reason ?? "not recorded"}</code>
          </span>
        </p>
      ) : (
        <Facts offer={offer} />
      )}
      {offer.status !== "refused" && offer.spec_reads?.length ? <SpecReads reads={offer.spec_reads} /> : null}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted-foreground">
        <span>{packs}</span>
        <span>
          seen {timeOf(offer.seen_at)} · {viaText(offer.source_api, offer.mock_of)}
        </span>
        <span className="ml-auto flex items-center gap-2">
          {offer.status !== "refused" ? <StoreLink url={offer.url} /> : null}
          {offer.status === "alternative" && onUse ? (
            <Button size="xs" variant="outline" disabled={busy} onClick={() => onUse(offer)}>
              Use this offer
            </Button>
          ) : null}
        </span>
      </div>
    </li>
  );
}

function Group({ title, count, tone, defaultOpen = false, children }: { title: string; count: number; tone: "info" | "fail"; defaultOpen?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!count) return null;
  return (
    <div className={cn("overflow-hidden rounded-lg border", tone === "fail" ? "border-fail/30" : "border-border")}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={cn("flex h-9 w-full items-center gap-2 px-3 text-small font-medium -outline-offset-2", tone === "fail" ? "bg-fail-tint text-fail" : "bg-muted text-secondary-text")}
      >
        <ChevronRight className={cn("size-4 transition-transform duration-150", open && "rotate-90")} strokeWidth={1.75} aria-hidden />
        {title} ({count})
      </button>
      {open ? <ul className="border-t border-border">{children}</ul> : null}
    </div>
  );
}

export type OfferTableProps = {
  offers: OfferRow[];
  qty: number;
  refusals?: PanelRefusal[];
  /** Makes alternative rows actionable: a cart edit (PLAN §12.3). */
  onUse?: (offer: OfferRow) => void;
  busy?: boolean;
  /** Open the Rejected and Refused groups from the start. */
  expandAll?: boolean;
};

export function OfferTable({ offers, qty, refusals = [], onUse, busy, expandAll = false }: OfferTableProps) {
  const chosen = offers.filter((o) => o.status === "chosen");
  const alternatives = offers.filter((o) => o.status === "alternative").sort((a, b) => a.line_usd - b.line_usd);
  const rejected = offers.filter((o) => o.status === "rejected");
  const refused = offers.filter((o) => o.status === "refused");
  // Refusals with no listing behind them (a store named by the source document, for example).
  const refusedStores = new Set(refused.map((o) => o.store_id));
  const bare = refusals.filter((r) => !refusedStores.has(r.attempted));
  const live = [...chosen, ...alternatives];

  return (
    <div className="space-y-3">
      {live.length ? (
        <ul className="overflow-hidden rounded-lg border border-border" aria-label="Offers from every store">
          {live.map((o) => (
            <Row key={o.offer_id} offer={o} qty={qty} onUse={onUse} busy={busy} />
          ))}
        </ul>
      ) : (
        <p className="rounded-lg border border-border bg-muted px-3 py-4 text-center text-small text-secondary-text">No acceptable offer in your stores.{rejected.length ? " The rejected listings below say why." : ""}</p>
      )}
      <Group title="Rejected" count={rejected.length} tone="info" defaultOpen={expandAll}>
        {rejected.map((o) => (
          <Row key={o.offer_id} offer={o} qty={qty} />
        ))}
      </Group>
      <Group title="Refused" count={refused.length + bare.length} tone="fail" defaultOpen={expandAll}>
        {refused.map((o) => (
          <Row key={o.offer_id} offer={o} qty={qty} />
        ))}
        {bare.map((r, i) => (
          <li key={`${r.attempted}-${i}`} className="flex items-start gap-1.5 border-b border-border bg-fail-tint px-3 py-2.5 text-caption text-fail last:border-b-0">
            <ShieldX className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
            <span>
              Refused: <span className="font-medium">{r.attempted}</span> ({r.triggered_by.replace(/_/g, " ")}
              {r.count > 1 ? `, ${plural(r.count, "time")}` : ""}). Clause <code className="rounded-sm bg-surface px-1 font-mono text-foreground">{r.clause}</code>
            </span>
          </li>
        ))}
      </Group>
    </div>
  );
}

export function ChosenBadge() {
  return (
    <ToneBadge tone="brand" icon={Star}>
      Chosen
    </ToneBadge>
  );
}
