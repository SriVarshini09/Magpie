// Stage-only view state (PLAN §11.12 stretch): which line is isolated, which meshes are hidden, and whether the
// leader-line labels are on. It lives beside the stage, not in the app store, because nothing outside the 3D
// views reads it.
import { create } from "zustand";

type StageViewState = {
  /** bom_line_id of the isolated line: every other mesh drops to 10% opacity and stops taking clicks. */
  isolatedLineId: string | null;
  /** Mesh keys hidden with Ctrl-click or the Hide chip. */
  hidden: ReadonlySet<string>;
  /** True while the two-column labels are on screen (the hover label steps aside). */
  labelsOn: boolean;
  isolate: (lineId: string | null) => void;
  hide: (meshKeys: string[]) => void;
  unhideAll: () => void;
  setLabelsOn: (on: boolean) => void;
  reset: () => void;
};

const NONE: ReadonlySet<string> = new Set();

export const useStageView = create<StageViewState>()((set) => ({
  isolatedLineId: null,
  hidden: NONE,
  labelsOn: false,
  isolate: (isolatedLineId) => set({ isolatedLineId }),
  hide: (meshKeys) => set((s) => ({ hidden: new Set([...s.hidden, ...meshKeys]) })),
  unhideAll: () => set({ hidden: NONE }),
  setLabelsOn: (labelsOn) => set((s) => (s.labelsOn === labelsOn ? s : { labelsOn })),
  reset: () => set({ isolatedLineId: null, hidden: NONE, labelsOn: false }),
}));
