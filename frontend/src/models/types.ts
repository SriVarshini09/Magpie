// Procedural models are data (PLAN §3.20, Appendix C). Owner: C.
// The model code holds geometry; the template (RunState.view) holds meaning: which BOM line
// a mesh belongs to, its explode vector and its assembly order.

export type PartShape = "box" | "cylinder" | "roundedBox" | "torus" | "capsule";
export type PartMaterial = "carbon" | "metal" | "pcb" | "plastic" | "battery" | "rubber" | "clear";

export type PartDef = {
  /** Matches view.parts[].mesh from the template. Instances of one BOM line share it. */
  mesh: string;
  shape: PartShape;
  /** Millimetres. */
  size: number[];
  /** Millimetres; Y is up, X to the right, +Z is the front. */
  pos: [number, number, number];
  /** Degrees. */
  rot?: [number, number, number];
  material: PartMaterial;
  /** A design-token name ("--b2c-mat-accent") that replaces the material's own colour (a motor's bell cap, a battery's label band). */
  colour?: string;
  /** Extra shapes merged into the same mesh (a camera's lens, a board's chip). Positions are relative to `pos`. */
  extras?: Array<{ shape: PartShape; size: number[]; pos: [number, number, number]; rot?: [number, number, number] }>;
  /**
   * Key of a detailed solid in models/detail (a motor with its windings instead of a cylinder). When it is
   * set, `shape`, `size`, `material` and `extras` are only the fallback.
   */
  detail?: string;
  /** Drawn only when the view maps this mesh to a BOM line (an optional part such as a GPS). */
  optional?: boolean;
  /** Short name for this piece, used in the hover label ("top plate"). */
  label?: string;
  /** 4 motors = 4 meshes, one BOM line. */
  instances?: Array<{ pos: [number, number, number]; rot?: [number, number, number]; explode?: [number, number, number] }>;
  /** Defaults; RunState.view.parts overrides them. Millimetres at full explode. */
  explode: [number, number, number];
  order: number;
};
