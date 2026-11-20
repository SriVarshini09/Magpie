// One item in a store group (PLAN §12.6): part name (click → back to the model with that part selected),
// listing title, quantity stepper, packs × unit price, line total with seen-at and source, Swap, Remove.
// Edited rows carry "edited by you"; a changed price shows old → new in amber.
import { Minus, Plus } from "lucide-react";

import { Money } from "@/components/common/Money";
import { Button } from "@/components/ui/button";
import { money, timeOf, viaText } from "@/lib/format";
import type { CartItem } from "@/lib/types";

export type CartItemRowProps = {
  item: CartItem;
  partName: string;
  /** Set only when the cart holds fewer of this part than the project needs: the BOM quantity. */
  bomQty: number | null;
  editable: boolean;
  busy: boolean;
  onOpenPart: () => void;
  onQty: (qty: number) => void;
  onSwap: () => void;
  onRemove: () => void;
};

export function CartItemRow({ item, partName, bomQty, editable, busy, onOpenPart, onQty, onSwap, onRemove }: CartItemRowProps) {
  const below = bomQty !== null;
  return (
    <li className="grid grid-cols-[1fr_auto_auto] items-start gap-x-4 gap-y-1 border-t border-border px-4 py-3">
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={onOpenPart} className="text-left text-body font-medium text-foreground underline-offset-2 hover:text-brand hover:underline" title="Show this part on the model">
            {partName}
          </button>
          {item.edited_by_user ? <span className="inline-flex h-5 items-center rounded-sm bg-brand-tint px-1.5 text-caption font-medium text-brand">edited by you</span> : null}
        </p>
        <p className="truncate text-small text-secondary-text" title={item.title}>
          {item.title}
        </p>
        <p className="tabular mt-0.5 font-mono text-caption text-muted-foreground">
          {item.packs} × {money(item.unit_price_usd)} · covers {item.qty}
        </p>
      </div>

      <div className="flex flex-col items-center gap-1">
        {editable ? (
          <div className="inline-flex h-8 items-center rounded-lg border border-border-strong" role="group" aria-label={`Quantity of ${partName}`}>
            <button type="button" disabled={busy || item.qty <= 1} onClick={() => onQty(item.qty - 1)} aria-label="One fewer" className="flex size-8 items-center justify-center rounded-l-lg text-secondary-text hover:bg-muted disabled:opacity-40">
              <Minus className="size-3.5" strokeWidth={2} aria-hidden />
            </button>
            <span className="tabular w-8 text-center font-mono text-small" aria-live="polite">
              {item.qty}
            </span>
            <button type="button" disabled={busy} onClick={() => onQty(item.qty + 1)} aria-label="One more" className="flex size-8 items-center justify-center rounded-r-lg text-secondary-text hover:bg-muted disabled:opacity-40">
              <Plus className="size-3.5" strokeWidth={2} aria-hidden />
            </button>
          </div>
        ) : (
          <span className="tabular inline-flex h-8 items-center font-mono text-small text-secondary-text">×{item.qty}</span>
        )}
        {below ? <span className="text-caption text-warn">The project needs {bomQty}</span> : null}
      </div>

      <div className="min-w-28 text-right">
        <Money value={item.line_usd} seenAt={item.seen_at} source={item.source_api} simulated={item.simulated} className="text-body font-semibold" />
        {item.changed ? (
          <p className="tabular font-mono text-caption text-warn">
            changed: {money(item.changed.old_usd)} → {money(item.line_usd)}
          </p>
        ) : (
          <p className="text-caption text-muted-foreground">
            seen {timeOf(item.seen_at)} · {viaText(item.source_api)}
          </p>
        )}
      </div>

      {editable ? (
        <div className="col-span-3 -ml-2 flex items-center gap-1">
          <Button variant="ghost" size="sm" disabled={busy} onClick={onSwap}>
            Swap{item.alternatives > 0 ? ` · +${item.alternatives} ${item.alternatives === 1 ? "offer" : "offers"}` : ""}
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={onRemove}>
            Remove
          </Button>
        </div>
      ) : null}
    </li>
  );
}
