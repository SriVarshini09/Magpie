// Procedural models are data (PLAN §3.20, Appendix C.1): quadcopter, RC car and claw are lists of PartDef.
// This file is the light door: the model data and the lazy view. The stage, three.js and the mesh builder live
// in components/stage/ProceduralScene and arrive in their own chunk (quality bar Q2).
import { lazy, Suspense } from "react";

import type { ProceduralViewProps } from "@/components/stage/ProceduralScene";
import { StageLoading } from "@/components/stage/StageLoading";
import type { ViewData } from "@/lib/types";

import { claw } from "./claw";
import { quadcopter } from "./quadcopter";
import { rcCar } from "./rcCar";
import type { PartDef } from "./types";

export { STAGE_SIZE, useReveal } from "@/components/stage/reveal";

export const PROCEDURAL_MODELS: Record<string, PartDef[]> = { quadcopter, rc_car: rcCar, claw };

export function hasProceduralModel(view: ViewData): boolean {
  return (PROCEDURAL_MODELS[view.model ?? ""]?.length ?? 0) > 0;
}

const ProceduralScene = lazy(() => import("@/components/stage/ProceduralScene"));

export function ProceduralView(props: ProceduralViewProps) {
  return (
    <Suspense fallback={<StageLoading />}>
      <ProceduralScene {...props} />
    </Suspense>
  );
}
