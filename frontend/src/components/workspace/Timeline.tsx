// Timeline (PLAN §11.5 B): the run as it happens, over SSE. Icon by severity, title, time, the system behind
// the event ("via Airbyte"), expandable detail and the record hash. Refusals are full-width red cards.
import { ChevronRight, CircleAlert, CircleCheck, CircleDot, Radio, TriangleAlert } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { HashText } from "@/components/common/HashText";
import { ProviderTag } from "@/components/common/ProviderTag";
import { EmptyState } from "@/components/common/States";
import { Skeleton } from "@/components/ui/skeleton";
import { timeOfSec } from "@/lib/format";
import { useAppStore, type StreamState } from "@/lib/store";
import type { Event, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

import { RefusalCard } from "./RefusalCard";

const ICON: Record<Severity, { icon: typeof CircleDot; className: string }> = {
  info: { icon: CircleDot, className: "text-muted-foreground" },
  ok: { icon: CircleCheck, className: "text-pass" },
  warn: { icon: TriangleAlert, className: "text-warn" },
  refusal: { icon: CircleAlert, className: "text-fail" },
  error: { icon: CircleAlert, className: "text-fail" },
};

function Item({ event, onSelect }: { event: Event; onSelect: (lineId: string) => void }) {
  const [open, setOpen] = useState(false);
  const meta = ICON[event.severity] ?? ICON.info;
  const Icon = meta.icon;
  const hasDetail = Boolean(event.detail);
  return (
    <div className="flex gap-2.5 px-4 py-2">
      <Icon className={cn("mt-0.5 size-4 shrink-0", meta.className)} strokeWidth={1.75} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2">
          {hasDetail ? (
            <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="group/tl flex min-w-0 flex-1 items-start gap-1 text-left text-small leading-[18px] text-foreground">
              <span className="min-w-0 flex-1">{event.title}</span>
              <ChevronRight className={cn("mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform duration-150", open && "rotate-90")} strokeWidth={1.75} aria-hidden />
            </button>
          ) : (
            <p className="min-w-0 flex-1 text-small leading-[18px] text-foreground">{event.title}</p>
          )}
          <time className="tabular shrink-0 font-mono text-caption text-muted-foreground">{timeOfSec(event.ts)}</time>
        </div>
        {open && event.detail ? <p className="mt-1 text-caption text-secondary-text">{event.detail}</p> : null}
        {event.provider || event.record_hash || event.bom_line_id ? (
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <ProviderTag provider={event.provider} simulated={event.simulated} />
            {event.bom_line_id ? (
              <button type="button" onClick={() => onSelect(event.bom_line_id!)} className="font-mono text-caption text-brand hover:text-brand-hover" aria-label={`Show part ${event.bom_line_id}`}>
                {event.bom_line_id}
              </button>
            ) : null}
            {event.record_hash ? <HashText hash={event.record_hash} label="rec" /> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

const STREAM_LABEL: Record<StreamState, string> = { idle: "Not connected", connecting: "Connecting…", open: "Live", closed: "Stream ended", error: "Reconnecting…" };

export function Timeline({ className }: { className?: string }) {
  const events = useAppStore((s) => s.events);
  const stream = useAppStore((s) => s.stream);
  const select = useAppStore((s) => s.select);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const mountedAt = useRef(Date.now());

  // Follow the newest event unless the reader has scrolled up.
  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  return (
    <section aria-label="Timeline" className={cn("flex min-h-0 flex-col", className)}>
      <header className="flex h-11 shrink-0 items-center justify-between border-b border-border px-4">
        <h2 className="text-small font-semibold">Timeline</h2>
        <span className={cn("inline-flex items-center gap-1.5 text-caption", stream === "open" ? "text-pass" : stream === "error" ? "text-warn" : "text-muted-foreground")}>
          <Radio className="size-3.5" strokeWidth={1.75} aria-hidden />
          {STREAM_LABEL[stream]}
        </span>
      </header>
      <div
        ref={scroller}
        aria-live="polite"
        aria-relevant="additions"
        className="min-h-0 flex-1 overflow-y-auto py-1"
        onScroll={(e) => {
          const el = e.currentTarget;
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
        }}
      >
        {!events.length && (stream === "connecting" || stream === "idle") ? (
          <div className="space-y-3 px-4 py-3" aria-busy="true">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="flex gap-2.5">
                <Skeleton className="size-4 rounded-full" />
                <Skeleton className="h-4 flex-1" />
              </div>
            ))}
          </div>
        ) : null}
        {!events.length && stream !== "connecting" && stream !== "idle" ? (
          <EmptyState title={stream === "error" ? "The event stream dropped." : "No events yet."}>{stream === "error" ? "The parts list still shows the last known state. Reconnecting on its own." : "Steps appear here as the agent works."}</EmptyState>
        ) : null}
        {events.map((event) => {
          const fresh = Date.now() - mountedAt.current > 1500;
          return (
            <motion.div key={event.seq} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}>
              {event.severity === "refusal" ? (
                <div className="px-3 py-1.5">
                  <RefusalCard event={event} fresh={fresh} onSelect={(id) => select(id)} />
                </div>
              ) : (
                <Item event={event} onSelect={(id) => select(id)} />
              )}
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
