// Receipt page content (PLAN §11.5 E, §3.7). Owner: D, built with C's components and reviewed by C.
// Verify banner, the request, provenance counts, three mandate cards, the chain as a filterable list,
// "Download receipt.json" and the public key.
import { Download, KeyRound, ReceiptText } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SimulatedTag, useSimulatedRunLabel } from "@/components/MockDataBadge";
import { HashText } from "@/components/common/HashText";
import { EmptyState, InlineError } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiFailure } from "@/lib/api";
import { plural } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { ProvenanceType, Receipt as ReceiptData, RunState, VerifyResult } from "@/lib/types";

import { ChainList } from "./ChainList";
import { IntakeCard, ProvenanceCounts } from "./IntakeCard";
import { JsonDisclosure } from "./JsonView";
import { ClosedMandateCard, OpenMandateCard, PaymentMandateCard } from "./MandateCards";
import { downloadJson, provenanceCountsFromRecords } from "./receiptFormat";
import { VerifyBanner } from "./VerifyBanner";

type Load = { phase: "loading" } | { phase: "ready"; receipt: ReceiptData } | { phase: "error"; error: ApiFailure };

function ReceiptSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading the receipt">
      <Skeleton className="h-24 w-full rounded-lg" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-40 rounded-lg" />
        <Skeleton className="h-40 rounded-lg" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-72 rounded-lg" />
        <Skeleton className="h-72 rounded-lg" />
        <Skeleton className="h-72 rounded-lg" />
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-lg" />
      ))}
    </div>
  );
}

export function Receipt({ runId }: { runId: string }) {
  const [load, setLoad] = useState<Load>({ phase: "loading" });
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const simLabel = useSimulatedRunLabel();
  const storeRun = useAppStore((s) => s.run);
  const [fetchedRun, setFetchedRun] = useState<RunState | null>(null);
  const run = storeRun && storeRun.run_id === runId ? storeRun : fetchedRun && fetchedRun.run_id === runId ? fetchedRun : null;

  const fetchReceipt = useCallback(() => {
    let cancelled = false;
    setLoad({ phase: "loading" });
    setVerify(null);
    api
      .receipt(runId)
      .then((receipt) => !cancelled && setLoad({ phase: "ready", receipt }))
      .catch((e: unknown) => !cancelled && setLoad({ phase: "error", error: e instanceof ApiFailure ? e : new ApiFailure(0, { error: "unknown", message: String(e), bom_line_ids: [] }) }));
    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => fetchReceipt(), [fetchReceipt]);

  // Provenance counts come from the run when we can get it; otherwise from the chain itself.
  useEffect(() => {
    if (storeRun && storeRun.run_id === runId) return;
    let cancelled = false;
    api
      .run(runId)
      .then((r) => !cancelled && setFetchedRun(r))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [runId, storeRun]);

  const receipt = load.phase === "ready" ? load.receipt : null;
  const intakeRecord = useMemo(() => receipt?.records.find((r) => r.kind === "intake") ?? null, [receipt]);
  const openSha = useMemo(() => {
    const rec = receipt?.records.find((r) => r.kind === "mandate_open") as Record<string, unknown> | undefined;
    return typeof rec?.mandate_sha256 === "string" ? rec.mandate_sha256 : null;
  }, [receipt]);
  const counts: { counts: Record<ProvenanceType, number>; source: "run" | "chain" } | null = useMemo(() => {
    if (run?.provenance_counts) return { counts: run.provenance_counts as Record<ProvenanceType, number>, source: "run" };
    return receipt ? { counts: provenanceCountsFromRecords(receipt.records), source: "chain" } : null;
  }, [run, receipt]);

  if (load.phase === "loading") return <ReceiptSkeleton />;

  if (load.phase === "error") {
    if (load.error.status === 404) {
      return (
        <div className="rounded-lg border border-border bg-surface">
          <EmptyState icon={ReceiptText} title="No receipt for this run">
            The receipt exists once a run has signed its open mandate. Check the link, or start a run from the landing page.
          </EmptyState>
        </div>
      );
    }
    return <InlineError title="Couldn't load the receipt" message={`${load.error.message} Nothing was changed.`} onRetry={fetchReceipt} />;
  }

  const r = load.receipt;
  const mockKey = r.public_key_jwk && (r.public_key_jwk as Record<string, unknown>).x === "MOCK";

  return (
    <div className="space-y-6">
      <VerifyBanner runId={runId} receipt={r} onResult={setVerify} />

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 className="text-h3 font-semibold text-foreground">Audit trail</h2>
        <span className="text-small text-muted-foreground">
          {plural(r.records.length, "record")} · head <HashText hash={r.head_hash} />
        </span>
        {r.simulated ? <SimulatedTag label={simLabel.long} /> : null}
        <Button variant="outline" className="ml-auto" onClick={() => downloadJson(`receipt_${runId}.json`, r)}>
          <Download aria-hidden />
          Download receipt.json
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <IntakeCard mandate={r.open_mandate} intakeRecord={intakeRecord} />
        {counts ? <ProvenanceCounts counts={counts.counts} source={counts.source} /> : null}
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-3">
        <OpenMandateCard mandate={r.open_mandate} sha256={openSha} />
        <ClosedMandateCard mandate={r.closed_mandate} />
        <PaymentMandateCard mandate={r.payment_mandate} />
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <h3 className="text-body-lg font-semibold text-foreground">The chain</h3>
          <p className="text-small text-muted-foreground">Each record's hash covers the record before it. Click a record for its JSON, or "prev" to follow the link back.</p>
        </div>
        <ChainList records={r.records} brokenAt={verify && !verify.ok ? verify.broken_at : null} />
      </section>

      <section className="space-y-2 rounded-lg border border-border bg-surface p-4">
        <p className="flex flex-wrap items-center gap-2 text-small font-medium text-foreground">
          <KeyRound className="size-4 text-secondary-text" strokeWidth={1.75} aria-hidden />
          Public key ({String((r.public_key_jwk as Record<string, unknown>).kid ?? "demo key")})
          {mockKey ? <SimulatedTag label="Mock key" /> : null}
        </p>
        <p className="text-caption text-muted-foreground">
          The mandates are signed with ES256. This demo key is generated by the backend and stands in for a key you would hold yourself.
        </p>
        <JsonDisclosure data={r.public_key_jwk} label="View key (JWK)" />
      </section>
    </div>
  );
}
