// The hash chain as a vertical list (PLAN §3.7, §11.5 E). Owner: D, with C's components.
// Filter by kind and search; each row links to the record before it by hash; refusals are red-tinted.
import { ArrowUp, ChevronRight, Search, ShieldX } from "lucide-react";
import { useMemo, useState } from "react";

import { SimulatedTag, useSimulatedRunLabel } from "@/components/MockDataBadge";
import { HashText } from "@/components/common/HashText";
import { EmptyState } from "@/components/common/States";
import { Input } from "@/components/ui/input";
import { shortHash, timeOfSec } from "@/lib/format";
import type { ChainRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

import { JsonBlock } from "./JsonView";
import { countByFilter, FILTER_LABEL, inFilter, kindLabel, refusalOf, summarize, type ChainFilter } from "./receiptFormat";

const FILTERS: ChainFilter[] = ["all", "mandates", "refusals", "decisions", "cart", "payment", "other"];

export const recordAnchor = (seq: number) => `chain-record-${seq}`;

function ChainRow({ rec, broken, afterBreak }: { rec: ChainRecord; broken: boolean; afterBreak: boolean }) {
  const [open, setOpen] = useState(false);
  const simLabel = useSimulatedRunLabel().short;
  const refusal = refusalOf(rec);
  const summary = summarize(rec);
  const simulated = rec.simulated === true;
  return (
    <li
      id={recordAnchor(rec.seq)}
      className={cn(
        "scroll-mt-20 rounded-lg border transition-colors duration-150",
        broken ? "border-fail bg-fail-tint" : refusal ? "border-fail/30 bg-fail-tint" : "border-border bg-surface",
        afterBreak && !broken && "opacity-60",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-3 py-2.5 text-left"
      >
        <span className="tabular w-8 shrink-0 pt-0.5 text-right font-mono text-caption text-muted-foreground">{rec.seq}</span>
        <ChevronRight className={cn("mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform duration-150", open && "rotate-90")} strokeWidth={1.75} aria-hidden />
        <span className="min-w-0 flex-1 space-y-0.5">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            {refusal ? <ShieldX className="size-3.5 text-fail" strokeWidth={1.75} aria-hidden /> : null}
            <span className={cn("text-small font-medium", refusal ? "text-fail" : "text-foreground")}>{kindLabel(rec.kind)}</span>
            <span className="font-mono text-caption text-muted-foreground">{rec.kind}</span>
            <span className="text-caption text-muted-foreground">{timeOfSec(rec.ts)}</span>
            {broken ? <span className="text-caption font-semibold text-fail">Broken here</span> : null}
          </span>
          {summary ? <span className="block truncate text-small text-secondary-text">{summary}</span> : null}
          {refusal?.clause ? (
            <span className="block font-mono text-caption text-fail">
              {refusal.clause}
            </span>
          ) : null}
        </span>
        {simulated ? <SimulatedTag label={simLabel} /> : null}
      </button>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border/70 px-3 py-1.5 pl-[4.25rem] text-caption text-muted-foreground">
        {rec.seq > 1 ? (
          <a href={`#${recordAnchor(rec.seq - 1)}`} title={`${rec.prev_hash} (go to record ${rec.seq - 1})`} className="inline-flex items-center gap-1 font-mono transition-colors duration-150 hover:text-brand">
            <ArrowUp className="size-3" strokeWidth={1.75} aria-hidden />
            prev {shortHash(rec.prev_hash)}
          </a>
        ) : (
          <span className="font-mono" title={rec.prev_hash}>
            genesis {shortHash(rec.prev_hash)}
          </span>
        )}
        <span aria-hidden>→</span>
        <HashText hash={rec.hash} label="hash" />
      </div>
      {open ? (
        <div className="border-t border-border/70 p-3">
          <JsonBlock data={rec} />
        </div>
      ) : null}
    </li>
  );
}

export function ChainList({ records, brokenAt, className }: { records: ChainRecord[]; brokenAt?: number | null; className?: string }) {
  const [filter, setFilter] = useState<ChainFilter>("all");
  const [query, setQuery] = useState("");
  const counts = useMemo(() => countByFilter(records), [records]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return records.filter((r) => inFilter(r, filter) && (!q || JSON.stringify(r).toLowerCase().includes(q)));
  }, [records, filter, query]);

  return (
    <section className={cn("space-y-3", className)} aria-label="Audit chain">
      <div className="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Filter records by kind" className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              disabled={f !== "all" && counts[f] === 0}
              onClick={() => setFilter(f)}
              className={cn(
                "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-caption font-medium transition-colors duration-150 disabled:opacity-40",
                filter === f ? "border-primary bg-primary text-primary-foreground" : "border-border bg-surface text-secondary-text hover:border-border-strong hover:text-foreground",
                f === "refusals" && filter !== f && counts.refusals > 0 && "text-fail",
              )}
            >
              {FILTER_LABEL[f]}
              <span className="tabular opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
        <label className="relative ml-auto w-64 max-w-full">
          <span className="sr-only">Search records</span>
          <Search className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground" strokeWidth={1.75} aria-hidden />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search records (store, rule, hash…)" className="pl-7 text-small" />
        </label>
      </div>

      {shown.length ? (
        <ol className="space-y-2">
          {shown.map((rec) => (
            <ChainRow key={rec.seq} rec={rec} broken={brokenAt === rec.seq} afterBreak={brokenAt != null && rec.seq > brokenAt} />
          ))}
        </ol>
      ) : (
        <div className="rounded-lg border border-border bg-surface">
          <EmptyState icon={Search} title={records.length ? "No records match" : "No records yet"}>
            {records.length ? "Try another filter or clear the search." : "Records appear here as the agent works: every tool call is one record."}
          </EmptyState>
        </div>
      )}
    </section>
  );
}
