// Guided checkout run (PLAN §12.3, §12.6): the card on the right of an approved cart. Progress bar
// "2 of 4 stores", Bought (marked by you) and Remaining, the store checklist with states, and the links to the
// signed mandate and the receipt. "Bought" only ever means stores the person ticked Done.
import { Check, CircleDot, FileSignature, PartyPopper, Pencil, ReceiptText, SkipForward } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { CountUpMoney } from "@/components/common/CountUp";
import { HashText } from "@/components/common/HashText";
import { TestBadge } from "@/components/common/StatusBadge";
import { ActionIcon } from "@/components/panel/ActionBadge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { signatureNote, timeOf } from "@/lib/format";
import type { ClosedMandate, UniversalCart as UniversalCartData } from "@/lib/types";
import { cn } from "@/lib/utils";

function ClosedMandateSheet({ runId, mandate: given }: { runId: string; mandate?: ClosedMandate | null }) {
  const [mandate, setMandate] = useState<ClosedMandate | null>(given ?? null);
  const [state, setState] = useState<"idle" | "loading" | "missing">("idle");
  const load = (open: boolean) => {
    if (!open || mandate || state === "loading") return;
    setState("loading");
    api
      .receipt(runId)
      .then((r) => {
        setMandate(r.closed_mandate ?? null);
        setState(r.closed_mandate ? "idle" : "missing");
      })
      .catch(() => setState("missing"));
  };
  const sigNote = mandate ? signatureNote(mandate.signature, mandate.simulated) : null;
  return (
    <Sheet onOpenChange={load}>
      <SheetTrigger asChild>
        <Button variant="outline" size="lg">
          <FileSignature aria-hidden /> View signed mandate
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-[560px] gap-0 sm:max-w-[560px]">
        <SheetHeader>
          <SheetTitle>Signed closed mandate</SheetTitle>
          <SheetDescription>Bound to these items, prices and hand-off links. Any later edit needs a new approval.</SheetDescription>
        </SheetHeader>
        {mandate ? (
          <>
            <div className="flex flex-wrap items-center gap-2 px-4 pb-3 text-caption text-muted-foreground">
              <span>approved {timeOf(mandate.approved_at)}</span>
              <span>
                {mandate.signature.alg} · key {mandate.signature.kid}
              </span>
              {sigNote ? <TestBadge>{sigNote}</TestBadge> : null}
              <HashText hash={mandate.plan_sha256} label="plan" />
            </div>
            <pre className="mx-4 mb-4 min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-muted p-3 font-mono text-caption leading-5">{JSON.stringify(mandate, null, 2)}</pre>
          </>
        ) : state === "missing" ? (
          <p className="px-4 text-small text-secondary-text">The closed mandate isn’t available from the receipt yet. The receipt page shows everything that was signed.</p>
        ) : (
          <div className="space-y-2 px-4" aria-busy="true">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-64 w-full" />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

export function CheckoutRun({
  cart,
  closedMandate,
  onEditCart,
  busy = false,
}: {
  cart: UniversalCartData;
  closedMandate?: ClosedMandate | null;
  /** "Edit cart": back to a draft (open store carts are cancelled); a new approval is needed afterwards. */
  onEditCart?: () => void;
  busy?: boolean;
}) {
  const stores = [...cart.stores].sort((a, b) => a.order - b.order);
  const finished = stores.filter((s) => s.handoff?.state === "done" || s.handoff?.state === "skipped").length;
  const pct = stores.length ? Math.round((finished / stores.length) * 100) : 0;
  const complete = cart.state === "complete";
  const currentId = cart.current_store_id ?? stores.find((s) => s.handoff?.state !== "done" && s.handoff?.state !== "skipped")?.store_id;

  return (
    <section aria-label="Checkout run" className="space-y-4 rounded-lg border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-body-lg font-semibold">{complete ? "Run complete" : "Checkout run"}</h2>
        {complete ? <PartyPopper className="size-5 text-pass" strokeWidth={1.75} aria-hidden /> : null}
      </div>

      <div className="space-y-1.5">
        <p className="flex items-center justify-between text-small">
          <span className="font-medium">
            {finished} of {stores.length} stores
          </span>
          <span className="tabular font-mono text-muted-foreground">{pct}%</span>
        </p>
        <Progress value={pct} aria-label="Stores finished" />
      </div>

      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-muted p-3">
          <dt className="text-caption text-muted-foreground">Bought (marked by you)</dt>
          <dd className="text-h3 font-semibold">
            <CountUpMoney value={cart.bought_usd} />
          </dd>
        </div>
        <div className="rounded-lg bg-muted p-3">
          <dt className="text-caption text-muted-foreground">Remaining</dt>
          <dd className="text-h3 font-semibold">
            <CountUpMoney value={cart.remaining_usd} />
          </dd>
        </div>
      </dl>

      <ol className="divide-y divide-border rounded-lg border border-border">
        {stores.map((s, i) => {
          const state = s.handoff?.state ?? "ready";
          const current = s.store_id === currentId && !complete;
          return (
            <li key={s.store_id} className={cn("flex items-center gap-2.5 px-3 py-2 text-small", current && "bg-brand-tint")}>
              <span
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full text-white",
                  state === "done" ? "bg-pass" : state === "skipped" ? "bg-border-strong" : current ? "bg-brand" : "border border-border-strong bg-surface text-muted-foreground",
                )}
              >
                {state === "done" ? <Check className="size-3.5" strokeWidth={2.5} aria-hidden /> : state === "skipped" ? <SkipForward className="size-3" strokeWidth={2} aria-hidden /> : current ? <CircleDot className="size-3.5" strokeWidth={2} aria-hidden /> : <span className="font-mono text-caption">{i + 1}</span>}
              </span>
              <span className={cn("min-w-0 flex-1 truncate", current && "font-medium")}>{s.display_name}</span>
              <ActionIcon level={s.action_level} className="text-muted-foreground" />
              <span className={cn("w-20 text-right text-caption", state === "done" ? "font-medium text-pass" : current ? "font-medium text-brand" : "text-muted-foreground")}>
                {state === "done" ? "Done" : state === "skipped" ? "Skipped" : state === "opened" ? "Opened" : current ? "Open now" : "Next"}
              </span>
            </li>
          );
        })}
      </ol>

      {complete ? <p className="text-small text-secondary-text">Every store is done or skipped. The receipt has the signed mandates and the full trail.</p> : null}

      <div className="flex flex-wrap gap-2">
        <ClosedMandateSheet runId={cart.run_id} mandate={closedMandate} />
        <Button asChild variant={complete ? "default" : "outline"} size="lg">
          <Link to={`/run/${cart.run_id}/receipt`}>
            <ReceiptText aria-hidden /> View receipt
          </Link>
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <p className="min-w-0 flex-1 text-caption text-muted-foreground">
          {complete ? "This run is complete. To change the cart, start a new run." : "This cart is locked to what you approved. Edit cart returns it to a draft, cancels the carts the agent opened, and needs a new approval."}
        </p>
        {onEditCart && !complete ? (
          <Button variant="outline" size="sm" disabled={busy} onClick={onEditCart}>
            <Pencil aria-hidden /> Edit cart
          </Button>
        ) : null}
      </div>
    </section>
  );
}
