// Price freshness (PLAN §12.3, P13): "Prices checked 3 min ago" from the oldest price in the cart, with
// Refresh prices. Approve is blocked when the oldest price is over 15 minutes old. Mock and replay prices are
// recordings: the chip says so and the age check is off.
import { Clock, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ageMinutes, ago, timeOf } from "@/lib/format";
import type { UniversalCart } from "@/lib/types";
import { cn } from "@/lib/utils";

export const STALE_AFTER_MIN = 15;

export type Freshness = { oldest: string; recorded: boolean; stale: boolean; label: string };

/** The oldest `seen_at` among the cart's items decides the age; the cart's own check time is the fallback. */
export function freshnessOf(cart: UniversalCart, now = Date.now()): Freshness {
  const seen = cart.stores.flatMap((s) => s.items.map((i) => i.seen_at)).filter(Boolean).sort();
  const lastCheck = cart.prices_checked_at;
  const oldest = lastCheck && seen[0] && lastCheck > seen[0] ? lastCheck : (seen[0] ?? lastCheck);
  const recorded = cart.simulated || cart.source_api === "mock" || import.meta.env.VITE_STATIC_REPLAY === "true";
  const age = ageMinutes(oldest, now);
  const stale = !recorded && age !== null && age > STALE_AFTER_MIN;
  const label = recorded ? `${cart.source_api === "mock" || cart.simulated ? "Mock prices" : "Replay: prices"} as recorded at ${timeOf(oldest)}` : `Prices checked ${ago(oldest, now)}`;
  return { oldest, recorded, stale, label };
}

export function useFreshness(cart: UniversalCart): Freshness {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  return freshnessOf(cart, now);
}

export function PriceFreshness({ cart, onRefresh, refreshing, canRefresh }: { cart: UniversalCart; onRefresh: () => void; refreshing: boolean; canRefresh: boolean }) {
  const f = useFreshness(cart);
  return (
    <div className="flex items-center gap-2">
      <span
        className={cn(
          "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-small whitespace-nowrap",
          f.recorded ? "border-dashed border-test bg-test-tint text-test" : f.stale ? "border-warn/40 bg-warn-tint text-warn" : "border-border bg-surface text-secondary-text",
        )}
        title={f.stale ? `Over ${STALE_AFTER_MIN} minutes old. Refresh before you approve.` : undefined}
      >
        <Clock className="size-3.5" strokeWidth={1.75} aria-hidden />
        {f.label}
      </span>
      <Button variant="outline" size="lg" onClick={onRefresh} disabled={refreshing || !canRefresh} title={canRefresh ? undefined : "An approved cart keeps the prices it was approved with."}>
        <RefreshCw className={cn(refreshing && "animate-spin")} aria-hidden /> {refreshing ? "Checking…" : "Refresh prices"}
      </Button>
    </div>
  );
}
