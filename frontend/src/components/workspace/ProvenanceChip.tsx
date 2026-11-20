// Provenance chip and detail (PLAN §3.18, Q18). Every BOM line says where it came from:
// Quoted · Reference design · Template (rule of thumb) · Seen in your photo · Assumed.
// Icon and word, never colour alone. An open assumption is amber everywhere it appears.
import { BookOpen, Camera, CircleHelp, ExternalLink, LayoutTemplate, Quote, type LucideIcon } from "lucide-react";
import { Popover } from "radix-ui";
import type { ReactNode } from "react";

import { HashText } from "@/components/common/HashText";
import { api } from "@/lib/api";
import { hostOf, PROVENANCE_LABEL, repoOf, sourceName, timeOf } from "@/lib/format";
import type { PhotoView, Provenance, ProvenanceType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";

export const PROVENANCE_ICON: Record<ProvenanceType, LucideIcon> = {
  readme_quote: Quote,
  reference_project: BookOpen,
  template_row: LayoutTemplate,
  photo_region: Camera,
  assumption: CircleHelp,
};

export function isOpenAssumption(p: Provenance): boolean {
  return p.type === "assumption" && !p.confirmed_by_user;
}

export function provenanceLabel(p: Provenance): string {
  if (p.type === "template_row" && p.basis === "rule_of_thumb") return "Template · rule of thumb";
  if (p.type === "assumption") return p.confirmed_by_user ? "Assumed · confirmed" : "Assumed";
  return PROVENANCE_LABEL[p.type] ?? "Source unknown";
}

function chipClass(p: Provenance, interactive: boolean) {
  return cn(
    "inline-flex h-6 shrink-0 items-center gap-1 rounded-sm border px-1.5 text-caption font-medium whitespace-nowrap transition-colors duration-150",
    isOpenAssumption(p) ? "border-warn/50 bg-warn-tint text-warn" : p.check === "fail" ? "border-fail/40 bg-fail-tint text-fail" : "border-border bg-surface text-secondary-text",
    interactive && (isOpenAssumption(p) ? "hover:border-warn" : "hover:border-border-strong hover:text-foreground"),
  );
}

/** The chip alone. With `detail` (the default) it opens a popover with the quote, row, crop or assumption. */
export function ProvenanceChip({ provenance, detail = true, photo, className }: { provenance: Provenance; detail?: boolean; photo?: PhotoView | null; className?: string }) {
  const Icon = PROVENANCE_ICON[provenance.type] ?? CircleHelp;
  const content = (
    <>
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
      {provenanceLabel(provenance)}
    </>
  );
  if (!detail) return <span className={cn(chipClass(provenance, false), className)}>{content}</span>;
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button type="button" onClick={(e) => e.stopPropagation()} aria-label={`${provenanceLabel(provenance)}: show the source`} className={cn(chipClass(provenance, true), className)}>
          {content}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="start"
          sideOffset={6}
          collisionPadding={12}
          onClick={(e) => e.stopPropagation()}
          className="z-50 w-[380px] rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-e2 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
        >
          <ProvenanceDetail provenance={provenance} photo={photo} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function Meta({ children }: { children: ReactNode }) {
  return <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted-foreground">{children}</p>;
}

function Ext({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-brand hover:text-brand-hover">
      {children}
      <ExternalLink className="size-3" strokeWidth={1.75} aria-hidden />
    </a>
  );
}

function QuoteBlock({ quote, lineFrom, lineTo }: { quote: string; lineFrom?: number; lineTo?: number }) {
  return (
    <figure className="rounded-sm border-l-2 border-brand bg-brand-tint px-3 py-2">
      <blockquote className="text-small text-foreground">
        <mark className="bg-transparent font-medium text-foreground">“{quote}”</mark>
      </blockquote>
      {lineFrom ? (
        <figcaption className="mt-1 font-mono text-caption text-muted-foreground">
          line {lineFrom}
          {lineTo && lineTo !== lineFrom ? `–${lineTo}` : ""}
        </figcaption>
      ) : null}
    </figure>
  );
}

const DETECTOR_LABEL: Record<string, string> = {
  "sie:grounding-dino-base": "Superlinked SIE, Grounding DINO",
  claude_vision: "Claude vision, approximate region",
};

/** The crop of the user's photo for a detected part. Needs the photo's size to place the box. */
function PhotoCrop({ imageId, box, photo, label }: { imageId: string; box: [number, number, number, number]; photo?: PhotoView | null; label: string }) {
  const src = photo && photo.image_id === imageId ? (photo.url.startsWith("http") ? photo.url : api.uploadUrl(imageId)) : api.uploadUrl(imageId);
  if (!photo || photo.image_id !== imageId || !photo.w || !photo.h) {
    return <img src={src} alt={`Your photo, where “${label}” was seen`} className="max-h-40 rounded-sm border border-border object-contain" />;
  }
  const [x1, y1, x2, y2] = box;
  const w = Math.max(1, x2 - x1);
  const h = Math.max(1, y2 - y1);
  const scale = Math.min(200 / w, 140 / h);
  return (
    <div
      role="img"
      aria-label={`Crop of your photo showing “${label}”`}
      className="rounded-sm border border-border bg-muted"
      style={{
        width: w * scale,
        height: h * scale,
        backgroundImage: `url(${src})`,
        backgroundSize: `${photo.w * scale}px ${photo.h * scale}px`,
        backgroundPosition: `${-x1 * scale}px ${-y1 * scale}px`,
        backgroundRepeat: "no-repeat",
      }}
    />
  );
}

/** Renders any of the five provenance types. Used by the chip's popover and by the Sources tab. */
export function ProvenanceDetail({ provenance: p, photo, actions }: { provenance: Provenance; photo?: PhotoView | null; actions?: ReactNode }) {
  const Icon = PROVENANCE_ICON[p.type] ?? CircleHelp;
  // The run's own source, when it was the mock connector's bundled copy: never call that a read "through Airbyte".
  const bundled = useAppStore((s) => p.type === "readme_quote" && Boolean(s.run?.source?.simulated) && s.run?.source?.sha256 === p.doc_sha256);
  return (
    <div className="space-y-2.5">
      <p className={cn("flex items-center gap-1.5 text-small font-semibold", isOpenAssumption(p) ? "text-warn" : "text-foreground")}>
        <Icon className="size-4" strokeWidth={1.75} aria-hidden />
        {provenanceLabel(p)}
        {p.check === "fail" ? <span className="font-medium text-fail">· check failed</span> : null}
      </p>

      {p.type === "readme_quote" ? (
        <>
          <QuoteBlock quote={p.quote} lineFrom={p.line_from} lineTo={p.line_to} />
          {p.more_quotes.map((q) => (
            <QuoteBlock key={`${q.line_from}-${q.quote}`} quote={q.quote} lineFrom={q.line_from} lineTo={q.line_to} />
          ))}
          <Meta>
            <Ext href={p.url}>{repoOf(p.url)}</Ext>
            <span className="font-mono">{p.path}</span>
            <span>
              commit <span className="font-mono">{p.commit_sha.slice(0, 7)}</span>
            </span>
            <span>{bundled ? "bundled copy (mock connector)" : p.via === "http" ? "read from GitHub directly (no token)" : `read through ${sourceName(p.via)}`}</span>
          </Meta>
          <Meta>
            The quote is checked against the fetched file. <HashText hash={p.doc_sha256} label="file" />
          </Meta>
        </>
      ) : null}

      {p.type === "reference_project" ? (
        <>
          <QuoteBlock quote={p.quote} />
          <Meta>
            <Ext href={p.url}>{p.title || hostOf(p.url)}</Ext>
            <span>{p.licence ? `licence ${p.licence}` : "licence not stated"}</span>
          </Meta>
          <Meta>
            <span>found through {sourceName(p.found_via)}</span>
            <span>
              fetched {timeOf(p.fetched_at)} by {sourceName(p.fetched_via)}
            </span>
            <HashText hash={p.doc_sha256} label="page" />
          </Meta>
        </>
      ) : null}

      {p.type === "template_row" ? (
        <>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-sm border border-border bg-muted px-3 py-2 text-small">
            <dt className="text-muted-foreground">Template</dt>
            <dd className="font-mono">{p.template_id}</dd>
            <dt className="text-muted-foreground">Row</dt>
            <dd className="font-mono">{p.row_id}</dd>
            {p.variant ? (
              <>
                <dt className="text-muted-foreground">Variant</dt>
                <dd className="font-mono">{p.variant}</dd>
              </>
            ) : null}
            <dt className="text-muted-foreground">Basis</dt>
            <dd>{p.basis === "rule_of_thumb" ? "Rule of thumb: a typical value, not a quote from a document" : "Taken from the reference build"}</dd>
          </dl>
          {p.derived_from ? (
            <Meta>
              <span>Reference</span>
              {/^https?:/.test(p.derived_from) ? <Ext href={p.derived_from}>{hostOf(p.derived_from)}</Ext> : <span>{p.derived_from}</span>}
            </Meta>
          ) : null}
          <Meta>
            <span className="font-mono">{p.kb_ref}</span>
            <HashText hash={p.template_sha256} label="template" />
          </Meta>
        </>
      ) : null}

      {p.type === "photo_region" ? (
        <>
          <PhotoCrop imageId={p.image_id} box={p.box_xyxy_px} photo={photo} label={p.label} />
          <Meta>
            <span>
              Seen as “{p.label}”
            </span>
            <span>{DETECTOR_LABEL[p.detector] ?? p.detector}</span>
            <span className="tabular">score {p.score.toFixed(2)}</span>
          </Meta>
          <Meta>
            <HashText hash={p.image_sha256} label="photo" />
          </Meta>
        </>
      ) : null}

      {p.type === "assumption" ? (
        <>
          <p className={cn("rounded-sm border px-3 py-2 text-small", p.confirmed_by_user ? "border-border bg-muted" : "border-warn/40 bg-warn-tint")}>{p.statement}</p>
          <Meta>
            <span>Why we assumed it: {p.basis}</span>
          </Meta>
          <Meta>
            <span>{p.confirmed_by_user ? `Confirmed by you${p.confirmed_at ? ` at ${timeOf(p.confirmed_at)}` : ""}` : "Not confirmed yet. Approval is blocked until you confirm, edit or remove it."}</span>
          </Meta>
        </>
      ) : null}

      {actions}

      {p.supports.length ? (
        <div className="space-y-2 border-t border-border pt-2">
          <p className="text-caption font-medium text-muted-foreground">Also supported by</p>
          {p.supports.map((s, i) => (
            <ProvenanceDetail key={i} provenance={s} photo={photo} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
