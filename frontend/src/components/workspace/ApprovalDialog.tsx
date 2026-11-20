// Approval dialog (PLAN §11.5 D), opened by Approve cart on the cart page. One line per store with its badge
// and subtotal, the total, how fresh the prices are, the warnings that need acknowledging (checkboxes), and what
// happens next. Primary "Approve and start checkout", secondary "Not yet".
import { ShieldX } from "lucide-react";
import { useEffect, useState } from "react";

import { Money } from "@/components/common/Money";
import { ActionBadge } from "@/components/panel/ActionBadge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { plural } from "@/lib/format";
import type { Check, UniversalCart } from "@/lib/types";

function nextText(cart: UniversalCart): string {
  const c = cart.counts;
  const parts = [
    c.agent_cart ? `create ${c.agent_cart === 1 ? "a cart" : "carts"} at ${plural(c.agent_cart, "store")}` : null,
    c.prefilled_cart ? `build ${plural(c.prefilled_cart, "prefilled cart link")}` : null,
    c.product_link ? `link the product pages at ${plural(c.product_link, "store")}` : null,
  ].filter(Boolean);
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : (parts[0] ?? "prepare the hand-offs");
  return `We ${list}. Nothing is charged. This signs a closed mandate bound to these items and prices; any later edit needs a new approval.`;
}

export function ApprovalDialog({
  cart,
  warnings,
  freshness,
  open,
  onOpenChange,
  onApprove,
  busy,
  error,
}: {
  cart: UniversalCart;
  /** Checks with `needs_ack`: each one is ticked before the button enables. */
  warnings: Check[];
  freshness: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: (acknowledged: string[]) => void;
  busy: boolean;
  error?: string | null;
}) {
  const [acked, setAcked] = useState<Record<string, boolean>>({});
  useEffect(() => {
    if (open) setAcked({});
  }, [open]);
  // One rule can warn about several parts (G1 for each powered part): each warning is its own tick.
  const keyOf = (w: Check, i: number) => `${w.rule_id}:${i}`;
  const allAcked = warnings.every((w, i) => acked[keyOf(w, i)]);
  const stores = [...cart.stores].sort((a, b) => a.order - b.order);
  const simulated = cart.simulated;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100vh-2rem)] gap-5 overflow-y-auto sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="text-h3">Approve this cart</DialogTitle>
          <DialogDescription>{freshness}</DialogDescription>
        </DialogHeader>

        <div className="rounded-lg border border-border">
          <ul className="divide-y divide-border">
            {stores.map((s) => (
              <li key={s.store_id} className="flex items-center gap-2 px-3 py-2.5 text-body">
                <span className="min-w-0 flex-1 truncate font-medium">{s.display_name}</span>
                <ActionBadge level={s.action_level} reason={s.downgrade_reason} />
                <Money value={s.subtotal_usd} simulated={simulated} className="w-24 text-right" />
              </li>
            ))}
          </ul>
          <p className="flex items-center justify-between border-t border-border bg-muted px-3 py-2.5 text-body font-semibold">
            <span>Items total · {plural(stores.length, "store")}</span>
            <Money value={cart.total_usd} simulated={simulated} />
          </p>
        </div>

        <ul className="space-y-1.5 text-small text-secondary-text">
          <li>Shipping and tax aren’t included. Each store adds them at its checkout.</li>
          {simulated ? <li className="text-test">Mock data: these stores, prices and hand-offs are simulated.</li> : null}
        </ul>

        {warnings.length ? (
          <fieldset className="max-h-56 space-y-2 overflow-y-auto rounded-lg border border-warn/40 bg-warn-tint p-3">
            <legend className="px-1 text-small font-semibold text-warn">Tick each warning to acknowledge it</legend>
            {warnings.map((w, i) => (
              <label key={keyOf(w, i)} className="flex items-start gap-2.5 text-small text-foreground">
                <Checkbox aria-label={`Acknowledge ${w.rule_id}: ${w.message}`} className="mt-0.5 bg-surface" checked={acked[keyOf(w, i)] ?? false} onCheckedChange={(v) => setAcked((cur) => ({ ...cur, [keyOf(w, i)]: v === true }))} />
                <span>
                  <span className="font-mono text-caption text-secondary-text">{w.rule_id}</span>
                  <br />
                  {w.message}
                </span>
              </label>
            ))}
          </fieldset>
        ) : null}

        <div className="rounded-lg bg-muted p-3">
          <p className="text-small font-semibold">What happens next</p>
          <p className="mt-1 text-small text-secondary-text">{nextText(cart)}</p>
        </div>

        {error ? (
          <p role="alert" className="flex items-start gap-2 rounded-lg border border-fail/30 bg-fail-tint px-3 py-2 text-small text-fail">
            <ShieldX className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} aria-hidden />
            {error}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="outline" size="lg" className="h-10 px-4" onClick={() => onOpenChange(false)} disabled={busy}>
            Not yet
          </Button>
          <Button size="lg" className="h-10 px-4 font-semibold" disabled={busy || !allAcked} onClick={() => onApprove([...new Set(warnings.map((w) => w.rule_id))])}>
            {busy ? "Signing…" : "Approve and start checkout"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
