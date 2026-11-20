// Off-model tray (PLAN §11.6 core 4): parts and tools with no mesh sit as chips under the stage with the
// same colours, hover and click. It is also the "tools you'll need" list; owned ones are struck through.
import { Wrench } from "lucide-react";

import { money } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import { paintFor, type StageData } from "@/lib/stage";
import { cn } from "@/lib/utils";

export function OffModelTray({ lineIds, data, title = "Not on the model" }: { lineIds: string[]; data: StageData; title?: string }) {
  const mode = useAppStore((s) => s.colourMode);
  const hoveredLineId = useAppStore((s) => s.hoveredLineId);
  const selectedLineId = useAppStore((s) => s.selectedLineId);
  const hover = useAppStore((s) => s.hover);
  const select = useAppStore((s) => s.select);
  const lines = lineIds.map((id) => data.lines.get(id)).filter((l) => l !== undefined);
  if (!lines.length) return null;
  return (
    <div className="pointer-events-auto border-t border-stage-border/70 bg-stage/80 px-4 py-2.5 backdrop-blur-sm">
      <p className="mb-1.5 text-caption font-medium text-stage-muted">{title}</p>
      <ul className="flex flex-wrap gap-1.5">
        {lines.map((line) => {
          const paint = paintFor(line, mode, data);
          const owned = line.status === "owned";
          const gone = owned || line.status === "skipped" || line.status === "removed";
          const active = selectedLineId === line.id;
          return (
            <li key={line.id}>
              <button
                type="button"
                onClick={() => select(line.id)}
                onMouseEnter={() => hover(line.id)}
                onMouseLeave={() => hover(null)}
                onFocus={() => hover(line.id)}
                onBlur={() => hover(null)}
                aria-pressed={active}
                className={cn(
                  "inline-flex h-7 items-center gap-1.5 rounded-full border bg-stage-surface px-2.5 text-caption transition-colors duration-150",
                  active ? "border-brand text-stage-text ring-2 ring-brand/40" : hoveredLineId === line.id ? "border-brand text-stage-text" : "border-stage-border text-stage-text/90",
                )}
              >
                {line.lineKind === "tool" ? (
                  <Wrench className="size-3 text-stage-muted" strokeWidth={1.75} aria-label="Tool" />
                ) : (
                  <span aria-hidden className="size-2 rounded-full" style={{ background: `var(${paint.token ?? "--b2c-stage-muted"})`, opacity: paint.ghost ? 0.5 : 1 }} />
                )}
                <span className={cn(gone && "line-through decoration-stage-muted")}>
                  {line.name}
                  {line.qty > 1 ? ` ×${line.qty}` : ""}
                </span>
                <span className="text-stage-muted">
                  · {owned ? "you own it" : line.openAssumption ? "assumed" : line.storeName ? `${line.storeName} · ${money(line.price)}` : line.status === "skipped" ? "left out" : line.status === "not_found" ? "not found" : "no offer yet"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
