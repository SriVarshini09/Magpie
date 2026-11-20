// The agent's message blocks. Both agents (the keyword assistant and Claude) send the same blocks; nothing here
// knows which one wrote them. Every figure comes from the block: no value is computed or guessed in the page.
// Mock and simulated data keep their violet dashed label wherever they appear.
import { ArrowRight, Check, CircleAlert, CircleHelp, FileSignature, Lock, PackageX, ShieldX, Store } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router";

import { Money } from "@/components/common/Money";
import { ChipQuestions } from "@/components/composer/ChipQuestions";
import { MandateForm } from "@/components/composer/MandateForm";
import { SimulatedTag } from "@/components/MockDataBadge";
import { ActionBadge } from "@/components/panel/ActionBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ProvenanceChip } from "@/components/workspace/ProvenanceChip";
import { BUILD_TYPE_LABEL, dayOf, LEFT_OUT_LABEL, moneyDelta, moneyShort, plural, reasonCode, viaText } from "@/lib/format";
import type { AssumptionRequest, BuildType, ChatAction, ChatBlock, Intake, MandatePreset, OfferRow, OfferStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ProgressBlock } from "./ProgressBlock";

export type BlockContext = {
  busy: boolean;
  /** This block is the newest of its kind and may still be acted on. Older ones are a read-only record. */
  live: boolean;
  onReply: (text: string) => void;
  /** Resolves to an error message, or null when the mandate was signed. */
  onSign: (mandate: MandatePreset) => Promise<string | null>;
  onAssumption: (body: AssumptionRequest) => Promise<void>;
  onRunStopped: () => void;
};

const card = "rounded-lg border border-border bg-surface";
const pill = "inline-flex h-8 items-center gap-1.5 rounded-full border border-border-strong bg-surface px-3 text-small text-foreground transition-colors duration-150 hover:border-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand disabled:opacity-50";
const ALL_TYPES: BuildType[] = ["quadcopter", "robot_arm", "rc_car", "claw_gripper", "electronics_mcu", "generic"];

function Actions({ actions, ctx }: { actions: ChatAction[]; ctx: BlockContext }) {
  const shown = actions.filter((a) => (a.kind === "link" && a.href) || (a.kind === "reply" && a.text));
  if (!shown.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      {shown.map((a) =>
        a.kind === "link" ? (
          <Button key={a.label} asChild variant="outline" className="h-8 px-3">
            <Link to={a.href ?? "/"}>
              {a.label} <ArrowRight aria-hidden />
            </Link>
          </Button>
        ) : (
          <button key={a.label} type="button" disabled={ctx.busy} onClick={() => ctx.onReply(a.text ?? a.label)} className={pill}>
            {a.label}
          </button>
        ),
      )}
    </div>
  );
}

function Head({ title, right, simulated }: { title: ReactNode; right?: ReactNode; simulated?: boolean }) {
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-2">
      <h3 className="text-small font-semibold">{title}</h3>
      {simulated ? <SimulatedTag label="Simulated store data" /> : null}
      {right ? <span className="ml-auto text-caption text-muted-foreground">{right}</span> : null}
    </header>
  );
}

// ------------------------------------------------------------------ before the run

function BuildTypeCard({ intake, text, ctx }: { intake: Intake; text?: string | null; ctx: BlockContext }) {
  const [open, setOpen] = useState(false);
  const order = [...new Set<BuildType>([intake.build_type, ...intake.alternatives.map((a) => a.build_type), ...ALL_TYPES])];
  return (
    <section className={cn(card, "space-y-2 p-3")} aria-label="Build type">
      <p className="flex flex-wrap items-center gap-2 text-body">
        <span className="text-secondary-text">I read this as</span>
        <span className="inline-flex h-7 items-center rounded-sm border border-border bg-page px-2 font-semibold">{BUILD_TYPE_LABEL[intake.build_type] ?? intake.build_type}</span>
        <span className="tabular text-small text-muted-foreground">{Math.round(intake.confidence * 100)}% sure</span>
        {ctx.live ? (
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="rounded-sm text-small font-medium text-brand hover:text-brand-hover focus-visible:outline-2 focus-visible:outline-brand">
            {open ? "Keep it" : "Change"}
          </button>
        ) : null}
        {text ? <span className="text-small text-muted-foreground">{text}</span> : null}
      </p>
      {intake.summary ? <p className="text-small text-secondary-text">{intake.summary}</p> : null}
      {intake.source_api === "keyword_router" ? <p className="text-caption text-muted-foreground">Read by the keyword router (Claude is not connected).</p> : null}
      {intake.simulated ? <SimulatedTag label="Sample classification" /> : null}
      {open && ctx.live ? (
        <div role="radiogroup" aria-label="Build type" className="flex flex-wrap gap-1.5">
          {order.map((type) => (
            <button
              key={type}
              type="button"
              role="radio"
              aria-checked={type === intake.build_type}
              disabled={ctx.busy}
              onClick={() => {
                setOpen(false);
                if (type !== intake.build_type) ctx.onReply(`Build type: ${type}`);
              }}
              className={cn(pill, type === intake.build_type && "border-ink bg-ink text-white")}
            >
              {BUILD_TYPE_LABEL[type]}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function QuestionsCard({ intake, ctx }: { intake: Intake; ctx: BlockContext }) {
  const answers = Object.fromEntries(intake.questions.filter((q) => q.answer).map((q) => [q.id, q.answer as string]));
  return (
    <section className={cn(card, "p-3")} aria-label="Questions">
      <ChipQuestions
        intake={intake}
        answers={answers}
        disabled={ctx.busy || !ctx.live}
        onAnswer={(id, value) => {
          const q = intake.questions.find((x) => x.id === id);
          const chip = q?.chips.find((c) => c.value === value);
          if (q && chip) ctx.onReply(`${q.text} ${chip.label}`);
        }}
        onSkip={() => ctx.onReply("Use the defaults")}
      />
      {ctx.live ? <p className="mt-2 text-caption text-muted-foreground">Tap a choice, or type it (for example “5 inch”).</p> : null}
    </section>
  );
}

function MandateCard({ intake, text, ctx }: { intake: Intake; text?: string | null; ctx: BlockContext }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const box = useRef<HTMLElement>(null);
  // The form opens below the summary: bring it into view inside the conversation.
  useEffect(() => {
    if (open) box.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [open]);
  const p = intake.mandate_preset;
  const shared = (Object.entries(p.data_sharing) as Array<[string, boolean]>).filter(([k, v]) => v && k !== "photo_to_models").map(([k]) => k.replace(/_/g, " "));
  const budget = intake.constraints.budget_usd ?? p.budget_usd;
  return (
    <section ref={box} className={cn(card, "scroll-mb-4 space-y-3 p-3")} aria-label="Mandate">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="inline-flex items-center gap-1.5 text-small font-semibold">
          <FileSignature className="size-4" strokeWidth={1.75} aria-hidden />
          Mandate
        </span>
        <dl className="flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-secondary-text">
          <div className="flex gap-1.5">
            <dt>Budget</dt>
            <dd className="tabular font-mono text-foreground">{moneyShort(budget)}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt>By</dt>
            <dd className="text-foreground">{dayOf(p.deadline) || p.deadline}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="sr-only">Stores</dt>
            <dd className="text-foreground">{plural(p.allowed_merchants.length, "store")}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt>Shares</dt>
            <dd className="text-foreground">{shared.length ? `${shared.join(", ")} only` : "nothing"}</dd>
          </div>
        </dl>
        {ctx.live && !open ? (
          <Button type="button" className="ml-auto h-8 px-3" onClick={() => setOpen(true)}>
            <Lock aria-hidden /> Sign
          </Button>
        ) : !ctx.live ? (
          <span className="ml-auto text-caption text-muted-foreground">Earlier form</span>
        ) : null}
      </div>
      {text ? <p className="text-small text-secondary-text">{text}</p> : null}
      {open && ctx.live ? (
        <MandateForm
          intake={intake}
          busy={busy}
          error={error}
          onSign={async (mandate) => {
            setBusy(true);
            setError(null);
            const failed = await ctx.onSign(mandate);
            setBusy(false);
            if (failed) setError(failed);
            else setOpen(false);
          }}
        />
      ) : null}
    </section>
  );
}

// ------------------------------------------------------------------ the run

function PartsCard({ block, ctx }: { block: ChatBlock; ctx: BlockContext }) {
  const rows = block.parts ?? [];
  const priced = rows.filter((r) => typeof r.line_usd === "number").length;
  return (
    <section className={card} aria-label="Parts">
      <Head title={`Parts · ${plural(rows.length, "line")}`} right={`${priced} with an offer`} simulated={block.simulated} />
      {rows.length ? (
        <ul className="divide-y divide-border">
          {rows.map((r) => (
            <li key={r.bom_line_id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-3 py-2">
              <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                <button
                  type="button"
                  disabled={ctx.busy}
                  onClick={() => ctx.onReply(`Why this ${r.name} (${r.bom_line_id})?`)}
                  title="Ask why this was chosen"
                  className="max-w-full truncate rounded-sm text-left text-body font-medium text-foreground hover:text-brand focus-visible:outline-2 focus-visible:outline-brand"
                >
                  {r.name}
                </button>
                <span className="tabular text-small text-muted-foreground">×{r.qty}</span>
                <ProvenanceChip provenance={r.provenance} />
              </div>
              <div className="flex items-center justify-end gap-2 text-small">
                {r.store_name ? (
                  <span className="inline-flex h-6 max-w-[190px] items-center gap-1 rounded-sm border border-border bg-page px-1.5 text-caption text-secondary-text" title={r.store_name}>
                    <Store className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
                    <span className="truncate">{r.store_name}</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
                    {r.status === "not_found" ? <PackageX className="size-3.5" strokeWidth={1.75} aria-hidden /> : null}
                    {r.note ?? "No offer chosen"}
                  </span>
                )}
                {r.more_stores > 0 ? (
                  <button type="button" disabled={ctx.busy} onClick={() => ctx.onReply(`Show me other offers for ${r.name} (${r.bom_line_id})`)} title="Compare the offers" className="tabular rounded-sm text-caption font-medium text-brand hover:text-brand-hover focus-visible:outline-2 focus-visible:outline-brand">
                    +{plural(r.more_stores, "store")}
                  </button>
                ) : null}
                {r.store_name ? <Money value={r.line_usd} simulated={r.simulated} className="w-[72px] text-right" /> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="px-3 py-3 text-small text-muted-foreground">This run has no parts yet.</p>
      )}
    </section>
  );
}

const STATUS: Record<OfferStatus, { label: string; cls: string }> = {
  chosen: { label: "Chosen", cls: "border-pass/40 bg-pass-tint text-pass" },
  alternative: { label: "Acceptable", cls: "border-border bg-page text-secondary-text" },
  rejected: { label: "Rejected", cls: "border-warn/50 bg-warn-tint text-warn" },
  refused: { label: "Refused", cls: "border-fail/40 bg-fail-tint text-fail" },
};

function StatusPill({ status }: { status: OfferStatus }) {
  const s = STATUS[status] ?? STATUS.alternative;
  const Icon = status === "chosen" ? Check : status === "refused" ? ShieldX : status === "rejected" ? CircleAlert : null;
  return (
    <span className={cn("inline-flex h-6 shrink-0 items-center gap-1 rounded-sm border px-1.5 text-caption font-medium", s.cls)}>
      {Icon ? <Icon className="size-3.5" strokeWidth={1.75} aria-hidden /> : null}
      {s.label}
    </span>
  );
}

function OfferLine({ o }: { o: OfferRow }) {
  return (
    <li className="grid grid-cols-[88px_minmax(0,1fr)_auto] items-start gap-x-3 px-3 py-2">
      <StatusPill status={o.status} />
      <div className="min-w-0">
        <p className="truncate text-small font-medium text-foreground" title={o.title}>
          {o.store_name} · <span className="font-normal text-secondary-text">{o.title}</span>
        </p>
        <p className="text-caption text-muted-foreground">
          {o.packs_needed} × {o.units_per_pack > 1 ? `pack of ${o.units_per_pack}` : "single"} · {viaText(o.source_api, o.mock_of)}
          {o.reason ? <span className={o.status === "refused" ? "text-fail" : "text-warn"}> · {o.status === "refused" ? "outside your mandate: " : ""}{o.reason}</span> : null}
        </p>
      </div>
      <div className="text-right">
        <Money value={o.line_usd} seenAt={o.seen_at} source={o.source_api} mockOf={o.mock_of} simulated={o.simulated} className="text-small" />
        {typeof o.vs_chosen_usd === "number" && o.vs_chosen_usd !== 0 ? <p className="tabular font-mono text-caption text-muted-foreground">{moneyDelta(o.vs_chosen_usd)}</p> : null}
      </div>
    </li>
  );
}

function ComparisonCard({ block }: { block: ChatBlock }) {
  const panel = block.panel;
  if (!panel) return null;
  return (
    <section className={card} aria-label={`Offers for ${panel.name}`}>
      <Head title={`Offers · ${panel.name} ×${panel.qty}`} right={plural(panel.offers.length, "offer")} simulated={block.simulated} />
      {panel.offers.length ? (
        <ul className="divide-y divide-border">
          {panel.offers.map((o) => (
            <OfferLine key={o.offer_id} o={o} />
          ))}
        </ul>
      ) : (
        <p className="px-3 py-3 text-small text-muted-foreground">No offers were found for this part in the stores your mandate allows.</p>
      )}
      {panel.refusals.length ? (
        <ul className="space-y-1 border-t border-border px-3 py-2">
          {panel.refusals.map((r) => (
            <li key={`${r.rule}-${r.attempted}`} className="flex items-center gap-1.5 text-caption text-fail">
              <ShieldX className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
              Refused{r.count > 1 ? ` ×${r.count}` : ""}: {r.attempted || reasonCode(r.rule)} <span className="font-mono text-muted-foreground">({r.clause})</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function WhyCard({ block }: { block: ChatBlock }) {
  const panel = block.panel;
  if (!panel) return null;
  const chosen = panel.offers.filter((o) => o.status === "chosen");
  return (
    <section className={card} aria-label={`Why this ${panel.name}`}>
      <Head title={`Why · ${panel.name}`} right={`${reasonCode(panel.why.tier)} plan`} simulated={block.simulated} />
      <div className="space-y-2 px-3 py-2.5">
        <p className="text-body text-foreground">{block.text || panel.why.explanation || "No explanation was recorded for this line."}</p>
        {panel.why.reason_codes.length ? (
          <p className="flex flex-wrap gap-1.5">
            {panel.why.reason_codes.map((c) => (
              <span key={c} className="inline-flex h-6 items-center rounded-sm border border-border bg-page px-1.5 text-caption text-secondary-text">
                {reasonCode(c)}
              </span>
            ))}
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground">
          <ProvenanceChip provenance={panel.provenance} />
          <span>Spec: {panel.spec}</span>
        </div>
      </div>
      {chosen.length ? (
        <ul className="divide-y divide-border border-t border-border">
          {chosen.map((o) => (
            <OfferLine key={o.offer_id} o={o} />
          ))}
        </ul>
      ) : null}
      {panel.checks.length ? (
        <ul className="space-y-1 border-t border-border px-3 py-2">
          {panel.checks.map((c) => (
            <li key={c.rule_id} className="flex items-start gap-1.5 text-caption">
              {c.result === "pass" ? <Check className="mt-0.5 size-3.5 shrink-0 text-pass" strokeWidth={2} aria-hidden /> : <CircleAlert className={cn("mt-0.5 size-3.5 shrink-0", c.result === "fail" ? "text-fail" : "text-warn")} strokeWidth={1.75} aria-hidden />}
              <span className="text-secondary-text">
                <span className="font-mono text-foreground">{c.rule_id}</span> {reasonCode(c.result)}: {c.message}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function CartCard({ block }: { block: ChatBlock }) {
  const cart = block.cart;
  if (!cart) return null;
  const delta = typeof cart.previous_total_usd === "number" ? cart.total_usd - cart.previous_total_usd : null;
  const over = cart.total_usd > cart.budget_usd;
  return (
    <section className={card} aria-label="Cart summary">
      <Head title={`Cart · ${reasonCode(cart.tier)} plan`} right={cart.state === "draft" ? "Draft · not approved" : reasonCode(cart.state)} simulated={block.simulated} />
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2 px-3 py-3">
        <div>
          <p className="text-caption text-muted-foreground">Total</p>
          <p className="flex items-baseline gap-2">
            <Money value={cart.total_usd} simulated={cart.simulated} className="text-h3 font-semibold" />
            {delta !== null ? <span className={cn("tabular font-mono text-small", delta < 0 ? "text-pass" : "text-warn")}>{moneyDelta(delta)}</span> : null}
          </p>
        </div>
        <div>
          <p className="text-caption text-muted-foreground">Signed budget</p>
          <p className={cn("tabular font-mono text-body", over && "text-fail")}>
            {moneyShort(cart.budget_usd)}
            {over ? " · over" : ""}
          </p>
        </div>
        <div>
          <p className="text-caption text-muted-foreground">Checkouts</p>
          <p className="tabular text-body">
            {plural(cart.stores.length, "store")}
            {cart.items_by_hand ? <span className="text-muted-foreground"> · {plural(cart.items_by_hand, "item")} by hand</span> : null}
          </p>
        </div>
      </div>
      {cart.stores.length ? (
        <ul className="divide-y divide-border border-t border-border">
          {cart.stores.map((s) => (
            <li key={s.store_id} className="flex items-center gap-2 px-3 py-2 text-small">
              <span className="min-w-0 truncate font-medium" title={s.display_name}>
                {s.display_name}
              </span>
              <ActionBadge level={s.action_level} />
              <span className="text-caption text-muted-foreground">{plural(s.items, "item")}</span>
              <Money value={s.subtotal_usd} simulated={cart.simulated} className="ml-auto text-small" />
            </li>
          ))}
        </ul>
      ) : (
        <p className="border-t border-border px-3 py-3 text-small text-muted-foreground">The cart is empty: nothing acceptable was found in the stores your mandate allows.</p>
      )}
      {cart.left_out.length ? (
        <p className="border-t border-border px-3 py-2 text-caption text-muted-foreground">
          Left out: {cart.left_out.map((l) => `${l.name} (${LEFT_OUT_LABEL[l.reason] ?? reasonCode(l.reason)})`).join(" · ")}
        </p>
      ) : null}
      {cart.open_assumptions.length ? (
        <p className="flex items-center gap-1.5 border-t border-warn/40 bg-warn-tint px-3 py-2 text-small text-warn">
          <CircleHelp className="size-4 shrink-0" strokeWidth={1.75} aria-hidden />
          {plural(cart.open_assumptions.length, "assumption")} to confirm before this cart can be approved.
        </p>
      ) : null}
    </section>
  );
}

function AssumptionsCard({ block, ctx }: { block: ChatBlock; ctx: BlockContext }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [spec, setSpec] = useState("");
  const [working, setWorking] = useState<string | null>(null);
  const rows = block.assumptions ?? [];
  const act = async (body: AssumptionRequest) => {
    setWorking(body.bom_line_id);
    await ctx.onAssumption(body);
    setWorking(null);
    setEditing(null);
  };
  return (
    <section className={cn(card, "border-warn/50")} aria-label="Assumptions to confirm">
      <Head title={`To confirm · ${plural(rows.length, "assumption")}`} />
      <ul className="divide-y divide-border">
        {rows.map((a) => {
          const off = !ctx.live || ctx.busy || working !== null;
          return (
            <li key={a.bom_line_id} className="space-y-2 px-3 py-2.5">
              <p className="text-body">
                <span className="font-medium">{a.name}</span> <span className="tabular text-small text-muted-foreground">×{a.qty}</span>
              </p>
              <p className="text-small text-secondary-text">
                {a.statement} <span className="text-muted-foreground">Basis: {a.basis}</span>
              </p>
              {editing === a.bom_line_id ? (
                <form
                  className="flex flex-wrap items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (spec.trim()) void act({ bom_line_id: a.bom_line_id, action: "edit", spec: spec.trim() });
                  }}
                >
                  <label className="sr-only" htmlFor={`spec-${a.bom_line_id}`}>
                    What it should be
                  </label>
                  <Input id={`spec-${a.bom_line_id}`} value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="What it should be" className="h-8 max-w-sm flex-1" autoFocus />
                  <Button type="submit" variant="outline" className="h-8 px-3" disabled={off || !spec.trim()}>
                    Save and confirm
                  </Button>
                  <Button type="button" variant="ghost" className="h-8 px-3" onClick={() => setEditing(null)}>
                    Cancel
                  </Button>
                </form>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" className="h-8 px-3" disabled={off} onClick={() => void act({ bom_line_id: a.bom_line_id, action: "confirm" })}>
                    <Check aria-hidden /> Confirm
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-8 px-3"
                    disabled={off}
                    onClick={() => {
                      setSpec(a.spec ?? "");
                      setEditing(a.bom_line_id);
                    }}
                  >
                    Edit
                  </Button>
                  <Button type="button" variant="ghost" className="h-8 px-3 text-secondary-text" disabled={off} onClick={() => void act({ bom_line_id: a.bom_line_id, action: "remove" })}>
                    Remove
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function RefusalCard({ block }: { block: ChatBlock }) {
  const r = block.refusal;
  return (
    <section role="note" className="flex items-start gap-2.5 rounded-lg border border-fail/40 bg-fail-tint px-3 py-2.5" aria-label="Refused">
      <ShieldX className="mt-0.5 size-4 shrink-0 text-fail" strokeWidth={1.75} aria-hidden />
      <div className="min-w-0 space-y-1">
        <p className="text-body text-foreground">{block.text ?? "Refused under your mandate."}</p>
        {r ? (
          <p className="text-caption text-secondary-text">
            Logged as a refusal · rule <span className="font-mono">{r.rule}</span> · <span className="font-mono">{r.clause}</span>
          </p>
        ) : null}
      </div>
    </section>
  );
}

export function Block({ block, ctx }: { block: ChatBlock; ctx: BlockContext }) {
  let body: ReactNode = null;
  let showText = true;
  switch (block.kind) {
    case "build_type":
      body = block.intake ? <BuildTypeCard intake={block.intake} text={block.text} ctx={ctx} /> : null;
      showText = false;
      break;
    case "questions":
      body = block.intake ? <QuestionsCard intake={block.intake} ctx={ctx} /> : null;
      break;
    case "mandate":
      body = block.intake ? <MandateCard intake={block.intake} text={block.text} ctx={ctx} /> : null;
      showText = false;
      break;
    case "progress":
      body = block.run_id ? <ProgressBlock runId={block.run_id} text={block.text} onStopped={ctx.onRunStopped} /> : null;
      showText = false;
      break;
    case "parts":
      body = <PartsCard block={block} ctx={ctx} />;
      break;
    case "comparison":
      body = <ComparisonCard block={block} />;
      break;
    case "why":
      body = <WhyCard block={block} />;
      showText = false;
      break;
    case "cart":
      body = <CartCard block={block} />;
      break;
    case "assumptions":
      body = <AssumptionsCard block={block} ctx={ctx} />;
      break;
    case "refusal":
      body = <RefusalCard block={block} />;
      showText = false;
      break;
    default:
      body = null;
  }
  // "Skip, use defaults" is already a button inside the questions card.
  const actions = block.kind === "questions" ? [] : block.actions;
  return (
    <div className="space-y-2">
      {showText && block.text ? (
        <p className={cn("text-body leading-6 whitespace-pre-line text-foreground", block.tone === "warn" && "rounded-lg border border-warn/40 bg-warn-tint px-3 py-2")}>{block.text}</p>
      ) : null}
      {body}
      <Actions actions={actions} ctx={ctx} />
    </div>
  );
}
