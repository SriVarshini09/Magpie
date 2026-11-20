// SourceChip: where the parts list came from, shown on top of the list (PLAN §11.5 B).
// A link run names the repository and how it was read; a typed run names the template; a photo run shows the photo.
import { ExternalLink, FileText, Image as ImageIcon, LayoutTemplate } from "lucide-react";

import { HashText } from "@/components/common/HashText";
import { SimulatedTag } from "@/components/MockDataBadge";
import { api } from "@/lib/api";
import { hostOf, PROVENANCE_LABEL, repoOf, sourceName } from "@/lib/format";
import type { ProvenanceType, RunState } from "@/lib/types";

const ORDER: ProvenanceType[] = ["readme_quote", "reference_project", "template_row", "photo_region", "assumption"];

export function SourceChip({ run }: { run: RunState }) {
  const counts = ORDER.filter((t) => (run.provenance_counts?.[t] ?? 0) > 0).map((t) => `${run.provenance_counts[t]} ${PROVENANCE_LABEL[t].toLowerCase()}`);
  const images = run.intake.inputs.images ?? [];
  return (
    <div className="space-y-1.5 border-b border-border px-4 py-3">
      {run.source ? (
        <>
          <p className="flex flex-wrap items-center gap-1.5 text-caption text-muted-foreground">
            <FileText className="size-3.5" strokeWidth={1.75} aria-hidden />
            {run.source.simulated ? (
              <>
                Source · a bundled copy of the README <SimulatedTag label={`Mock ${sourceName(run.source.via)} connector`} />
              </>
            ) : (
              <>Source · read through {run.source.via === "http" && repoOf(run.source.url) !== hostOf(run.source.url) ? "GitHub directly (no token)" : sourceName(run.source.via)}</>
            )}
          </p>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <a href={run.source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-small font-medium text-brand hover:text-brand-hover">
              {repoOf(run.source.url)}
              <ExternalLink className="size-3" strokeWidth={1.75} aria-hidden />
            </a>
            <span className="font-mono text-caption text-muted-foreground">
              {run.source.path} @ {run.source.commit_sha.slice(0, 7)}
            </span>
            <HashText hash={run.source.sha256} />
          </p>
        </>
      ) : run.template ? (
        <>
          <p className="flex items-center gap-1.5 text-caption text-muted-foreground">
            <LayoutTemplate className="size-3.5" strokeWidth={1.75} aria-hidden />
            Source · your request and a build template
          </p>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small">
            <span className="font-mono font-medium">{run.template.template_id}</span>
            {run.template.variant ? <span className="font-mono text-caption text-muted-foreground">variant {run.template.variant}</span> : null}
          </p>
        </>
      ) : (
        <p className="flex items-center gap-1.5 text-caption text-muted-foreground">
          <FileText className="size-3.5" strokeWidth={1.75} aria-hidden />
          Source · your request
        </p>
      )}
      {images.length ? (
        <p className="flex items-center gap-2 text-caption text-muted-foreground">
          <ImageIcon className="size-3.5" strokeWidth={1.75} aria-hidden />
          {images.map((im) => (
            <img key={im.image_id} src={api.uploadUrl(im.image_id)} alt="Your photo" className="size-8 rounded-sm border border-border object-cover" />
          ))}
          your photo
        </p>
      ) : null}
      {counts.length ? <p className="text-caption text-muted-foreground">{counts.join(" · ")}</p> : null}
    </div>
  );
}
