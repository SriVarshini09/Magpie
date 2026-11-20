// Sources tab (PLAN §11.6, §11.13): the line's provenance, whichever of the five types it is: the README
// sentence with line numbers, commit and how it was read; a reference design's sentence; the template row
// ("rule of thumb" if so); the photo crop with detector and score; or the assumption with Confirm · Edit ·
// Remove. Then the knowledge-base rows with line ranges and score, and the hybrid SQL in a mono block.
import { AssumptionActions } from "@/components/workspace/AssumptionBar";
import { MatchedTermsLine, MatchedText, rankText } from "@/components/workspace/KbMatch";
import { ProvenanceDetail } from "@/components/workspace/ProvenanceChip";
import { TestBadge } from "@/components/common/StatusBadge";
import type { PartPanel, PhotoView, RunTemplate } from "@/lib/types";

export function SqlBlock({ sql, label = "Query" }: { sql: string; label?: string }) {
  const mock = /^\s*--\s*MOCK/i.test(sql);
  return (
    <figure className="space-y-1">
      <figcaption className="flex items-center gap-2 text-caption text-muted-foreground">
        {label}
        {mock ? <TestBadge>Mock: a sketch, never run</TestBadge> : null}
      </figcaption>
      <pre className="max-h-44 overflow-auto rounded-lg border border-border bg-muted p-3 font-mono text-caption leading-5 whitespace-pre-wrap text-secondary-text">{sql}</pre>
    </figure>
  );
}

export function SourcesTab({ panel, runId, photo, template }: { panel: PartPanel; runId: string; photo?: PhotoView | null; template?: RunTemplate | null }) {
  const p = panel.provenance;
  const open = p.type === "assumption" && !p.confirmed_by_user;
  const sql = panel.kb.find((k) => k.sql)?.sql ?? (p.type === "template_row" ? template?.sql : null);
  return (
    <div className="space-y-5">
      <section className={open ? "rounded-lg border border-warn/40 bg-warn-tint/50 p-3" : "rounded-lg border border-border p-3"}>
        <ProvenanceDetail
          provenance={p}
          photo={photo}
          actions={open ? <AssumptionActions runId={runId} line={{ bom_line_id: panel.bom_line_id, qty: panel.qty, spec: panel.spec }} /> : undefined}
        />
      </section>

      <section className="space-y-2">
        <h3 className="text-small font-semibold">Knowledge base</h3>
        {panel.kb.length ? (
          <ul className="space-y-2">
            {panel.kb.map((chunk) => (
              <li key={`${chunk.kb_ref}-${chunk.line_from}`} className="rounded-lg border border-border p-3">
                <p className="flex flex-wrap items-center justify-between gap-2 text-caption text-muted-foreground">
                  <span className="font-medium text-foreground">{chunk.doc_title}</span>
                  <span className="tabular font-mono">
                    lines {chunk.line_from}
                    {chunk.line_to !== chunk.line_from ? `–${chunk.line_to}` : ""}
                    {rankText(chunk) ? ` · ${rankText(chunk)}` : ""} · score {chunk.score.toFixed(3)}
                  </span>
                </p>
                <p className="mt-1.5 text-small text-secondary-text">
                  <MatchedText text={chunk.text} terms={chunk.matched_terms ?? []} />
                </p>
                <MatchedTermsLine chunk={chunk} className="mt-1" />
                <p className="mt-1.5 font-mono text-caption text-muted-foreground">{chunk.kb_ref}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-small text-muted-foreground">No knowledge-base rows were used for this line.</p>
        )}
        {sql ? <SqlBlock sql={sql} label="Hybrid search SQL" /> : null}
      </section>
    </div>
  );
}
