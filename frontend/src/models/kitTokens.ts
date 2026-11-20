// Kit view tokens (PLAN Appendix C.5, P18): one small model per part category, each inside a 60 mm cube.
// Millimetres, Y up, resting on the table at y = 0.
import type { PartCategory } from "@/lib/types";

import type { PartDef } from "./types";

export const KIT_ORDER: PartCategory[] = [
  "board", "esc_driver", "motor", "battery", "power", "sensor", "camera", "radio", "cable", "mechanical", "printed",
];

type Token = Omit<PartDef, "mesh" | "explode" | "order">;

export const kitTokens: Record<PartCategory, Token[]> = {
  board: [{ shape: "roundedBox", size: [60, 4, 40], pos: [0, 2, 0], material: "pcb", extras: [{ shape: "box", size: [14, 3, 14], pos: [6, 3.5, 0] }, { shape: "box", size: [10, 6, 14], pos: [-22, 5, 0] }] }],
  esc_driver: [{ shape: "box", size: [40, 6, 30], pos: [0, 3, 0], material: "pcb", colour: "--b2c-mat-pcb-blue", extras: [{ shape: "box", size: [22, 8, 18], pos: [0, 7, 0] }] }],
  motor: [{ shape: "cylinder", size: [14, 22], pos: [0, 11, 0], material: "metal", extras: [{ shape: "cylinder", size: [2.2, 12], pos: [0, 17, 0] }] }],
  battery: [
    { shape: "roundedBox", size: [55, 22, 30], pos: [0, 11, 0], material: "battery", extras: [{ shape: "capsule", size: [1.6, 18], pos: [34, -4, 0], rot: [0, 0, 90] }] },
    { shape: "box", size: [18, 22.8, 30.8], pos: [-6, 11, 0], material: "battery", colour: "--b2c-mat-label" },
  ],
  power: [{ shape: "roundedBox", size: [45, 28, 35], pos: [0, 14, 0], material: "plastic", extras: [{ shape: "box", size: [2, 10, 6], pos: [-23.5, 2, -7] }, { shape: "box", size: [2, 10, 6], pos: [-23.5, 2, 7] }] }],
  sensor: [{ shape: "box", size: [22, 3, 16], pos: [0, 1.5, 0], material: "pcb", colour: "--b2c-mat-pcb-blue", extras: [{ shape: "box", size: [20, 6, 2.5], pos: [0, 4, -6] }, { shape: "box", size: [5, 2, 5], pos: [2, 2.5, 2] }] }],
  camera: [{ shape: "box", size: [22, 22, 22], pos: [0, 11, 0], material: "plastic", extras: [{ shape: "cylinder", size: [7, 9], pos: [0, 0, 14], rot: [90, 0, 0] }] }],
  radio: [{ shape: "box", size: [28, 4, 22], pos: [0, 2, 0], material: "pcb", extras: [{ shape: "capsule", size: [1.6, 34], pos: [-10, 18, -8] }] }],
  cable: [{ shape: "torus", size: [18, 3], pos: [0, 3, 0], rot: [90, 0, 0], material: "plastic", extras: [{ shape: "torus", size: [15, 2.6], pos: [0, 0, -4.5] }] }],
  mechanical: [{ shape: "cylinder", size: [14, 8, 6], pos: [0, 4, 0], material: "metal", extras: [{ shape: "cylinder", size: [7, 1, 24], pos: [0, 4.2, 0] }] }],
  printed: [{ shape: "box", size: [40, 6, 24], pos: [0, 3, 0], material: "plastic", colour: "--b2c-mat-printed", extras: [{ shape: "box", size: [6, 30, 24], pos: [-17, 18, 0] }] }],
  tool: [{ shape: "capsule", size: [5, 34], pos: [0, 5, 0], rot: [0, 0, 90], material: "plastic", colour: "--b2c-mat-accent", extras: [{ shape: "cylinder", size: [1.6, 30], pos: [0, -32, 0] }] }],
};
