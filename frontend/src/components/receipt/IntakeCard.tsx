// Intake card and provenance counts on the receipt (PLAN §3.17, §3.18, §11.5 E). Owner: D.
import { Inbox, Layers } from "lucide-react";

import { HashText } from "@/components/common/HashText";
import { ProvenanceChip } from "@/components/workspace/ProvenanceChip";
import { BUILD_TYPE_LABEL, PROVENANCE_LABEL } from "@/lib/format";
import type { ChainRecord, OpenMandate, Provenance, ProvenanceType } from "@/lib/types";
import { cn } from "@/lib/utils";

import { PROVENANCE_ORDER } from "./receiptFormat";

type Dict = Record<string, unknown>;

/** What the user asked for, as the chain recorded it before the mandate was signed. */
export function IntakeCard({ mandate, intakeRecord, className }: { mandate: OpenMandate; intakeRecord?: ChainRecord | null; className?: string }) {
  const s = mandate.scope;
  const rec = (intakeRecord ?? null) as Dict | null;
  const answers = rec && rec.answers && typeof rec.answers === "object" ? Object.entries(rec.answers as Dict) : [];
  const defaulted = rec && Array.isArray(rec.defaulted) ? (rec.defaulted as unknown[]).map(String) : [];
  const confidence = rec && typeof rec.confidence === "number" ? rec.confidence : null;
  const changed = rec?.changed_by_user === true || s.build_type_set_by === "user";
  return (
    <section className={cn("flex min-w-0 flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-e1", className)}>
      <header className="flex items-start gap-2">
        <Inbox className="mt-0.5 size-4 shrink-0 text-secondary-text" strokeWidth={1.75} aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-body font-semibold text-foreground">Your request</h3>
          <p className="text-caption text-muted-foreground">Read before the mandate was signed; the classifier is not an agent tool.</p>
        </div>
      </header>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-small">
        <dt className="text-muted-foreground">Build type</dt>
        <dd>
          {BUILD_TYPE_LABEL[s.build_type] ?? s.build_type}
          <span className="text-muted-foreground">
            {" "}
            · {changed ? "changed by you" : "set by the classifier"}
            {confidence !== null ? ` · confidence ${confidence.toFixed(2)}` : ""}
          </span>
        </dd>
        <dt className="text-muted-foreground">Goal</dt>
        <dd>{s.goal}</dd>
        <dt className="text-muted-foreground">Inputs</dt>
        <dd className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {s.inputs.source_url ? <span className="text-caption">link</span> : null}
          {s.inputs.text_sha256 ? <HashText hash={s.inputs.text_sha256} label="text" /> : null}
          {s.inputs.image_sha256.length ? (
            s.inputs.image_sha256.map((h) => <HashText key={h} hash={h} label="photo" />)
          ) : (
            <span className="text-caption text-muted-foreground">no photo</span>
          )}
        </dd>
        {answers.length ? (
          <>
            <dt className="text-muted-foreground">Answers</dt>
            <dd className="flex flex-wrap gap-1.5">
              {answers.map(([k, v]) => (
                <span key={k} className="rounded-full border border-border bg-muted px-2 py-0.5 text-caption text-secondary-text">
                  {k.replace(/_/g, " ")}: <span className="font-medium text-foreground">{String(v)}</span>
                  {defaulted.includes(k) ? <span className="text-warn"> · default</span> : null}
                </span>
              ))}
            </dd>
          </>
        ) : null}
        <dt className="text-muted-foreground">Intake</dt>
        <dd>
          <HashText hash={s.intake_sha256} />
        </dd>
      </dl>
    </section>
  );
}

/** A display-only provenance for the chip, so counts use the same icon and words as the parts list. */
function sampleProvenance(type: ProvenanceType): Provenance {
  switch (type) {
    case "readme_quote":
      return { type, check: "pass", supports: [], url: "", path: "", commit_sha: "", via: "http", quote: "", span: [0, 0], line_from: 0, line_to: 0, doc_sha256: "", more_quotes: [] };
    case "reference_project":
      return { type, check: "pass", supports: [], url: "", title: "", quote: "", span: [0, 0], doc_sha256: "", fetched_at: "", found_via: "template", fetched_via: "http" };
    case "template_row":
      return { type, check: "pass", supports: [], kb_ref: "", template_id: "", row_id: "", template_sha256: "", basis: "reference" };
    case "photo_region":
      return { type, check: "pass", supports: [], image_id: "", image_sha256: "", box_xyxy_px: [0, 0, 0, 0], label: "", score: 0, detector: "claude_vision" };
    case "assumption":
      return { type, check: "pass", supports: [], statement: "", basis: "", confirmed_by_user: true };
  }
}

/** How many BOM lines came from each of the five provenance types (PLAN §3.18, §9). */
export function ProvenanceCounts({ counts, source, className }: { counts: Record<ProvenanceType, number>; source: "run" | "chain"; className?: string }) {
  const total = PROVENANCE_ORDER.reduce((n, t) => n + (counts[t] ?? 0), 0);
  return (
    <section className={cn("flex min-w-0 flex-col gap-3 rounded-lg border border-border bg-surface p-4 shadow-e1", className)}>
      <header className="flex items-start gap-2">
        <Layers className="mt-0.5 size-4 shrink-0 text-secondary-text" strokeWidth={1.75} aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-body font-semibold text-foreground">Where every line comes from</h3>
          <p className="text-caption text-muted-foreground">
            {total} {total === 1 ? "line" : "lines"} · {source === "run" ? "from the run" : "counted from the part decisions in the chain"}
          </p>
        </div>
      </header>
      <ul className="space-y-1.5">
        {PROVENANCE_ORDER.map((t) => (
          <li key={t} className={cn("flex items-center gap-2", !(counts[t] ?? 0) && "opacity-50")}>
            <ProvenanceChip provenance={sampleProvenance(t)} detail={false} />
            <span className="sr-only">{PROVENANCE_LABEL[t]}</span>
            <span className="tabular ml-auto font-mono text-small text-foreground">{counts[t] ?? 0}</span>
          </li>
        ))}
      </ul>
      <p className="text-caption text-muted-foreground">Templates are starting points, not verified designs. Assumptions were confirmed by you before approval.</p>
    </section>
  );
}
