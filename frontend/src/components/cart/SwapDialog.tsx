// Swap dialog (PLAN §12.3): "Swap" on a cart item opens the part's offer table, the same OfferTable as the part
// panel. Picking a row is a cart edit, checked by the guard; a refused row explains its clause instead.
import { useEffect, useState } from "react";

import { InlineError } from "@/components/common/States";
import { OfferTable } from "@/components/panel/OfferTable";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiFailure } from "@/lib/api";
import type { OfferRow, PartPanel } from "@/lib/types";

export function SwapDialog({ runId, bomLineId, open, onOpenChange, onPick, busy }: { runId: string; bomLineId: string | null; open: boolean; onOpenChange: (open: boolean) => void; onPick: (offer: OfferRow) => void; busy: boolean }) {
  const [panel, setPanel] = useState<PartPanel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!open || !bomLineId) return;
    let cancelled = false;
    setPanel(null);
    setError(null);
    api
      .partPanel(runId, bomLineId)
      .then((p) => !cancelled && setPanel(p))
      .catch((e: unknown) => !cancelled && setError(e instanceof ApiFailure ? e.message : "Couldn't load the offers."));
    return () => {
      cancelled = true;
    };
  }, [open, runId, bomLineId, attempt]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[84vh] flex-col gap-4 sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Swap the offer{panel ? ` for ${panel.name}` : ""}</DialogTitle>
          <DialogDescription>Every offer found in this run. Only offers from stores in your mandate that passed the compatibility rules can be used.</DialogDescription>
        </DialogHeader>
        <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
          {error ? (
            <InlineError message={error} onRetry={() => setAttempt((n) => n + 1)} />
          ) : !panel ? (
            <div className="space-y-2" aria-busy="true">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : (
            <OfferTable offers={panel.offers} qty={panel.qty} refusals={panel.refusals} onUse={onPick} busy={busy} expandAll />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
