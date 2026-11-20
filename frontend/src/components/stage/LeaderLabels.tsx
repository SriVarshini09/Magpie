// Two-column leader-line labels (PLAN §11.12 stretch), after the Labels class of the `exploded-view` skill,
// ported to r3f with DOM labels: labels sit in two columns at the stage's edges, keep their parts' vertical
// order, push apart when they would overlap, and a leader line runs from each label to its part.
// Shown while the model is pulled apart or a line is isolated. One overlay, no React root per label.
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useState, type RefObject } from "react";
import { Vector3, type Mesh } from "three";

import { useAppStore } from "@/lib/store";
import type { StageData } from "@/lib/stage";
import { cn } from "@/lib/utils";

import type { StageEntry } from "./Stage3D";
import { useStageView } from "./viewStore";

type Item = { key: string; lineId: string | null; label: string; short: string; primary: boolean };

/** What the DOM layer and the in-canvas projector share. */
export type LabelBus = {
  items: Item[];
  labels: Map<string, HTMLElement>;
  paths: Map<string, SVGPathElement>;
  dots: Map<string, SVGCircleElement>;
};

export function createLabelBus(): LabelBus {
  return { items: [], labels: new Map(), paths: new Map(), dots: new Map() };
}

/** The explode slider value from which the labels show. */
const SHOW_FROM = 0.3;
/** More labels than this and only the first mesh of each line gets one. */
const MAX_LABELS = 18;
/** Clear of the colour switch and legend (top) and the stage chips (bottom). */
const TOP = 128;
const BOTTOM = 52;
const SIDE = 12;
const GAP = 5;
const MIN_WIDTH = 560;

const point = new Vector3();
type Placed = { item: Item; el: HTMLElement; sx: number; sy: number; w: number; h: number; y: number };

/** Runs inside the canvas: projects each labelled part and lays the two columns out, every frame. */
export function LeaderLabelProjector({ bus, entries }: { bus: LabelBus; entries: RefObject<Map<string, StageEntry>> }) {
  useFrame(({ camera, size }) => {
    if (!bus.items.length) return;
    const shown: Placed[] = [];
    // Narrow stage, narrow labels: the model keeps the middle.
    const maxWidth = `${Math.round(Math.min(220, size.width * 0.23))}px`;
    for (const item of bus.items) {
      const el = bus.labels.get(item.key);
      const path = bus.paths.get(item.key);
      const dot = bus.dots.get(item.key);
      if (!el || !path || !dot) continue;
      if (el.style.maxWidth !== maxWidth) el.style.maxWidth = maxWidth;
      const entry = entries.current.get(item.key);
      const mesh = entry?.object as Mesh | undefined;
      let visible = Boolean(mesh) && size.width >= MIN_WIDTH && mesh!.parent?.visible !== false;
      if (visible) {
        const box = mesh!.geometry.boundingBox;
        if (box) box.getCenter(point);
        else point.set(0, 0, 0);
        point.applyMatrix4(mesh!.matrixWorld).project(camera);
        visible = point.z < 1 && Math.abs(point.x) < 1.02 && Math.abs(point.y) < 1.02;
      }
      if (!visible) {
        el.style.visibility = path.style.visibility = dot.style.visibility = "hidden";
        continue;
      }
      shown.push({ item, el, sx: (point.x * 0.5 + 0.5) * size.width, sy: (-point.y * 0.5 + 0.5) * size.height, w: el.offsetWidth || 120, h: el.offsetHeight || 24, y: 0 });
    }
    if (!shown.length) return;

    const rowHeight = shown[0].h + GAP;
    const rows = Math.max(1, Math.floor((size.height - TOP - BOTTOM + GAP) / rowHeight));
    const mid = size.width / 2;
    // Split by side, then move the labels nearest the middle across if one column is over-full.
    shown.sort((a, b) => a.sx - b.sx);
    let split = shown.findIndex((p) => p.sx >= mid);
    if (split < 0) split = shown.length;
    split = Math.min(Math.max(split, shown.length - rows), rows);
    const columns = [shown.slice(0, split), shown.slice(split)];

    for (const [c, column] of columns.entries()) {
      const left = c === 0;
      column.sort((a, b) => a.sy - b.sy);
      // Too many for the height: the first mesh of each line keeps its label.
      while (column.length > rows) {
        let drop = column.length - 1;
        for (let i = column.length - 1; i >= 0; i--) {
          if (!column[i].item.primary) {
            drop = i;
            break;
          }
        }
        const [gone] = column.splice(drop, 1);
        gone.el.style.visibility = "hidden";
        bus.paths.get(gone.item.key)!.style.visibility = bus.dots.get(gone.item.key)!.style.visibility = "hidden";
      }
      let y = TOP;
      for (const p of column) {
        p.y = Math.max(p.sy - p.h / 2, y);
        y = p.y + p.h + GAP;
      }
      // Shift the column up if it runs off the bottom.
      let limit = size.height - BOTTOM;
      for (let i = column.length - 1; i >= 0; i--) {
        const p = column[i];
        if (p.y + p.h > limit) p.y = limit - p.h;
        limit = p.y - GAP;
      }
      for (const p of column) {
        const path = bus.paths.get(p.item.key)!;
        const dot = bus.dots.get(p.item.key)!;
        const x = left ? SIDE : size.width - SIDE - p.w;
        p.el.style.transform = `translate(${x.toFixed(1)}px, ${p.y.toFixed(1)}px)`;
        const ex = left ? x + p.w + 4 : x - 4;
        const ey = p.y + p.h / 2;
        const bend = left ? ex + 16 : ex - 16;
        path.setAttribute("d", `M${ex.toFixed(1)},${ey.toFixed(1)} L${bend.toFixed(1)},${ey.toFixed(1)} L${p.sx.toFixed(1)},${p.sy.toFixed(1)}`);
        dot.setAttribute("cx", p.sx.toFixed(1));
        dot.setAttribute("cy", p.sy.toFixed(1));
        p.el.style.visibility = path.style.visibility = dot.style.visibility = "visible";
      }
    }
  });
  return null;
}

function Label({ item, bus }: { item: Item; bus: LabelBus }) {
  const active = useAppStore((s) => item.lineId !== null && (s.hoveredLineId === item.lineId || s.selectedLineId === item.lineId));
  const exact = useAppStore((s) => s.selectedMeshKey === item.key);
  return (
    <button
      type="button"
      tabIndex={-1}
      ref={(el) => {
        if (el) bus.labels.set(item.key, el);
        else bus.labels.delete(item.key);
      }}
      style={{ visibility: "hidden" }}
      title={item.label}
      onPointerEnter={() => item.lineId && useAppStore.getState().hover(item.lineId)}
      onPointerLeave={() => {
        const s = useAppStore.getState();
        if (s.hoveredLineId === item.lineId) s.hover(null);
      }}
      onClick={() => item.lineId && useAppStore.getState().select(item.lineId, item.key, undefined, item.label)}
      className={cn(
        "pointer-events-auto absolute top-0 left-0 flex h-6 cursor-pointer items-center gap-1.5 rounded-sm border px-2 text-caption whitespace-nowrap will-change-transform transition-colors duration-150",
        active || exact ? "border-brand bg-stage-surface text-stage-text" : "border-stage-border bg-stage-surface/90 text-stage-muted hover:text-stage-text",
      )}
    >
      <span className="truncate font-medium">{item.short}</span>
    </button>
  );
}

function Leader({ item, bus }: { item: Item; bus: LabelBus }) {
  const active = useAppStore((s) => item.lineId !== null && (s.hoveredLineId === item.lineId || s.selectedLineId === item.lineId));
  const colour = active ? "var(--b2c-brand)" : "var(--b2c-stage-muted)";
  return (
    <g>
      <path
        ref={(el) => {
          if (el) bus.paths.set(item.key, el);
          else bus.paths.delete(item.key);
        }}
        fill="none"
        stroke={colour}
        strokeWidth={active ? 1.5 : 1}
        strokeOpacity={active ? 1 : 0.7}
        style={{ visibility: "hidden" }}
      />
      <circle
        ref={(el) => {
          if (el) bus.dots.set(item.key, el);
          else bus.dots.delete(item.key);
        }}
        r={active ? 3.5 : 2.5}
        fill={colour}
        style={{ visibility: "hidden" }}
      />
    </g>
  );
}

/** The DOM half: decides which parts get a label and draws the labels and their leader lines. */
export function LeaderLabelLayer({ bus, entries, data, readyKey }: { bus: LabelBus; entries: RefObject<Map<string, StageEntry>>; data: StageData; readyKey: string }) {
  const exploded = useAppStore((s) => s.explode > SHOW_FROM);
  const isolatedLineId = useStageView((s) => s.isolatedLineId);
  const hidden = useStageView((s) => s.hidden);
  const on = exploded || isolatedLineId !== null;
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    if (!on) return setItems([]);
    let all: Item[] = [...entries.current.entries()].filter(([key]) => !hidden.has(key)).map(([key, e]) => ({ key, lineId: e.lineId, label: e.label, short: e.shortLabel, primary: e.primary }));
    if (isolatedLineId) all = all.filter((i) => i.lineId === isolatedLineId);
    if (all.length > MAX_LABELS) {
      // One label per line, named for the line.
      const seen = new Set<string>();
      const perLine = all.filter((i) => i.lineId !== null && !seen.has(i.lineId) && Boolean(seen.add(i.lineId))).map((i) => ({ ...i, primary: true, short: data.lines.get(i.lineId!)?.name ?? i.short }));
      // A model with no lines behind it (the gallery) keeps its mesh names.
      all = perLine.length ? perLine : all.slice(0, MAX_LABELS);
    }
    setItems(all);
    // `data` is read for names only; the set of labels follows the meshes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on, isolatedLineId, hidden, readyKey, entries]);

  useEffect(() => {
    bus.items = items;
    useStageView.getState().setLabelsOn(items.length > 0);
  }, [bus, items]);
  useEffect(
    () => () => {
      bus.items = [];
      useStageView.getState().setLabelsOn(false);
    },
    [bus],
  );

  const leaders = useMemo(() => items.map((item) => <Leader key={item.key} item={item} bus={bus} />), [items, bus]);
  if (!items.length) return null;
  return (
    <div className="pointer-events-none absolute inset-0 animate-in fade-in duration-300" data-stage-labels>
      <svg className="absolute inset-0 size-full overflow-visible" aria-hidden>
        {leaders}
      </svg>
      {items.map((item) => (
        <Label key={item.key} item={item} bus={bus} />
      ))}
    </div>
  );
}
