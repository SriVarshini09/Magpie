// View gallery (/views): every view the router can show, with example data, for checking a model before it
// is switched on (PLAN §11.12). Not linked from the product. Nothing here is a price or an offer.
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

import { Logo } from "@/components/brand/Logo";
import { ArmViewer } from "@/components/workspace/ArmViewer";
import { KitView } from "@/components/workspace/KitView";
import { PartsDiagram } from "@/components/workspace/PartsDiagram";
import { PhotoHotspots } from "@/components/workspace/PhotoHotspots";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { StageData } from "@/lib/stage";
import type { PartCategory, ViewData } from "@/lib/types";
import { cn } from "@/lib/utils";
import { demoView } from "@/models/demo";
import { KIT_ORDER } from "@/models/kitTokens";
import { ProceduralView } from "@/models/ProceduralView";

const TABS = ["quadcopter", "rc_car", "claw", "so101", "kit", "diagram", "photo"] as const;
type Tab = (typeof TABS)[number];
const LABEL: Record<Tab, string> = { quadcopter: "Quadcopter", rc_car: "RC car", claw: "Claw", so101: "SO-101 arm", kit: "Kit tokens", diagram: "Board diagram", photo: "Photo hotspots" };

const EMPTY: StageData = { lines: new Map(), storeSlot: new Map(), storeNames: new Map() };

export function ViewsPage() {
  const [tab, setTab] = useState<Tab>("quadcopter");
  const [remote, setRemote] = useState<Partial<Record<"diagram" | "photo", ViewData>>>({});
  const explode = useAppStore((s) => s.explode);
  const setExplode = useAppStore((s) => s.setExplode);
  const clearSelection = useAppStore((s) => s.clearSelection);

  useEffect(() => {
    api.mockView("view_diagram_esp32.json").then((v) => setRemote((r) => ({ ...r, diagram: v }))).catch(() => undefined);
    api.mockView("view_photo_sample.json").then((v) => setRemote((r) => ({ ...r, photo: v }))).catch(() => undefined);
  }, []);
  useEffect(() => {
    clearSelection();
    setExplode(0);
  }, [tab, clearSelection, setExplode]);

  const model = useMemo(() => (tab === "quadcopter" || tab === "rc_car" || tab === "claw" || tab === "so101" ? demoView(tab) : null), [tab]);
  const kit = useMemo(() => {
    const cats: PartCategory[] = [...KIT_ORDER, "tool"];
    const view: ViewData = { kind: "kit", parts: [], tray: [], note: "Example tokens.", simulated: false, tokens: cats.map((c, i) => ({ bom_line_id: `k${i}`, category: c, qty: i % 3 === 0 ? 4 : 1, label: c.replace("_", " ") })) };
    return view;
  }, []);

  return (
    <div className="flex h-screen flex-col bg-page">
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-surface px-(--b2c-gutter)">
        <Link to="/">
          <Logo />
        </Link>
        <span className="text-small text-muted-foreground">View gallery · example data, no run behind it</span>
        <nav className="ml-auto flex gap-1" aria-label="Views">
          {TABS.map((t) => (
            <button key={t} type="button" onClick={() => setTab(t)} aria-pressed={tab === t} className={cn("h-8 rounded-md px-3 text-small", tab === t ? "bg-ink text-white" : "text-secondary-text hover:bg-muted")}>
              {LABEL[t]}
            </button>
          ))}
        </nav>
        <label className="flex items-center gap-2 text-small text-secondary-text">
          Pull apart
          <input type="range" min={0} max={1} step={0.01} value={explode} onChange={(e) => setExplode(Number(e.target.value))} className="w-28 accent-brand" />
        </label>
      </header>
      <main className="min-h-0 flex-1 p-(--b2c-gutter)">
        <div className="stage relative size-full overflow-hidden rounded-2xl border border-stage-border">
          {model && tab === "so101" ? <ArmViewer view={model.view} data={model.data} /> : null}
          {model && tab !== "so101" ? <ProceduralView key={tab} view={model.view} data={model.data} /> : null}
          {tab === "kit" ? <KitView view={kit} data={EMPTY} /> : null}
          {tab === "diagram" ? remote.diagram ? <PartsDiagram view={remote.diagram} data={EMPTY} checks={[]} title="Example" /> : <Waiting /> : null}
          {tab === "photo" ? (
            remote.photo ? (
              <div className="flex size-full items-center justify-center p-8">
                <PhotoHotspots view={remote.photo} data={EMPTY} lines={[]} />
              </div>
            ) : (
              <Waiting />
            )
          ) : null}
        </div>
      </main>
    </div>
  );
}

function Waiting() {
  return <p className="flex size-full items-center justify-center text-small text-stage-muted">This sample comes from the mock backend. Start it in mock mode to see it.</p>;
}
