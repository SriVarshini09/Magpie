// View router (PLAN §3.20): one slot, one selection store, one part panel. RunState.view says what to render.
// Fallback order when a view is not ready: urdf → diagram; procedural → kit → diagram; kit → diagram.
// The stage carries the colour-mode switch and legend, the Photo / Model toggle, the off-model tray and,
// under it, the view's honest label ("Illustrative model…", "Model from the project's own repository.").
import { Blocks, Box, Image as ImageIcon, Info, LayoutGrid, Workflow } from "lucide-react";
import { Component, useMemo, useState, type ReactNode } from "react";

import { ProceduralView, hasProceduralModel } from "@/models/ProceduralView";
import { BUILD_TYPE_LABEL } from "@/lib/format";
import { useAppStore, type StageMode } from "@/lib/store";
import { buildStageData, type StageData } from "@/lib/stage";
import type { RunState, ViewData } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ArmViewer } from "./ArmViewer";
import { ColorModeSwitch } from "./ColorModeSwitch";
import { KitView, kitTokensFor } from "./KitView";
import { Legend } from "./Legend";
import { OffModelTray } from "./OffModelTray";
import { PartsDiagram } from "./PartsDiagram";
import { PhotoHotspots } from "./PhotoHotspots";

type Resolved = "urdf" | "procedural" | "kit" | "diagram";

/** A WebGL failure (no GPU, lost context) must never take the page down: the diagram takes over. */
class StageBoundary extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function resolve(view: ViewData, data: StageData, failed3d: boolean): Resolved {
  const canKit = !failed3d && kitTokensFor(view, data).length > 0;
  if (view.kind === "urdf") return failed3d ? "diagram" : "urdf";
  if (view.kind === "procedural") return !failed3d && hasProceduralModel(view) ? "procedural" : canKit ? "kit" : "diagram";
  if (view.kind === "kit" || view.kind === "generated") return canKit ? "kit" : "diagram";
  return "diagram";
}

function ModeButton({ mode, current, onClick, icon: Icon, children }: { mode: StageMode; current: StageMode; onClick: (m: StageMode) => void; icon: typeof Box; children: ReactNode }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={mode === current}
      onClick={() => onClick(mode)}
      className={cn("inline-flex h-7 items-center gap-1.5 rounded-sm px-2.5 text-caption font-medium transition-colors duration-150", mode === current ? "bg-stage-text text-stage" : "text-stage-muted hover:text-stage-text")}
    >
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
      {children}
    </button>
  );
}

function ExplodeSlider() {
  const explode = useAppStore((s) => s.explode);
  const setExplode = useAppStore((s) => s.setExplode);
  return (
    <label className="flex h-8 items-center gap-2 rounded-md border border-stage-border bg-stage-surface/90 px-2.5 text-caption text-stage-muted">
      <Blocks className="size-3.5" strokeWidth={1.75} aria-hidden />
      Pull apart
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={explode}
        onChange={(e) => setExplode(Number(e.target.value))}
        aria-label="Pull the model apart"
        className="h-1 w-24 cursor-pointer appearance-none rounded-full bg-stage-border accent-brand"
      />
    </label>
  );
}

export function ViewRouter({ run, className }: { run: RunState; className?: string }) {
  const view = run.view;
  const data = useMemo(() => buildStageData(run), [run]);
  const [failed3d, setFailed3d] = useState(false);
  const stageMode = useAppStore((s) => s.stageMode);
  const setStageMode = useAppStore((s) => s.setStageMode);
  const setExplode = useAppStore((s) => s.setExplode);

  const base = resolve(view, data, failed3d);
  const hasPhoto = Boolean(view.photo);
  const canKit = !failed3d && base !== "kit" && base !== "diagram" && kitTokensFor(view, data).length > 0;
  const mode: StageMode = stageMode === "photo" && !hasPhoto ? "model" : stageMode === "kit" && !canKit ? "model" : stageMode;
  const shown: Resolved | "photo" = mode === "photo" ? "photo" : mode === "kit" ? "kit" : base;
  const is3d = shown === "urdf" || shown === "procedural";
  const title = run.intake.summary || BUILD_TYPE_LABEL[run.build_type];

  // Lines with no mesh, node or token in the shown view go to the tray, so every line stays reachable.
  const trayIds = useMemo(() => {
    if (shown === "kit") return run.bom.filter((l) => !l.category).map((l) => l.bom_line_id);
    if (shown === "photo") {
      const boxed = new Set((view.photo?.regions ?? []).map((r) => r.bom_line_id));
      return run.bom.filter((l) => !boxed.has(l.bom_line_id)).map((l) => l.bom_line_id);
    }
    if (shown === "diagram" && !view.diagram?.nodes.length) return run.bom.filter((l) => view.tray.includes(l.bom_line_id) || l.line_kind === "tool").map((l) => l.bom_line_id);
    const drawn = new Set(shown === "diagram" ? (view.diagram?.nodes ?? []).map((n) => n.bom_line_id) : view.parts.map((p) => p.bom_line_id));
    return run.bom.filter((l) => !drawn.has(l.bom_line_id)).map((l) => l.bom_line_id);
  }, [shown, run.bom, view]);

  const note =
    shown === "photo"
      ? "Your photo. Boxes mark where each part was seen; a dashed box is an approximate region."
      : shown === "kit" && base !== "kit"
        ? "Kit view: every part laid out on the table with its price."
        : shown === "kit" && view.kind !== "kit"
          ? "No model for this build yet, so this is the kit view: one token per line, shaped by category."
          : shown === "diagram" && (view.kind === "urdf" || view.kind === "procedural")
            ? "The 3D view isn't available here, so the same slot shows the parts as a diagram."
            : shown === "diagram" && view.kind !== "diagram"
              ? "Parts shown as a diagram. Lines are the compatibility checks."
              : view.note || "Illustrative view.";

  const pick = (m: StageMode) => {
    setStageMode(m);
    if (m !== "model") setExplode(0);
  };

  return (
    <section aria-label="Part map" className={cn("flex min-h-0 flex-col gap-2", className)}>
      <div className="stage relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-stage-border">
        <div className="relative min-h-0 flex-1">
          <div className="absolute inset-0">
            <StageBoundary key={shown} onError={() => setFailed3d(true)}>
              {shown === "urdf" ? <ArmViewer view={view} data={data} onError={() => setFailed3d(true)} /> : null}
              {shown === "procedural" ? <ProceduralView view={view} data={data} /> : null}
              {shown === "kit" ? <KitView view={view} data={data} /> : null}
              {shown === "diagram" ? <PartsDiagram view={view} data={data} checks={run.checks} title={title} /> : null}
              {shown === "photo" ? (
                <div className="flex size-full items-center justify-center p-6 pt-16">
                  <PhotoHotspots view={view} data={data} lines={run.bom} className="max-h-full" />
                </div>
              ) : null}
            </StageBoundary>
          </div>

          <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-3">
            <div className="pointer-events-auto flex flex-col items-start gap-2.5">
              <ColorModeSwitch />
              <div className="rounded-md bg-stage/60 px-2 py-1.5 backdrop-blur-sm">
                <Legend data={data} />
              </div>
            </div>
            <div className="pointer-events-auto flex flex-col items-end gap-2">
              {hasPhoto || canKit ? (
                <div role="radiogroup" aria-label="View" className="inline-flex rounded-md border border-stage-border bg-stage-surface/90 p-0.5">
                  {hasPhoto ? (
                    <ModeButton mode="photo" current={mode} onClick={pick} icon={ImageIcon}>
                      Photo
                    </ModeButton>
                  ) : null}
                  <ModeButton mode="model" current={mode} onClick={pick} icon={base === "diagram" ? Workflow : Box}>
                    {base === "diagram" ? "Diagram" : "Model"}
                  </ModeButton>
                  {canKit ? (
                    <ModeButton mode="kit" current={mode} onClick={pick} icon={LayoutGrid}>
                      Kit
                    </ModeButton>
                  ) : null}
                </div>
              ) : null}
              {is3d ? <ExplodeSlider /> : null}
            </div>
          </div>

          {shown === "diagram" && view.diagram?.nodes.length ? (
            <p className="pointer-events-none absolute inset-x-0 bottom-2 text-center text-caption text-stage-muted">
              Lines are the compatibility rules: <span className="text-pass">green pass</span> · <span className="text-warn">amber needs your check</span> · <span className="text-fail">red fail</span>
            </p>
          ) : null}
        </div>
        <OffModelTray lineIds={trayIds} data={data} title={shown === "diagram" ? "Not on the board" : shown === "photo" ? "Not in the photo" : shown === "kit" ? "Not in the kit view" : "Not on the model"} />
      </div>
      <p className="flex items-center gap-1.5 px-1 text-caption text-muted-foreground">
        <Info className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
        {note}
        {is3d ? <span className="ml-auto shrink-0">Drag to rotate · scroll to zoom · click a part</span> : null}
      </p>
    </section>
  );
}
