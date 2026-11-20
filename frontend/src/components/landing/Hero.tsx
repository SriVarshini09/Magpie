// The live view on the landing page (PLAN §11.5 A, §11.13): the dark stage, slowly rotating. The quadcopter by
// default; it switches to the matching model as soon as a build type is known. The floating chips are examples
// of what a run shows and are labelled as such.
import { ListPlus, ShieldX, ShoppingCart } from "lucide-react";
import { Component, useMemo, type ReactNode } from "react";

import { ArmViewer } from "@/components/workspace/ArmViewer";
import { BUILD_TYPE_LABEL } from "@/lib/format";
import type { BuildType } from "@/lib/types";
import { demoView, MODEL_FOR_BUILD } from "@/models/demo";
import { ProceduralView } from "@/models/ProceduralView";
// The chips' slow float (b2c-float) lives with the stage's own styles.
import "@/components/stage/stage.css";


class Quiet extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <p className="flex size-full items-center justify-center px-8 text-center text-small text-stage-muted">The 3D view needs WebGL, which this browser has switched off. Everything else works without it.</p> : this.props.children;
  }
}

const CHIPS: Record<string, Array<{ icon: typeof ShoppingCart; text: string; tone?: "fail" }>> = {
  quadcopter: [
    { icon: ShoppingCart, text: "4× motor · one store · Agent cart" },
    { icon: ListPlus, text: "Battery · checked against the board" },
    { icon: ShieldX, text: "Store outside your mandate · refused", tone: "fail" },
  ],
  so101: [
    { icon: ShoppingCart, text: "6× servo · one store · Agent cart" },
    { icon: ListPlus, text: "Power supply · swapped to match 12V servos" },
    { icon: ShieldX, text: "Store outside your mandate · refused", tone: "fail" },
  ],
};

const POSITIONS = ["top-[16%] left-5", "top-[44%] right-5", "bottom-[20%] left-8"];

export function Hero({ buildType }: { buildType?: BuildType | null }) {
  const model = (buildType && MODEL_FOR_BUILD[buildType]) || "quadcopter";
  const { view, data } = useMemo(() => demoView(model), [model]);
  const chips = CHIPS[model] ?? CHIPS.quadcopter;
  return (
    <figure className="stage relative aspect-[5/4] w-full overflow-hidden rounded-2xl border border-stage-border shadow-e2">
      <Quiet>
          {model === "so101" ? <ArmViewer key="arm" view={view} data={data} interactive={false} autoRotate /> : <ProceduralView key={model} view={view} data={data} interactive={false} autoRotate />}
      </Quiet>
      {chips.map((chip, i) => (
        <span
          key={chip.text}
          style={{ animationDelay: `${i * -1.7}s` }}
          className={`b2c-float pointer-events-none absolute ${POSITIONS[i]} inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-caption font-medium shadow-e2 ${chip.tone === "fail" ? "border-fail/50 bg-stage-surface text-stage-fail" : "border-stage-border bg-stage-surface text-stage-text"}`}
        >
          <chip.icon className="size-3.5" strokeWidth={1.75} aria-hidden />
          {chip.text}
        </span>
      ))}
      <figcaption className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between px-4 py-3 text-caption text-stage-muted">
        <span>Example view{buildType ? ` · ${BUILD_TYPE_LABEL[buildType]}` : ""} · the labels are examples, not offers</span>
        <span>Live 3D · it turns on its own · drag to rotate</span>
      </figcaption>
    </figure>
  );
}
