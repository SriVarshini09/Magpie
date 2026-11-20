// Mandate bar (PLAN §11.5 B): sticky, 56 px. What you signed (budget, stores, sharing, deadline), how many
// times the agent was refused, the tier switch, the plan total and the one primary button: Review cart.
import { CalendarClock, ChevronDown, Lock, Share2, ShieldX, Store } from "lucide-react";
import { Popover } from "radix-ui";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { LogoMark } from "@/components/brand/Logo";
import { CountUpMoney } from "@/components/common/CountUp";
import { HashText } from "@/components/common/HashText";
import { TestBadge } from "@/components/common/StatusBadge";
import { ACTION_ICON } from "@/components/panel/ActionBadge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import { ACTION_LABEL, dayOf, moneyShort, plural, signatureNote, timeOf } from "@/lib/format";
import type { ActionLevel, DataSharing, OpenMandate, RunState, StoreInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

import { TierSwitch } from "./TierSwitch";

const LEVELS: ActionLevel[] = ["agent_cart", "prefilled_cart", "product_link"];
const SHORT_LEVEL: Record<ActionLevel, string> = { agent_cart: "agent cart", prefilled_cart: "prefilled", product_link: "link" };
const SHARE_LABEL: Record<keyof DataSharing, string> = {
  country: "country",
  postal_code: "postal code",
  street_address: "street address",
  email: "email",
  phone: "phone",
  name: "name",
  photo_to_models: "photos to models",
};

export function sharesText(sharing: DataSharing): string {
  const on = (Object.keys(SHARE_LABEL) as Array<keyof DataSharing>).filter((k) => sharing[k]);
  if (!on.length) return "Shares: nothing";
  if (on.length === 1) return `Shares: ${SHARE_LABEL[on[0]]} only`;
  return `Shares: ${on.map((k) => SHARE_LABEL[k]).join(", ")}`;
}

const chip = "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 text-caption text-secondary-text whitespace-nowrap";

let storesCache: Promise<StoreInfo[]> | null = null;
export function useStores(): StoreInfo[] {
  const [stores, setStores] = useState<StoreInfo[]>([]);
  useEffect(() => {
    let cancelled = false;
    storesCache ??= api.stores();
    storesCache.then((s) => !cancelled && setStores(s)).catch(() => (storesCache = null));
    return () => {
      cancelled = true;
    };
  }, []);
  return stores;
}

function StoresChip({ mandate }: { mandate: OpenMandate }) {
  const stores = useStores();
  const allowed = mandate.constraints.allowed_merchants;
  const byId = new Map(stores.map((s) => [s.store_id, s]));
  const groups = LEVELS.map((level) => ({ level, items: allowed.filter((id) => byId.get(id)?.action_level === level) })).filter((g) => g.items.length);
  const unknown = allowed.filter((id) => !byId.has(id));
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button type="button" className={cn(chip, "hover:border-border-strong")}>
          <Store className="size-3.5" strokeWidth={1.75} aria-hidden />
          {plural(allowed.length, "store")}
          {groups.length ? <span className="hidden text-muted-foreground 2xl:inline">: {groups.map((g) => `${g.items.length} ${SHORT_LEVEL[g.level]}`).join(" · ")}</span> : null}
          <ChevronDown className="size-3" strokeWidth={1.75} aria-hidden />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="start" sideOffset={8} className="z-50 w-80 space-y-3 rounded-lg border border-border bg-popover p-4 shadow-e2">
          <p className="text-small font-semibold">Stores in your mandate</p>
          {groups.map((g) => {
            const Icon = ACTION_ICON[g.level];
            return (
              <div key={g.level}>
                <p className="flex items-center gap-1.5 text-caption font-medium text-muted-foreground">
                  <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
                  {ACTION_LABEL[g.level]}
                </p>
                <p className="text-small">{g.items.map((id) => byId.get(id)?.display_name ?? id).join(", ")}</p>
              </div>
            );
          })}
          {unknown.length ? <p className="text-small text-secondary-text">{unknown.join(", ")}</p> : null}
          <p className="text-caption text-muted-foreground">Any other store is refused and logged.</p>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function MandateSheet({ mandate }: { mandate: OpenMandate }) {
  const sigNote = signatureNote(mandate.signature, mandate.simulated);
  return (
    <Sheet>
      <SheetTrigger asChild>
        <button type="button" className={cn(chip, "hover:border-border-strong")}>
          <Lock className="size-3.5" strokeWidth={1.75} aria-hidden />
          Signed {timeOf(mandate.created_at)}
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[560px] gap-0 sm:max-w-[560px]">
        <SheetHeader>
          <SheetTitle>Signed open mandate</SheetTitle>
          <SheetDescription>What the agent may do. Anything outside it is refused in code and logged. {mandate.note}.</SheetDescription>
        </SheetHeader>
        <div className="flex flex-wrap items-center gap-2 px-4 pb-3 text-caption text-muted-foreground">
          <span className="font-mono">{mandate.mandate_id}</span>
          <span>
            {mandate.signature.alg} · key {mandate.signature.kid}
          </span>
          {sigNote ? <TestBadge>{sigNote}</TestBadge> : null}
          <HashText hash={mandate.scope.intake_sha256} label="intake" />
        </div>
        <pre className="mx-4 mb-4 min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-muted p-3 font-mono text-caption leading-5">{JSON.stringify(mandate, null, 2)}</pre>
      </SheetContent>
    </Sheet>
  );
}

export function MandateBar({ run }: { run: RunState }) {
  const plan = run.plans[run.active_tier];
  const c = run.mandate.constraints;
  const total = plan?.total_usd ?? 0;
  const pct = c.budget_usd > 0 ? Math.min(100, (total / c.budget_usd) * 100) : 0;
  const over = plan ? total > c.budget_usd : false;
  const canReview = run.status === "waiting_approval" || run.status === "approved" || run.status === "done";
  return (
    <header className="sticky top-0 z-40 flex h-(--b2c-mandate-bar-h) shrink-0 items-center gap-3 border-b border-border bg-surface px-(--b2c-gutter)">
      <Link to="/" aria-label="Build-to-Cart: start" className="mr-1 flex size-8 shrink-0 items-center justify-center rounded-md hover:bg-muted">
        <LogoMark />
      </Link>

      <div className="w-36 shrink-0" title="Plan total against the budget you signed">
        <p className="text-small leading-tight">
          <span className="tabular font-mono font-semibold">{plan ? moneyShort(total) : "no plan yet"}</span> <span className="text-muted-foreground">of {moneyShort(c.budget_usd)}</span>
        </p>
        <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Budget used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
          <div className={cn("h-full rounded-full transition-[width] duration-300 ease-b2c", over ? "bg-fail" : "bg-ink")} style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden">
        <StoresChip mandate={run.mandate} />
        <span className={chip}>
          <Share2 className="size-3.5" strokeWidth={1.75} aria-hidden />
          {sharesText(c.data_sharing)}
        </span>
        <span className={cn(chip, "hidden xl:inline-flex")}>
          <CalendarClock className="size-3.5" strokeWidth={1.75} aria-hidden />
          By {dayOf(c.deadline)}
        </span>
        <MandateSheet mandate={run.mandate} />
        {run.refusals > 0 ? (
          <span className={cn(chip, "border-fail/30 bg-fail-tint font-medium text-fail")}>
            <ShieldX className="size-3.5" strokeWidth={1.75} aria-hidden />
            {run.refusals} refused
          </span>
        ) : null}
      </div>

      <TierSwitch run={run} />
      <p className="shrink-0 text-small whitespace-nowrap">
        {plan ? (
          <>
            <CountUpMoney value={total} className="font-semibold" /> <span className="text-muted-foreground">· {plural(plan.checkouts, "checkout")}</span>
          </>
        ) : (
          <span className="text-muted-foreground">Planning…</span>
        )}
      </p>
      {canReview ? (
        <Button asChild size="lg" className="px-4">
          <Link to={`/run/${run.run_id}/cart`}>Review cart</Link>
        </Button>
      ) : (
        <Button size="lg" className="px-4" disabled title="The cart is ready when the plan is.">
          Review cart
        </Button>
      )}
    </header>
  );
}
