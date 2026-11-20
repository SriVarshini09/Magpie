// Refusal card (PLAN §11.5 B): full width, red tint, the mandate clause quoted. It shakes 4 px once when it
// appears. Refusals are never toasts; they stay on screen.
import { ShieldX } from "lucide-react";

import { HashText } from "@/components/common/HashText";
import { timeOfSec } from "@/lib/format";
import type { Event, RefusalRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

const TRIGGER: Record<string, string> = {
  source_document: "asked for by the source document",
  user_chat: "asked for in chat",
  store_listing: "asked for by a store listing, treated as data",
  agent: "attempted by the agent",
  user_edit: "from a cart edit",
};

export function RefusalCard({ event, fresh = false, onSelect }: { event: Event; fresh?: boolean; onSelect?: (lineId: string) => void }) {
  const data = event.data ?? {};
  const refusal = (data.refusal as RefusalRecord | undefined) ?? undefined;
  const clause = refusal?.clause ?? (event.detail ? event.detail.split(" · ")[0] : null);
  const rest = event.detail ? event.detail.split(" · ").slice(1).join(" · ") : "";
  const trigger = refusal?.triggered_by ?? (data.triggered_by as string | undefined);
  return (
    <article className={cn("rounded-lg border border-fail/30 bg-fail-tint p-3", fresh && "shake-once")}>
      <p className="flex items-start gap-2 text-small font-semibold text-fail">
        <ShieldX className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} aria-hidden />
        <span className="flex-1">{event.title}</span>
        <time className="tabular shrink-0 font-mono text-caption font-normal text-fail/80">{timeOfSec(event.ts)}</time>
      </p>
      {clause ? (
        <p className="mt-1.5 ml-6 text-caption text-secondary-text">
          Mandate clause <code className="rounded-sm bg-surface px-1 py-0.5 font-mono text-foreground">{clause}</code>
        </p>
      ) : null}
      {rest || trigger ? <p className="mt-1 ml-6 text-caption text-secondary-text">{[rest, trigger ? (TRIGGER[trigger] ?? trigger) : null].filter(Boolean).join(" · ")}</p> : null}
      <p className="mt-1 ml-6 flex items-center gap-3">
        {event.bom_line_id && onSelect ? (
          <button type="button" className="text-caption font-medium text-brand hover:text-brand-hover" onClick={() => onSelect(event.bom_line_id!)}>
            Show the part
          </button>
        ) : null}
        {event.record_hash ? <HashText hash={event.record_hash} label="rec" /> : null}
      </p>
    </article>
  );
}
