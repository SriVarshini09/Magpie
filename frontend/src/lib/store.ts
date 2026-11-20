// App state (zustand). Owner: C. One selection store for every view (PLAN §3.20, §11.6 core 2).
import { create } from "zustand";

import type { Event, Health, RunState, UniversalCart } from "@/lib/types";

export type ColourMode = "status" | "store" | "checkout";
export type StreamState = "idle" | "connecting" | "open" | "closed" | "error";
export type PanelTab = "offers" | "why" | "sources" | "prices";
export type StageMode = "model" | "photo" | "kit";

type SelectionSlice = {
  /** bom_line_id of the selected part: list row, mesh, diagram node, kit token or photo box. */
  selectedLineId: string | null;
  hoveredLineId: string | null;
  /** The mesh (or node) that was actually clicked, when a line has several (six servos). */
  selectedMeshKey: string | null;
  /** "Servo 2 of 6 · shoulder_lift": what the clicked mesh is called, for the part panel's header. */
  selectedMeshLabel: string | null;
  select: (lineId: string | null, meshKey?: string | null, tab?: PanelTab, meshLabel?: string | null) => void;
  hover: (lineId: string | null) => void;
  clearSelection: () => void;
};

type RunSlice = {
  runId: string | null;
  run: RunState | null;
  cart: UniversalCart | null;
  events: Event[];
  lastSeq: number;
  stream: StreamState;
  setRun: (run: RunState) => void;
  setCart: (cart: UniversalCart | null) => void;
  pushEvent: (event: Event) => void;
  setStream: (state: StreamState) => void;
  resetRun: (runId: string | null) => void;
};

type UiSlice = {
  health: Health | null;
  /** True once the backend has said, by /api/health or a response header, that data may be mock. */
  mockSeen: boolean;
  colourMode: ColourMode;
  /** 0..1: how far the model is pulled apart (PLAN 11.6 E5). */
  explode: number;
  /** Which tab the part panel opens on (a diagram edge opens Why). */
  panelTab: PanelTab;
  /** Photo / Model toggle and the knolling Kit view. */
  stageMode: StageMode;
  setExplode: (t: number) => void;
  setPanelTab: (tab: PanelTab) => void;
  setStageMode: (mode: StageMode) => void;
  setHealth: (health: Health | null) => void;
  setMockSeen: (seen: boolean) => void;
  setColourMode: (mode: ColourMode) => void;
};

export type AppState = SelectionSlice & RunSlice & UiSlice;

export const useAppStore = create<AppState>()((set) => ({
  selectedLineId: null,
  hoveredLineId: null,
  selectedMeshKey: null,
  selectedMeshLabel: null,
  select: (lineId, meshKey = null, tab, meshLabel = null) =>
    set((s) => ({ selectedLineId: lineId, selectedMeshKey: lineId ? meshKey : null, selectedMeshLabel: lineId ? meshLabel : null, panelTab: tab ?? (lineId === s.selectedLineId ? s.panelTab : "offers") })),
  hover: (lineId) => set({ hoveredLineId: lineId }),
  clearSelection: () => set({ selectedLineId: null, selectedMeshKey: null, selectedMeshLabel: null, hoveredLineId: null }),

  runId: null,
  run: null,
  cart: null,
  events: [],
  lastSeq: 0,
  stream: "idle",
  setRun: (run) => set({ run, runId: run.run_id }),
  setCart: (cart) => set({ cart }),
  pushEvent: (event) =>
    set((s) => (event.seq <= s.lastSeq ? s : { events: [...s.events, event], lastSeq: event.seq })),
  setStream: (stream) => set({ stream }),
  // Selection survives a tier switch (PLAN §11.6) but not a change of run.
  resetRun: (runId) =>
    set({ runId, run: null, cart: null, events: [], lastSeq: 0, stream: "idle", selectedLineId: null, selectedMeshKey: null, selectedMeshLabel: null, hoveredLineId: null, explode: 0, stageMode: "model" }),

  health: null,
  mockSeen: false,
  colourMode: "status",
  explode: 0,
  panelTab: "offers",
  stageMode: "model",
  setExplode: (explode) => set({ explode }),
  setPanelTab: (panelTab) => set({ panelTab }),
  setStageMode: (stageMode) => set({ stageMode }),
  setHealth: (health) => set((s) => ({ health, mockSeen: s.mockSeen || Boolean(health?.mock) })),
  setMockSeen: (mockSeen) => set({ mockSeen }),
  setColourMode: (colourMode) => set({ colourMode }),
}));

/** True when the UI must show the "Mock data" badge. */
export const selectIsMock = (s: AppState) => s.mockSeen || Boolean(s.health?.mock);
