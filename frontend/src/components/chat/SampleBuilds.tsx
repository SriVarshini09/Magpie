// "Sample builds" on the start page: three blueprint cards (camera drone, SO-101 arm, e-paper weather display).
// A card starts its sample exactly as typing it would: the example text, or the project's link. The drawings are
// illustrative and labelled so; their numbers are measured from our own models (see StartArt).
import { Keyboard, Link2 } from "lucide-react";
import type { ComponentType } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { repoOf } from "@/lib/format";
import type { ProjectSample } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ArmDrawing, Crosshair, DroneDrawing, EpaperDrawing } from "./StartArt";

const ART: Record<string, { name: string; drawing: ComponentType<{ className?: string }>; note: string }> = {
  quadcopter: { name: "Camera drone", drawing: DroneDrawing, note: "Illustrative · 5-inch" },
  robot_arm: { name: "SO-101 robot arm", drawing: ArmDrawing, note: "Illustrative" },
  electronics_mcu: { name: "E-paper weather display", drawing: EpaperDrawing, note: "Illustrative sketch" },
};

/** Small corner ticks, like the registration marks on a drawing sheet. */
function Corners() {
  const t = "pointer-events-none absolute size-3.5 border-blueprint-line/35";
  return (
    <span aria-hidden>
      <span className={cn(t, "top-2 right-2 border-t border-r")} />
      <span className={cn(t, "bottom-2 left-2 border-b border-l")} />
    </span>
  );
}

export function SampleBuilds({ cards, busy, onStart }: { cards: ProjectSample[] | null; busy: boolean; onStart: (s: ProjectSample) => void }) {
  return (
    <section aria-labelledby="sample-builds" className="mt-6">
      <div className="flex items-center gap-5">
        <h2 id="sample-builds" className="shrink-0 font-serif text-[clamp(32px,2.8vw,42px)] leading-none tracking-[-0.02em] text-ink">
          Sample builds
        </h2>
        <span className="h-px flex-1 bg-blueprint-edge" aria-hidden />
        <Crosshair className="-mr-1 shrink-0" />
      </div>
      <ul className="mt-5 grid grid-cols-3 gap-4" aria-label="Sample builds">
        {cards === null
          ? [0, 1, 2].map((i) => (
              <li key={i}>
                <Skeleton className="h-[clamp(232px,30vh,272px)] w-full rounded-[4px]" />
              </li>
            ))
          : cards.map((s) => {
              const art = ART[s.build_type];
              const name = art?.name ?? s.title.replace(/\s*\(link\)\s*$/i, "");
              const Drawing = art?.drawing;
              const request = s.source_url ?? s.example_text ?? s.title;
              return (
                <li key={s.title}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onStart(s)}
                    title={`Start this sample: ${request}`}
                    className="group relative flex h-[clamp(232px,30vh,272px)] w-full flex-col overflow-hidden rounded-[4px] border border-blueprint-edge text-left blueprint-grid-fine transition-[border-color,box-shadow] duration-150 hover:border-blueprint hover:shadow-[0_10px_28px_-16px_rgb(29_78_216/0.45)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60"
                  >
                    <Corners />
                    <span className="px-4 pt-3 font-serif text-[clamp(22px,1.9vw,27px)] leading-[1.15] tracking-[-0.01em] text-ink">{name}</span>
                    {Drawing ? (
                      <span className="relative min-h-0 flex-1 px-3 pt-1">
                        <Drawing className="size-full" />
                      </span>
                    ) : (
                      <span className="flex-1 px-4 pt-2 text-small text-secondary-text">{s.blurb}</span>
                    )}
                    <span className="flex shrink-0 items-center gap-2 px-4 pt-1 pb-2.5 text-caption text-muted-foreground">
                      {s.source_url ? <Link2 className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden /> : <Keyboard className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />}
                      <span className="min-w-0 truncate">{s.source_url ? repoOf(s.source_url) : "Typed request"}</span>
                      <span className="ml-auto shrink-0 font-mono text-[10.5px] tracking-wide text-blueprint-line/70">{art?.note ?? "Illustrative"}</span>
                    </span>
                  </button>
                </li>
              );
            })}
      </ul>
    </section>
  );
}
