// The 5-inch freestyle quad, part by part, from real dimensions (PLAN Appendix C.2). Millimetres, Y up, +Z front.
// Every builder works in its part's own frame: the origin is the `pos` of its PartDef in models/quadcopter.ts.
// Typical dimensions of the class (220 mm true-X frame, 30.5 mm stack, 2207 motors, 127 mm tri-blade props,
// 4S 1300 mAh pack), not any product's drawing.
//
// Checklist this model is graded against (written before the code, after the `cutaway` method):
//  1. Silhouette: a true X, 220 mm motor to motor; the body plates 38 mm wide (0.17 of the diagonal) and about
//     130 mm long (0.59); props 127 mm (0.58), their discs overlapping the body's sides, never touching.
//  2. Signature: four 2207 motors with copper windings showing through six windows in the bell and through the
//     gap under it. NEVER a plain cylinder.
//  3. Props are three real blades with twist (about 40° at the root, 15° at the tip) and a rounded swept tip.
//     NEVER a flat bar or a disc.
//  4. Plates in three sizes with gaps over the mechanism: bottom X plate, main plate, top plate, with windows
//     cut over the stack, the camera and the video transmitter. NEVER one closed box.
//  5. The stack reads as two boards: a black 4-in-1 ESC with 12 FETs, gold motor pads and the XT60 lead, and a
//     green flight controller with a 10 mm MCU turned 45°, a USB-C shell and JST sockets, on soft mounts.
//  6. Real materials: carbon plate, steel, black anodized aluminium, copper, gold pads, silicone wire, lens
//     glass, a printed battery wrap. Grey plastic is the exception.
//  7. Hardware in every joint: 8 knurled standoffs, M3 button heads, 4 stack bolts with nuts, 4 screws under
//     each motor. No part floats.
//  8. Wiring: three leads from each motor along its arm to the ESC pads, the battery lead looping to a mated
//     XT60 pair, the FC-to-ESC harness, two receiver whips in a V, the video antenna tilted 30° back.
//  9. Camera: a 19 mm body tilted 20° between the front standoffs, a knurled lens barrel, a glossy front element.
// 10. Colour: near-black and metal with copper and gold; yellow only on the XT60 and one battery band. The
//     brand blue is kept for what is hovered or selected.
// 11. Density: at 900 px wide the centre reads as mechanism, not as flat plates.
// 12. Budget: under 150 draw calls and 300k triangles for the whole drone.
import { ExtrudeGeometry, Path, Shape, Vector3 } from "three";

import { QUAD } from "../quadcopter";
import { arc, at, box, crease, cyl, lathe, loft, plate, rbox, slot, tone, trace, tube, turn, type Hole, type P2, type P3, type Sculpt } from "./shop";

const D = Math.SQRT1_2;
const C = {
  carbon: () => tone("--b2c-mat-carbon-deep"),
  steel: () => tone("--b2c-mat-steel"),
  alu: () => tone("--b2c-mat-metal"),
  gun: () => tone("--b2c-mat-gunmetal"),
  black: () => tone("--b2c-mat-anodized"),
  copper: () => tone("--b2c-mat-copper"),
  gold: () => tone("--b2c-mat-gold"),
  pcbBlack: () => tone("--b2c-mat-pcb-black"),
  pcbGreen: () => tone("--b2c-mat-pcb-dark"),
  chip: () => tone("--b2c-mat-chip"),
  silk: () => tone("--b2c-mat-silk"),
  nylon: () => tone("--b2c-mat-nylon"),
  tan: () => tone("--b2c-mat-ceramic"),
  red: () => tone("--b2c-mat-wire-red"),
  wire: () => tone("--b2c-mat-wire-black"),
  rubber: () => tone("--b2c-mat-rubber"),
  plastic: () => tone("--b2c-mat-plastic"),
  yellow: () => tone("--b2c-mat-label"),
  prop: () => tone("--b2c-mat-accent"),
  lens: () => tone("--b2c-mat-lens"),
  wrap: () => tone("--b2c-mat-wrap"),
};

// ------------------------------------------------------------------------------------------------ layout
const QUADRANTS: P2[] = [[1, 1], [1, -1], [-1, -1], [-1, 1]];
/** The plates clamp each arm out to 42 mm from the centre, 9 mm either side of its centre line. */
const LOBE_A = (42 - 9) * D;
const LOBE_B = (42 + 9) * D;
const BODY = 19;
/** Arm bolts, as distances from the centre along each arm. */
const ARM_BOLTS = [27, 38];
const STANDOFFS: P2[] = [[14, 60], [14, 42], [14, -42], [14, -58], [-14, 60], [-14, 42], [-14, -42], [-14, -58]];
const STACK: P2[] = QUADRANTS.map(([sx, sz]): P2 => [sx * QUAD.stack, sz * QUAD.stack]);
const ARM_BOLT_HOLES: P2[] = QUADRANTS.flatMap(([sx, sz]) => ARM_BOLTS.map((r): P2 => [sx * r * D, sz * r * D]));
/** Motor pads on the ESC for the front-right motor; the other three are the same pads turned with their motor. */
const PAD_Z = [11.5, 8, 4.5];
const PAD_X = 16.6;
const TURNS = [0, 90, -90, 180];
/** Where the XT60 pair sits behind the frame, in the model's frame. */
const XT = { red: -9.3, black: -2.7, y: 18, join: -84 };

const mirror = (right: P2[]): P2[] => [...right, ...right.map(([x, z]): P2 => [-x, z]).reverse()];
const holes = (pts: P2[], r: number): Hole[] => pts.map((c) => ({ c, r }));
const square = (h: number): P2[] => [[-h, -h], [h, -h], [h, h], [-h, h]];

/** An M3 button head with its socket, sitting on y = 0. `down` puts it under a plate instead. */
function head(s: Sculpt, x: number, y: number, z: number, down = false, r = 2.75): void {
  s.group(at(x, y, z, down ? 180 : 0), () => {
    s.add("metal", C.steel(), lathe([[0, 0], [r, 0], [r, 0.55], [r * 0.74, 1.35], [r * 0.45, 1.65], [0, 1.65]], s.seg(14)));
    if (s.hi) s.add("metal", C.black(), cyl(r * 0.42, 0.12, 6), at(0, 1.66, 0));
  });
}

function nut(s: Sculpt, x: number, y: number, z: number, r = 2.9, h = 2.4): void {
  s.add("metal", C.steel(), cyl(r, h, 6), at(x, y + h / 2, z));
}

// ------------------------------------------------------------------------------------------------- frame
function bottomPlate(s: Sculpt): void {
  const c = LOBE_B - LOBE_A;
  const outline: P2[] = [[LOBE_A, LOBE_B], [LOBE_B, LOBE_A], [c, 0], [LOBE_B, -LOBE_A], [LOBE_A, -LOBE_B], [0, -c], [-LOBE_A, -LOBE_B], [-LOBE_B, -LOBE_A], [-c, 0], [-LOBE_B, LOBE_A], [-LOBE_A, LOBE_B], [0, c]];
  s.add("carbon", C.carbon(), plate(outline, QUAD.plateT, { round: 4, holes: [...holes(STACK, 1.7), ...holes(ARM_BOLT_HOLES, 1.65), { c: [0, 0], r: 6 }] }));
  // The eight arm bolts: heads under the plate, shanks up through the arm and the main plate.
  for (const [x, z] of ARM_BOLT_HOLES) {
    head(s, x, 0, z, true);
    s.add("metal", C.steel(), cyl(1.45, 11.4, 8), at(x, 5.7, z));
  }
}

function arm(s: Sculpt): void {
  const pad = QUAD.M * Math.SQRT2;
  const outline: P2[] = [[1.5, 0], [9.5, 8], [44, 8], [86, 5.6], ...arc(pad, 0, 14, 155, -155, s.hi ? 22 : 12), [86, -5.6], [44, -8], [9.5, -8]];
  const round = outline.map((_, i) => (i === 0 ? 0.6 : i < 4 || i > outline.length - 4 ? 5 : 0));
  const cut: Hole[] = [
    ...holes(ARM_BOLTS.map((r): P2 => [r, 0]), 1.65),
    // 16 × 16 mm motor pattern and the hole under the shaft.
    ...holes([[pad + 8, 8], [pad + 8, -8], [pad - 8, 8], [pad - 8, -8]], 1.2),
    { c: [pad, 0], r: 3.2 },
    slot(66, 0, 26, 4.2),
  ];
  s.add("carbon", C.carbon(), plate(outline, QUAD.armT, { round, holes: cut, bevel: 0.55 }));
}

const BODY_RIGHT: P2[] = [[15, 66], [BODY, 56], [BODY, -56], [15, -64]];

function mainPlate(s: Sculpt): void {
  const f = LOBE_B - (LOBE_A - BODY);
  const r = LOBE_A - (LOBE_B - BODY);
  const right: P2[] = [[15, 66], [BODY, 56], [BODY, f], [LOBE_A, LOBE_B], [LOBE_B, LOBE_A], [BODY, r], [BODY, -r], [LOBE_B, -LOBE_A], [LOBE_A, -LOBE_B], [BODY, -f], [BODY, -56], [15, -64]];
  const cut: Hole[] = [
    ...holes(STACK, 1.7),
    ...holes(ARM_BOLT_HOLES, 1.65),
    ...holes(STANDOFFS, 1.6),
    { pts: square(6.5), r: 2.5 },
    slot(0, 29, 14, 6),
    slot(0, 49, 12, 7),
    { pts: [[-6, -44], [6, -44], [6, -57], [-6, -57]], r: 2.5 },
  ];
  s.add("carbon", C.carbon(), plate(mirror(right), QUAD.plateT, { round: 3, holes: cut }));
  for (const [x, z] of ARM_BOLT_HOLES) nut(s, x, QUAD.plateT, z);
  for (const [x, z] of STANDOFFS) head(s, x, 0, z, true);
}

function topPlate(s: Sculpt): void {
  const cut: Hole[] = [
    ...holes(STANDOFFS, 1.6),
    // Windows over the camera and the video transmitter; strap slots and lightening under the battery.
    { pts: [[-8, 53], [8, 53], [5.5, 44], [-5.5, 44]], r: 2.2 },
    { pts: [[-6.5, -43], [6.5, -43], [6.5, -55], [-6.5, -55]], r: 2.5 },
    slot(11.5, 16, 20, 3.2, 90),
    slot(-11.5, 16, 20, 3.2, 90),
    slot(11.5, -16, 20, 3.2, 90),
    slot(-11.5, -16, 20, 3.2, 90),
    slot(0, 0, 30, 9, 90),
  ];
  s.add("carbon", C.carbon(), plate(mirror(BODY_RIGHT), QUAD.plateT, { round: 3, holes: cut }));
  for (const [x, z] of STANDOFFS) head(s, x, QUAD.plateT, z);
  // The anti-slip pad the battery sits on.
  s.add("rubber", C.rubber(), rbox(30, 1, 60, 0.4, 1), at(0, QUAD.plateT + 0.5, 0));
  if (s.hi) for (let i = -4; i <= 4; i++) s.add("rubber", C.plastic(), box(30, 0.25, 1.1), at(0, QUAD.plateT + 1.05, i * 6.4));
}

function standoffs(s: Sculpt): void {
  const h = QUAD.standoff;
  const profile: P2[] = [[0, 0], [2.5, 0], [2.5, 2], [2.15, 2.3], [2.15, 3.1], [2.5, 3.4], [2.5, h - 3.4], [2.15, h - 3.1], [2.15, h - 2.3], [2.5, h - 2], [2.5, h], [0, h]];
  for (const [x, z] of STANDOFFS) s.add("metal", C.alu(), lathe(profile, s.seg(16)), at(x, 0, z));
}

function stackBolts(s: Sculpt): void {
  for (const [x, z] of STACK) {
    head(s, x, 1.65, z, true);
    s.add("metal", C.steel(), cyl(1.5, 27.6, 8), at(x, 1.65 + 13.8, z));
  }
}

// ------------------------------------------------------------------------------------------------- motor
/** A 2207 motor on its arm: +X points out along the arm, the leads leave toward the centre. */
function motor(s: Sculpt): void {
  // Base: a disc with four ears on the 16 × 16 mm pattern.
  const n = s.hi ? 72 : 36;
  const base: P2[] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const r = 8.2 + 5.2 * Math.pow(Math.cos(2 * (a - Math.PI / 4)), 4);
    base.push([r * Math.cos(a), r * Math.sin(a)]);
  }
  s.add("metal", C.black(), plate(base, 2.6, { round: 0, bevel: 0.35, holes: [...holes([[8, 8], [8, -8], [-8, 8], [-8, -8]], 1.15), { c: [0, 0], r: 3 }] }));
  // Shaft: the retained end under the arm, and the M5 thread the prop sits on.
  s.add("metal", C.steel(), cyl(2, 9, 10), at(0, -1.2, 0));
  if (s.hi) {
    const thread: P2[] = [[0, 14]];
    for (let y = 14; y < 29; y += 0.75) thread.push([2.5, y], [2.2, y + 0.375]);
    thread.push([2.3, 29], [0, 29]);
    s.add("metal", C.steel(), lathe(thread, 10, 80));
  } else s.add("metal", C.steel(), cyl(2.5, 15, 8), at(0, 21.5, 0));

  // Stator: a laminated hub with 12 teeth, each wound with copper.
  s.add("metal", C.gun(), cyl(5.7, 7, s.seg(24)), at(0, 6.7, 0));
  const turns: P2[] = [[1.3, 0]];
  const ribs = s.hi ? 9 : 4;
  for (let i = 0; i <= ribs; i++) turns.push([i % 2 ? 1.78 : 2.0, 0.3 + (4.0 * i) / ribs]);
  turns.push([1.3, 4.6]);
  for (let i = 0; i < 12; i++) {
    s.group(at(0, 6.7, 0, 0, i * 30 + 15, 0), () => {
      s.add("metal", C.gun(), box(5.4, 6.6, 1.9), at(8.1, 0, 0));
      s.add("metal", C.steel(), box(0.9, 7, 4.7), at(10.95, 0, 0));
      // The coil: turns of wire round the tooth, taller than it is wide.
      s.add("metal", C.copper(), lathe(turns, s.hi ? 10 : 6, 180), at(5.9, 0, 0, 0, 0, -90, [2.15, 1, 0.98]));
    });
  }
  if (s.hi) for (let i = 0; i < 14; i++) s.add("metal", C.gun(), box(1, 8.2, 4.5), at(0, 0, 0, 0, (i * 360) / 14, 0).multiply(at(12.1, 7.9, 0)));

  // Bell: a steel flux ring, and a black cap with six windows over the windings.
  const ring: P2[] = [[12.6, 3.4], [13.45, 3.4], [13.75, 3.7], [13.75, 5.2], [13.58, 5.35], [13.58, 5.65], [13.75, 5.8], [13.75, 11.4], [13.58, 11.55], [13.58, 11.85], [13.75, 12], [13.75, 12.5], [12.6, 12.5], [12.6, 3.4]];
  s.add("metal", C.steel(), lathe(ring, s.seg(48)));
  const windows: Hole[] = [];
  for (let i = 0; i < 6; i++) {
    const a = i * 60 + 30;
    windows.push({ pts: [...arc(0, 0, 11.5, a - 21, a + 21, s.hi ? 6 : 3), ...arc(0, 0, 6.6, a + 16, a - 16, s.hi ? 3 : 1)], r: 0.9 });
  }
  s.add("metal", C.black(), plate(arc(0, 0, 13.75, 0, 360 - 360 / s.seg(48), s.seg(48) - 1), 2, { round: 0, bevel: 0.6, holes: windows }), at(0, 12.4, 0));
  s.add("metal", C.black(), lathe([[0, 12.6], [6.1, 12.6], [6.1, 14.7], [5, 16.2], [0, 16.2]], s.seg(28)));

  // Four screws up through the arm into the base.
  for (const [x, z] of [[8, 8], [8, -8], [-8, 8], [-8, -8]] as P2[]) {
    head(s, x, -QUAD.armT, z, true, 2.1);
    if (s.hi) s.add("metal", C.steel(), cyl(1, 8, 6), at(x, -1, z));
  }

  // Three leads along the arm, up onto the main plate and across to the ESC pads.
  const reach = QUAD.M * Math.SQRT2;
  const padY = QUAD.escY + 1.6 - (QUAD.armY + QUAD.armT) + 0.75;
  PAD_Z.forEach((pz, i) => {
    // The pad, seen from this motor: along the arm (x) and across it (z).
    const dx = PAD_X - QUAD.M;
    const dz = pz - QUAD.M;
    const x = (dx + dz) * D;
    const z = (dz - dx) * D;
    const run = -4.3 - 1.75 * i;
    const path: P3[] = [[-6.5, 1.5, -1.5 - 1.2 * i], [-17, 1, run], [-(reach - 47), 1, run], [-(reach - 40.5), 2.95, run], [-(reach - 31), 2.95, run], [x + 5.5, padY - 2.4, (run + z) / 2], [x, padY, z]];
    s.add("satin", C.wire(), tube(path, 0.85, s.hi ? 6 : 4, s.hi ? 5 : 3));
  });
}

/** A 5-inch tri-blade prop with its lock nut. The origin is the prop seat on the bell. */
function prop(s: Sculpt): void {
  s.add("gloss", C.prop(), lathe([[0, 0], [6.2, 0], [6.6, 0.6], [6.6, 5.4], [6, 6.2], [0, 6.2]], s.seg(48)));
  const stations = s.hi ? 16 : 8;
  const K = s.hi ? 12 : 8;
  for (let b = 0; b < 3; b++) {
    const rings: Vector3[][] = [];
    for (let i = 0; i <= stations; i++) {
      const t = i / stations;
      const r = 4 + (63.5 - 4) * t;
      let chord = t < 0.32 ? 6.5 + 9 * Math.sin((t / 0.32) * (Math.PI / 2)) : 15.5 - 7 * Math.pow((t - 0.32) / 0.68, 1.5);
      if (t > 0.88) chord *= Math.max(0.2, Math.sqrt(1 - Math.pow((t - 0.88) / 0.12, 2)));
      const pitch = Math.min((40 * Math.PI) / 180, Math.atan(109 / (2 * Math.PI * r)));
      const thick = 1.9 - 1.3 * t;
      const sweep = -6 * t * t;
      const ring: Vector3[] = [];
      for (let k = 0; k < K; k++) {
        const phi = (k / K) * Math.PI * 2;
        const u = (chord / 2) * Math.cos(phi) + sweep;
        // An aerofoil section: thickest a third of the way back from the leading edge.
        const v = (thick / 2) * Math.sin(phi) * (1 + 0.45 * Math.cos(phi));
        ring.push(new Vector3(r, u * Math.sin(pitch) + v * Math.cos(pitch), u * Math.cos(pitch) - v * Math.sin(pitch)));
      }
      rings.push(ring);
    }
    s.add("gloss", C.prop(), loft(rings), at(0, 3.1, 0, 0, b * 120, 0));
  }
  s.add("metal", C.steel(), cyl(4.7, 1, s.seg(20)), at(0, 6.7, 0));
  s.add("metal", C.steel(), cyl(4.1, 4.2, 6), at(0, 9.3, 0));
}

// ------------------------------------------------------------------------------------------------- stack
function esc(s: Sculpt): void {
  const top = 1.6;
  s.add("satin", C.pcbBlack(), plate(square(18), top, { round: 3, bevel: 0.12, holes: holes(STACK, 1.7) }));
  for (const [x, z] of STACK) s.add("rubber", C.wire(), cyl(2.7, 4.4, s.seg(14)), at(x, -2.2, z));
  for (const deg of TURNS) {
    for (const pz of PAD_Z) {
      const [px, pzz] = turn([PAD_X, pz], deg);
      s.add("metal", C.gold(), box(2.4, 0.3, 2.4), at(px, top + 0.1, pzz));
      s.add("metal", C.steel(), lathe([[0, 0], [1.25, 0], [1.05, 0.55], [0, 0.95]], 8, 180), at(px, top + 0.2, pzz));
      const [fx, fz] = turn([12, pz], deg);
      s.add("satin", C.chip(), box(3.1, 0.9, 3.1), at(fx, top + 0.45, fz));
      const [lx, lz] = turn([14.25, pz], deg);
      if (s.hi) s.add("metal", C.steel(), box(0.5, 0.25, 2.7), at(lx, top + 0.12, lz, 0, deg, 0));
    }
  }
  s.add("satin", C.chip(), box(5, 0.9, 5), at(0, top + 0.45, 0));
  for (const [sx, sz] of QUADRANTS) s.add("satin", C.chip(), box(3, 0.8, 3), at(sx * 6.2, top + 0.4, sz * 6.2));
  if (s.hi) {
    for (let j = 0; j < 3; j++) {
      for (const sign of [-1, 1]) {
        s.add("satin", C.tan(), box(0.8, 0.5, 1.6), at(sign * (3.6 + 2.1 * j), top + 0.25, 0));
        s.add("satin", C.tan(), box(1.6, 0.5, 0.8), at(0, top + 0.25, sign * (3.6 + 2.1 * j)));
      }
    }
    // Silkscreen: a frame round the processor and a line by the power pads.
    for (const sign of [-1, 1]) {
      s.add("satin", C.silk(), box(7, 0.04, 0.22), at(0, top + 0.02, sign * 3.2));
      s.add("satin", C.silk(), box(0.22, 0.04, 7), at(sign * 3.2, top + 0.02, 0));
    }
    s.add("satin", C.silk(), box(9, 0.04, 0.22), at(-6.2, top + 0.02, -13));
  }
  // Current shunt, the two battery pads and the lead to the XT60.
  s.add("satin", C.chip(), box(6.3, 0.7, 3.2), at(-6.2, top + 0.35, -10.4));
  s.add("metal", C.steel(), box(1, 0.75, 3.3), at(-9.1, top + 0.37, -10.4));
  s.add("metal", C.steel(), box(1, 0.75, 3.3), at(-3.3, top + 0.37, -10.4));
  const xtY = XT.y - QUAD.escY;
  for (const [x0, x1, colour] of [[-9, XT.red, C.red()], [-3.4, XT.black, C.wire()]] as Array<[number, number, ReturnType<typeof C.red>]>) {
    s.add("metal", C.gold(), box(4, 0.3, 3.6), at(x0, top + 0.1, -15.7));
    s.add("metal", C.steel(), lathe([[0, 0], [1.9, 0], [1.6, 0.8], [0, 1.4]], 10, 180), at(x0, top + 0.2, -15.7));
    s.add("satin", colour, tube([[x0, top + 0.9, -15.4], [x0, top + 1.6, -21], [x0, 5.4, -30], [x1, xtY - 0.4, -50], [x1, xtY, -66]], 1.9, s.seg(10), s.hi ? 6 : 3));
    s.add("rubber", C.wire(), cyl(2.35, 5, s.seg(12)), at(x1, xtY, -66.5, 90));
    // The pins of the plug: hidden while the battery is connected, bare once it is lifted away.
    s.add("metal", C.gold(), cyl(1.75, 7, s.seg(12)), at(x1, xtY, XT.join - 3.2, 90));
  }
  s.add("satin", C.yellow(), rbox(15.8, 8.1, 15, 1.2), at((XT.red + XT.black) / 2, xtY, XT.join + 7.5));
  // The low-ESR capacitor, on its legs beside the board.
  s.add("satin", C.chip(), cyl(4, 10.5, s.seg(20)), at(22.6, 1.6, -8.6, 90));
  s.add("metal", C.steel(), cyl(3.6, 0.3, s.seg(20)), at(22.6, 1.6, -13.95, 90));
  if (s.hi) {
    s.add("satin", C.silk(), box(0.3, 2.6, 9.6), at(26.52, 1.6, -8.6));
    s.add("metal", C.steel(), tube([[21.6, 1.6, -3.4], [20.6, 1.8, -1.6], [17.2, 1.8, -1.6]], 0.4, 5, 4));
    s.add("metal", C.steel(), tube([[23.6, 1.6, -3.4], [23.4, 1.8, 0.6], [17.2, 1.8, 0.9]], 0.4, 5, 4));
  }
  // The socket for the harness up to the flight controller.
  s.add("satin", C.nylon(), box(9.5, 2.9, 3.6), at(6, top + 1.45, 15.6));
  s.add("satin", C.chip(), box(8.3, 0.2, 1.3), at(6, top + 2.92, 15.6));
}

function fc(s: Sculpt): void {
  const top = 1.6;
  s.add("satin", C.pcbGreen(), plate(square(18), top, { round: 3.2, bevel: 0.12, holes: holes(STACK, 2) }));
  for (const [x, z] of STACK) {
    // Soft mount: a rubber grommet through the board, down to the ESC; a lock nut on top.
    s.add("rubber", C.rubber(), lathe([[0, -7], [2.9, -7], [2.9, -5.8], [2.2, -4.6], [2.2, -2.2], [2.9, -1], [2.9, 2.3], [0, 2.3]], s.seg(14)), at(x, 0, z));
    nut(s, x, 2.3, z, 3.1, 2.8);
  }
  // The processor, turned 45° as it is on most boards, with its legs showing.
  s.group(at(0, top, 0, 0, 45, 0), () => {
    s.add("satin", C.chip(), box(10, 1.3, 10), at(0, 0.75, 0));
    for (const deg of [0, 90, 180, 270]) s.add("metal", C.steel(), box(9.2, 0.3, 0.9), at(0, 0, 0, 0, deg, 0).multiply(at(0, 0.2, 5.3)));
    if (s.hi) s.add("satin", C.silk(), box(5, 0.04, 0.5), at(0, 1.42, 2.6));
  });
  s.add("satin", C.chip(), box(3, 0.9, 3), at(9.6, top + 0.45, -9.6));
  s.add("metal", C.steel(), box(2.6, 1, 2.1), at(-10.5, top + 0.5, 9.6));
  s.add("satin", C.chip(), box(4.5, 0.9, 4.5), at(-9.6, top + 0.45, -9.6));
  s.add("satin", C.chip(), box(5.2, 0.9, 4), at(9.6, top + 0.45, 10.6));
  s.add("metal", C.gun(), rbox(3.6, 1.9, 3.6, 0.5, 1), at(0, top + 0.95, -10.8));
  s.add("metal", C.gun(), rbox(3.6, 1.9, 3.6, 0.5, 1), at(0, top + 0.95, 10.8));
  // Sockets: ESC harness at the front, video at the back, receiver on the right; USB-C on the left.
  for (const [w, d, x, z] of [[9.5, 3.6, 0, 15.6], [7.5, 3.6, 0, -15.6], [3.6, 5.5, 15.6, 6]]) {
    s.add("satin", C.nylon(), box(w, 2.9, d), at(x, top + 1.45, z));
    s.add("satin", C.chip(), box(Math.max(1.2, w - 1.4), 0.2, Math.max(1.2, d - 2.2)), at(x, top + 2.92, z));
  }
  s.add("metal", C.steel(), rbox(7.4, 3.2, 9, 1, 2), at(-14.6, top + 1.6, 0));
  s.add("satin", C.chip(), box(0.3, 2, 7.4), at(-18.2, top + 1.6, 0));
  s.add("metal", C.steel(), box(3, 1.2, 2.6), at(11, top + 0.6, -3));
  s.add("satin", C.chip(), cyl(0.8, 0.4, 8), at(11, top + 1.3, -3));
  // Solder pads along the edges.
  const pads: P2[] = [];
  for (let j = 0; j < 5; j++) pads.push([16.4, -11.5 + 2.4 * j]);
  for (let j = 0; j < 3; j++) pads.push([-16.4, -11.5 + 2.4 * j], [-16.4, 6.7 + 2.4 * j], [6.5 + 2.4 * j, -16.4], [-6.5 - 2.4 * j, -16.4], [7 + 2.4 * j, 16.4], [-7 - 2.4 * j, 16.4]);
  for (const [x, z] of pads) s.add("metal", C.gold(), box(1.5, 0.22, 1.5), at(x, top + 0.08, z));
  if (s.hi) {
    for (let j = 0; j < 4; j++) {
      s.add("satin", C.tan(), box(0.8, 0.5, 1.6), at(5.2 + 2 * j, top + 0.25, -13.4));
      s.add("satin", C.tan(), box(0.8, 0.5, 1.6), at(-11.4 + 2 * j, top + 0.25, 13.4));
      s.add("satin", C.chip(), box(1.6, 0.5, 0.8), at(-13.2, top + 0.25, -6.5 + 2 * j));
    }
    for (let j = 0; j < 3; j++) s.add("satin", C.nylon(), box(1.6, 0.6, 0.8), at(-12.4 + 2.3 * j, top + 0.3, -13.5));
    s.add("satin", C.silk(), box(0.22, 0.04, 6), at(13.6, top + 0.02, -5));
    s.add("satin", C.silk(), box(6, 0.04, 0.22), at(-9, top + 0.02, 5.4));
    // The harness down to the ESC.
    const down = QUAD.escY + 1.6 + 1.45 - QUAD.fcY;
    for (let i = 0; i < 6; i++) {
      const x = -2.75 + 1.1 * i;
      s.add("satin", i === 0 ? C.red() : i === 5 ? C.nylon() : C.wire(), tube([[x, top + 1.5, 17.2], [x, top + 1.1, 20.4], [x + 3, -2, 21.8], [x + 6, down + 0.3, 19.8], [x + 6, down, 17.2]], 0.42, 5, 5));
    }
  }
}

// ------------------------------------------------------------------------------------- radio, video, camera
function receiver(s: Sculpt): void {
  s.add("rubber", C.rubber(), box(16, 0.8, 9), at(0, -0.4, 0));
  s.add("satin", C.pcbGreen(), box(18, 1, 10), at(0, 0.5, 0));
  s.add("metal", C.steel(), rbox(7, 1.5, 6.4, 0.3, 1), at(-3.5, 1.75, 0));
  s.add("satin", C.chip(), box(3, 0.8, 3), at(2.6, 1.4, 2.8));
  for (let j = 0; j < 4; j++) s.add("metal", C.gold(), box(1.3, 0.22, 1.3), at(-8.1, 1.08, -3.6 + 2.4 * j));
  // Two whips out through the back in a V, with a sleeve on the active end.
  const whips: P3[][] = [
    [[6.8, 2, -2.6], [9.5, 7, -8], [10.3, 13, -18], [10.3, 15.5, -30], [22, 21, -54]],
    [[6.8, 2, 2.6], [2, 6.5, -4], [-8, 13, -12], [-10.3, 15.5, -30], [-22, 21, -54]],
  ];
  for (const path of whips) {
    s.add("metal", C.gold(), cyl(1.1, 1.3, 8), at(path[0][0], 1.65, path[0][2]));
    s.add("satin", C.wire(), tube(path, 0.55, 5, s.hi ? 6 : 3));
    const [a, b] = [path[path.length - 2], path[path.length - 1]];
    const mid: P3 = [a[0] + (b[0] - a[0]) * 0.42, a[1] + (b[1] - a[1]) * 0.42, a[2] + (b[2] - a[2]) * 0.42];
    s.add("rubber", C.wire(), tube([mid, b], 1.05, 6, 2));
  }
}

function vtx(s: Sculpt): void {
  const top = 1.4;
  s.add("satin", C.pcbBlack(), plate([[-11, -11.5], [11, -11.5], [11, 11.5], [-11, 11.5]], top, { round: 2, bevel: 0.12, holes: holes([[9, 9.5], [9, -9.5], [-9, 9.5], [-9, -9.5]], 1.1) }));
  for (const [x, z] of [[9, 9.5], [9, -9.5], [-9, 9.5], [-9, -9.5]] as P2[]) {
    s.add("rubber", C.wire(), cyl(1.6, 4, 8), at(x, -2, z));
    head(s, x, top, z, false, 1.5);
  }
  // The RF can, the regulator's inductor and capacitor, the driver chip and the socket.
  s.add("metal", C.steel(), rbox(11, 2, 11, 0.4, 1), at(-3.2, top + 1, 2.2));
  if (s.hi) s.add("metal", C.gun(), box(9, 0.06, 0.3), at(-3.2, top + 2.02, 2.2));
  s.add("metal", C.gun(), rbox(4, 2, 4, 0.5, 1), at(6.2, top + 1, 4.6));
  s.add("satin", C.tan(), box(3.4, 1.8, 2), at(6.2, top + 0.9, -0.4));
  s.add("satin", C.chip(), box(4, 0.9, 4), at(-4.6, top + 0.45, -7.4));
  s.add("satin", C.nylon(), box(7.5, 2.9, 3.4), at(-1.5, top + 1.45, 9.6));
  s.add("satin", C.chip(), box(6.1, 0.2, 1.3), at(-1.5, top + 2.92, 9.6));
  // MMCX socket, the coax up behind the top plate and the antenna, tilted 30° back.
  s.add("metal", C.gold(), cyl(1.8, 3.4, s.seg(12)), at(7, top + 1.4, -10.2, 90));
  s.add("satin", C.wire(), tube([[7, top + 1.4, -11.6], [7, 4, -17], [7, 10, -22.5], [7, 22, -28.5], [7, 42.8, -40.5]], 1.2, s.seg(8), s.hi ? 6 : 3));
  s.group(at(7, 48, -43.5, -30), () => {
    s.add("satin", C.black(), lathe([[0, -6.5], [6.6, -6.5], [8, -5], [8, 5], [6.6, 6.5], [0, 6.5]], s.seg(28)));
    s.add("rubber", C.wire(), cyl(2.3, 4.5, s.seg(10)), at(0, -8.2, 0));
    if (s.hi) s.add("satin", C.gun(), lathe([[7.95, -0.5], [8.12, -0.5], [8.12, 0.5], [7.95, 0.5], [7.95, -0.5]], 28));
  });
}

function camera(s: Sculpt): void {
  // The printed cheeks that hold it between the front standoffs.
  for (const sign of [-1, 1]) {
    s.add("rubber", C.plastic(), rbox(2, 22, 16, 0.8, 2), at(sign * 10.6, 0, 0));
    s.add("metal", C.steel(), cyl(1.7, 1, s.seg(12)), at(sign * 11.9, 0, 0, 0, 0, 90));
  }
  s.group(at(0, 0, 0, -20), () => {
    s.add("metal", C.black(), rbox(19, 19, 12, 1.4, 2), at(0, 0, -2.5));
    s.add("satin", C.pcbGreen(), box(18, 18, 1.2), at(0, 0, -9.2));
    s.add("satin", C.nylon(), box(6, 2.4, 3), at(0, -5, -11));
    if (s.hi) for (let i = -2; i <= 2; i++) s.add("metal", C.gun(), box(19.2, 0.5, 9), at(0, i * 3.2, -2.5));
    s.add("metal", C.black(), rbox(14, 14, 5, 1, 2), at(0, 0, 6));
    // The lens along +Z: barrel, knurled focus ring, front element.
    s.group(at(0, 0, 8.5, 90), () => {
      s.add("metal", C.black(), lathe([[0, 0], [6, 0], [6, 5.5], [7, 5.8], [7, 9], [6.4, 9.4], [6.4, 10.6], [5.6, 11.2], [0, 11.2]], s.seg(32)));
      if (s.hi) for (let i = 0; i < 24; i++) s.add("metal", C.gun(), box(0.34, 2.8, 0.7), at(0, 0, 0, 0, i * 15, 0).multiply(at(7.05, 7.4, 0)));
      s.add("gloss", C.lens(), lathe([[0, 11.15], [5.2, 11.15], [4.7, 12], [3.1, 12.75], [0, 13.05]], s.seg(28), 60));
    });
  });
}

// ------------------------------------------------------------------------------------------------- power
function battery(s: Sculpt): void {
  s.add("gloss", C.wrap(), rbox(35, 35, 73, 4.5, 3), at(0, 17.5, 0));
  // The printed wrap: a pale label panel on the top and both sides, one yellow band, lines of print.
  s.add("satin", C.prop(), box(26, 0.25, 46), at(0, 35.03, 4));
  s.add("satin", C.yellow(), box(26, 0.3, 3), at(0, 35.05, 24));
  for (const sign of [-1, 1]) {
    s.add("satin", C.prop(), box(0.25, 15, 46), at(sign * 17.53, 19, 4));
    s.add("satin", C.yellow(), box(0.3, 15, 3), at(sign * 17.55, 19, 24));
    if (s.hi) {
      for (const [h, d, y, z] of [[3.4, 9, 22.6, 15], [1, 14, 22.6, -11], [1, 22, 19.4, 8.5], [1, 9, 19.4, -11.5], [0.7, 30, 16.6, 4.5], [0.7, 17, 14.6, 11], [2, 6, 14.9, -13]]) s.add("satin", C.wrap(), box(0.3, h, d), at(sign * 17.56, y, z));
    }
    s.add("rubber", C.rubber(), box(27, 27, 0.5), at(0, 17.5, sign * 36.5));
  }
  if (s.hi) {
    for (const [w, d, x, z] of [[9, 3.4, -7, 15], [14, 1, 4, 15.6], [20, 1, -1.5, -13.5], [12, 1, -5.5, -15.8], [7, 2, 8, -15]]) s.add("satin", C.wrap(), box(w, 0.3, d), at(x, 35.05, z));
  }
  // The strap, round the pack and the top plate, with its buckle.
  const strap = trace(new Shape(), [[-20.4, -4.4], [20.4, -4.4], [20.4, 36.5], [-20.4, 36.5]], 4.2);
  strap.holes.push(trace(new Path(), [[-19.2, -3.2], [19.2, -3.2], [19.2, 35.3], [-19.2, 35.3]], 3.2));
  const band = new ExtrudeGeometry(strap, { depth: 20, bevelEnabled: false, curveSegments: 4 });
  band.deleteAttribute("uv");
  s.add("rubber", C.rubber(), crease(band, 30), at(0, 0, -10));
  s.add("rubber", C.rubber(), box(15, 1, 19), at(-1.5, 36.9, 0));
  s.add("metal", C.steel(), rbox(3.6, 2, 22.5, 0.6, 1), at(-11.5, 37.2, 0));
  if (s.hi) for (const z of [-6.5, 6.5]) s.add("rubber", C.plastic(), box(13, 0.2, 1.2), at(11, 36.55, z));

  // Main lead: out of the back, looping down to the plug that mates with the ESC's.
  const y = XT.y - (QUAD.topY + QUAD.plateT + 1);
  for (const [x, colour] of [[XT.red, C.red()], [XT.black, C.wire()]] as Array<[number, ReturnType<typeof C.red>]>) {
    s.add("satin", colour, tube([[x, 27, -34], [x, 28, -58], [x, 24, -90], [x, 8, -110], [x, -9, -113], [x, y, -106], [x, y, -101]], 1.9, s.seg(10), s.hi ? 6 : 3));
    s.add("rubber", C.wire(), cyl(2.35, 4.5, s.seg(12)), at(x, y, -102, 90));
  }
  s.add("satin", C.yellow(), rbox(15.8, 8.1, 16, 1.2), at((XT.red + XT.black) / 2, y, XT.join - 8));
  // Balance lead and its plug.
  if (s.hi) for (let j = 0; j < 5; j++) s.add("satin", j === 0 ? C.red() : C.wire(), tube([[8 + j, 27, -34], [8 + j, 27.5, -43.5], [8.5 + j, 20, -46.5], [8.5 + j, 14, -42]], 0.45, 5, 4));
  s.add("satin", C.nylon(), box(13, 5.7, 6), at(10.5, 11.6, -40.6));
}

function gps(s: Sculpt): void {
  s.add("rubber", C.plastic(), rbox(20, 3, 20, 1, 2), at(0, 1.5, 0));
  s.add("satin", C.pcbBlack(), box(18, 1.2, 18), at(0, 3.6, 0));
  // The ceramic patch antenna with its silvered top.
  s.add("satin", C.tan(), rbox(13, 3.2, 13, 0.5, 1), at(0, 5.8, 0));
  s.add("metal", C.steel(), box(10, 0.15, 10), at(0, 7.45, 0));
  if (s.hi) {
    s.add("satin", C.chip(), box(3, 0.8, 3), at(-7, 4.6, -7));
    s.add("satin", C.nylon(), box(5, 1.6, 2.6), at(4, 5, -8.2));
  }
}

export const QUAD_DETAIL: Record<string, (s: Sculpt) => void> = {
  "quad/bottom-plate": bottomPlate,
  "quad/arm": arm,
  "quad/main-plate": mainPlate,
  "quad/top-plate": topPlate,
  "quad/standoffs": standoffs,
  "quad/stack-bolts": stackBolts,
  "quad/motor": motor,
  "quad/prop": prop,
  "quad/esc": esc,
  "quad/fc": fc,
  "quad/receiver": receiver,
  "quad/vtx": vtx,
  "quad/camera": camera,
  "quad/battery": battery,
  "quad/gps": gps,
};
