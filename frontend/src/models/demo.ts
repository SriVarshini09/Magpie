// Example data for views that have no run behind them: the landing hero and the view gallery.
// Every line is marked as an example; nothing here is a price or an offer.
import type { StageData, StageLine } from "@/lib/stage";
import type { BuildType, PartCategory, ViewData, ViewModel } from "@/lib/types";

import { PROCEDURAL_MODELS } from "./ProceduralView";

export const MODEL_FOR_BUILD: Partial<Record<BuildType, ViewModel>> = { quadcopter: "quadcopter", rc_car: "rc_car", claw_gripper: "claw", robot_arm: "so101" };

const CATEGORY: Record<string, PartCategory> = {
  frame: "mechanical", motor: "motor", esc: "esc_driver", fc: "board", receiver: "radio", vtx: "radio", camera: "camera", props: "mechanical", battery: "battery",
  chassis: "mechanical", printed: "printed", usb_battery: "battery", sbc: "board", servo_driver: "esc_driver", jumpers: "cable",
  wrist: "printed", servo: "motor", jaw_fixed: "printed", jaw_moving: "printed", screws: "mechanical", controller: "board", psu: "power", clamp: "mechanical",
};

function line(id: string, name: string, category: PartCategory | null): StageLine {
  return { id, name, qty: 1, status: "chosen", category, lineKind: "part", storeId: null, storeName: null, level: null, price: null, seenAt: null, simulated: false, openAssumption: false, failed: false, ownedNote: null };
}

/** A view and stage data for a procedural model with every mesh mapped to an example line. */
export function demoView(model: ViewModel): { view: ViewData; data: StageData } {
  const meshes = [...new Set((PROCEDURAL_MODELS[model] ?? []).map((d) => d.mesh))];
  const lines = new Map<string, StageLine>();
  const parts = meshes.map((mesh, i) => {
    const id = `ex${i + 1}`;
    lines.set(id, line(id, mesh.replace(/_/g, " "), CATEGORY[mesh] ?? null));
    return { mesh, bom_line_id: id, instances: 1, explode: [0, 0, 0] as [number, number, number], order: i + 1 };
  });
  return {
    view: { kind: model === "so101" ? "urdf" : "procedural", model, urdf_url: model === "so101" ? "/so101/so101_new_calib.urdf" : null, parts, tray: [], note: "Example view.", simulated: false },
    data: { lines, storeSlot: new Map(), storeNames: new Map() },
  };
}
