// Mesh name -> BOM line, for whichever view is showing (PLAN §3.20, §11.12). Owner: C.
import type { ViewData } from "@/lib/types";

/** mesh name (URDF mesh file stem, procedural mesh, diagram node id) -> bom_line_id */
export function meshToLine(view: ViewData): Map<string, string> {
  return new Map(view.parts.map((p) => [p.mesh, p.bom_line_id]));
}

/** bom_line_id -> mesh names. A line with several meshes (six servos) highlights all of them. */
export function lineToMeshes(view: ViewData): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const p of view.parts) out.set(p.bom_line_id, [...(out.get(p.bom_line_id) ?? []), p.mesh]);
  return out;
}

/** The SO-101 URDF references meshes as "assets/<name>.stl": this gives <name>. */
export function meshNameFromFile(filename: string): string {
  return filename.replace(/^.*[\\/]/, "").replace(/\.stl$/i, "");
}
