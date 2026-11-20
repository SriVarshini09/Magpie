// What the stage shows while a 3D view's code or model is on its way. No three.js here: it is part of the
// first paint.
import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";

export function StageLoading({ children }: { children?: ReactNode }) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-3" role="status">
      <Skeleton className="h-40 w-28 bg-stage-surface" />
      <p className="text-small text-stage-muted">{children ?? "Loading the 3D view…"}</p>
    </div>
  );
}
