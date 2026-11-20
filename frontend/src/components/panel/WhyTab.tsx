// Why tab, the why-card (PLAN §11.6): tier, reason codes as chips, one-sentence explanation, compatibility
// checks with pass / warn / fail and fixes, and "edited by you" if it was.
import { Brain, UserPen, Wrench } from "lucide-react";

import { CheckBadge } from "@/components/common/StatusBadge";
import { reasonCode } from "@/lib/format";
import type { PartPanel } from "@/lib/types";

const METHOD: Record<PartPanel["method"], string> = {
  exact_from_source: "Taken exactly from the source",
  kb: "Resolved with the knowledge base",
  llm_inferred: "Inferred by the model: check it",
};

export function WhyTab({ panel }: { panel: PartPanel }) {
  const attrs = Object.entries(panel.attrs ?? {});
  return (
    <div className="space-y-5">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex h-6 items-center rounded-full bg-ink px-2 text-caption font-medium text-white">Tier: {reasonCode(panel.why.tier)}</span>
          {panel.why.reason_codes.map((code) => (
            <span key={code} className="inline-flex h-6 items-center rounded-full border border-border bg-surface px-2 text-caption text-secondary-text">
              {reasonCode(code)}
            </span>
          ))}
          {panel.why.edited_by_user ? (
            <span className="inline-flex h-6 items-center gap-1 rounded-full border border-brand/30 bg-brand-tint px-2 text-caption font-medium text-brand">
              <UserPen className="size-3.5" strokeWidth={1.75} aria-hidden />
              edited by you
            </span>
          ) : null}
        </div>
        <p className="text-body text-foreground">{panel.why.explanation || "No explanation was recorded for this line."}</p>
      </section>

      <section className="space-y-2">
        <h3 className="text-small font-semibold">Compatibility checks</h3>
        {panel.checks.length ? (
          <ul className="space-y-2">
            {panel.checks.map((check) => (
              <li key={check.rule_id} className="rounded-lg border border-border p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-mono text-caption text-secondary-text">{check.rule_id}</p>
                  <CheckBadge result={check.result} />
                </div>
                <p className="mt-1 text-small text-foreground">{check.message}</p>
                {check.fix ? (
                  <p className="mt-1.5 flex items-start gap-1.5 text-caption text-pass">
                    <Wrench className="mt-0.5 size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
                    Fixed: {check.fix}
                  </p>
                ) : null}
                {check.kb_refs.length ? <p className="mt-1.5 font-mono text-caption text-muted-foreground">{check.kb_refs.join(" · ")}</p> : null}
                {check.needs_ack ? <p className="mt-1.5 text-caption text-warn">You acknowledge this when you approve the cart.</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-small text-muted-foreground">No rule applies to this line.</p>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="text-small font-semibold">What we searched for</h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-small">
          <dt className="text-muted-foreground">Spec</dt>
          <dd>{panel.spec || "not resolved"}</dd>
          {attrs.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{reasonCode(k)}</dt>
              <dd className="font-mono text-caption leading-5">{v}</dd>
            </div>
          ))}
          <dt className="text-muted-foreground">How</dt>
          <dd className="flex items-center gap-1.5">
            <Brain className="size-3.5 text-muted-foreground" strokeWidth={1.75} aria-hidden />
            {METHOD[panel.method] ?? panel.method} · <span className="tabular">{Math.round(panel.confidence * 100)}% confidence</span>
          </dd>
          {panel.owned ? (
            <>
              <dt className="text-muted-foreground">Owned</dt>
              <dd>
                Remembered: {panel.owned.memory_text} <span className="text-muted-foreground">({panel.owned.provider === "cognee" ? "via Cognee" : "your owned-parts list"})</span>
              </dd>
            </>
          ) : null}
        </dl>
      </section>
    </div>
  );
}
