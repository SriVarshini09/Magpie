// Workspace footer (PLAN §11.5 B, 28 px): health dots, the mode, run counters and the Data button.
// A failed integration is a grey dot here, never a crash (§11.7). Mock services are violet and say so.
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { plural, sourceName } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { HealthState, RunState } from "@/lib/types";
import { cn } from "@/lib/utils";

import { DataDrawer } from "./DataDrawer";

const DOT: Record<HealthState, string> = {
  ok: "bg-pass",
  down: "bg-fail",
  off: "bg-border-strong",
  mock: "border border-dashed border-test bg-test-tint",
  fallback: "border border-pass bg-pass-tint",
};
const WORD: Record<HealthState, string> = { ok: "ok", down: "down", off: "off", mock: "mock", fallback: "fallback" };
/** What a keyless fallback actually is, per service: real data, not the sponsor service. */
const FALLBACK: Record<string, string> = { singlestore: "SQLite fallback", airbyte_github: "GitHub, keyless fetch" };

function stateWord(key: string, state: HealthState): string {
  return state === "fallback" ? (FALLBACK[key] ?? WORD.fallback) : (WORD[state] ?? state);
}
const MODE: Record<string, string> = { mock: "Mock data", live: "Live", record: "Live, recording", replay: "Replay of a recorded run" };

export function HealthDots() {
  const health = useAppStore((s) => s.health);
  if (!health) return <span className="text-muted-foreground">Backend not reachable</span>;
  const entries = [...Object.entries(health.integrations), ...Object.entries(health.stores)];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="inline-flex items-center gap-1" aria-label={`Service health: ${entries.map(([k, v]) => `${sourceName(k)} ${stateWord(k, v)}`).join(", ")}`}>
          {entries.map(([key, state]) => (
            <span key={key} className={cn("size-2 rounded-full", DOT[state] ?? DOT.off)} />
          ))}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-104">
        <ul className="grid grid-cols-2 gap-x-4 gap-y-0.5">
          {entries.map(([key, state]) => (
            <li key={key} className="flex items-center justify-between gap-3">
              <span>{sourceName(key)}</span>
              <span className="font-mono">{stateWord(key, state)}</span>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}

export function WorkspaceFooter({ run }: { run: RunState | null }) {
  const health = useAppStore((s) => s.health);
  const s = run?.stats;
  // mock SIE calls are counted like real ones, so the label says which they were
  const sieLabel = health?.integrations?.sie === "mock" ? "SIE (mock)" : "SIE";
  return (
    <footer className="flex h-(--b2c-footer-h) shrink-0 items-center gap-4 border-t border-border bg-surface px-(--b2c-gutter) pl-36 text-caption text-muted-foreground">
      <HealthDots />
      <span className={cn("font-medium", health?.mock ? "text-test" : "text-foreground")}>
        {!health ? "Offline" : health.mode === "live" && health.mock ? (Object.values(health.stores).some((v) => v === "ok") ? "Real pipeline, some stores and services mock" : "Real pipeline, mock services") : (MODE[health.mode] ?? health.mode)}
      </span>
      {s ? (
        <span className="truncate">
          Claude: {plural(s.claude_calls, "call")} · {sieLabel}: {plural(s.sie_calls, "call")}
          {s.sie_calls ? `, median ${s.sie_median_ms} ms` : ""} · KB: {plural(s.kb_queries, "query", "queries")} · Stores: {s.stores_searched} searched
        </span>
      ) : null}
      <span className="ml-auto" />
      {run ? <HashTextLite hash={run.head_hash} /> : null}
      {/* D's drawer brings its own trigger button and sheet. */}
      <DataDrawer runId={run?.run_id} />
    </footer>
  );
}

function HashTextLite({ hash }: { hash: string }) {
  return (
    <span className="hidden font-mono xl:inline" title={`Head of the audit chain: ${hash}`}>
      chain {hash.replace(/^sha256:/, "").slice(0, 8)}…
    </span>
  );
}
