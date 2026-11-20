// Part panel (PLAN §11.6 core 1, M9): a 520 px sheet over the list and timeline; the part map stays visible.
// Header: name, quantity, status, the mesh chip ("Servo 2 of 6 · shoulder_lift"), the decision record's hash.
// Tabs: Offers (default) · Why · Sources · Prices. Opens from cached data in well under 200 ms.
import { CircleHelp, Package, X } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { HashText } from "@/components/common/HashText";
import { Money } from "@/components/common/Money";
import { InlineError } from "@/components/common/States";
import { StatusBadge, ToneBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { isOpenAssumption, ProvenanceChip } from "@/components/workspace/ProvenanceChip";
import { api, ApiFailure } from "@/lib/api";
import { money, plural, timeOf, viaText } from "@/lib/format";
import { useAppStore, type PanelTab } from "@/lib/store";
import type { OfferRow, PartPanel as PartPanelData, RunState } from "@/lib/types";

import { ActionBadge } from "./ActionBadge";
import { OfferTable, StoreLink } from "./OfferTable";
import { PricesTab } from "./PricesTab";
import { SourcesTab } from "./SourcesTab";
import { WhyTab } from "./WhyTab";

const cache = new Map<string, PartPanelData>();
export function forgetPanels(runId: string) {
  for (const key of cache.keys()) if (key.startsWith(`${runId}/`)) cache.delete(key);
}

function usePanel(runId: string, bomLineId: string, version: string) {
  const key = `${runId}/${bomLineId}`;
  const [panel, setPanel] = useState<PartPanelData | null>(cache.get(key) ?? null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    let cancelled = false;
    setError(null);
    setPanel(cache.get(key) ?? null);
    api
      .partPanel(runId, bomLineId)
      .then((p) => {
        cache.set(key, p);
        if (!cancelled) setPanel(p);
      })
      .catch((e: unknown) => {
        if (!cancelled && !cache.has(key)) setError(e instanceof ApiFailure ? e.message : "Couldn't load this part.");
      });
    return () => {
      cancelled = true;
    };
    // `version` (the run's chain head) refetches when the run changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, runId, bomLineId, version]);
  useEffect(() => load(), [load]);
  return { panel: panel && panel.bom_line_id === bomLineId ? panel : null, error, reload: load };
}

function PanelSkeleton() {
  return (
    <div className="space-y-4 p-5" aria-busy="true" aria-label="Loading the part">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-7 w-3/4" />
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-28 w-full" />
      {Array.from({ length: 4 }, (_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  );
}

function ChosenCard({ chosen, qty }: { chosen: OfferRow[]; qty: number }) {
  const first = chosen[0];
  const total = chosen.reduce((sum, o) => sum + o.line_usd, 0);
  const sim = chosen.some((o) => o.simulated);
  return (
    <section className="rounded-lg border border-brand/40 bg-brand-tint/60 p-4" aria-label="Chosen offer">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="flex flex-wrap items-center gap-1.5 text-caption font-medium text-brand">
            Chosen
            <ActionBadge level={first.action_level} reason={first.downgrade_reason} />
          </p>
          <p className="text-body font-semibold">{first.store_name}</p>
          {chosen.map((o) => (
            <p key={o.offer_id} className="text-small text-secondary-text">
              <span className="tabular font-mono">
                {o.packs_needed} × {o.units_per_pack > 1 ? `${o.units_per_pack}-pack` : "single"} {money(o.price_usd)}
              </span>{" "}
              · {o.title}
            </p>
          ))}
        </div>
        <div className="shrink-0 text-right">
          <Money value={total} seenAt={first.seen_at} source={first.source_api} mockOf={first.mock_of} simulated={sim} className="text-h3 font-semibold" />
          <p className="text-caption text-muted-foreground">for {qty}</p>
        </div>
      </div>
      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted-foreground">
        <span>
          seen {timeOf(first.seen_at)} · {viaText(first.source_api, first.mock_of)}
        </span>
        <span>Shipping and tax are added at the store</span>
        <StoreLink url={first.url} className="ml-auto" />
      </p>
    </section>
  );
}

export function PartPanel({ run, bomLineId, onClose }: { run: RunState; bomLineId: string; onClose: () => void }) {
  const runId = run.run_id;
  const { panel, error, reload } = usePanel(runId, bomLineId, run.head_hash);
  const tab = useAppStore((s) => s.panelTab);
  const setTab = useAppStore((s) => s.setPanelTab);
  const meshLabel = useAppStore((s) => s.selectedMeshLabel);
  const setCart = useAppStore((s) => s.setCart);
  const setRun = useAppStore((s) => s.setRun);
  const [busy, setBusy] = useState(false);
  const line = run.bom.find((l) => l.bom_line_id === bomLineId);
  const editable = run.status !== "approved" && run.status !== "done";

  const swapTo = async (offer: OfferRow) => {
    setBusy(true);
    try {
      const cart = await api.cartEdit(runId, { op: "swap_offer", bom_line_id: bomLineId, offer_id: offer.offer_id });
      setCart(cart);
      forgetPanels(runId);
      toast(`Swapped to ${offer.store_name}`, { description: cart.simulated ? "Mock mode: the edit was accepted, but fixture data doesn't change." : "The cart was re-planned with your choice pinned." });
      void api.run(runId).then(setRun).catch(() => undefined);
      reload();
    } catch (e) {
      toast(e instanceof ApiFailure ? e.message : "Couldn't swap the offer. Nothing changed.");
    } finally {
      setBusy(false);
    }
  };

  const chosen = panel?.offers.filter((o) => o.status === "chosen") ?? [];
  const provenance = panel?.provenance ?? line?.provenance;
  const openAssumption = provenance ? isOpenAssumption(provenance) : false;

  return (
    <motion.aside
      role="complementary"
      aria-label="Part panel"
      initial={{ x: 32, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 32, opacity: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="absolute inset-y-0 right-0 z-30 flex w-(--b2c-panel-w) max-w-full flex-col border-l border-border bg-surface shadow-e2"
    >
      <header className="shrink-0 space-y-2 border-b border-border px-5 pt-4 pb-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-caption text-muted-foreground">
            Part <span className="font-mono">{bomLineId}</span> · quantity <span className="tabular font-mono">{panel?.qty ?? line?.qty ?? "…"}</span>
            {(panel?.line_kind ?? line?.line_kind) && (panel?.line_kind ?? line?.line_kind) !== "part" ? ` · ${panel?.line_kind ?? line?.line_kind}` : ""}
          </p>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close the part panel (Esc)">
            <X aria-hidden />
          </Button>
        </div>
        <h2 className="text-h3 font-semibold tracking-tight">{panel?.name ?? line?.raw_name ?? "Loading…"}</h2>
        <div className="flex flex-wrap items-center gap-1.5">
          {(panel ?? line) ? <StatusBadge status={(panel ?? line)!.status} /> : null}
          {openAssumption ? (
            <ToneBadge tone="warn" icon={CircleHelp}>
              Assumed: confirm it
            </ToneBadge>
          ) : null}
          {provenance ? <ProvenanceChip provenance={provenance} detail={false} /> : null}
          {meshLabel ? (
            <span className="inline-flex h-6 items-center gap-1 rounded-sm bg-muted px-1.5 text-caption text-secondary-text">
              <Package className="size-3.5" strokeWidth={1.75} aria-hidden />
              {meshLabel}
            </span>
          ) : panel && panel.mesh_keys.length ? (
            <span className="inline-flex h-6 items-center rounded-sm bg-muted px-1.5 text-caption text-secondary-text">{plural(panel.mesh_keys.length, "mesh", "meshes")} on the model</span>
          ) : null}
          {panel ? <HashText hash={panel.record_hash} label="rec" className="ml-auto" /> : null}
        </div>
      </header>

      {error ? (
        <div className="p-5">
          <InlineError title="This part didn't load" message={`${error} The parts list and the model still work.`} onRetry={reload} />
        </div>
      ) : !panel ? (
        <PanelSkeleton />
      ) : (
        <Tabs value={tab} onValueChange={(v) => setTab(v as PanelTab)} className="min-h-0 flex-1 gap-0">
          <div className="shrink-0 border-b border-border px-5 py-2">
            <TabsList className="w-full">
              <TabsTrigger value="offers">Offers</TabsTrigger>
              <TabsTrigger value="why">Why</TabsTrigger>
              <TabsTrigger value="sources">Sources</TabsTrigger>
              <TabsTrigger value="prices">Prices</TabsTrigger>
            </TabsList>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            <TabsContent value="offers" className="space-y-4">
              {chosen.length ? (
                <ChosenCard chosen={chosen} qty={panel.qty} />
              ) : (
                <section className="rounded-lg border border-border bg-muted p-4 text-small text-secondary-text">
                  {panel.owned ? `Nothing to buy. Remembered: ${panel.owned.memory_text}.` : panel.status === "not_found" ? "Not found in your stores. The rejected and refused listings below say why." : panel.status === "skipped" || panel.status === "owned" ? `Left out of the cart${line?.owned_note ? `: ${line.owned_note}` : "."}` : "No offer is chosen for this line yet."}
                </section>
              )}
              {panel.offers.length || panel.refusals.length ? (
                <div className="space-y-2">
                  <h3 className="text-small font-semibold">Every store</h3>
                  <OfferTable offers={panel.offers} qty={panel.qty} refusals={panel.refusals} onUse={editable ? (o) => void swapTo(o) : undefined} busy={busy} />
                </div>
              ) : null}
            </TabsContent>
            <TabsContent value="why">
              <WhyTab panel={panel} />
            </TabsContent>
            <TabsContent value="sources">
              <SourcesTab panel={panel} runId={runId} photo={run.view.photo} template={run.template} />
            </TabsContent>
            <TabsContent value="prices">
              <PricesTab runId={runId} bomLineId={bomLineId} storeNames={Object.fromEntries(panel.offers.map((o) => [o.store_id, o.store_name]))} />
            </TabsContent>
          </div>
        </Tabs>
      )}
    </motion.aside>
  );
}
