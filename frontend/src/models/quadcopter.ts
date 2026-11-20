// The quadcopter as data (PLAN Appendix C.2): a 5-inch freestyle quad from real dimensions. The 3-inch build is
// the same model scaled through the template's `_view.scale`.
// Millimetres, Y up, +Z is the front. Typical dimensions of the class, not any product's drawing:
// 220 mm motor to motor, 5 mm arms, 30.5 mm stack, 2207 motors, 127 mm props, a 73 × 35 × 35 mm 4S pack.
// Mesh names match RunState.view.parts[].mesh: frame, motor, esc, fc, receiver, vtx, camera, props, battery
// (and gps, which is drawn only when the view maps it to a line).
// Each part's solid is built in models/detail/quadcopter.ts under its `detail` key; `shape` and `size` are the
// plain block that stands in if a key is ever missing.
import type { PartDef } from "./types";

/** The layout both this file and the detail builders measure from. */
export const QUAD = {
  /** Motor offset from the centre on X and Z: a 220 mm diagonal. */
  M: 77.8,
  /** Levels, bottom to top: bottom plate, arms, main plate, standoffs, top plate. */
  bottomY: -2,
  armY: 0,
  armT: 5,
  mainY: 5,
  plateT: 2,
  standoff: 25,
  topY: 32,
  /** Board levels of the stack (the underside of each board). */
  escY: 11.4,
  fcY: 20,
  /** Height of a motor from the arm to the prop seat. */
  motorH: 16.2,
  /** Half of the 30.5 mm stack pattern. */
  stack: 15.25,
} as const;

const { M } = QUAD;
const A = 14; // outward explode along an arm, per axis (20 mm along the diagonal)
const corners: Array<[number, number]> = [
  [1, 1],
  [1, -1],
  [-1, 1],
  [-1, -1],
];
/** Turns a part's +X to point out along its arm. */
const out = (sx: number, sz: number) => (Math.atan2(-sz, sx) * 180) / Math.PI;

export const quadcopter: PartDef[] = [
  { mesh: "frame", label: "bottom plate", detail: "quad/bottom-plate", shape: "roundedBox", size: [60, 2, 60], pos: [0, QUAD.bottomY, 0], material: "carbon", explode: [0, -24, 0], order: 1 },
  {
    mesh: "frame",
    label: "arm",
    detail: "quad/arm",
    shape: "box",
    size: [124, 5, 14],
    pos: [0, 0, 0],
    material: "carbon",
    instances: corners.map(([sx, sz]) => ({ pos: [0, QUAD.armY, 0], rot: [0, out(sx, sz), 0], explode: [sx * A, -10, sz * A] })),
    explode: [0, -10, 0],
    order: 1,
  },
  { mesh: "frame", label: "main plate", detail: "quad/main-plate", shape: "roundedBox", size: [38, 2, 130], pos: [0, QUAD.mainY, 0], material: "carbon", explode: [0, 0, 0], order: 1 },
  { mesh: "frame", label: "stack bolts", detail: "quad/stack-bolts", shape: "cylinder", size: [1.5, 29], pos: [0, QUAD.bottomY - 1.6, 0], material: "metal", explode: [0, -40, 0], order: 1 },
  {
    mesh: "motor",
    detail: "quad/motor",
    shape: "cylinder",
    size: [13.75, 16],
    pos: [0, 0, 0],
    material: "metal",
    instances: corners.map(([sx, sz]) => ({ pos: [sx * M, QUAD.armY + QUAD.armT, sz * M], rot: [0, out(sx, sz), 0], explode: [sx * A, 30, sz * A] })),
    explode: [0, 30, 0],
    order: 2,
  },
  { mesh: "esc", detail: "quad/esc", shape: "box", size: [36, 1.6, 36], pos: [0, QUAD.escY, 0], material: "pcb", explode: [0, 18, 0], order: 3 },
  { mesh: "fc", detail: "quad/fc", shape: "box", size: [36, 1.6, 36], pos: [0, QUAD.fcY, 0], material: "pcb", explode: [0, 38, 0], order: 4 },
  { mesh: "receiver", detail: "quad/receiver", shape: "box", size: [18, 1, 10], pos: [0, 7.8, -32], material: "pcb", explode: [0, 10, -45], order: 5 },
  { mesh: "vtx", detail: "quad/vtx", shape: "box", size: [22, 1.4, 23], pos: [0, 11, -50.5], material: "pcb", explode: [0, 25, -60], order: 5 },
  { mesh: "camera", detail: "quad/camera", shape: "box", size: [19, 19, 19], pos: [0, 18, 54], material: "plastic", explode: [0, 10, 55], order: 6 },
  { mesh: "frame", label: "standoffs", detail: "quad/standoffs", shape: "cylinder", size: [2.5, 25], pos: [0, QUAD.mainY + QUAD.plateT, 0], material: "metal", explode: [0, 30, 0], order: 7 },
  { mesh: "frame", label: "top plate", detail: "quad/top-plate", shape: "roundedBox", size: [38, 2, 130], pos: [0, QUAD.topY, 0], material: "carbon", explode: [0, 60, 0], order: 7 },
  {
    mesh: "props",
    detail: "quad/prop",
    shape: "cylinder",
    size: [63.5, 6],
    pos: [0, 0, 0],
    material: "plastic",
    colour: "--b2c-mat-accent",
    instances: corners.map(([sx, sz], i) => ({ pos: [sx * M, QUAD.armY + QUAD.armT + QUAD.motorH, sz * M], rot: [0, i * 37, 0], explode: [sx * A, 65, sz * A] })),
    explode: [0, 65, 0],
    order: 8,
  },
  { mesh: "battery", detail: "quad/battery", shape: "roundedBox", size: [35, 35, 73], pos: [0, QUAD.topY + QUAD.plateT + 1, 0], material: "battery", explode: [0, 100, 0], order: 9 },
  { mesh: "gps", optional: true, detail: "quad/gps", shape: "box", size: [18, 7, 18], pos: [0, QUAD.topY + QUAD.plateT, -54], material: "plastic", explode: [0, 80, -30], order: 9 },
];
