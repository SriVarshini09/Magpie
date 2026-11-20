// Parts list (PLAN §11.5 B): the source chip on top, then one row per BOM line with its quantity, name,
// provenance chip, status badge, chosen store, action-level badge and price. Two-way highlight with the
// part map; arrow keys move through the rows, Enter opens the part panel.
import { motion } from "motion/react";
import { useEffect, useRef, type KeyboardEvent } from "react";
import { Link } from "react-router";

import { Money } from "@/components/common/Money";
import { SourceChip } from "@/components/common/SourceChip";
import { InlineError } from "@/components/common/States";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ActionBadge } from "@/components/panel/ActionBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAppStore } from "@/lib/store";
import type { BOMLine, RunState } from "@/lib/types";
import { cn } from "@/lib/utils";

import { isOpenAssumption, ProvenanceChip } from "./ProvenanceChip";

export function PartsListSkeleton({ rows = 7 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading the parts list">
      <div className="space-y-2 border-b border-border px-4 py-3">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-4 w-56" />
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex h-[68px] items-center gap-3 border-b border-border px-4">
          <Skeleton className="h-4 w-6" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>
      ))}
    </div>
  );
}

function Row({ line, index, photo }: { line: BOMLine; index: number; photo: RunState["view"]["photo"] }) {
  const selected = useAppStore((s) => s.selectedLineId === line.bom_line_id);
  const hovered = useAppStore((s) => s.hoveredLineId === line.bom_line_id);
  const select = useAppStore((s) => s.select);
  const hover = useAppStore((s) => s.hover);
  const ref = useRef<HTMLDivElement>(null);

  // Hover a mesh → its row highlights and scrolls into view.
  useEffect(() => {
    if (hovered || selected) ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [hovered, selected]);

  const chosen = line.chosen ?? [];
  const first = chosen[0];
  const total = chosen.reduce((sum, c) => sum + c.price * c.packs, 0);
  const owned = line.status === "owned";
  const gone = owned || line.status === "removed";
  const assumed = isOpenAssumption(line.provenance);
  const others = (line.stores_count ?? 0) - (first ? 1 : 0);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      select(line.bom_line_id);
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const li = e.currentTarget.parentElement;
      const next = (e.key === "ArrowDown" ? li?.nextElementSibling : li?.previousElementSibling)?.querySelector<HTMLElement>("[data-row]");
      next?.focus();
    }
  };

  return (
    <motion.li initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, delay: Math.min(index, 12) * 0.04, ease: [0.16, 1, 0.3, 1] }}>
      <div
        ref={ref}
        data-row
        role="button"
        tabIndex={0}
        aria-pressed={selected}
        aria-label={`${line.qty} × ${line.raw_name}. Open the part panel.`}
        onClick={() => select(line.bom_line_id)}
        onKeyDown={onKeyDown}
        onMouseEnter={() => hover(line.bom_line_id)}
        onMouseLeave={() => hover(null)}
        onFocus={(e) => e.target === e.currentTarget && hover(line.bom_line_id)}
        onBlur={() => hover(null)}
        className={cn(
          "relative flex min-h-[68px] cursor-pointer gap-3 border-b border-border px-4 py-2.5 transition-colors duration-150 -outline-offset-2",
          selected ? "bg-brand-tint" : hovered ? "bg-muted" : assumed ? "bg-warn-tint/60" : "bg-surface",
        )}
      >
        {selected ? <span aria-hidden className="absolute inset-y-0 left-0 w-0.5 bg-brand" /> : null}
        <span className="tabular w-7 shrink-0 pt-0.5 text-right font-mono text-small text-muted-foreground">{line.qty}×</span>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-start justify-between gap-2">
            <p className={cn("text-body leading-5 font-medium", gone && "text-muted-foreground line-through decoration-muted-foreground")}>{line.raw_name}</p>
            <StatusBadge status={line.status} label={line.status === "skipped" && line.category === "printed" ? "Print at home" : assumed ? "Assumed" : undefined} className={assumed ? "border-warn/40 bg-warn-tint text-warn" : undefined} />
          </div>
          {first ? (
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-secondary-text">
              <span className="truncate">{first.store_name}</span>
              <Money value={total} seenAt={first.seen_at} source={first.source_api} simulated={first.simulated} className="font-medium text-foreground" />
              {others > 0 ? <span className="text-caption text-muted-foreground">+{others} {others === 1 ? "store" : "stores"}</span> : null}
            </p>
          ) : (
            <p className="text-small text-secondary-text">
              {line.owned_note ? (owned ? `Remembered: ${line.owned_note}` : line.owned_note) : line.status === "not_found" ? "Not found in your stores" : line.status === "skipped" ? "Left out of the cart" : "Looking across your stores…"}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-1.5">
            <ProvenanceChip provenance={line.provenance} photo={photo} />
            {first ? <ActionBadge level={first.action_level} /> : null}
            {line.line_kind !== "part" ? <span className="text-caption text-muted-foreground">{line.line_kind === "tool" ? "tool" : "optional"}</span> : null}
          </div>
        </div>
      </div>
    </motion.li>
  );
}

/** Why the run stopped: the last error event's own words (the backend says what failed and what to change). */
function RunStopped({ run }: { run: RunState }) {
  const events = useAppStore((s) => s.events);
  const last = [...events].reverse().find((e) => e.type === "error" || e.severity === "error");
  const message = last?.detail || last?.title || "The run stopped before it found any parts.";
  return (
    <li className="space-y-3 px-4 py-6">
      <InlineError title={run.bom.length ? "This run stopped early" : "This run stopped before it found any parts"} message={message} />
      {!run.bom.length ? (
        <Button asChild variant="outline" size="sm">
          <Link to="/">Start a new build</Link>
        </Button>
      ) : null}
    </li>
  );
}

export function PartsList({ run }: { run: RunState }) {
  const failed = run.status === "error";
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SourceChip run={run} />
      <ul className="min-h-0 flex-1 overflow-y-auto" aria-label="Parts list">
        {failed ? <RunStopped run={run} /> : null}
        {run.bom.map((line, i) => (
          <Row key={line.bom_line_id} line={line} index={i} photo={run.view.photo} />
        ))}
        {!run.bom.length && !failed ? <li className="px-4 py-8 text-center text-small text-muted-foreground">Reading the source. Parts appear here as they are found.</li> : null}
      </ul>
    </div>
  );
}
