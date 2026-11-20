// The start page's centred visual: our own procedural quadcopter on a small dark stage, turning slowly.
// Not interactive, no network: the model is built in code and three.js arrives in its own chunk. Until it does
// (or if WebGL is off) the logo mark stands in at the same size, so nothing shifts.
import { Component, lazy, Suspense, useMemo, type ReactNode } from "react";

import { LogoMark } from "@/components/brand/Logo";
import { demoView } from "@/models/demo";

const Scene = lazy(() => import("@/components/stage/ProceduralScene"));

function Mark() {
  return (
    <span className="flex size-full items-center justify-center">
      <LogoMark onDark className="size-12" />
    </span>
  );
}

class Quiet extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <Mark /> : this.props.children;
  }
}

export function MiniStage() {
  const { view, data } = useMemo(() => demoView("quadcopter"), []);
  return (
    <div aria-hidden className="pointer-events-none relative size-36 shrink-0 overflow-hidden rounded-full border border-stage-border bg-stage shadow-e2">
      <Quiet>
        <Suspense fallback={<Mark />}>
          <Scene view={view} data={data} interactive={false} autoRotate />
        </Suspense>
      </Quiet>
    </div>
  );
}
