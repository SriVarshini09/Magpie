// The servo gripper as data (PLAN Appendix C.4). SO-101-style; opens along X. Millimetres, Y up.
// Mesh names: wrist, servo, jaw_fixed, jaw_moving, screws, controller, psu, clamp.
import type { PartDef } from "./types";

export const claw: PartDef[] = [
  { mesh: "wrist", shape: "roundedBox", size: [46, 40, 36], pos: [0, 20, 0], material: "plastic", colour: "--b2c-mat-printed", explode: [0, 0, 0], order: 1 },
  { mesh: "servo", shape: "box", size: [45, 33, 25], pos: [0, 56.5, 0], material: "metal", colour: "--b2c-mat-servo", extras: [{ shape: "cylinder", size: [10, 4], pos: [10, 18.5, 0] }], explode: [0, 45, 0], order: 2 },
  { mesh: "jaw_fixed", shape: "box", size: [12, 90, 24], pos: [-24, 120, 0], material: "plastic", colour: "--b2c-mat-printed", extras: [{ shape: "roundedBox", size: [14, 30, 24], pos: [4, 44, 0] }], explode: [-50, 40, 0], order: 3 },
  { mesh: "jaw_moving", shape: "box", size: [12, 90, 24], pos: [28, 119, 0], rot: [0, 0, -12], material: "plastic", colour: "--b2c-mat-printed", extras: [{ shape: "roundedBox", size: [14, 30, 24], pos: [-4, 44, 0] }], explode: [50, 40, 0], order: 3 },
  {
    mesh: "screws",
    shape: "cylinder",
    size: [1.8, 8],
    pos: [0, 0, 0],
    material: "metal",
    instances: [
      { pos: [-19, 68, 13.5], rot: [90, 0, 0] },
      { pos: [19, 68, 13.5], rot: [90, 0, 0] },
      { pos: [-19, 45, 13.5], rot: [90, 0, 0] },
      { pos: [19, 45, 13.5], rot: [90, 0, 0] },
    ],
    explode: [0, 45, 30],
    order: 4,
  },
  { mesh: "controller", shape: "box", size: [42, 3, 32], pos: [95, 1.5, 0], material: "pcb", extras: [{ shape: "box", size: [12, 6, 10], pos: [-12, 4.5, 8] }, { shape: "box", size: [10, 3, 10], pos: [8, 3, -4] }], explode: [40, 0, 0], order: 5 },
  { mesh: "psu", shape: "roundedBox", size: [60, 30, 40], pos: [165, 15, 0], material: "plastic", extras: [{ shape: "capsule", size: [2, 22], pos: [-41, -9, 0], rot: [0, 0, 90] }], explode: [70, 0, 0], order: 5 },
  {
    mesh: "clamp",
    shape: "box",
    size: [20, 70, 8],
    pos: [0, -35, -26],
    material: "metal",
    // The C shape: a back bar and two arms.
    extras: [
      { shape: "box", size: [20, 8, 40], pos: [0, 31, 16] },
      { shape: "box", size: [20, 8, 40], pos: [0, -31, 16] },
      { shape: "cylinder", size: [3, 26], pos: [0, -18, 24] },
    ],
    explode: [0, -40, 0],
    order: 5,
  },
];
