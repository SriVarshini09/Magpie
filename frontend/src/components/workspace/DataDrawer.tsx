// Data drawer (PLAN §11.5 B footer "Data" button, §7 SingleStore and SIE rows). Owner: D, with C's components.
// Row counts per table and KB rows by kind, the last SQL with its time, the SIE call table, a live
// KB search that shows the exact SQL it ran, the run's call counts, and the price query for the selected part.
import { Cpu, Database, Search, Table2, Timer } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { MockDataBadge, SimulatedTag } from "@/components/MockDataBadge";
import { Money } from "@/components/common/Money";
import { EmptyState, InlineError } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MatchedTermsLine, MatchedText, QueryTokens, rankText } from "@/components/workspace/KbMatch";
import { api, API_BASE, ApiFailure } from "@/lib/api";
import { ago, timeOf, viaText } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { DataStats, KbSearchResponse, PricesResponse, RunStats } from "@/lib/types";
import { cn } from "@/lib/utils";

type StatsLoad = { phase: "loading" } | { phase: "ready"; stats: DataStats } | { phase: "unavailable"; status: number } | { phase: "error"; message: string };

const TABLE_ORDER = ["kb_docs", "kb_chunks", "price_observations", "audit_events", "mandates", "runs", "owned_parts"];
const BACKEND_LABEL: Record<DataStats["backend"], string> = { singlestore: "SingleStore", sqlite: "SQLite (local fallback)", mock: "mock data" };

async function fetchStats(): Promise<DataStats> {
  return api.dataStats();
}

function SqlBlock({ sql, className }: { sql: string; className?: string }) {
  return (
    <pre className={cn("max-h-64 overflow-auto rounded-sm border border-border bg-muted p-3 font-mono text-caption leading-relaxed whitespace-pre text-foreground", className)}>
      {sql}
    </pre>
  );
}

function SectionTitle({ icon: Icon, children, right }: { icon: typeof Database; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-secondary-text" strokeWidth={1.75} aria-hidden />
      <h3 className="text-small font-semibold text-foreground">{children}</h3>
      {right ? <span className="ml-auto">{right}</span> : null}
    </div>
  );
}

function CountGrid({ entries }: { entries: Array<[string, number]> }) {
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {entries.map(([name, n]) => (
        <div key={name} className="rounded-sm border border-border bg-surface px-3 py-2">
          <dt className="truncate font-mono text-caption text-muted-foreground">{name}</dt>
          <dd className="tabular font-mono text-body-lg font-semibold text-foreground">{n.toLocaleString("en-US")}</dd>
        </div>
      ))}
    </dl>
  );
}

function TablesTab({ stats, reload, runStats }: { stats: StatsLoad; reload: () => void; runStats: RunStats | null }) {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <SectionTitle icon={Table2} right={stats.phase === "ready" && stats.stats.simulated ? <SimulatedTag label="Mock data" /> : null}>
          Tables{stats.phase === "ready" ? ` · ${BACKEND_LABEL[stats.stats.backend] ?? stats.stats.backend}` : ""}
        </SectionTitle>
        {stats.phase === "loading" ? (
          <div className="grid grid-cols-3 gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-sm" />
            ))}
          </div>
        ) : stats.phase === "unavailable" ? (
          <p className="rounded-sm border border-border bg-muted px-3 py-2 text-small text-secondary-text">
            Row counts not available yet: the backend does not serve <span className="font-mono">/api/data/stats</span> in this build. The KB search and price query below still work.
          </p>
        ) : stats.phase === "error" ? (
          <InlineError message={stats.message} onRetry={reload} />
        ) : (
          <>
            <CountGrid
              entries={[
                ...TABLE_ORDER.filter((t) => t in stats.stats.tables).map((t) => [t, stats.stats.tables[t]] as [string, number]),
                ...Object.entries(stats.stats.tables).filter(([t]) => !TABLE_ORDER.includes(t)),
              ]}
            />
            {Object.keys(stats.stats.kb_by_kind).length ? (
              <div className="space-y-1.5">
                <p className="text-caption font-medium text-muted-foreground">Knowledge-base rows by kind</p>
                <ul className="flex flex-wrap gap-1.5">
                  {Object.entries(stats.stats.kb_by_kind).map(([kind, n]) => (
                    <li key={kind} className="rounded-full border border-border bg-surface px-2.5 py-0.5 text-caption text-secondary-text">
                      {kind} <span className="tabular font-mono font-medium text-foreground">{n}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </div>

      {stats.phase === "ready" && stats.stats.last_query ? (
        <div className="space-y-2">
          <SectionTitle icon={Timer} right={<span className="text-caption text-muted-foreground">{stats.stats.last_query.took_ms} ms · {ago(stats.stats.last_query.at)}</span>}>
            Last query
          </SectionTitle>
          <SqlBlock sql={stats.stats.last_query.sql} />
        </div>
      ) : null}

      {stats.phase === "ready" && stats.stats.sie.length ? (
        <div className="space-y-2">
          <SectionTitle icon={Cpu}>Superlinked SIE calls</SectionTitle>
          <table className="w-full text-small">
            <thead>
              <tr className="border-b border-border text-left text-caption text-muted-foreground">
                <th className="py-1.5 pr-2 font-medium">Step</th>
                <th className="py-1.5 pr-2 font-medium">Model</th>
                <th className="py-1.5 pr-2 text-right font-medium">Calls</th>
                <th className="py-1.5 text-right font-medium">Median</th>
              </tr>
            </thead>
            <tbody>
              {stats.stats.sie.map((row) => (
                <tr key={row.step} className="border-b border-border/70">
                  <td className="py-1.5 pr-2">{row.step}</td>
                  <td className="max-w-40 truncate py-1.5 pr-2 font-mono text-caption" title={row.model}>
                    {row.model}
                  </td>
                  <td className="tabular py-1.5 pr-2 text-right font-mono">{row.calls}</td>
                  <td className="tabular py-1.5 text-right font-mono">{row.median_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {runStats ? (
        <div className="space-y-2">
          <SectionTitle icon={Cpu}>This run</SectionTitle>
          <CountGrid
            entries={[
              ["Claude calls", runStats.claude_calls],
              ["SIE calls", runStats.sie_calls],
              ["SIE median ms", runStats.sie_median_ms],
              ["KB queries", runStats.kb_queries],
              ["SerpAPI calls", runStats.serpapi_calls],
              ["Stores searched", runStats.stores_searched],
            ]}
          />
        </div>
      ) : null}
    </div>
  );
}

function KbSearchTab() {
  const [q, setQ] = useState("12V servo power supply");
  const [state, setState] = useState<{ phase: "idle" } | { phase: "loading" } | { phase: "ready"; res: KbSearchResponse; q: string } | { phase: "error"; message: string }>({ phase: "idle" });

  const run = (query: string) => {
    if (!query.trim()) return;
    setState({ phase: "loading" });
    api
      .kbSearch(query.trim())
      .then((res) => setState({ phase: "ready", res, q: query.trim() }))
      .catch((e: unknown) => setState({ phase: "error", message: e instanceof ApiFailure ? e.message : "Search failed." }));
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    run(q);
  };

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex gap-2">
        <label className="flex-1">
          <span className="sr-only">Search the knowledge base</span>
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. 12V servo power supply" className="text-small" />
        </label>
        <Button type="submit" disabled={state.phase === "loading" || !q.trim()}>
          <Search aria-hidden />
          Search
        </Button>
      </form>

      {state.phase === "idle" ? (
        <p className="text-small text-muted-foreground">Runs the same hybrid query the agent uses (full-text plus vector, fused by rank) and shows the SQL it sent, how the query was split into index tokens, and why each row matched.</p>
      ) : state.phase === "loading" ? (
        <div className="space-y-2">
          <Skeleton className="h-28 rounded-sm" />
          <Skeleton className="h-12 rounded-sm" />
          <Skeleton className="h-12 rounded-sm" />
        </div>
      ) : state.phase === "error" ? (
        <InlineError message={state.message} onRetry={() => run(q)} />
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-caption text-muted-foreground">
            <span>
              {state.res.chunks.length} rows for “{state.q}” · {state.res.took_ms} ms
            </span>
            {state.res.simulated ? <SimulatedTag label="Mock data" /> : null}
          </div>
          {state.res.analyzer ? <QueryTokens terms={state.res.query_terms ?? []} analyzer={state.res.analyzer} chunks={state.res.chunks} /> : null}
          <SqlBlock sql={[state.res.analyze_sql, state.res.sql].filter(Boolean).join("\n\n")} />
          {state.res.chunks.length ? (
            <ul className="space-y-2">
              {state.res.chunks.map((c) => {
                const ranks = rankText(c);
                return (
                  <li key={c.kb_ref} className="space-y-1 rounded-sm border border-border bg-surface px-3 py-2">
                    <p className="flex flex-wrap items-center gap-x-2 text-caption text-muted-foreground">
                      <span className="font-mono text-foreground">{c.kb_ref}</span>
                      <span>{c.doc_title}</span>
                      <span className="font-mono">
                        L{c.line_from}
                        {c.line_to !== c.line_from ? `–${c.line_to}` : ""}
                      </span>
                      <span className="tabular ml-auto font-mono">
                        {ranks ? `${ranks} · ` : ""}score {c.score.toFixed(3)}
                      </span>
                    </p>
                    <p className="line-clamp-3 text-small text-foreground">
                      <MatchedText text={c.text} terms={c.matched_terms ?? []} />
                    </p>
                    <MatchedTermsLine chunk={c} />
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState icon={Search} title="No rows matched">
              Try fewer words, or a part name from the list.
            </EmptyState>
          )}
        </div>
      )}
    </div>
  );
}

function PricesQueryTab({ runId, bomLineId, lineName }: { runId: string | null; bomLineId: string | null; lineName: string | null }) {
  const [state, setState] = useState<{ phase: "loading" } | { phase: "ready"; res: PricesResponse } | { phase: "error"; message: string } | { phase: "none" }>({ phase: "none" });

  const load = useCallback(() => {
    if (!runId || !bomLineId) {
      setState({ phase: "none" });
      return () => undefined;
    }
    let cancelled = false;
    setState({ phase: "loading" });
    api
      .prices(runId, bomLineId)
      .then((res) => !cancelled && setState({ phase: "ready", res }))
      .catch((e: unknown) => !cancelled && setState({ phase: "error", message: e instanceof ApiFailure ? e.message : "Couldn't load prices." }));
    return () => {
      cancelled = true;
    };
  }, [runId, bomLineId]);

  useEffect(() => load(), [load]);

  if (state.phase === "none") {
    return (
      <EmptyState icon={Table2} title="Select a part">
        Pick a part in the list or the view to see every price seen for it, with its age and distance from the median.
      </EmptyState>
    );
  }
  if (state.phase === "loading") {
    return (
      <div className="space-y-2">
        <Skeleton className="h-28 rounded-sm" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-8 rounded-sm" />
        ))}
      </div>
    );
  }
  if (state.phase === "error") return <InlineError message={state.message} onRetry={() => void load()} />;

  const { res } = state;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-caption text-muted-foreground">
        <span>
          {res.rows.length} prices for <span className="font-mono text-foreground">{bomLineId}</span>
          {lineName ? ` · ${lineName}` : ""}
        </span>
        {res.simulated ? <SimulatedTag label="Mock data" /> : null}
      </div>
      <SqlBlock sql={res.sql} />
      {res.rows.length ? (
        <table className="w-full text-small">
          <thead>
            <tr className="border-b border-border text-left text-caption text-muted-foreground">
              <th className="py-1.5 pr-2 font-medium">Store</th>
              <th className="py-1.5 pr-2 font-medium">Listing</th>
              <th className="py-1.5 pr-2 text-right font-medium">Price</th>
              <th className="py-1.5 pr-2 text-right font-medium">Age</th>
              <th className="py-1.5 text-right font-medium">vs median</th>
            </tr>
          </thead>
          <tbody>
            {res.rows.map((row, i) => (
              <tr key={`${row.store_id}-${i}`} className={cn("border-b border-border/70", row.refused && "text-muted-foreground")}>
                <td className="py-1.5 pr-2 align-top">
                  {row.store_id}
                  {row.refused ? <span className="block text-caption text-fail">refused</span> : null}
                </td>
                <td className="max-w-48 py-1.5 pr-2 align-top">
                  <span className="line-clamp-2">{row.title}</span>
                  <span className="text-caption text-muted-foreground">
                    seen {timeOf(row.seen_at)} · {viaText(row.source_api)}
                  </span>
                </td>
                <td className="py-1.5 pr-2 text-right align-top">
                  <Money value={row.price_usd} seenAt={row.seen_at} source={row.source_api} simulated={row.simulated} />
                </td>
                <td className="tabular py-1.5 pr-2 text-right align-top font-mono">{Math.round(row.age_min)} min</td>
                <td className={cn("tabular py-1.5 text-right align-top font-mono", Math.abs(row.vs_median_pct) >= 25 && "text-warn")}>
                  {row.vs_median_pct > 0 ? "+" : row.vs_median_pct < 0 ? "−" : ""}
                  {Math.abs(row.vs_median_pct).toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <EmptyState icon={Table2} title="No prices seen yet">
          Prices appear once the agent has searched the stores for this part.
        </EmptyState>
      )}
    </div>
  );
}

export function DataDrawer({
  runId: runIdProp,
  trigger,
  open,
  onOpenChange,
  className,
}: {
  /** Defaults to the run in the store. */
  runId?: string | null;
  /** The button that opens the drawer (defaults to a small "Data" button for the footer). */
  trigger?: ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
}) {
  const storeRunId = useAppStore((s) => s.runId);
  const run = useAppStore((s) => s.run);
  const selectedLineId = useAppStore((s) => s.selectedLineId);
  const runId = runIdProp ?? storeRunId;
  const runStats = run && run.run_id === runId ? run.stats : null;
  const line = run && run.run_id === runId ? (run.bom.find((l) => l.bom_line_id === selectedLineId) ?? null) : null;

  const [internalOpen, setInternalOpen] = useState(false);
  const isOpen = open ?? internalOpen;
  const setOpen = (v: boolean) => {
    if (open === undefined) setInternalOpen(v);
    onOpenChange?.(v);
  };

  const [stats, setStats] = useState<StatsLoad>({ phase: "loading" });
  const loadStats = useCallback(() => {
    setStats({ phase: "loading" });
    fetchStats()
      .then((s) => setStats({ phase: "ready", stats: s }))
      .catch((e: unknown) => {
        if (e instanceof ApiFailure && (e.status === 404 || e.status === 405 || e.status === 501)) setStats({ phase: "unavailable", status: e.status });
        else setStats({ phase: "error", message: e instanceof ApiFailure && e.status ? `${e.message}.` : "Couldn't reach the backend. Is it running on port 8000?" });
      });
  }, []);

  useEffect(() => {
    if (isOpen) loadStats();
  }, [isOpen, loadStats]);

  return (
    <Sheet open={isOpen} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        {trigger ?? (
          <Button variant="ghost" size="xs" className={className}>
            <Database aria-hidden />
            Data
          </Button>
        )}
      </SheetTrigger>
      <SheetContent side="right" className="gap-0 data-[side=right]:w-full data-[side=right]:sm:max-w-2xl">
        <SheetHeader className="border-b border-border">
          <SheetTitle className="flex items-center gap-2">
            <Database className="size-4 text-secondary-text" strokeWidth={1.75} aria-hidden />
            Data
          </SheetTitle>
          <SheetDescription>One database holds the knowledge base, the prices seen and the audit chain. Every query below shows the SQL it ran.</SheetDescription>
        </SheetHeader>
        <Tabs defaultValue="tables" className="min-h-0 flex-1 overflow-y-auto p-4">
          <TabsList>
            <TabsTrigger value="tables">Tables</TabsTrigger>
            <TabsTrigger value="kb">KB search</TabsTrigger>
            <TabsTrigger value="prices">Prices{line ? ` · ${line.bom_line_id}` : ""}</TabsTrigger>
          </TabsList>
          <TabsContent value="tables" className="pt-3">
            <TablesTab stats={stats} reload={loadStats} runStats={runStats} />
          </TabsContent>
          <TabsContent value="kb" className="pt-3">
            <KbSearchTab />
          </TabsContent>
          <TabsContent value="prices" className="pt-3">
            <PricesQueryTab runId={runId ?? null} bomLineId={selectedLineId} lineName={line?.raw_name ?? null} />
          </TabsContent>
        </Tabs>
        {isOpen ? <MockDataBadge /> : null}
      </SheetContent>
    </Sheet>
  );
}
