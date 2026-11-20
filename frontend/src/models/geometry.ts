// Turns PartDef shapes into three.js geometry. No external assets, no fonts, no network (PLAN §3.20).
import { BoxGeometry, CapsuleGeometry, CylinderGeometry, Euler, MathUtils, Matrix4, Quaternion, TorusGeometry, Vector3, type BufferGeometry } from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import type { Natural } from "@/components/stage/PartMesh";
import { token } from "@/lib/stage";

import { detailFor } from "./detail";
import type { PartDef, PartMaterial, PartShape } from "./types";

type Vec3 = [number, number, number];

export function shapeGeometry(shape: PartShape, size: number[]): BufferGeometry {
  switch (shape) {
    case "box":
      return new BoxGeometry(size[0], size[1], size[2]);
    case "roundedBox":
      return new RoundedBoxGeometry(size[0], size[1], size[2], 3, Math.min(size[0], size[1], size[2]) * 0.28);
    case "cylinder":
      // [radius, height, sides?]; the axis is Y.
      return new CylinderGeometry(size[0], size[0], size[1], size[2] ?? 40);
    case "torus":
      // [ring radius, tube radius]; lies in the XY plane.
      return new TorusGeometry(size[0], size[1], 14, 48);
    case "capsule":
      // [radius, length of the straight part]; the axis is Y.
      return new CapsuleGeometry(size[0], size[1], 6, 14);
  }
}

export function quatOf(rot?: Vec3): Quaternion {
  const q = new Quaternion();
  if (rot) q.setFromEuler(new Euler(MathUtils.degToRad(rot[0]), MathUtils.degToRad(rot[1]), MathUtils.degToRad(rot[2])));
  return q;
}

const ONE = new Vector3(1, 1, 1);

/** The part's main shape plus its extras, merged into one geometry in the part's own frame. */
export function partGeometry(def: Pick<PartDef, "shape" | "size" | "extras">): BufferGeometry {
  if (!def.extras?.length) return shapeGeometry(def.shape, def.size);
  const pieces = [shapeGeometry(def.shape, def.size)];
  for (const extra of def.extras) {
    const g = shapeGeometry(extra.shape, extra.size);
    g.applyMatrix4(new Matrix4().compose(new Vector3(...extra.pos), quatOf(extra.rot), ONE));
    pieces.push(g);
  }
  // Non-indexed pieces merge whatever their source; uv is dropped because nothing is textured.
  const flat = pieces.map((p) => {
    const n = p.index ? p.toNonIndexed() : p;
    n.deleteAttribute("uv");
    return n;
  });
  const merged = mergeGeometries(flat, false);
  for (const p of [...pieces, ...flat]) if (p !== merged) p.dispose();
  return merged ?? shapeGeometry(def.shape, def.size);
}

const MATERIALS: Record<PartMaterial, { tokenName: string; roughness: number; metalness: number; opacity?: number }> = {
  carbon: { tokenName: "--b2c-mat-carbon", roughness: 0.5, metalness: 0.15 },
  metal: { tokenName: "--b2c-mat-metal", roughness: 0.35, metalness: 0.75 },
  pcb: { tokenName: "--b2c-mat-pcb", roughness: 0.55, metalness: 0.1 },
  plastic: { tokenName: "--b2c-mat-plastic", roughness: 0.6, metalness: 0.05 },
  battery: { tokenName: "--b2c-mat-battery", roughness: 0.7, metalness: 0.1 },
  rubber: { tokenName: "--b2c-mat-rubber", roughness: 0.92, metalness: 0 },
  clear: { tokenName: "--b2c-mat-clear", roughness: 0.15, metalness: 0, opacity: 0.16 },
};

export function naturalOf(def: Pick<PartDef, "material" | "colour">): Natural {
  const m = MATERIALS[def.material];
  return { colour: token(def.colour ?? m.tokenName), roughness: m.roughness, metalness: m.metalness, opacity: m.opacity };
}

/**
 * What a part is drawn with: its detailed solid (one geometry, colours and finishes in its vertices) when the
 * model has one, otherwise the plain shape. `hi` false asks for the light variant of a detailed solid.
 * A detailed geometry is shared by every instance of the part.
 */
export function partSolid(def: Pick<PartDef, "shape" | "size" | "extras" | "material" | "colour" | "detail">, hi = true): { geometry: BufferGeometry; natural: Natural | Natural[]; detailed: boolean } {
  const built = detailFor(def.detail, hi);
  if (built) return { geometry: built.geometry, natural: built.natural, detailed: true };
  return { geometry: partGeometry(def), natural: naturalOf(def), detailed: false };
}
