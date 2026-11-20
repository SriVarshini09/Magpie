// One card per store (PLAN §12.6, §12.3). Header: store, domain, action-level badge, subtotal. Rows: the items.
// Footer: the hand-off. In a draft the button is shown disabled with what it will do. Once approved it is
// Open cart / Open prefilled cart / per-item Open product page, the caveat, and the Done / Skip tick.
// The current store of the run has a blue ring and "Store 2 of 4". Finished stores collapse with a check.
// Tier 2 adds, visually apart, a violet dashed stepper for the simulated store authorization.
import { Check, ChevronDown, CircleCheck, ExternalLink, FlaskConical, SkipForward, Undo2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Money } from "@/components/common/Money";
import { ACTION_ICON, ActionBadge } from "@/components/panel/ActionBadge";
import { Button } from "@/components/ui/button";
import { HANDOFF_VERB, hostOf, money, plural } from "@/lib/format";
import type { ActionLevel, CartItem, HandoffState, StoreGroup as StoreGroupData, StoreTest } from "@/lib/types";
import { cn } from "@/lib/utils";

const DRAFT_NOTE: Record<ActionLevel, (store: string) => string> = {
  agent_cart: (s) => `The agent creates a real cart at ${s} when you approve.`,
  prefilled_cart: (s) => `One link puts these items in your ${s} cart when you approve.`,
  product_link: (s) => `We link each product page at ${s}. You add the items yourself.`,
};
const OPEN_NOTE: Record<ActionLevel, (store: string) => string> = {
  agent_cart: (s) => `Opens the real cart the agent built at ${s}, on ${s}'s own checkout. You pay there; we never see your card.`,
  prefilled_cart: (s) => `Opens ${s} with these items in your cart. Compare it with the list above before you pay.`,
  product_link: (s) => `Each link opens the exact product page at ${s}. Add it to your cart there.`,
};

const TEST_STEPS: Array<{ id: StoreTest["state"]; label: (t: StoreTest) => string }> = [
  { id: "queued", label: () => "Queued" },
  { id: "card_issued", label: (t) => `Card issued${t.card_last4 ? ` •••• ${t.card_last4}` : ""}${t.limit_usd != null ? `, limit ${money(t.limit_usd)}` : ""}` },
  { id: "authorized", label: () => "Authorized (simulated)" },
  { id: "settled", label: () => "Settled (test)" },
];

function TestStepper({ test }: { test: StoreTest }) {
  const declined = test.state === "declined";
  const at = declined ? 2 : TEST_STEPS.findIndex((s) => s.id === test.state);
  return (
    <div className="mx-4 mb-4 rounded-lg border border-dashed border-test bg-test-tint px-3 py-2" aria-label="Test-mode store authorization (simulated)">
      <p className="mb-1 flex items-center gap-1.5 text-caption font-semibold text-test">
        <FlaskConical className="size-3.5" strokeWidth={1.75} aria-hidden />
        Test mode · simulated authorization, no real money
      </p>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption">
        {TEST_STEPS.map((step, i) => (
          <li key={step.id} className={cn("flex items-center gap-2", i <= at ? "font-medium text-test" : "text-muted-foreground")}>
            {i > 0 ? <span aria-hidden>→</span> : null}
            {declined && i === 2 ? "Declined (simulated)" : step.label(test)}
          </li>
        ))}
      </ol>
    </div>
  );
}

export type StoreGroupProps = {
  group: StoreGroupData;
  index: number;
  total: number;
  approved: boolean;
  current: boolean;
  busy: boolean;
  /** Rows for the items, rendered by the parent so edits live in one place. */
  children: ReactNode;
  onHandoff: (state: HandoffState) => void;
  /** Persists the per-item "added" tick of a product-link store. */
  onItemAdded?: (offerId: string, added: boolean) => void;
};

function isMockUrl(url: string) {
  return hostOf(url).endsWith("mock.invalid");
}

function OpenLink({ url, label, primary, onOpened }: { url: string; label: string; primary: boolean; onOpened: () => void }) {
  const mock = isMockUrl(url);
  const className = cn(
    "inline-flex h-10 items-center gap-2 rounded-lg px-4 text-body font-semibold transition-colors duration-150",
    primary ? "bg-ink text-white hover:bg-ink/85" : "border border-border-strong bg-surface text-foreground hover:bg-muted",
  );
  if (mock) {
    // Mock hand-offs point at the reserved mock.invalid host: there is nothing real to open.
    return (
      <button
        type="button"
        className={className}
        onClick={() => {
          onOpened();
          toast("Mock hand-off: there is no real store page to open.", { description: "With live stores this button opens the store in a new tab." });
        }}
      >
        {label}
        <span className="rounded-sm border border-dashed border-test bg-test-tint px-1 text-caption font-medium text-test">mock</span>
      </button>
    );
  }
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={className} onClick={onOpened}>
      {label}
      <ExternalLink className="size-4" strokeWidth={1.75} aria-hidden />
    </a>
  );
}

function ProductLinks({ items, onOpened, onItemAdded, busy }: { items: CartItem[]; onOpened: () => void; onItemAdded?: (offerId: string, added: boolean) => void; busy: boolean }) {
  // The tick lives on the backend with the cart (`item.added`); without a handler it is local only.
  const [local, setLocal] = useState<Record<string, boolean>>({});
  const isAdded = (item: CartItem) => (onItemAdded ? Boolean(item.added) : (local[item.offer_id] ?? Boolean(item.added)));
  const toggle = (item: CartItem, value: boolean) => (onItemAdded ? onItemAdded(item.offer_id, value) : setLocal((cur) => ({ ...cur, [item.offer_id]: value })));
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.offer_id} className="flex flex-wrap items-center gap-3">
          <OpenLink url={item.url} label={HANDOFF_VERB.product_link} primary={false} onOpened={onOpened} />
          <span className="min-w-0 flex-1 truncate text-small text-secondary-text">
            {item.title} · ×{item.qty}
          </span>
          <label className="flex items-center gap-1.5 text-small">
            <input type="checkbox" className="size-4 accent-ink" aria-label={`I added ${item.title} to my cart at the store`} checked={isAdded(item)} disabled={busy} onChange={(e) => toggle(item, e.target.checked)} />
            added
          </label>
        </li>
      ))}
    </ul>
  );
}

export function StoreGroup({ group, index, total, approved, current, busy, children, onHandoff, onItemAdded }: StoreGroupProps) {
  const state = group.handoff?.state ?? "ready";
  const finished = approved && (state === "done" || state === "skipped");
  const [expanded, setExpanded] = useState(false);
  const open = !finished || expanded;
  const Icon = ACTION_ICON[group.action_level];
  const simulated = group.items.some((i) => i.simulated);

  return (
    <motion.section
      layout="position"
      transition={{ type: "spring", stiffness: 420, damping: 36 }}
      aria-label={`${group.display_name}, ${plural(group.items.length, "item")}`}
      className={cn("overflow-hidden rounded-lg border bg-surface", current && approved && !finished ? "border-brand ring-2 ring-brand/30" : "border-border", finished && "bg-muted/40")}
    >
      <header className="flex items-center gap-3 px-4 py-3">
        {finished ? (
          <span className={cn("flex size-6 shrink-0 items-center justify-center rounded-full", state === "done" ? "bg-pass text-white" : "bg-border-strong text-white")}>
            {state === "done" ? <Check className="size-4" strokeWidth={2.5} aria-hidden /> : <SkipForward className="size-3.5" strokeWidth={2} aria-hidden />}
          </span>
        ) : null}
        <div className="min-w-0 flex-1">
          {approved ? (
            <p className={cn("text-caption font-medium", current && !finished ? "text-brand" : "text-muted-foreground")}>
              Store {index + 1} of {total}
              {current && !finished ? " · open this one now" : ""}
            </p>
          ) : null}
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-body-lg font-semibold">{group.display_name}</span>
            <span className="font-mono text-caption text-muted-foreground">{group.domain}</span>
            <ActionBadge level={group.action_level} reason={group.downgrade_reason} />
          </p>
          {finished ? (
            <p className="text-small text-secondary-text">
              {state === "done" ? `Done · marked by ${group.handoff?.done_via === "checkout_kit" ? "the store's checkout" : "you"}` : "Skipped by you"}
              {group.handoff?.order_id ? ` · order ${group.handoff.order_id}` : ""}
            </p>
          ) : null}
        </div>
        <Money value={group.subtotal_usd} simulated={simulated} className="text-h3 font-semibold" />
        {finished && !expanded ? (
          // Undo stays one click away on a collapsed store (the footer's Undo shows when it is expanded)
          <Button variant="outline" size="sm" disabled={busy} onClick={() => onHandoff("ready")} aria-label={`Undo: ${group.display_name} is not ${state === "done" ? "done" : "skipped"}`}>
            <Undo2 aria-hidden /> Undo
          </Button>
        ) : null}
        {finished ? (
          <Button variant="ghost" size="icon-sm" aria-expanded={expanded} aria-label={expanded ? "Hide the items" : "Show the items"} onClick={() => setExpanded((e) => !e)}>
            <ChevronDown className={cn("transition-transform duration-150", expanded && "rotate-180")} aria-hidden />
          </Button>
        ) : null}
      </header>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ type: "spring", stiffness: 420, damping: 38 }} className="overflow-hidden">
            <ul>{children}</ul>

            <footer className="space-y-2.5 border-t border-border bg-page/60 px-4 py-3.5">
              {!approved || !group.handoff ? (
                <div className="flex flex-wrap items-center gap-3">
                  <Button size="lg" className="h-10 px-4 text-body" disabled title="Available after you approve the cart">
                    <Icon aria-hidden /> {HANDOFF_VERB[group.action_level]}
                  </Button>
                  <p className="min-w-0 flex-1 text-small text-secondary-text">{approved ? `Creating the hand-off at ${group.display_name}…` : DRAFT_NOTE[group.action_level](group.display_name)}</p>
                </div>
              ) : (
                <>
                  {group.handoff.kind === "product_link" ? (
                    <ProductLinks items={group.items} busy={busy} onItemAdded={onItemAdded} onOpened={() => state === "ready" && onHandoff("opened")} />
                  ) : (
                    <div className="flex flex-wrap items-center gap-3">
                      <OpenLink url={group.handoff.url} label={HANDOFF_VERB[group.handoff.kind]} primary={current && !finished} onOpened={() => state === "ready" && onHandoff("opened")} />
                      {!isMockUrl(group.handoff.url) ? (
                        <a href={group.handoff.url} target="_blank" rel="noopener noreferrer" className="text-small font-medium text-brand hover:text-brand-hover" onClick={() => state === "ready" && onHandoff("opened")}>
                          Open in new tab
                        </a>
                      ) : null}
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-2">
                    {finished ? (
                      <Button variant="outline" size="sm" disabled={busy} onClick={() => onHandoff("ready")}>
                        <Undo2 aria-hidden /> Undo
                      </Button>
                    ) : (
                      <>
                        <Button variant="outline" size="lg" disabled={busy} onClick={() => onHandoff("done")}>
                          <CircleCheck aria-hidden /> Done
                        </Button>
                        <Button variant="ghost" size="lg" disabled={busy} onClick={() => onHandoff("skipped")}>
                          Skip
                        </Button>
                      </>
                    )}
                    {state === "opened" ? <span className="text-caption text-muted-foreground">Opened. Tick Done when you have paid at the store.</span> : null}
                  </div>
                  <p className="text-small text-secondary-text">
                    {group.handoff.caveat ? `${group.handoff.caveat}. ` : ""}
                    {isMockUrl(group.handoff.url) ? "Mock hand-off: nothing real was created at this store. With live stores: " : ""}
                    {OPEN_NOTE[group.handoff.kind](group.display_name)}
                  </p>
                </>
              )}
            </footer>
            {group.test ? <TestStepper test={group.test} /> : null}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}
