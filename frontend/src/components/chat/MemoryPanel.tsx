// The Memory panel (PLAN §3.15): what the agent remembers about you, the last improve pass, and the button that
// wipes it. Facts are written only from your own decisions (approving a cart, removing or swapping a line) and
// from what you said you own. Opened from the sidebar; loads when opened.
import { Brain, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { SimulatedTag } from "@/components/MockDataBadge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { MemoryFact, MemoryResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const KIND: Record<MemoryFact["kind"], { label: string; className: string }> = {
  owned: { label: "You own", className: "border-border bg-muted text-secondary-text" },
  preference: { label: "Preference", className: "border-brand/30 bg-brand-tint text-foreground" },
  purchase: { label: "Purchase", className: "border-border bg-surface text-secondary-text" },
  seed: { label: "Seed", className: "border-border bg-surface text-muted-foreground" },
};

const STORE: Record<string, string> = {
  mock: "Mock memory: kept in this backend process. Cognee is not called.",
  cloud: "Cognee Cloud. This list is the facts this app wrote there.",
  local: "Cognee, running locally. This list is the facts this app wrote there.",
  off: "Cognee is off: this is your owned-parts list in the database.",
};

const errorText = (e: unknown) => (e instanceof Error ? e.message : "Memory couldn't be reached.");

function timeOf(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function MemoryPanel({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [memory, setMemory] = useState<MemoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [forgetting, setForgetting] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMemory(await api.memory());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      setNote(null);
      void load();
    }
  }, [open, load]);

  const forget = async () => {
    setForgetting(true);
    setError(null);
    try {
      const res = await api.memoryForget("everything");
      setNote(res.detail);
      setConfirming(false);
      await load();
    } catch (e) {
      setError(errorText(e));
      setConfirming(false);
    } finally {
      setForgetting(false);
    }
  };

  const improve = memory?.last_improve ?? null;
  const facts = memory?.facts ?? [];

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-[440px]" data-testid="memory-panel">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Brain className="size-4" strokeWidth={1.75} aria-hidden />
              Memory
              {memory?.simulated ? <SimulatedTag label="Mock memory" /> : null}
            </SheetTitle>
            <SheetDescription>
              What the agent remembers about you. It learns only from what you decide: carts you approve, lines you remove or swap, and parts you say you own.
            </SheetDescription>
          </SheetHeader>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 pb-4">
            {memory ? <p className="text-caption text-muted-foreground">{STORE[memory.mode] ?? `Mode: ${memory.mode}`}</p> : null}
            {error ? (
              <p role="alert" className="rounded-lg border border-border bg-muted px-3 py-2 text-small text-secondary-text">
                {error}
              </p>
            ) : null}
            {note ? (
              <p role="status" className="rounded-lg border border-border bg-muted px-3 py-2 text-small text-secondary-text">
                {note}
              </p>
            ) : null}

            <section aria-label="Remembered facts">
              <h3 className="mb-2 flex items-center justify-between text-small font-medium text-foreground">
                <span>Facts{memory ? ` (${facts.length})` : ""}</span>
                <Button variant="ghost" size="xs" onClick={() => void load()} disabled={loading} aria-label="Reload memory">
                  <RefreshCw className={cn(loading && "animate-spin")} aria-hidden /> Reload
                </Button>
              </h3>
              {!memory && loading ? (
                <div className="space-y-2" aria-busy="true">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : memory && !facts.length ? (
                <p className="rounded-lg border border-dashed border-border px-3 py-4 text-small text-muted-foreground">
                  Nothing is remembered. Approve a cart or tell the agent what you already own, and it shows up here.
                </p>
              ) : (
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {facts.map((f, i) => (
                    <li key={`${f.text}-${i}`} className="space-y-1 px-3 py-2.5">
                      <p className="text-small text-foreground">{f.text}</p>
                      <p className="flex flex-wrap items-center gap-1.5 text-caption text-muted-foreground">
                        <span className={cn("inline-flex h-5 items-center rounded-sm border px-1.5 font-medium", KIND[f.kind].className)} data-kind={f.kind}>
                          {KIND[f.kind].label}
                        </span>
                        {f.source && f.source !== "seed" ? <span>{f.source}</span> : null}
                        {timeOf(f.at) ? <span>{timeOf(f.at)}</span> : null}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section aria-label="Last improve pass">
              <h3 className="mb-2 text-small font-medium text-foreground">Last improve pass</h3>
              {improve ? (
                <div className="rounded-lg border border-border">
                  <p className="flex flex-wrap items-center gap-1.5 border-b border-border px-3 py-2 text-caption text-muted-foreground">
                    <span>{timeOf(improve.at) ?? improve.at}</span>
                    <span>
                      · {improve.feedback.length} decision{improve.feedback.length === 1 ? "" : "s"} fed back
                    </span>
                    {improve.simulated ? <SimulatedTag /> : null}
                  </p>
                  <ul className="divide-y divide-border">
                    {improve.stages.map((s) => (
                      <li key={s.stage} className="px-3 py-2">
                        <p className="flex items-center justify-between gap-2 text-small">
                          <span className="font-mono text-caption text-foreground">{s.stage}</span>
                          <span
                            className={cn(
                              "inline-flex h-5 items-center rounded-sm border px-1.5 text-caption font-medium",
                              improve.simulated ? "border-dashed border-test bg-test-tint text-test" : "border-border bg-muted text-secondary-text",
                            )}
                          >
                            {s.status.replace(/_/g, " ")}
                          </span>
                        </p>
                        {s.reason ? <p className="mt-0.5 text-caption text-muted-foreground">{s.reason.replace(/_/g, " ")}</p> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-small text-muted-foreground">None yet. One pass runs after you approve a cart.</p>
              )}
            </section>
          </div>

          <div className="border-t border-border px-4 py-3">
            <Button variant="destructive" size="lg" className="w-full" disabled={!memory || !facts.length || forgetting} onClick={() => setConfirming(true)}>
              <Trash2 aria-hidden /> Forget everything
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <Dialog open={confirming} onOpenChange={(o) => !forgetting && setConfirming(o)}>
        <DialogContent className="gap-5 sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle className="text-h3">Forget everything?</DialogTitle>
            <DialogDescription>
              This removes all {facts.length} remembered fact{facts.length === 1 ? "" : "s"}: what you own, what you chose and what you rejected. The next build starts
              without them. It can’t be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" size="lg" className="h-10 px-4" onClick={() => setConfirming(false)} disabled={forgetting}>
              Keep it
            </Button>
            <Button variant="destructive" size="lg" className="h-10 px-4 font-semibold" onClick={() => void forget()} disabled={forgetting}>
              {forgetting ? "Forgetting…" : "Forget everything"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
