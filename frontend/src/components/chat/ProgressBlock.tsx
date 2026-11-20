// Live progress of a run inside the chat, read from the run's own SSE stream (GET /api/runs/{id}/events).
// It shows what the agent is doing as it happens: reading, extracting, offers found, refusals. The card keeps a
// fixed height while it fills, so the conversation below it does not jump.
import { Check, CircleAlert, Loader2, ShieldX } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { SimulatedTag, useSimulatedRunLabel } from "@/components/MockDataBadge";
import { api } from "@/lib/api";
import { plural, timeOfSec } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { Event } from "@/lib/types";
import { cn } from "@/lib/utils";

const STOP = new Set(["run.waiting_approval", "run.done", "error"]);
const SHOWN = 6;

type Phase = "connecting" | "running" | "stopped" | "failed" | "lost";

export function ProgressBlock({ runId, text, onStopped }: { runId: string; text?: string | null; onStopped?: () => void }) {
  const [events, setEvents] = useState<Event[]>([]);
  const [phase, setPhase] = useState<Phase>("connecting");
  const [all, setAll] = useState(false);
  const stopped = useRef(onStopped);
  useEffect(() => {
    stopped.current = onStopped;
  }, [onStopped]);

  useEffect(() => {
    setEvents([]);
    setPhase("connecting");
    let source: EventSource | null = null;
    let done = false;
    let opened = false;
    let lastSeq = 0;
    let retries = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const finish = (next: Phase) => {
      if (done) return;
      done = true;
      source?.close();
      setPhase(next);
      if (next !== "lost") stopped.current?.();
    };
    const connect = () => {
      const es = new EventSource(lastSeq ? `${api.eventsOnceUrl(runId)}&after=${lastSeq}` : api.eventsOnceUrl(runId));
      source = es;
      es.onopen = () => {
        opened = true;
        setPhase((p) => (p === "connecting" ? "running" : p));
      };
      es.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data) as Event;
          opened = true;
          lastSeq = Math.max(lastSeq, event.seq);
          if (event.simulated) useAppStore.getState().setMockSeen(true);
          setEvents((cur) => (cur.some((e) => e.seq === event.seq) ? cur : [...cur, event]));
          if (STOP.has(event.type)) finish(event.type === "error" ? "failed" : "stopped");
        } catch {
          // A malformed frame is dropped; the stream stays up.
        }
      };
      // The server ends the stream once the run stops; EventSource reports that as an error. If it ended before the
      // run's last event (a dropped connection), pick up after the last step seen instead of calling the run finished.
      es.onerror = () => {
        es.close();
        if (done) return;
        if (opened && retries < 5) {
          retries += 1;
          retryTimer = setTimeout(connect, 300 * retries);
          return;
        }
        finish(opened ? "stopped" : "lost");
      };
    };
    connect();
    return () => {
      done = true;
      clearTimeout(retryTimer);
      source?.close();
    };
  }, [runId]);

  const simLabel = useSimulatedRunLabel().short;
  const count = (type: string) => events.filter((e) => e.type === type).length;
  const lines = count("bom.line");
  const offers = events.filter((e) => e.type === "offers.found").reduce((n, e) => n + (typeof e.data?.offers === "number" ? e.data.offers : 0), 0);
  const searched = count("offers.found");
  const refusals = count("refusal");
  // one offer.rejected event groups the listings rejected for the same reason; data.count says how many
  const rejected = events.filter((e) => e.type === "offer.rejected").reduce((n, e) => n + (typeof e.data?.count === "number" ? e.data.count : 1), 0);
  const simulated = events.some((e) => e.simulated);
  const empty = phase === "stopped" && !events.length;
  const list = all ? events : events.slice(-SHOWN);
  const running = phase === "connecting" || phase === "running";

  return (
    <section className="rounded-lg border border-border bg-surface" aria-label="Run progress" aria-busy={running}>
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-2">
        <span className="inline-flex items-center gap-1.5 text-small font-semibold">
          {running ? <Loader2 className="size-4 animate-spin text-brand motion-reduce:animate-none" strokeWidth={2} aria-hidden /> : phase === "failed" ? <CircleAlert className="size-4 text-fail" strokeWidth={1.75} aria-hidden /> : <Check className="size-4 text-pass" strokeWidth={2} aria-hidden />}
          {running ? "Working on it" : phase === "failed" ? "The run stopped with an error" : phase === "lost" ? "Lost the live feed" : "Run finished"}
        </span>
        <span className="tabular text-caption text-muted-foreground">
          {plural(lines, "line")} · {offers ? plural(offers, "offer") : `${plural(searched, "part")} searched`} · {plural(rejected, "offer")} rejected · {plural(refusals, "refusal")}
        </span>
        {simulated ? <SimulatedTag label={simLabel} /> : null}
      </header>
      {text ? <p className="px-3 pt-2 text-small text-secondary-text">{text}</p> : null}
      <ol className={cn("space-y-0.5 px-3 py-2", !all && "h-[156px] overflow-hidden")} aria-live="polite">
        {empty ? <li className="text-small text-muted-foreground">This run has no recorded events.</li> : null}
        {phase === "lost" && !events.length ? <li className="text-small text-muted-foreground">Couldn’t reach the run’s event stream. The run itself is not affected.</li> : null}
        {list.map((e) => (
          <li key={e.seq} className="flex h-6 items-center gap-2 text-small">
            <span className="tabular w-[84px] shrink-0 font-mono text-caption text-muted-foreground">{timeOfSec(e.ts)}</span>
            {e.severity === "refusal" ? (
              <ShieldX className="size-3.5 shrink-0 text-fail" strokeWidth={1.75} aria-hidden />
            ) : e.severity === "error" || e.severity === "warn" ? (
              <CircleAlert className={cn("size-3.5 shrink-0", e.severity === "error" ? "text-fail" : "text-warn")} strokeWidth={1.75} aria-hidden />
            ) : (
              <span className={cn("mx-1 size-1.5 shrink-0 rounded-full", e.severity === "ok" ? "bg-pass" : "bg-border-strong")} aria-hidden />
            )}
            <span className={cn("truncate", e.severity === "refusal" ? "text-fail" : "text-foreground")} title={e.title}>
              {e.title}
            </span>
          </li>
        ))}
      </ol>
      {events.length > SHOWN ? (
        <button type="button" onClick={() => setAll((v) => !v)} className="w-full border-t border-border px-3 py-1.5 text-left text-caption font-medium text-brand hover:text-brand-hover focus-visible:outline-2 focus-visible:outline-brand">
          {all ? "Show the latest only" : `Show all ${events.length} steps`}
        </button>
      ) : null}
    </section>
  );
}
