// Photo hotspots (PLAN §3.20, P15). Owner: D, with C's components and selection store.
// The user's own photo with one clickable box per part, in percent coordinates so it scales with the image.
// Solid boxes: detected by Superlinked SIE (Grounding DINO). Dashed boxes: Claude's approximate region.
// A region under 0.35, or one that matches no BOM line, is never drawn. Lines with no box sit in the tray.
// Box colours come from C's `paintFor` (lib/stage.ts), so the photo agrees with every other view and colour mode.
import { Camera, ImageOff, ScanSearch } from "lucide-react";
import { useMemo, useState, type CSSProperties } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/format";
import { buildStageData, paintFor, type StageData, type StageLine } from "@/lib/stage";
import { useAppStore } from "@/lib/store";
import type { BOMLine, PhotoRegion, PhotoView, ViewData } from "@/lib/types";
import { cn } from "@/lib/utils";

export const MIN_REGION_SCORE = 0.35;

type Hotspot = { region: PhotoRegion; line: BOMLine | null; lineId: string; index: number };

function photoSrc(photo: PhotoView): string {
  return /^https?:/.test(photo.url) ? photo.url : api.uploadUrl(photo.image_id);
}

function pct(v: number, of: number): string {
  return `${Math.min(100, Math.max(0, (v / of) * 100))}%`;
}

/** The box colour token: C's paint for the current colour mode; a chosen part with no paint reads as pass. */
function boxToken(stageLine: StageLine | undefined, paintToken: string | null): string {
  if (paintToken) return paintToken;
  if (stageLine?.status === "chosen") return "--b2c-pass";
  return "--b2c-stage-text";
}

export function PhotoHotspots({
  view,
  photo: photoProp,
  lines: linesProp,
  data: dataProp,
  className,
}: {
  view?: ViewData | null;
  /** Pass the photo directly when there is no ViewData (defaults to `view.photo`). */
  photo?: PhotoView | null;
  /** BOM lines to bind boxes to (defaults to the run in the store). */
  lines?: BOMLine[] | null;
  /** C's stage data (lib/stage.ts); built from the run in the store when not given. */
  data?: StageData | null;
  className?: string;
}) {
  const photo = photoProp ?? view?.photo ?? null;
  const run = useAppStore((s) => s.run);
  const lines = linesProp ?? run?.bom ?? null;
  const colourMode = useAppStore((s) => s.colourMode);
  const selectedLineId = useAppStore((s) => s.selectedLineId);
  const hoveredLineId = useAppStore((s) => s.hoveredLineId);
  const select = useAppStore((s) => s.select);
  const hover = useAppStore((s) => s.hover);
  const [img, setImg] = useState<"loading" | "ready" | "error">("loading");

  const data = useMemo(() => dataProp ?? (run ? buildStageData(run) : null), [dataProp, run]);
  const byId = useMemo(() => new Map((lines ?? []).map((l) => [l.bom_line_id, l])), [lines]);

  const hotspots: Hotspot[] = useMemo(() => {
    if (!photo) return [];
    const out: Hotspot[] = [];
    photo.regions.forEach((region, index) => {
      if (region.score < MIN_REGION_SCORE || !region.bom_line_id) return;
      const [x1, y1, x2, y2] = region.box_xyxy_px;
      if (!(x2 > x1 && y2 > y1)) return;
      const line = byId.get(region.bom_line_id) ?? null;
      // With the BOM known, a region that matches no line is dropped (PLAN §3.20).
      if (lines && !line) return;
      out.push({ region, line, lineId: region.bom_line_id, index });
    });
    return out;
  }, [photo, byId, lines]);

  const boxed = useMemo(() => new Set(hotspots.map((h) => h.lineId)), [hotspots]);
  const trayIds = lines ? lines.filter((l) => !boxed.has(l.bom_line_id)).map((l) => l.bom_line_id) : (view?.tray ?? []).filter((id) => !boxed.has(id));

  if (!photo) return null;

  const hasSie = hotspots.some((h) => !h.region.approximate);
  const hasApprox = hotspots.some((h) => h.region.approximate);

  return (
    <section aria-label="Your photo with the parts found in it" className={cn("space-y-2", className)}>
      <div className="stage overflow-hidden rounded-2xl p-3">
        <div className="relative mx-auto w-full" style={{ aspectRatio: `${photo.w} / ${photo.h}`, maxWidth: photo.w }}>
          {img === "loading" ? <Skeleton className="absolute inset-0 rounded-lg bg-stage-surface" /> : null}
          {img === "error" ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-lg border border-stage-border px-6 text-center text-small text-stage-muted">
              <ImageOff className="size-5" strokeWidth={1.75} aria-hidden />
              Couldn't load your photo. The parts list still works; pick a part there or in the tray below.
            </div>
          ) : null}
          <img
            src={photoSrc(photo)}
            alt="Your photo"
            width={photo.w}
            height={photo.h}
            onLoad={() => setImg("ready")}
            onError={() => setImg("error")}
            className={cn("absolute inset-0 size-full rounded-lg object-contain transition-opacity duration-200", img === "ready" ? "opacity-100" : "opacity-0")}
          />
          {img !== "error"
            ? hotspots.map(({ region, line, lineId, index }) => {
                const [x1, y1, x2, y2] = region.box_xyxy_px;
                const stageLine = data?.lines.get(lineId);
                const paint = data ? paintFor(stageLine, colourMode, data) : { token: null, ghost: false };
                const colour = `var(${boxToken(stageLine, paint.token)})`;
                const selected = selectedLineId === lineId;
                const hovered = hoveredLineId === lineId;
                const name = line?.raw_name ?? region.label;
                const tagBelow = y1 / photo.h < 0.08;
                const boxStyle: CSSProperties = {
                  left: pct(x1, photo.w),
                  top: pct(y1, photo.h),
                  width: pct(x2 - x1, photo.w),
                  height: pct(y2 - y1, photo.h),
                  borderColor: selected ? "var(--b2c-brand)" : colour,
                };
                return (
                  <button
                    key={`${lineId}-${index}`}
                    type="button"
                    onClick={() => select(lineId)}
                    onMouseEnter={() => hover(lineId)}
                    onMouseLeave={() => hover(null)}
                    onFocus={() => hover(lineId)}
                    onBlur={() => hover(null)}
                    aria-pressed={selected}
                    aria-label={`${name}: seen as “${region.label}”, score ${region.score.toFixed(2)}${region.approximate ? ", approximate region" : ", detected by SIE"}${line ? `, ${STATUS_LABEL[line.status] ?? line.status}` : ""}. Open the part panel.`}
                    className={cn(
                      "absolute rounded-sm border-2 transition-[box-shadow,background-color,opacity] duration-150 focus-visible:outline-offset-0",
                      region.approximate && "border-dashed",
                      paint.ghost && !selected && !hovered && "opacity-50",
                      selected ? "bg-brand/15 shadow-e2 ring-2 ring-brand" : hovered ? "bg-stage-text/10 ring-2 ring-stage-text/60" : "hover:bg-stage-text/10",
                    )}
                    style={boxStyle}
                  >
                    <span
                      className={cn(
                        "pointer-events-none absolute left-[-2px] inline-flex max-w-[16rem] items-center gap-1 rounded-sm bg-stage-surface px-1.5 py-0.5 text-caption font-medium whitespace-nowrap text-stage-text shadow-e1",
                        tagBelow ? "top-full mt-1" : "bottom-full mb-1",
                        selected && "bg-brand text-white",
                      )}
                    >
                      <span aria-hidden className="inline-block size-2 shrink-0 rounded-full" style={{ backgroundColor: selected ? "currentColor" : colour }} />
                      <span className="truncate">{name}</span>
                      <span className="tabular opacity-80">{region.score.toFixed(2)}</span>
                    </span>
                  </button>
                );
              })
            : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Camera className="size-3.5" strokeWidth={1.75} aria-hidden />
          Your photo · {hotspots.length} {hotspots.length === 1 ? "part" : "parts"} marked
        </span>
        {hasSie ? (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="inline-block size-3 rounded-sm border-2 border-secondary-text" />
            detected by SIE (Grounding DINO)
          </span>
        ) : null}
        {hasApprox ? (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="inline-block size-3 rounded-sm border-2 border-dashed border-secondary-text" />
            approximate region (Claude)
          </span>
        ) : null}
        <span>Boxes show where a part is, not its exact spec.</span>
      </div>

      {trayIds.length ? (
        <div className="space-y-1.5">
          <p className="flex items-center gap-1.5 text-caption font-medium text-muted-foreground">
            <ScanSearch className="size-3.5" strokeWidth={1.75} aria-hidden />
            Not marked in the photo
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {trayIds.map((id) => {
              const line = byId.get(id) ?? null;
              const selected = selectedLineId === id;
              const struck = line && (line.status === "owned" || line.status === "removed" || line.status === "skipped");
              return (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => select(id)}
                    onMouseEnter={() => hover(id)}
                    onMouseLeave={() => hover(null)}
                    onFocus={() => hover(id)}
                    onBlur={() => hover(null)}
                    aria-pressed={selected}
                    title={line?.owned_note ?? undefined}
                    className={cn(
                      "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-caption font-medium transition-colors duration-150",
                      selected ? "border-brand bg-brand-tint text-brand" : "border-border bg-surface text-secondary-text hover:border-border-strong hover:text-foreground",
                    )}
                  >
                    <span className={cn(struck && "line-through")}>{line ? `${line.qty}× ${line.raw_name}` : id}</span>
                    {line ? <span className="text-muted-foreground">· {STATUS_LABEL[line.status] ?? line.status}</span> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
