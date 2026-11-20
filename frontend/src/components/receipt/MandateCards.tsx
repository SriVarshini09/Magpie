// The three mandate cards on the receipt (PLAN §3.7, §12.4, §11.5 E). Owner: D, with C's components.
// Open: what the agent was allowed to do. Closed: exactly what you approved. Payment: Tier 2, TEST MODE only.
import { Check, CreditCard, FileSignature, Lock, Minus, ShoppingBag } from "lucide-react";
import type { ReactNode } from "react";

import { SimulatedTag, useSimulatedRunLabel } from "@/components/MockDataBadge";
import { TestModeBadge } from "@/components/cart/TestModeBadge";
import { HashText } from "@/components/common/HashText";
import { Money } from "@/components/common/Money";
import { ActionBadge } from "@/components/panel/ActionBadge";
import { BUILD_TYPE_LABEL, dayOf, money, moneyShort, plural, timeOf } from "@/lib/format";
import type { ClosedMandate, OpenMandate, PaymentMandate, Signature } from "@/lib/types";
import { cn } from "@/lib/utils";

import { JsonDisclosure } from "./JsonView";
import { isPlaceholderJws, shortJws } from "./receiptFormat";

function CardFrame({ icon: Icon, title, meta, badge, children, muted = false }: { icon: typeof Lock; title: string; meta?: ReactNode; badge?: ReactNode; children: ReactNode; muted?: boolean }) {
  return (
    <section className={cn("flex min-w-0 flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-e1", muted && "bg-muted shadow-none")}>
      <header className="flex items-start gap-2">
        <Icon className="mt-0.5 size-4 shrink-0 text-secondary-text" strokeWidth={1.75} aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-body font-semibold text-foreground">{title}</h3>
          {meta ? <p className="text-caption text-muted-foreground">{meta}</p> : null}
        </div>
        {badge}
      </header>
      {children}
    </section>
  );
}

function Rows({ children }: { children: ReactNode }) {
  return <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-small">{children}</dl>;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-foreground">{children}</dd>
    </>
  );
}

function Flag({ on, children }: { on: boolean; children: ReactNode }) {
  const Icon = on ? Check : Minus;
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1 rounded-full border px-2 text-caption font-medium whitespace-nowrap",
        on ? "border-pass/30 bg-pass-tint text-pass" : "border-border bg-surface text-muted-foreground",
      )}
    >
      <Icon className="size-3" strokeWidth={2} aria-hidden />
      <span className="sr-only">{on ? "allowed:" : "not allowed:"}</span>
      {children}
    </span>
  );
}

/** "ES256 · demo-key-1 · eyJhbGci…Xk2Q", with an honest tag for the scaffold's placeholder signatures. */
export function SignatureLine({ signature, hashLabel, hash }: { signature?: Signature | null; hashLabel?: string; hash?: string | null }) {
  if (!signature) {
    return <p className="text-caption text-muted-foreground">Not signed.</p>;
  }
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border pt-3 text-caption text-muted-foreground">
      <FileSignature className="size-3.5" strokeWidth={1.75} aria-hidden />
      <span className="font-mono text-foreground">{signature.alg}</span>
      <span>
        key <span className="font-mono text-foreground">{signature.kid}</span>
      </span>
      <span title={signature.jws} className="font-mono">
        JWS {shortJws(signature.jws)}
      </span>
      {isPlaceholderJws(signature.jws) ? <SimulatedTag label="Placeholder signature" /> : null}
      {hash ? <HashText hash={hash} label={hashLabel} /> : null}
    </div>
  );
}

const SHARE_LABEL: Record<string, string> = {
  country: "country",
  postal_code: "postal code",
  street_address: "street address",
  email: "email",
  phone: "phone",
  name: "name",
  photo_to_models: "photo to models",
};

const ACTION_NAME: Record<string, string> = {
  search: "search",
  create_cart: "create carts",
  build_cart_link: "build cart links",
  checkout: "check out",
  pay: "pay",
  message_seller: "message sellers",
};

export function OpenMandateCard({ mandate, sha256 }: { mandate: OpenMandate; sha256?: string | null }) {
  const simLabel = useSimulatedRunLabel().short;
  const c = mandate.constraints;
  const s = mandate.scope;
  const shared = Object.entries(c.data_sharing).filter(([, v]) => v).map(([k]) => SHARE_LABEL[k] ?? k);
  return (
    <CardFrame
      icon={Lock}
      title="Open mandate"
      meta={
        <>
          Signed {timeOf(mandate.created_at)} · expires {timeOf(mandate.expires_at)} · <span className="font-mono">{mandate.mandate_id}</span>
        </>
      }
      badge={mandate.simulated ? <SimulatedTag label={simLabel} /> : null}
    >
      <Rows>
        <Row label="Goal">{s.goal}</Row>
        <Row label="Build type">
          {BUILD_TYPE_LABEL[s.build_type] ?? s.build_type} <span className="text-muted-foreground">· set by {s.build_type_set_by === "user" ? "you" : "the classifier"}</span>
        </Row>
        <Row label="Budget">
          <span className="tabular font-mono">{moneyShort(c.budget_usd)}</span>
        </Row>
        <Row label="Deadline">
          {dayOf(c.deadline)} · ships to {c.ship_to_country}
        </Row>
        <Row label="Template">
          <span className="font-mono">{s.template_id}</span>
          {s.reference_search ? <span className="text-muted-foreground"> · reference search allowed</span> : null}
        </Row>
      </Rows>

      <div className="space-y-1.5">
        <p className="text-caption font-medium text-muted-foreground">Allowed stores ({c.allowed_merchants.length})</p>
        <ul className="flex flex-wrap gap-1.5">
          {c.allowed_merchants.map((m) => (
            <li key={m} className="rounded-sm border border-border bg-surface px-1.5 py-0.5 text-caption text-secondary-text">
              {m}
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-1.5">
        <p className="text-caption font-medium text-muted-foreground">Shares: {shared.length ? shared.join(", ") : "nothing"}</p>
        <ul className="flex flex-wrap gap-1.5">
          {Object.entries(c.data_sharing).map(([k, v]) => (
            <li key={k}>
              <Flag on={Boolean(v)}>{SHARE_LABEL[k] ?? k}</Flag>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-1.5">
        <p className="text-caption font-medium text-muted-foreground">The agent may</p>
        <ul className="flex flex-wrap gap-1.5">
          {Object.entries(c.actions).map(([k, v]) => (
            <li key={k}>
              <Flag on={Boolean(v)}>{ACTION_NAME[k] ?? k}</Flag>
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-1">
        <p className="text-caption font-medium text-muted-foreground">Bound to your inputs</p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption">
          {s.inputs.source_url ? (
            <a href={s.inputs.source_url} target="_blank" rel="noopener noreferrer" className="max-w-full truncate text-brand hover:text-brand-hover">
              {s.inputs.source_url}
            </a>
          ) : null}
          {s.inputs.text_sha256 ? <HashText hash={s.inputs.text_sha256} label="text" /> : null}
          {s.inputs.image_sha256.map((h) => (
            <HashText key={h} hash={h} label="photo" />
          ))}
          <HashText hash={s.intake_sha256} label="intake" />
        </div>
      </div>

      <p className="text-caption text-muted-foreground">{mandate.note}</p>
      <SignatureLine signature={mandate.signature} hash={sha256} hashLabel="mandate" />
      <JsonDisclosure data={mandate} />
    </CardFrame>
  );
}

export function ClosedMandateCard({ mandate }: { mandate?: ClosedMandate | null }) {
  const simLabel = useSimulatedRunLabel().short;
  if (!mandate) {
    return (
      <CardFrame icon={ShoppingBag} title="Closed mandate" muted>
        <p className="text-small text-secondary-text">Not approved yet. The closed mandate is signed when you approve the Universal Cart, and it binds every hand-off by hash.</p>
      </CardFrame>
    );
  }
  return (
    <CardFrame
      icon={ShoppingBag}
      title="Closed mandate"
      meta={
        <>
          Approved {timeOf(mandate.approved_at)} with the button in the UI · {mandate.tier} tier
        </>
      }
      badge={mandate.simulated ? <SimulatedTag label={simLabel} /> : null}
    >
      <Rows>
        <Row label="Total">
          <Money value={mandate.total_usd} simulated={mandate.simulated} className="font-semibold" />
          <span className="text-muted-foreground"> · prices checked {timeOf(mandate.prices_checked_at)}</span>
        </Row>
        <Row label="Plan">
          <span className="font-mono">{mandate.plan_id}</span> <HashText hash={mandate.plan_sha256} />
        </Row>
        <Row label="Chain head">
          <HashText hash={mandate.chain_head} />
        </Row>
        <Row label="Open mandate">
          <HashText hash={mandate.open_mandate_sha256} />
        </Row>
        <Row label="Approval token">
          <HashText hash={mandate.approval_token_sha256} />
        </Row>
        {mandate.step_up ? (
          <Row label="Step-up">
            {mandate.step_up.provider} · {mandate.step_up.status} · <span className="font-mono">{mandate.step_up.inquiry_id}</span>
          </Row>
        ) : null}
      </Rows>

      <div className="space-y-1.5">
        <p className="text-caption font-medium text-muted-foreground">Hand-offs ({mandate.handoffs.length})</p>
        <ul className="divide-y divide-border rounded-sm border border-border">
          {mandate.handoffs.map((h) => (
            <li key={h.store_id} className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2.5 py-2 text-small">
              <span className="min-w-24 font-medium text-foreground">{h.store_id}</span>
              <ActionBadge level={h.action_level} />
              <span className="text-caption text-muted-foreground">{plural(h.items.length, "item")}</span>
              <span className="ml-auto">
                <Money value={h.subtotal_usd} simulated={h.simulated} />
              </span>
              <span className="basis-full text-caption text-muted-foreground">
                <HashText hash={h.url_sha256} label="link" />
                {h.caveat ? <span> · {h.caveat}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <SignatureLine signature={mandate.signature} />
      <JsonDisclosure data={mandate} />
    </CardFrame>
  );
}

export function PaymentMandateCard({ mandate }: { mandate?: PaymentMandate | null }) {
  if (!mandate) {
    return (
      <CardFrame icon={CreditCard} title="Payment mandate" muted>
        <p className="text-small text-secondary-text">No payment mandate: Tier 2 not used. This app never pays; you check out on each store's own page.</p>
      </CardFrame>
    );
  }
  return (
    <CardFrame
      icon={CreditCard}
      title="Payment mandate"
      meta={
        <>
          Consent {timeOf(mandate.user_consent.at)} · status {mandate.status} · <span className="font-mono">{mandate.mandate_id}</span>
        </>
      }
      badge={<TestModeBadge />}
    >
      <figure className="rounded-sm border border-dashed border-test bg-test-tint px-3 py-2 text-small text-foreground">“{mandate.user_consent.text_shown}”</figure>
      <Rows>
        <Row label="Total (test)">
          <Money value={mandate.total.amount / 100} simulated />
        </Row>
        {mandate.payment ? (
          <Row label="Stripe test">
            <span className="font-mono">{mandate.payment.payment_intent}</span>
            <span className="text-muted-foreground">
              {" "}
              · authorized {money(mandate.payment.authorized / 100)} · captured {money(mandate.payment.captured / 100)} · released {money(mandate.payment.released / 100)}
            </span>
          </Row>
        ) : null}
        <Row label="Closed mandate">
          <HashText hash={mandate.closed_mandate_sha256} />
        </Row>
      </Rows>
      <div className="space-y-1.5">
        <p className="text-caption font-medium text-muted-foreground">Allocations, one per store (simulated)</p>
        <ul className="divide-y divide-border rounded-sm border border-dashed border-test/60">
          {mandate.allocations.map((a) => (
            <li key={a.store_id} className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2.5 py-2 text-small">
              <span className="min-w-24 font-medium text-foreground">{a.store_id}</span>
              <ActionBadge level={a.action_level} />
              <span className="text-caption text-muted-foreground">limit</span>
              <Money value={a.limit / 100} simulated />
              {a.instrument ? <span className="font-mono text-caption text-muted-foreground">test card ···{a.instrument.last4}</span> : null}
              <span className="ml-auto">
                <SimulatedTag label={a.status} />
              </span>
            </li>
          ))}
        </ul>
      </div>
      <SignatureLine signature={mandate.signature} hash={mandate.mandate_hash} hashLabel="mandate" />
      <JsonDisclosure data={mandate} />
    </CardFrame>
  );
}
