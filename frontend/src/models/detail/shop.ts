// The shop: what every detailed part is cut from (PLAN §3.20). A part is built from many small solids, each
// with a finish and a colour. `Sculpt` merges them into ONE geometry with the colour and the finish (roughness,
// metalness, clear coat, carbon weave) baked into the vertices, so a motor with a steel ring, copper windings,
// a black bell and silicone leads is one draw call. No textures, no files, no network.
//
// Method after the `cutaway` skill (Nyxera0x/cutaway, MIT, on whaleyxbt/claude-motion, MIT): a material shop
// plus a few shape helpers, profiles turned round an axis with hard edges kept (its `sweepX`; here three's
// LatheGeometry through `toCreasedNormals`), dense mechanism under plates with gaps. See THIRD_PARTY.md.
import {
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  CatmullRomCurve3,
  Color,
  CylinderGeometry,
  Euler,
  ExtrudeGeometry,
  LatheGeometry,
  MathUtils,
  Matrix4,
  Path,
  Quaternion,
  Shape,
  TubeGeometry,
  Vector2,
  Vector3,
} from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { toCreasedNormals } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import type { Natural } from "@/components/stage/PartMesh";
import { token } from "@/lib/stage";

/** A finish is a shading class; the colour of each solid inside it comes from its vertices. */
export type Finish = "carbon" | "metal" | "satin" | "gloss" | "rubber";

/** Per vertex: roughness, metalness, clear coat, carbon weave (0 or 1). Read by PartMesh's material. */
const FINISHES: Record<Finish, [number, number, number, number]> = {
  // Carbon plate: a 2/2 twill under a thin resin skin, so the softboxes sit on it as soft bars.
  carbon: [0.5, 0.05, 0.4, 1],
  // Steel, anodized aluminium, copper, gold: the colour decides which.
  metal: [0.32, 0.92, 0, 0],
  // Solder mask, moulded plastic, silicone wire, chip packages.
  satin: [0.52, 0.04, 0, 0],
  // Polycarbonate props, lens glass, shrink wrap.
  gloss: [0.24, 0, 1, 0],
  rubber: [0.86, 0, 0, 0],
};
const NATURAL: Natural = { colour: "#ffffff", roughness: 1, metalness: 1, clearcoat: 1, clearcoatRoughness: 0.16, vertexColours: true, vertexFinish: true };

export type Sculpted = { geometry: BufferGeometry; natural: Natural };
export type P2 = [number, number];
export type P3 = [number, number, number];

const colours = new Map<string, Color>();
/** A design token as a linear colour for a vertex attribute. */
export function tone(name: string): Color {
  let c = colours.get(name);
  if (!c) colours.set(name, (c = new Color(token(name))));
  return c;
}

const rad = MathUtils.degToRad;
const ONE = new Vector3(1, 1, 1);

/** A placement: position in millimetres, rotation in degrees, optional scale. */
export function at(x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, scale?: P3): Matrix4 {
  return new Matrix4().compose(new Vector3(x, y, z), new Quaternion().setFromEuler(new Euler(rad(rx), rad(ry), rad(rz))), scale ? new Vector3(...scale) : ONE);
}

type Chunk = { pos: ArrayLike<number>; nor: ArrayLike<number>; colour: Color; finish: Finish };

export class Sculpt {
  private chunks: Chunk[] = [];
  private stack: Matrix4[] = [];
  /** `hi` is the full model; the low one (the start page's small stage) skips the small parts. */
  constructor(readonly hi: boolean) {}

  /** Segments round a circle: halved on the low model. */
  seg(n: number): number {
    return this.hi ? n : Math.max(6, Math.round(n / 2));
  }

  /** Everything added inside `fn` is placed by `m` (a tilted camera, one coil of twelve). */
  group(m: Matrix4, fn: () => void): void {
    const top = this.stack[this.stack.length - 1];
    this.stack.push(top ? top.clone().multiply(m) : m);
    fn();
    this.stack.pop();
  }

  /** Adds one solid. The geometry is consumed. */
  add(finish: Finish, colour: Color, g: BufferGeometry, m?: Matrix4): this {
    const top = this.stack[this.stack.length - 1];
    const full = top && m ? top.clone().multiply(m) : (top ?? m);
    if (full) g.applyMatrix4(full);
    const flat = g.index ? g.toNonIndexed() : g;
    if (!flat.getAttribute("normal")) flat.computeVertexNormals();
    this.chunks.push({ pos: flat.getAttribute("position").array, nor: flat.getAttribute("normal").array, colour, finish });
    g.dispose();
    if (flat !== g) flat.dispose();
    return this;
  }

  done(): Sculpted {
    let total = 0;
    for (const c of this.chunks) total += c.pos.length;
    const pos = new Float32Array(total);
    const nor = new Float32Array(total);
    const col = new Float32Array(total);
    const fin = new Float32Array((total / 3) * 4);
    let o = 0;
    for (const c of this.chunks) {
      pos.set(c.pos, o);
      nor.set(c.nor, o);
      const f = FINISHES[c.finish];
      for (let i = 0; i < c.pos.length; i += 3) {
        col[o + i] = c.colour.r;
        col[o + i + 1] = c.colour.g;
        col[o + i + 2] = c.colour.b;
        fin.set(f, ((o + i) / 3) * 4);
      }
      o += c.pos.length;
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(pos, 3));
    geometry.setAttribute("normal", new BufferAttribute(nor, 3));
    geometry.setAttribute("color", new BufferAttribute(col, 3));
    geometry.setAttribute("finish", new BufferAttribute(fin, 4));
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();
    this.chunks = [];
    return { geometry, natural: NATURAL };
  }
}

// ---------------------------------------------------------------------------------------------- shapes

/** Smooth where the surface turns gently, a hard edge where it turns by more than `angle` degrees. */
export function crease(g: BufferGeometry, angle = 34): BufferGeometry {
  const out = toCreasedNormals(g, rad(angle));
  if (out !== g) g.dispose();
  return out;
}

export const box = (w: number, h: number, d: number): BufferGeometry => new BoxGeometry(w, h, d);
export const rbox = (w: number, h: number, d: number, r?: number, seg = 2): BufferGeometry =>
  new RoundedBoxGeometry(w, h, d, seg, r ?? Math.min(w, h, d) * 0.22);
/** A cylinder along Y: radius, height, sides, and a different top radius for a cone. */
export const cyl = (r: number, h: number, seg = 20, rTop = r): BufferGeometry => new CylinderGeometry(rTop, r, h, seg);

/** A profile of [radius, y] points turned round the Y axis. List it bottom → outside → top for a solid. */
export function lathe(profile: P2[], seg = 32, angle = 34): BufferGeometry {
  return crease(new LatheGeometry(profile.map(([r, y]) => new Vector2(Math.max(0, r), y)), seg), angle);
}

/** A wire or hose through the points. */
export function tube(points: P3[], r: number, radial = 6, perSpan = 6): BufferGeometry {
  const curve = new CatmullRomCurve3(points.map((p) => new Vector3(...p)), false, "centripetal");
  return new TubeGeometry(curve, Math.max(2, (points.length - 1) * perSpan), r, radial, false);
}

/** Traces a closed polygon with rounded corners. `r` is one radius or one per corner. */
export function trace<T extends Path>(path: T, pts: P2[], r: number | number[]): T {
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const p = pts[i];
    const a = pts[(i + n - 1) % n];
    const b = pts[(i + 1) % n];
    const da = Math.hypot(a[0] - p[0], a[1] - p[1]);
    const db = Math.hypot(b[0] - p[0], b[1] - p[1]);
    const k = Math.min(Array.isArray(r) ? r[i] : r, da / 2, db / 2);
    const inX = p[0] + ((a[0] - p[0]) * k) / (da || 1);
    const inY = p[1] + ((a[1] - p[1]) * k) / (da || 1);
    if (i === 0) path.moveTo(inX, inY);
    else path.lineTo(inX, inY);
    if (k > 1e-4) path.quadraticCurveTo(p[0], p[1], p[0] + ((b[0] - p[0]) * k) / db, p[1] + ((b[1] - p[1]) * k) / db);
  }
  path.closePath();
  return path;
}

/** A round hole, or a polygon hole with rounded corners. Coordinates are [x, z] of the plate. */
export type Hole = { c: P2; r: number } | { pts: P2[]; r: number };

/** A slot: `len` long, `w` wide, turned `angle` degrees from the X axis. */
export function slot(cx: number, cz: number, len: number, w: number, angle = 0): Hole {
  const c = Math.cos(rad(angle));
  const s = Math.sin(rad(angle));
  const pts = ([[-len / 2, -w / 2], [len / 2, -w / 2], [len / 2, w / 2], [-len / 2, w / 2]] as P2[]).map(([x, z]): P2 => [cx + x * c - z * s, cz + x * s + z * c]);
  return { pts, r: w / 2 };
}

/** Points on a circle, for outlines with a round end. Degrees, anticlockwise from +X toward +Z. */
export function arc(cx: number, cz: number, r: number, from: number, to: number, steps: number): P2[] {
  const out: P2[] = [];
  for (let i = 0; i <= steps; i++) {
    const a = rad(from + ((to - from) * i) / steps);
    out.push([cx + r * Math.cos(a), cz + r * Math.sin(a)]);
  }
  return out;
}

const flip = ([x, z]: P2): P2 => [x, -z];

/**
 * A flat plate cut from sheet: an outline in [x, z], holes, a thickness along Y (the plate sits on y = 0) and
 * a small chamfer on every edge, which is what catches the light on a real carbon plate.
 */
export function plate(outline: P2[], thickness: number, opts: { holes?: Hole[]; round?: number | number[]; bevel?: number; curve?: number } = {}): BufferGeometry {
  const { holes = [], round = 2, bevel = 0.3, curve = 5 } = opts;
  const shape = trace(new Shape(), outline.map(flip), round);
  for (const h of holes) {
    const p = new Path();
    if ("c" in h) p.absarc(h.c[0], -h.c[1], h.r, 0, Math.PI * 2, false);
    else trace(p, h.pts.map(flip), h.r);
    shape.holes.push(p);
  }
  const b = Math.min(bevel, thickness / 3);
  const g = new ExtrudeGeometry(shape, { depth: thickness - 2 * b, bevelEnabled: b > 0, bevelThickness: b, bevelSize: b, bevelOffset: -b, bevelSegments: 1, curveSegments: curve });
  g.deleteAttribute("uv");
  g.rotateX(-Math.PI / 2);
  g.translate(0, b, 0);
  return crease(g, 30);
}

/** A closed skin over rings of points (each ring the same length), capped at both ends. Wound outward. */
export function loft(rings: Vector3[][]): BufferGeometry {
  const k = rings[0].length;
  const pos: number[] = [];
  for (const ring of rings) for (const p of ring) pos.push(p.x, p.y, p.z);
  const idx: number[] = [];
  for (let i = 0; i < rings.length - 1; i++) {
    for (let j = 0; j < k; j++) {
      const a = i * k + j;
      const b = i * k + ((j + 1) % k);
      const c = (i + 1) * k + ((j + 1) % k);
      const d = (i + 1) * k + j;
      idx.push(a, d, c, a, c, b);
    }
  }
  for (const [i, turn] of [[0, false], [rings.length - 1, true]] as Array<[number, boolean]>) {
    const centre = new Vector3();
    for (const p of rings[i]) centre.add(p);
    centre.divideScalar(k);
    const at0 = pos.length / 3;
    pos.push(centre.x, centre.y, centre.z);
    for (let j = 0; j < k; j++) {
      const a = i * k + j;
      const b = i * k + ((j + 1) % k);
      if (turn) idx.push(at0, a, b);
      else idx.push(at0, b, a);
    }
  }
  // Outward whichever way the rings ran: a closed skin has a positive volume.
  let volume = 0;
  for (let t = 0; t < idx.length; t += 3) {
    const [a, b, c] = [idx[t] * 3, idx[t + 1] * 3, idx[t + 2] * 3];
    volume += pos[a] * (pos[b + 1] * pos[c + 2] - pos[b + 2] * pos[c + 1]) + pos[a + 1] * (pos[b + 2] * pos[c] - pos[b] * pos[c + 2]) + pos[a + 2] * (pos[b] * pos[c + 1] - pos[b + 1] * pos[c]);
  }
  if (volume < 0) for (let t = 0; t < idx.length; t += 3) [idx[t + 1], idx[t + 2]] = [idx[t + 2], idx[t + 1]];
  const g = new BufferGeometry();
  g.setAttribute("position", new BufferAttribute(new Float32Array(pos), 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/** Rotates a point in the plate plane by `deg` about Y (the same turn an instance's `rot: [0, deg, 0]` makes). */
export function turn([x, z]: P2, deg: number): P2 {
  const c = Math.cos(rad(deg));
  const s = Math.sin(rad(deg));
  return [x * c + z * s, -x * s + z * c];
}
