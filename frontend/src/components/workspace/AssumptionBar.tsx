// Assumption bar (PLAN §3.18, §11.5 B, §11.13): amber, shown only while assumptions are open.
// "2 assumptions to confirm before you can approve", each with its one-sentence statement and
// Confirm · Edit · Remove. The same bar sits on top of the cart's right column.
import { Check, CircleHelp, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiFailure } from "@/lib/api";
import { plural } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { AssumptionAction, BOMLine, RunState } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Confirm · Edit · Remove for one line. Also used inside the part panel's Sources tab. */
export function AssumptionActions({ runId, line, onResolved, compact = false }: { runId: string; line: Pick<BOMLine, "bom_line_id" | "qty" | "spec">; onResolved?: (run: RunState) => void; compact?: boolean }) {
  const setRun = useAppStore((s) => s.setRun);
  const [busy, setBusy] = useState<AssumptionAction | null>(null);
  const [editing, setEditing] = useState(false);
  const [spec, setSpec] = useState(line.spec ?? "");
  const [qty, setQty] = useState(String(line.qty));
  const [error, setError] = useState<string | null>(null);

  const act = async (action: AssumptionAction) => {
    setBusy(action);
    setError(null);
    try {
      const n = Number(qty);
      const run = await api.assumption(runId, { bom_line_id: line.bom_line_id, action, ...(action === "edit" ? { spec: spec.trim() || null, qty: Number.isFinite(n) && n > 0 ? Math.round(n) : null } : {}) });
      setRun(run);
      onResolved?.(run);
      setEditing(false);
      toast(action === "confirm" ? "Assumption confirmed" : action === "edit" ? "Assumption replaced with what you entered" : "Line removed");
    } catch (e) {
      setError(e instanceof ApiFailure ? e.message : "Couldn't save that. Nothing changed.");
    } finally {
      setBusy(null);
    }
  };

  if (editing) {
    return (
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void act("edit");
        }}
      >
        <label className="min-w-40 flex-1 text-caption text-secondary-text">
          What is true instead
          <Input value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="e.g. I need a radio, 4 channels or more" className="mt-1 h-8 bg-surface" autoFocus />
        </label>
        <label className="w-16 text-caption text-secondary-text">
          Quantity
          <Input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="numeric" className="mt-1 h-8 bg-surface" />
        </label>
        <Button type="submit" size="sm" disabled={busy !== null}>
          Save
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
          Cancel
        </Button>
        {error ? <p className="w-full text-caption text-fail">{error}</p> : null}
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Button size={compact ? "xs" : "sm"} variant="outline" className="border-warn/50 bg-surface" disabled={busy !== null} onClick={() => void act("confirm")}>
        <Check aria-hidden /> Confirm
      </Button>
      <Button size={compact ? "xs" : "sm"} variant="ghost" disabled={busy !== null} onClick={() => setEditing(true)}>
        <Pencil aria-hidden /> Edit
      </Button>
      <Button size={compact ? "xs" : "sm"} variant="ghost" disabled={busy !== null} onClick={() => void act("remove")}>
        <Trash2 aria-hidden /> Remove
      </Button>
      {error ? <p className="w-full text-caption text-fail">{error}</p> : null}
    </div>
  );
}

export function AssumptionBar({ run, onResolved, className }: { run: RunState; onResolved?: (run: RunState) => void; className?: string }) {
  const select = useAppStore((s) => s.select);
  const open = run.bom.filter((l) => run.open_assumptions.includes(l.bom_line_id) && l.provenance.type === "assumption");
  if (!open.length) return null;
  return (
    <section aria-label="Assumptions to confirm" className={cn("rounded-lg border border-warn/40 bg-warn-tint p-3", className)}>
      <p className="flex items-center gap-1.5 text-small font-semibold text-warn">
        <CircleHelp className="size-4" strokeWidth={1.75} aria-hidden />
        {plural(open.length, "assumption")} to confirm before you can approve
      </p>
      <ul className="mt-2 space-y-3">
        {open.map((line) => (
          <li key={line.bom_line_id} className="space-y-1.5">
            <p className="text-small text-foreground">
              <button type="button" className="font-medium underline decoration-warn/50 underline-offset-2 hover:decoration-warn" onClick={() => select(line.bom_line_id, null, "sources")}>
                {line.raw_name}
              </button>
              {": "}
              {line.provenance.type === "assumption" ? line.provenance.statement : ""}
            </p>
            <AssumptionActions runId={run.run_id} line={line} onResolved={onResolved} compact />
          </li>
        ))}
      </ul>
    </section>
  );
}
