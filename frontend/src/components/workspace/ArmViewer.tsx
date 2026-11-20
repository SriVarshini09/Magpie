// SO-101 URDF arm viewer (PLAN §3.12, §11.6, §11.12). This file is the light door: three.js, the stage and the
// model loader live in components/stage/ArmScene and arrive in their own chunk, so pages that only link here
// (the landing page, the workspace shell) paint before any 3D code has loaded (quality bar Q2).
import { lazy, Suspense } from "react";

import type { ArmViewerProps } from "@/components/stage/ArmScene";
import { StageLoading } from "@/components/stage/StageLoading";

const ArmScene = lazy(() => import("@/components/stage/ArmScene"));

export function ArmViewer(props: ArmViewerProps) {
  return (
    <Suspense fallback={<StageLoading />}>
      <ArmScene {...props} />
    </Suspense>
  );
}
