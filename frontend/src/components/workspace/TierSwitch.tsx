// Tier switch with live re-optimization (PLAN §11.6 E2): "Cheapest · Fewest checkouts".
// On change: POST /replan, the total counts to its new value, and a toast names the difference.
import { useState } from "react";
import { toast } from "sonner";

import { api, ApiFailure } from "@/lib/api";
import { money, moneyDelta, plural } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { RunState } from "@/lib/types";
import { cn } from "@/lib/utils";

const TIERS: Array<{ id: string; label: string }> = [
  { id: "cheapest", label: "Cheapest" },
  { id: "fewest_checkouts", label: "Fewest checkouts" },
];

export function TierSwitch({ run }: { run: RunState }) {
  const setRun = useAppStore((s) => s.setRun);
  const [busy, setBusy] = useState<string | null>(null);
  const locked = run.status === "approved" || run.status === "done";

  const choose = async (tier: string) => {
    if (tier === run.active_tier || busy) return;
    setBusy(tier);
    const before = run.plans[run.active_tier];
    try {
      const { plan } = await api.replan(run.run_id, { tier });
      // The selection survives a tier switch: only the plan changes.
      setRun({ ...run, active_tier: plan.tier, plans: { ...run.plans, [plan.tier]: plan } });
      const diff = before ? plan.total_usd - before.total_usd : 0;
      toast(`${TIERS.find((t) => t.id === tier)?.label ?? tier}: ${money(plan.total_usd)} · ${plural(plan.checkouts, "checkout")}`, {
        description: before ? `${moneyDelta(diff)} and ${plan.checkouts - before.checkouts >= 0 ? "+" : "−"}${Math.abs(plan.checkouts - before.checkouts)} checkouts against the plan before.${plan.simulated ? " Prices are mock data." : ""}` : undefined,
      });
      void api.run(run.run_id).then((fresh) => fresh.active_tier === plan.tier && setRun(fresh)).catch(() => undefined);
    } catch (e) {
      toast(e instanceof ApiFailure ? e.message : "Couldn't re-plan. The plan on screen is unchanged.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div role="radiogroup" aria-label="Plan tier" className="inline-flex rounded-md border border-border bg-muted p-0.5">
      {TIERS.map((t) => {
        const active = (busy ?? run.active_tier) === t.id;
        return (
          <button
            key={t.id}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={locked || busy !== null}
            title={locked ? "The cart is approved. Edit the cart to change the plan." : undefined}
            onClick={() => void choose(t.id)}
            className={cn(
              "h-7 rounded-sm px-2.5 text-caption font-medium whitespace-nowrap transition-colors duration-150 disabled:cursor-not-allowed",
              active ? "bg-surface text-foreground shadow-e1" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
