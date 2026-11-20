// Library / Carts / Receipts: the runs this backend knows, each linking to its real page. Nothing is listed
// that does not exist: runs live in the backend's memory, so a restart empties these lists.
import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { Money } from "@/components/common/Money";
import { SimulatedTag } from "@/components/MockDataBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiFailure } from "@/lib/api";
import { BUILD_TYPE_LABEL, dayOf, plural, reasonCode, timeOf } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

export type RunsView = "library" | "carts" | "receipts";

const COPY: Record<RunsView, { title: string; lead: string; empty: string; cta: string; href: (id: string) => string; keep: (r: RunSummary) => boolean }> = {
  library: {
    title: "Library",
    lead: "Every run on this backend, with its 3D workspace.",
    empty: "No runs yet. Start a build and it will be listed here.",
    cta: "Open 3D workspace",
    href: (id) => `/run/${id}`,
    keep: () => true,
  },
  carts: {
    title: "Carts",
    lead: "Runs that have a cart to review, approve or check out.",
    empty: "No carts yet. A cart appears once a run has found offers.",
    cta: "Review cart",
    href: (id) => `/run/${id}/cart`,
    keep: (r) => typeof r.total_usd === "number" && r.status !== "running" && r.status !== "error",
  },
  receipts: {
    title: "Receipts",
    lead: "The audit trail of each run: the signed mandate, every decision and refusal, and Verify.",
    empty: "No receipts yet. Every run gets one as soon as it starts.",
    cta: "Open receipt",
    href: (id) => `/run/${id}/receipt`,
    keep: () => true,
  },
};

export function RunsList({ view }: { view: RunsView }) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const copy = COPY[view];

  useEffect(() => {
    let cancelled = false;
    setRuns(null);
    setError(null);
    api
      .runs()
      .then((r) => !cancelled && setRuns(r))
      .catch((e) => !cancelled && setError(e instanceof ApiFailure ? e.message : "Couldn't load the runs."));
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const rows = (runs ?? []).filter(copy.keep);
  return (
    <div className="mx-auto w-full max-w-[860px] px-6 py-8">
      <h1 className="text-h2 font-semibold tracking-tight">{copy.title}</h1>
      <p className="mt-1 text-body text-secondary-text">{copy.lead}</p>
      <div className="mt-6 rounded-lg border border-border bg-surface">
        {error ? (
          <div className="flex items-center gap-3 px-4 py-4" role="alert">
            <p className="text-body text-fail">{error}</p>
            <Button variant="outline" className="ml-auto h-8 px-3" onClick={() => setAttempt((n) => n + 1)}>
              Retry
            </Button>
          </div>
        ) : runs === null ? (
          <div className="space-y-3 px-4 py-4" aria-busy="true">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-5 w-3/5" />
          </div>
        ) : !rows.length ? (
          <div className="flex flex-wrap items-center gap-3 px-4 py-6">
            <p className="text-body text-secondary-text">{copy.empty}</p>
            <Button asChild className="ml-auto h-8 px-3">
              <Link to="/">New build</Link>
            </Button>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {rows.map((r) => (
              <li key={r.run_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body font-medium" title={r.title}>
                    {r.title}
                  </p>
                  <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted-foreground">
                    <span>{BUILD_TYPE_LABEL[r.build_type] ?? r.build_type}</span>
                    <span>· {reasonCode(r.status)}</span>
                    {view !== "library" ? <span>· cart {reasonCode(r.cart_state)}</span> : null}
                    <span>
                      · {plural(r.lines, "line")}, {plural(r.stores, "store")}
                    </span>
                    <span>
                      · {dayOf(r.created_at)} {timeOf(r.created_at)}
                    </span>
                    <span className="font-mono">{r.run_id}</span>
                    {r.simulated ? <SimulatedTag label="Simulated store data" /> : null}
                  </p>
                </div>
                {typeof r.total_usd === "number" ? <Money value={r.total_usd} simulated={r.simulated} className="text-body" /> : <span className="text-small text-muted-foreground">no total yet</span>}
                <Button asChild variant="outline" className="h-8 px-3">
                  <Link to={copy.href(r.run_id)}>
                    {copy.cta} <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
