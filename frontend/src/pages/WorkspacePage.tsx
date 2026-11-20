// Workspace (PLAN §11.5 B): the part map is the page; everything else serves it.
// Mandate bar · composer strip · part map 50% (the view router) · parts list 26% · timeline 24% ·
// part panel (520 px, over the list and timeline) · footer. At 1280–1439 the timeline is a bottom drawer.
import { History } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { useCallback, useEffect, useRef } from "react";
import { Link, useParams } from "react-router";

import { NarrowNotice } from "@/components/common/NarrowNotice";
import { InlineError } from "@/components/common/States";
import { PartPanel } from "@/components/panel/PartPanel";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { AssumptionBar } from "@/components/workspace/AssumptionBar";
import { ComposerStrip } from "@/components/workspace/ComposerStrip";
import { WorkspaceFooter } from "@/components/workspace/HealthDots";
import { MandateBar } from "@/components/workspace/MandateBar";
import { PartsList, PartsListSkeleton } from "@/components/workspace/PartsList";
import { Timeline } from "@/components/workspace/Timeline";
import { ViewRouter } from "@/components/workspace/ViewRouter";
import { useRun } from "@/hooks/useRun";
import { useRunEvents } from "@/hooks/useRunEvents";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { Event, EventType } from "@/lib/types";
import { LogoMark } from "@/components/brand/Logo";

/** Events after which the run state on the server has changed. */
const REFRESH_ON = new Set<EventType>([
  "bom.line", "spec.resolved", "owned.matched", "offers.found", "compat.check", "compat.fix", "plan.ready", "plan.changed", "cart.edited", "refusal",
  "approval.granted", "mandate.closed", "run.waiting_approval", "run.done", "assumption.opened", "assumption.resolved", "view.ready", "template.loaded", "photo.parts", "error",
]);

function WorkspaceSkeleton() {
  return (
    <>
      <div className="flex h-(--b2c-mandate-bar-h) shrink-0 items-center gap-4 border-b border-border bg-surface px-(--b2c-gutter)">
        <Link to="/" aria-label="Build-to-Cart: start">
          <LogoMark />
        </Link>
        <Skeleton className="h-6 w-36" />
        <Skeleton className="h-6 w-24 rounded-full" />
        <Skeleton className="h-6 w-32 rounded-full" />
        <Skeleton className="ml-auto h-8 w-28" />
      </div>
      <div className="h-11 shrink-0 border-b border-border" />
      <main className="flex min-h-0 flex-1 gap-4 px-(--b2c-gutter) py-4">
        <Skeleton className="w-1/2 rounded-2xl bg-stage/90" />
        <div className="flex-[26] overflow-hidden rounded-lg border border-border bg-surface">
          <PartsListSkeleton />
        </div>
        <div className="hidden flex-[24] rounded-lg border border-border bg-surface min-[1440px]:block" />
      </main>
    </>
  );
}

export function WorkspacePage() {
  const { id } = useParams();
  const { run, error, loading, reload } = useRun(id);
  const selectedLineId = useAppStore((s) => s.selectedLineId);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const events = useAppStore((s) => s.events);
  const timer = useRef<number | null>(null);

  const onEvent = useCallback(
    (event: Event) => {
      if (!id || !REFRESH_ON.has(event.type)) return;
      // Only a run that is still moving needs a re-read; a replayed finished run does not.
      const current = useAppStore.getState().run;
      if (current && current.status !== "running" && !["plan.changed", "cart.edited", "assumption.resolved", "approval.granted", "mandate.closed", "run.done"].includes(event.type)) return;
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        void api.run(id).then((r) => useAppStore.getState().setRun(r)).catch(() => undefined);
      }, 350);
    },
    [id],
  );
  useRunEvents(id, onEvent);
  useEffect(() => () => void (timer.current && window.clearTimeout(timer.current)), []);

  // Esc closes the part panel (dialogs and sheets handle their own Esc first).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      if (document.querySelector('[role="dialog"][data-state="open"]')) return;
      clearSelection();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clearSelection]);

  useEffect(() => {
    document.title = run ? `${run.intake.summary || "Run"} · Build-to-Cart` : "Build-to-Cart";
  }, [run]);

  const last = events[events.length - 1];

  return (
    <NarrowNotice min={1100}>
      <div className="flex h-screen flex-col bg-page">
        {error ? (
          <div className="mx-auto mt-24 w-full max-w-lg space-y-4 px-6">
            <Link to="/" className="inline-flex">
              <LogoMark />
            </Link>
            <InlineError
              title={error.status === 404 ? "No run with that ID" : "This run didn't load"}
              message={error.status === 404 ? "Runs live in the backend's memory: it may have restarted since, or the run was started on another machine. Start a new one from the first page." : `${error.message} If the backend was not restarted, the run is still there.`}
              onRetry={reload}
            />
            <Button asChild variant="outline">
              <Link to="/">Start a new build</Link>
            </Button>
          </div>
        ) : loading || !run ? (
          <WorkspaceSkeleton />
        ) : (
          <>
            <MandateBar run={run} />
            {run.status === "running" ? (
              <div className="relative h-6 shrink-0 overflow-hidden border-b border-border bg-surface px-(--b2c-gutter)" role="status">
                <span className="absolute inset-x-0 top-0 h-0.5 overflow-hidden bg-muted">
                  <span className="progress-line block h-full w-1/4 bg-brand" />
                </span>
                <p className="truncate text-caption leading-6 text-secondary-text">{last ? `${last.title}…` : "Starting the run…"}</p>
              </div>
            ) : null}
            <ComposerStrip run={run} />
            <main className="relative flex min-h-0 flex-1 gap-4 px-(--b2c-gutter) py-4">
              <ViewRouter run={run} className="w-1/2 shrink-0" />
              <section aria-label="Parts" className="flex min-w-0 flex-[26] flex-col gap-3">
                <AssumptionBar run={run} className="shrink-0" />
                <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-surface">
                  <PartsList run={run} />
                  <div className="shrink-0 border-t border-border p-2 min-[1440px]:hidden">
                    <Sheet>
                      <SheetTrigger asChild>
                        <Button variant="ghost" size="sm" className="w-full justify-start">
                          <History aria-hidden /> Timeline · {events.length} events
                        </Button>
                      </SheetTrigger>
                      <SheetContent side="bottom" className="h-[60vh] gap-0">
                        <SheetHeader className="sr-only">
                          <SheetTitle>Timeline</SheetTitle>
                          <SheetDescription>Every step of this run.</SheetDescription>
                        </SheetHeader>
                        <Timeline className="min-h-0 flex-1" />
                      </SheetContent>
                    </Sheet>
                  </div>
                </div>
              </section>
              <div className="hidden min-w-0 flex-[24] overflow-hidden rounded-lg border border-border bg-surface min-[1440px]:flex">
                <Timeline className="min-h-0 flex-1" />
              </div>
              <AnimatePresence>{selectedLineId ? <PartPanel key="panel" run={run} bomLineId={selectedLineId} onClose={clearSelection} /> : null}</AnimatePresence>
            </main>
          </>
        )}
        <WorkspaceFooter run={run} />
      </div>
    </NarrowNotice>
  );
}
