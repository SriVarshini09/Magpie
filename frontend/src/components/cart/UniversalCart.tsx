// The Universal Cart screen (PLAN §12.6, §12.3, §11.13). Two columns, max width 1200.
// Left (64%): one StoreGroup per store in run order, then Left out. Right (36%, sticky): in a draft the
// assumption bar, the summary and Approve cart; once approved, the checkout run and B's test-payment panel.
// Bottom strip: what is real and what is test. Approve is disabled while any assumption is open
// ("Confirm 2 assumptions first"), while prices are stale, or while a price change is unseen.
import { Download, PackageX } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { CountUpMoney } from "@/components/common/CountUp";
import { Money } from "@/components/common/Money";
import { EmptyState } from "@/components/common/States";
import { ACTION_ICON } from "@/components/panel/ActionBadge";
import { forgetPanels } from "@/components/panel/PartPanel";
import { Button } from "@/components/ui/button";
import { ApprovalDialog } from "@/components/workspace/ApprovalDialog";
import { AssumptionBar } from "@/components/workspace/AssumptionBar";
import { api, ApiFailure } from "@/lib/api";
import { ACTION_LABEL, LEFT_OUT_LABEL, money, moneyShort, plural, reasonCode, timeOf } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { ActionLevel, CartEditRequest, ClosedMandate, HandoffState, OfferRow, RunState, UniversalCart as UniversalCartData } from "@/lib/types";
import { cn } from "@/lib/utils";

import { CartItemRow } from "./CartItemRow";
import { CheckoutRun } from "./CheckoutRun";
import { PriceFreshness, useFreshness } from "./PriceFreshness";
import { StoreGroup } from "./StoreGroup";
import { StripeTestPanel } from "./StripeTestPanel";
import { SwapDialog } from "./SwapDialog";
import { TestModeBadge } from "./TestModeBadge";

const LEVELS: ActionLevel[] = ["agent_cart", "prefilled_cart", "product_link"];
const LEVEL_PLURAL: Record<ActionLevel, [string, string]> = { agent_cart: ["agent cart", "agent carts"], prefilled_cart: ["prefilled cart", "prefilled carts"], product_link: ["store by product link", "stores by product link"] };

function describeChange(before: UniversalCartData, after: UniversalCartData): string {
  if (after.source_api === "mock" && useAppStore.getState().health?.mode === "mock" && before.total_usd === after.total_usd && before.stores.length === after.stores.length) return "Mock mode: the edit was accepted, but fixture data doesn't change.";
  const moved = after.total_usd - before.total_usd;
  const bits = [`Total ${money(before.total_usd)} → ${money(after.total_usd)}`];
  if (before.stores.length !== after.stores.length) bits.push(`${plural(before.stores.length, "store")} → ${after.stores.length}`);
  return moved === 0 && bits.length === 1 ? "The total is unchanged." : `${bits.join(" · ")}.`;
}

export function UniversalCart({ cart, run, onCart }: { cart: UniversalCartData; run: RunState | null; onCart: (cart: UniversalCartData) => void }) {
  const navigate = useNavigate();
  const select = useAppStore((s) => s.select);
  const health = useAppStore((s) => s.health);
  const freshness = useFreshness(cart);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [swapLine, setSwapLine] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [approveBusy, setApproveBusy] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [changesSeen, setChangesSeen] = useState(false);
  const [closedMandate, setClosedMandate] = useState<ClosedMandate | null>(null);
  const [inlineError, setInlineError] = useState<string | null>(null);

  const draft = cart.state === "draft";
  const editable = draft && cart.editable;
  const stores = [...cart.stores].sort((a, b) => a.order - b.order);
  const names = new Map((run?.bom ?? []).map((l) => [l.bom_line_id, l]));
  const cartQty = new Map<string, number>();
  for (const s of stores) for (const i of s.items) cartQty.set(i.bom_line_id, (cartQty.get(i.bom_line_id) ?? 0) + i.qty);

  const openAssumptions = cart.open_assumptions.length;
  const unseenChanges = cart.price_changes.length > 0 && !changesSeen;
  const overBudget = cart.total_usd > cart.budget_usd;
  const warnings = (run?.checks ?? []).filter((c) => c.needs_ack);
  const blocker = openAssumptions
    ? `Confirm ${plural(openAssumptions, "assumption")} first`
    : freshness.stale
      ? "Refresh the prices first"
      : unseenChanges
        ? "Review the price changes first"
        : overBudget
          ? "Over budget: remove or swap items"
          : !stores.length
            ? "Nothing to approve"
            : null;
  const testTier = (health?.pay_tier ?? 1) >= 2 || Boolean(cart.test_payment) || stores.some((s) => s.test);
  const currentId = cart.current_store_id ?? stores.find((s) => s.handoff?.state !== "done" && s.handoff?.state !== "skipped")?.store_id ?? null;

  const edit = async (body: CartEditRequest, done: string) => {
    setBusy(true);
    setInlineError(null);
    try {
      const next = await api.cartEdit(cart.run_id, body);
      forgetPanels(cart.run_id);
      // A restored line goes back on the list; it is in the cart only if a store in the mandate has it.
      const stillOut = body.op === "restore" && next.left_out.find((x) => x.bom_line_id === body.bom_line_id);
      if (stillOut) toast("Back on the list, not in the cart", { description: `No store in your mandate has ${stillOut.name}: it stays under Left out (${LEFT_OUT_LABEL[stillOut.reason] ?? stillOut.reason}).` });
      else toast(done, { description: describeChange(cart, next) });
      onCart(next);
      return true;
    } catch (e) {
      // Refusals and failures are never toasts: they stay on screen.
      setInlineError(e instanceof ApiFailure ? `${e.detail.refusal ? "Refused: " : ""}${e.message}${e.detail.refusal ? ` (mandate clause ${e.detail.refusal.clause})` : ""}` : "Couldn't change the cart. Nothing changed.");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const refresh = async () => {
    setRefreshing(true);
    setInlineError(null);
    try {
      const result = await api.cartRefresh(cart.run_id);
      const next = await api.cart(cart.run_id);
      onCart(next);
      setChangesSeen(false);
      toast(result.changes.length ? `${plural(result.changes.length, "price")} changed` : "Prices checked. Nothing changed.", { description: result.note ?? (result.simulated ? "Mock data." : undefined) });
    } catch (e) {
      setInlineError(e instanceof ApiFailure ? `${e.message} The prices on screen are the last ones seen.` : "Couldn't refresh prices. The prices on screen are the last ones seen.");
    } finally {
      setRefreshing(false);
    }
  };

  const approve = async (acknowledged: string[]) => {
    setApproveBusy(true);
    setApproveError(null);
    try {
      const res = await api.approve(cart.run_id, { plan_id: cart.plan_id, acknowledged_warnings: acknowledged });
      setClosedMandate(res.closed_mandate);
      onCart(res.cart);
      setApproving(false);
      toast("Cart approved. The closed mandate is signed.", { description: res.simulated ? "Mock mode: the hand-offs are simulated." : "Hand-offs are ready. Open the first store." });
      void api.run(cart.run_id).then((r) => useAppStore.getState().setRun(r)).catch(() => undefined);
    } catch (e) {
      setApproveError(e instanceof ApiFailure ? `${e.message.replace(/\.?$/, ".")} Nothing was signed.` : "Couldn't approve. Nothing was signed.");
    } finally {
      setApproveBusy(false);
    }
  };

  const handoff = async (storeId: string, state: HandoffState) => {
    setBusy(true);
    setInlineError(null);
    try {
      const next = await api.handoff(cart.run_id, { store_id: storeId, state, done_via: state === "done" ? "user" : null });
      onCart(next);
      if (state === "opened") toast("Checkout opened");
      if (next.state === "complete" && cart.state !== "complete") toast("Run complete. The receipt is ready.");
    } catch (e) {
      setInlineError(e instanceof ApiFailure ? e.message : "Couldn't update that store. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const itemAdded = async (offerId: string, added: boolean) => {
    setBusy(true);
    setInlineError(null);
    try {
      onCart(await api.cartItemAdded(cart.run_id, offerId, added));
    } catch (e) {
      setInlineError(e instanceof ApiFailure ? e.message : "Couldn't save that tick. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const editCart = async () => {
    setBusy(true);
    setInlineError(null);
    try {
      const next = await api.cartReopen(cart.run_id);
      forgetPanels(cart.run_id);
      setClosedMandate(null);
      onCart(next);
      toast("Cart is a draft again", { description: "The hand-offs were withdrawn. Approve again when you are done editing." });
      void api.run(cart.run_id).then((r) => useAppStore.getState().setRun(r)).catch(() => undefined);
    } catch (e) {
      setInlineError(e instanceof ApiFailure ? e.message : "Couldn't reopen the cart. Nothing changed.");
    } finally {
      setBusy(false);
    }
  };

  const openPart = (lineId: string) => {
    select(lineId);
    navigate(`/run/${cart.run_id}`);
  };

  const pickSwap = async (offer: OfferRow) => {
    if (!swapLine) return;
    if (await edit({ op: "swap_offer", bom_line_id: swapLine, offer_id: offer.offer_id }, `Swapped to ${offer.store_name}`)) setSwapLine(null);
  };

  return (
    <div className="mx-auto w-full max-w-[1200px] space-y-6 px-(--b2c-gutter) py-8">
      {testTier ? <TestModeBadge fixed /> : null}

      <header className="flex flex-wrap items-end justify-between gap-6">
        <div className="space-y-1.5">
          <p className="text-body text-secondary-text">
            Your cart · {plural(cart.counts.stores, "store")} · {draft ? "draft" : cart.state === "complete" ? "complete" : `approved${closedMandate ? ` ${timeOf(closedMandate.approved_at)}` : ""}`}
          </p>
          <h1 className="text-display font-semibold tracking-tight">
            <CountUpMoney value={cart.total_usd} className={cart.simulated ? "underline decoration-test decoration-dashed decoration-2 underline-offset-8" : undefined} />
          </h1>
          <p className="text-body text-secondary-text">
            Items {money(cart.total_usd)} of {moneyShort(cart.budget_usd)} budget · shipping and tax are calculated at each store
          </p>
          <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-small text-secondary-text" aria-label="Hand-offs in this cart">
            {LEVELS.map((level) => {
              const n = cart.counts[level];
              const Icon = ACTION_ICON[level];
              return (
                <li key={level} className={cn("inline-flex items-center gap-1.5", !n && "text-muted-foreground")} title={ACTION_LABEL[level]}>
                  <Icon className="size-4" strokeWidth={1.75} aria-hidden />
                  {n} {LEVEL_PLURAL[level][n === 1 ? 0 : 1]}
                </li>
              );
            })}
            <li className={cn(!cart.counts.items_by_hand && "text-muted-foreground")}>{plural(cart.counts.items_by_hand, "item")} to add by hand</li>
          </ul>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PriceFreshness cart={cart} onRefresh={() => void refresh()} refreshing={refreshing} canRefresh={draft} />
          <Button asChild variant="outline" size="lg">
            <a href={api.cartCsvUrl(cart.run_id)} download={`cart-${cart.run_id}.csv`}>
              <Download aria-hidden /> Download CSV
            </a>
          </Button>
        </div>
      </header>

      {inlineError ? (
        <p role="alert" className="rounded-lg border border-fail/30 bg-fail-tint px-4 py-3 text-small text-fail">
          {inlineError}
        </p>
      ) : null}

      {cart.price_changes.length ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warn/40 bg-warn-tint px-4 py-3 text-small">
          <p className="min-w-0 flex-1 text-foreground">
            <span className="font-semibold text-warn">{plural(cart.price_changes.length, "price")} changed since the plan was made: </span>
            <span className="tabular font-mono">{cart.price_changes.map((c) => `${money(c.old_usd)} → ${money(c.new_usd)}`).join(" · ")}</span>
          </p>
          {changesSeen ? (
            <span className="text-secondary-text">Seen by you</span>
          ) : (
            <Button variant="outline" size="sm" className="bg-surface" onClick={() => setChangesSeen(true)}>
              I’ve seen the changes
            </Button>
          )}
        </div>
      ) : null}

      <div className="grid grid-cols-[minmax(0,64fr)_minmax(0,36fr)] items-start gap-6">
        <div className="space-y-4">
          {stores.length ? (
            stores.map((group, i) => (
              <StoreGroup key={group.store_id} group={group} index={i} total={stores.length} approved={!draft} current={group.store_id === currentId} busy={busy} onHandoff={(state) => void handoff(group.store_id, state)} onItemAdded={(offerId, added) => void itemAdded(offerId, added)}>
                {group.items.map((item) => {
                  const line = names.get(item.bom_line_id);
                  const short = line && (cartQty.get(item.bom_line_id) ?? 0) < line.qty ? line.qty : null;
                  return (
                    <CartItemRow
                      key={item.offer_id}
                      item={item}
                      partName={line?.raw_name ?? `Part ${item.bom_line_id}`}
                      bomQty={short}
                      editable={editable}
                      busy={busy}
                      onOpenPart={() => openPart(item.bom_line_id)}
                      onQty={(qty) => void edit({ op: "set_qty", bom_line_id: item.bom_line_id, offer_id: item.offer_id, qty }, `Quantity set to ${qty}`)}
                      onSwap={() => setSwapLine(item.bom_line_id)}
                      onRemove={() => void edit({ op: "remove", bom_line_id: item.bom_line_id }, "Removed from the cart")}
                    />
                  );
                })}
              </StoreGroup>
            ))
          ) : (
            <div className="rounded-lg border border-border bg-surface">
              <EmptyState icon={PackageX} title="Nothing to buy in this cart">
                Every line is owned, left out or not found. The parts list on the model page says why.
              </EmptyState>
            </div>
          )}

          {cart.left_out.length ? (
            <section aria-label="Left out" className="rounded-lg border border-border bg-surface">
              <h2 className="px-4 pt-3 pb-2 text-body font-semibold">Left out ({cart.left_out.length})</h2>
              <ul>
                {cart.left_out.map((item) => (
                  <li key={item.bom_line_id} className="flex items-center gap-3 border-t border-border px-4 py-2.5 text-small">
                    <button type="button" className="font-medium text-foreground underline-offset-2 hover:text-brand hover:underline" onClick={() => openPart(item.bom_line_id)}>
                      {item.name}
                    </button>
                    <span className={cn("min-w-0 flex-1 truncate", cart.open_assumptions.includes(item.bom_line_id) ? "text-warn" : "text-secondary-text")}>
                      · {LEFT_OUT_LABEL[item.reason] ?? item.reason}
                      {item.note ? ` (${item.note})` : ""}
                    </span>
                    {editable && (item.reason === "owned" || item.reason === "removed_by_you") ? (
                      <Button variant="ghost" size="sm" disabled={busy} onClick={() => void edit({ op: "restore", bom_line_id: item.bom_line_id }, "Restored to the cart")}>
                        Restore
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>

        <aside className="sticky top-6 space-y-4">
          {draft ? (
            <>
              {run ? <AssumptionBar run={run} onResolved={() => void api.cart(cart.run_id).then(onCart).catch(() => undefined)} /> : null}
              <section aria-label="Summary" className="space-y-4 rounded-lg border border-border bg-surface p-5">
                <h2 className="text-body-lg font-semibold">Summary</h2>
                <ul className="space-y-1.5 text-small">
                  {stores.map((s) => (
                    <li key={s.store_id} className="flex items-center justify-between gap-3">
                      <span className="min-w-0 truncate text-secondary-text">
                        {s.display_name} · {ACTION_LABEL[s.action_level].toLowerCase()}
                      </span>
                      <Money value={s.subtotal_usd} simulated={cart.simulated} />
                    </li>
                  ))}
                  <li className="flex items-center justify-between gap-3 border-t border-border pt-2 text-body font-semibold">
                    <span>Items total</span>
                    <Money value={cart.total_usd} simulated={cart.simulated} />
                  </li>
                </ul>
                <div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Budget used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100, Math.round((cart.total_usd / Math.max(cart.budget_usd, 0.01)) * 100))}>
                    <div className={cn("h-full rounded-full transition-[width] duration-300 ease-b2c", overBudget ? "bg-fail" : "bg-ink")} style={{ width: `${Math.min(100, (cart.total_usd / Math.max(cart.budget_usd, 0.01)) * 100)}%` }} />
                  </div>
                  <p className={cn("mt-1.5 text-small", overBudget ? "text-fail" : "text-secondary-text")}>
                    {overBudget ? `${money(cart.total_usd - cart.budget_usd)} over` : `${money(cart.budget_usd - cart.total_usd)} under`} your {moneyShort(cart.budget_usd)} budget · tier: {reasonCode(cart.tier)}
                  </p>
                </div>

                <div className="space-y-1.5 rounded-lg bg-muted p-3 text-small text-secondary-text">
                  <p className="font-semibold text-foreground">Before you approve</p>
                  <p>Shipping and tax aren’t included. Each store adds them at its checkout.</p>
                  {[...new Set(warnings.map((w) => w.message))].map((message) => (
                    <p key={message} className="text-warn">
                      {message}
                    </p>
                  ))}
                  {cart.simulated ? <p className="text-test">Mock data: stores, prices and hand-offs on this page are simulated.</p> : null}
                </div>

                <Button size="lg" className="h-11 w-full text-body font-semibold" disabled={Boolean(blocker)} onClick={() => setApproving(true)}>
                  {blocker ?? "Approve cart"}
                </Button>
                <p className="text-small text-secondary-text">
                  <span className="font-medium text-foreground">How buying works:</span> this cart is the master list. For each store we hand you the strongest thing it allows: a real cart, a prefilled cart, or a link. You pay each store on its own checkout. We never pay and never see your card.
                </p>
              </section>
            </>
          ) : (
            <CheckoutRun cart={cart} closedMandate={closedMandate} busy={busy} onEditCart={() => void editCart()} />
          )}
          {/* Tier 2 (Stripe TEST MODE) is B's panel; it is mounted only when the backend runs that tier. */}
          {testTier && import.meta.env.VITE_STATIC_REPLAY !== "true" ? <StripeTestPanel cart={cart} /> : null}
        </aside>
      </div>

      <p className="rounded-lg border border-border bg-surface px-4 py-3 text-small text-secondary-text">
        <span className="font-semibold text-foreground">What’s real:</span> this cart, the store carts, the store links and checkouts.{" "}
        <span className="font-semibold text-test">What’s test:</span> the single payment and the store authorizations. No real money moves in this app.
        {cart.simulated ? <span className="text-test"> Right now the stores are mock stores, so the stores, prices and hand-offs here are simulated too.</span> : null}
      </p>

      <SwapDialog runId={cart.run_id} bomLineId={swapLine} open={swapLine !== null} onOpenChange={(o) => !o && setSwapLine(null)} onPick={(o) => void pickSwap(o)} busy={busy} />
      <ApprovalDialog cart={cart} warnings={warnings} freshness={freshness.label} open={approving} onOpenChange={setApproving} onApprove={(a) => void approve(a)} busy={approveBusy} error={approveError} />
    </div>
  );
}
