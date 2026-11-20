// Kit view (PLAN §3.20 P18, §11.12, Appendix C.5): every part laid out on the table in a priced grid.
// This file is the light door: which lines get a place in the kit, and the lazy view. The scene itself lives
// in components/stage/KitScene and arrives in its own chunk (quality bar Q2).
import { lazy, Suspense } from "react";

import type { KitViewProps } from "@/components/stage/KitScene";
import { StageLoading } from "@/components/stage/StageLoading";
import type { StageData } from "@/lib/stage";
import type { KitToken, PartCategory, ViewData } from "@/lib/types";

export function kitTokensFor(view: ViewData, data: StageData): KitToken[] {
  if (view.tokens?.length) return view.tokens;
  return [...data.lines.values()]
    .filter((l) => l.category && l.status !== "removed")
    .map((l) => ({ bom_line_id: l.id, category: l.category as PartCategory, qty: l.qty, label: l.name }));
}

const KitScene = lazy(() => import("@/components/stage/KitScene"));

export function KitView(props: KitViewProps) {
  return (
    <Suspense fallback={<StageLoading />}>
      <KitScene {...props} />
    </Suspense>
  );
}
