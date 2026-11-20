// Prices tab (PLAN §11.6): every price seen for this line: store, price, age, distance from the median, source.
import { ShieldX } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Money } from "@/components/common/Money";
import { InlineError } from "@/components/common/States";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiFailure } from "@/lib/api";
import { sourceName, timeOf } from "@/lib/format";
import type { PricesResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

import { SqlBlock } from "./SourcesTab";

export function PricesTab({ runId, bomLineId, storeNames = {} }: { runId: string; bomLineId: string; storeNames?: Record<string, string> }) {
  const [data, setData] = useState<PricesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    let cancelled = false;
    setError(null);
    setData(null);
    api
      .prices(runId, bomLineId)
      .then((d) => !cancelled && setData(d))
      .catch((e: unknown) => !cancelled && setError(e instanceof ApiFailure && e.status === 501 ? "Price history isn't connected yet. The Offers tab has every price found in this run." : e instanceof ApiFailure ? e.message : "Couldn't load the price history."));
    return () => {
      cancelled = true;
    };
  }, [runId, bomLineId]);
  useEffect(() => load(), [load]);

  if (error) return <InlineError message={error} onRetry={load} />;
  if (!data) {
    return (
      <div className="space-y-2" aria-busy="true">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }
  if (!data.rows.length) return <p className="py-6 text-center text-small text-muted-foreground">No prices were recorded for this line.</p>;

  return (
    <div className="space-y-4">
      <table className="w-full text-small">
        <thead>
          <tr className="border-b border-border text-left text-caption text-muted-foreground">
            <th className="py-2 pr-2 font-medium">Store and listing</th>
            <th className="py-2 pr-2 text-right font-medium">Price</th>
            <th className="py-2 pr-2 text-right font-medium">Age</th>
            <th className="py-2 text-right font-medium">vs. median</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={`${row.store_id}-${i}`} className={cn("border-b border-border align-top last:border-b-0", row.refused && "bg-fail-tint")}>
              <td className="max-w-0 py-2 pr-2">
                <p className="flex items-center gap-1.5 font-medium">
                  {storeNames[row.store_id] ?? row.store_id}
                  {row.refused ? (
                    <span className="inline-flex items-center gap-1 text-caption font-medium text-fail">
                      <ShieldX className="size-3.5" strokeWidth={1.75} aria-hidden />
                      Refused
                    </span>
                  ) : null}
                </p>
                <p className="truncate text-caption text-muted-foreground" title={row.title}>
                  {row.title}
                </p>
                <p className="text-caption text-muted-foreground">
                  seen {timeOf(row.seen_at)} · {sourceName(row.source_api)}
                </p>
              </td>
              <td className="py-2 pr-2 text-right">
                <Money value={row.price_usd} seenAt={row.seen_at} source={row.source_api} simulated={row.simulated} />
              </td>
              <td className="tabular py-2 pr-2 text-right font-mono text-caption leading-5 text-secondary-text">{Math.round(row.age_min)} min</td>
              <td className={cn("tabular py-2 text-right font-mono text-caption leading-5", row.vs_median_pct < 0 ? "text-pass" : row.vs_median_pct > 0 ? "text-secondary-text" : "text-muted-foreground")}>
                {row.vs_median_pct === 0 ? "median" : `${row.vs_median_pct > 0 ? "+" : "−"}${Math.abs(row.vs_median_pct).toFixed(1)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <SqlBlock sql={data.sql} label="Price observations SQL" />
    </div>
  );
}
