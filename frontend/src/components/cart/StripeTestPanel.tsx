// Tier 2 "Single payment (test mode)" panel (PLAN §12.3 Tier 2, §12.4, §12.6). Owner: B, built with C's components and tokens.
//
// Hard rules (PLAN §12.2): Stripe TEST MODE only (the publishable key must start with pk_test_), the app never sees a
// card number (card entry happens only inside Stripe's Payment Element), every authorization row says "simulated",
// violet dashed styling keeps it apart from the real hand-off buttons, and only a person's click starts a test payment.
//
// Three ways it renders:
//   live + pk_test_ key   Payment Element (deferred intent, manual capture) -> POST /pay/intent -> confirmPayment -> /pay/fanout
//   mock, or no key       a simulated run through the same endpoints, no Payment Element
//   replay                "Recorded test-mode run": the recorded states, the Payment Element is not mounted
// Stripe.js is loaded from @stripe/stripe-js/pure, so nothing is fetched from Stripe unless the live form is shown.
import { Elements, PaymentElement, useElements, useStripe } from "@stripe/react-stripe-js";
import type { Stripe } from "@stripe/stripe-js";
import { loadStripe } from "@stripe/stripe-js/pure";
import { Check, CircleDashed, CreditCard, FlaskConical, Loader2, ShieldCheck, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ApiFailure, api } from "@/lib/api";
import { money, shortHash } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { StoreGroup, StoreTestState, UniversalCart as UniversalCartData } from "@/lib/types";
import { cn } from "@/lib/utils";

import { TestModeBadge } from "./TestModeBadge";

const PK = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY ?? "";
const PK_OK = PK.startsWith("pk_test_");

let stripePromise: Promise<Stripe | null> | null = null;
function getStripe(): Promise<Stripe | null> {
  // Never load Stripe.js with anything but a test key.
  if (!PK_OK) return Promise.resolve(null);
  stripePromise ??= loadStripe(PK);
  return stripePromise;
}

/** Must match the backend's checkout/stripe_test.py consent_text() character for character. */
export function consentText(totalUsd: number): string {
  return `You authorise up to ${money(totalUsd)}, split as shown. Each store can charge at most its own subtotal. TEST MODE: no real money moves.`;
}

const STEPS: Array<{ state: StoreTestState; label: string }> = [
  { state: "queued", label: "Queued" },
  { state: "card_issued", label: "Card issued" },
  { state: "authorized", label: "Authorized (simulated)" },
  { state: "settled", label: "Settled (test)" },
];
const RANK: Record<StoreTestState, number> = { queued: 0, card_issued: 1, authorized: 2, declined: 2, settled: 3 };

type Phase = "idle" | "starting" | "confirming" | "fanning_out" | "done" | "error";

function StoreStepper({ group }: { group: StoreGroup }) {
  const t = group.test;
  const rank = t ? RANK[t.state] : -1;
  const declined = t?.state === "declined";
  return (
    <li className="space-y-1.5 rounded-md border border-dashed border-test/50 bg-surface px-3 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-small font-medium text-foreground">{group.display_name}</span>
        <span className="font-mono text-caption tabular-nums text-secondary-text">
          {t?.card_last4 ? `•••• ${t.card_last4} · ` : ""}limit {money(t?.limit_usd ?? group.subtotal_usd)}
        </span>
      </div>
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1" aria-label={`${group.display_name} test payment steps`}>
        {STEPS.map((step, i) => {
          const reached = rank >= RANK[step.state] && !(declined && step.state !== "queued" && step.state !== "card_issued");
          const failedHere = declined && step.state === "authorized";
          return (
            <li key={step.state} className="flex items-center gap-1.5">
              {i > 0 ? <span className="h-px w-3 bg-test/40" aria-hidden /> : null}
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-sm px-1.5 py-0.5 text-caption",
                  failedHere ? "bg-warn-tint text-warn" : reached ? "bg-test-tint text-test" : "text-secondary-text",
                )}
              >
                {failedHere ? (
                  <TriangleAlert className="size-3" strokeWidth={1.75} aria-hidden />
                ) : reached ? (
                  <Check className="size-3" strokeWidth={2} aria-hidden />
                ) : (
                  <CircleDashed className="size-3" strokeWidth={1.75} aria-hidden />
                )}
                {failedHere ? "Declined (simulated)" : step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </li>
  );
}

function Summary({ cart }: { cart: UniversalCartData }) {
  const tp = cart.test_payment;
  if (!tp) return null;
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-md border border-dashed border-test/50 bg-surface px-3 py-2 text-small">
      <dt className="text-secondary-text">Test hold</dt>
      <dd className="font-mono text-caption">{tp.payment_intent}</dd>
      <dt className="text-secondary-text">Captured (test)</dt>
      <dd className="tabular-nums">{money(tp.captured_usd)}</dd>
      <dt className="text-secondary-text">Released</dt>
      <dd className="tabular-nums">{money(tp.released_usd)}</dd>
      <dt className="text-secondary-text">Bound to mandate</dt>
      <dd className="font-mono text-caption" title={tp.mandate_hash}>
        {shortHash(tp.mandate_hash, 11, 4)}
      </dd>
    </dl>
  );
}

/** The live form: Payment Element in deferred-intent mode, then the server creates the PaymentIntent. */
function LivePayForm({ total, consent, agreed, onPaid, onError, disabled }: {
  total: number; consent: string; agreed: boolean; disabled: boolean; onPaid: (piId: string) => Promise<void>; onError: (m: string) => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);

  const pay = async () => {
    if (!stripe || !elements) return;
    setBusy(true);
    try {
      const { error: submitError } = await elements.submit();
      if (submitError) throw new Error(submitError.message ?? "Check the test card details");
      const runId = useAppStore.getState().runId;
      if (!runId) throw new Error("No run is open");
      const intent = await api.payIntent(runId, consent);
      if (intent.livemode !== false) throw new Error("Refusing a payment that is not in test mode");
      const { error, paymentIntent } = await stripe.confirmPayment({ elements, clientSecret: intent.client_secret, redirect: "if_required" });
      if (error) throw new Error(error.message ?? "The test card was declined");
      if (paymentIntent?.status !== "requires_capture") throw new Error(`Unexpected test payment status: ${paymentIntent?.status ?? "none"}`);
      await onPaid(intent.payment_intent_id);
    } catch (e) {
      onError(e instanceof ApiFailure ? e.detail.message : e instanceof Error ? e.message : "The test payment failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-dashed border-test/50 bg-surface p-3">
        <PaymentElement options={{ layout: "tabs", wallets: { applePay: "never", googlePay: "never" } }} />
      </div>
      <p className="text-caption text-secondary-text">Use Stripe&rsquo;s test card 4242 4242 4242 4242, any future date, any CVC.</p>
      <Button className="w-full" disabled={!agreed || disabled || busy || !stripe} onClick={() => void pay()}>
        {busy ? <Loader2 className="animate-spin" aria-hidden /> : <CreditCard aria-hidden />}
        Pay {money(total)} once (test)
      </Button>
    </div>
  );
}

export function StripeTestPanel({ cart }: { cart: UniversalCartData }) {
  const mode = useAppStore((s) => s.health?.mode);
  const isMockData = useAppStore((s) => s.mockSeen || Boolean(s.health?.mock)) || cart.simulated;
  const setCart = useAppStore((s) => s.setCart);
  const [agreed, setAgreed] = useState(false);
  const [phase, setPhase] = useState<Phase>(cart.test_payment ? "done" : "idle");
  const [message, setMessage] = useState<string | null>(null);
  const alive = useRef(true);
  useEffect(() => () => void (alive.current = false), []);

  const replay = mode === "replay";
  const draft = cart.state === "draft";
  const paid = Boolean(cart.test_payment);
  const useLiveForm = PK_OK && !replay && mode !== "mock" && !isMockData;
  const consent = consentText(cart.total_usd);
  const stores = useMemo(() => [...cart.stores].sort((a, b) => a.order - b.order), [cart.stores]);
  const elementsOptions = useMemo(
    () => ({ mode: "payment" as const, amount: Math.round(cart.total_usd * 100), currency: "usd", captureMethod: "manual" as const, paymentMethodTypes: ["card"] }),
    [cart.total_usd],
  );

  /** After the hold: fan out to one test card per store, then follow the cart until the capture lands. */
  const afterHold = useCallback(
    async (paymentIntentId: string) => {
      setPhase("fanning_out");
      await api.payFanout(cart.run_id, paymentIntentId);
      for (let i = 0; i < 20 && alive.current; i++) {
        const next = await api.cart(cart.run_id);
        setCart(next);
        if (next.test_payment) break;
        await new Promise((r) => setTimeout(r, 700));
      }
      if (alive.current) setPhase("done");
    },
    [cart.run_id, setCart],
  );

  const fail = (m: string) => {
    setMessage(m);
    setPhase("error");
  };

  const simulatedPay = async () => {
    setPhase("starting");
    setMessage(null);
    try {
      const intent = await api.payIntent(cart.run_id, consent);
      if (intent.livemode !== false) throw new Error("Refusing a payment that is not in test mode");
      await afterHold(intent.payment_intent_id);
    } catch (e) {
      fail(e instanceof ApiFailure ? e.detail.message : e instanceof Error ? e.message : "The test payment failed");
    }
  };

  return (
    <section
      aria-labelledby="stripe-test-title"
      data-testid="stripe-test-panel"
      className="space-y-4 rounded-lg border-2 border-dashed border-test bg-test-tint/60 p-4"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <h2 id="stripe-test-title" className="flex items-center gap-1.5 text-body font-semibold text-test">
            <FlaskConical className="size-4" strokeWidth={1.75} aria-hidden />
            Single payment (test mode)
          </h2>
          <p className="text-caption text-secondary-text">
            One Stripe test hold, then one test virtual card per store capped at its subtotal. Simulated: no real money moves, and
            these test cards never work at a real store.
          </p>
        </div>
        <TestModeBadge />
      </header>

      {replay ? (
        <p className="rounded-md border border-dashed border-test/50 bg-surface px-3 py-2 text-small text-test">
          Recorded test-mode run. Replay does not take payments, so the payment form is not shown.
        </p>
      ) : draft ? (
        <p className="text-small text-secondary-text">Approve the cart first: the test payment is bound to the signed cart.</p>
      ) : paid ? null : (
        <div className="space-y-3">
          <label className="flex items-start gap-2.5 text-small text-foreground">
            <Checkbox checked={agreed} onCheckedChange={(v) => setAgreed(v === true)} className="mt-0.5" aria-describedby="stripe-consent" />
            <span id="stripe-consent">{consent}</span>
          </label>
          {useLiveForm ? (
            <Elements stripe={getStripe()} options={elementsOptions}>
              <LivePayForm
                total={cart.total_usd}
                consent={consent}
                agreed={agreed}
                disabled={phase === "fanning_out"}
                onPaid={afterHold}
                onError={fail}
              />
            </Elements>
          ) : (
            <div className="space-y-2">
              <p className="text-caption text-secondary-text">
                {PK_OK ? "Mock data on screen, so the run is simulated end to end." : "No Stripe test key is set (VITE_STRIPE_PUBLISHABLE_KEY must start with pk_test_), so the run is simulated."}{" "}
                No card form is shown.
              </p>
              <Button className="w-full" disabled={!agreed || phase === "starting" || phase === "fanning_out"} onClick={() => void simulatedPay()}>
                {phase === "starting" || phase === "fanning_out" ? <Loader2 className="animate-spin" aria-hidden /> : <ShieldCheck aria-hidden />}
                Pay {money(cart.total_usd)} once (simulated)
              </Button>
            </div>
          )}
        </div>
      )}

      {phase === "fanning_out" ? (
        <p role="status" className="flex items-center gap-1.5 text-small text-test">
          <Loader2 className="size-3.5 animate-spin" aria-hidden /> Issuing one test card per store and simulating each store&rsquo;s charge…
        </p>
      ) : null}
      {message ? (
        <p role="alert" className="flex items-start gap-1.5 rounded-md bg-warn-tint px-3 py-2 text-small text-warn">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.75} aria-hidden /> {message}
        </p>
      ) : null}

      {!draft ? (
        <ol className="space-y-2" aria-label="Test payment per store">
          {stores.map((g) => (
            <StoreStepper key={g.store_id} group={g} />
          ))}
        </ol>
      ) : null}
      <Summary cart={cart} />
    </section>
  );
}
