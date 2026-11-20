// Procedural models on the stage (PLAN §3.20, Appendix C.1): the heavy half, loaded on demand by
// models/ProceduralView. Every PartDef becomes one mesh per instance inside the same stage, lighting, <Bvh>,
// hover outline and camera code as the arm. No external assets, no fonts, no network.
// A PartDef with a `detail` key is drawn with its detailed solid (models/detail): one geometry shared by all
// its instances, one material per finish. The non-interactive stage (the start page) gets the light variant.
// The model holds geometry, explode vectors and assembly order; RunState.view says which BOM line a mesh belongs to.
import { useEffect, useMemo } from "react";
import { Box3, Matrix4, Vector3, type BufferGeometry, type Quaternion } from "three";

import { instanceLabel, type StageData } from "@/lib/stage";
import type { ViewData } from "@/lib/types";
import { partSolid, quatOf } from "@/models/geometry";
import { PROCEDURAL_MODELS } from "@/models/ProceduralView";
import type { PartDef } from "@/models/types";

import { PartMesh, type Natural } from "./PartMesh";
import { STAGE_SIZE, useReveal } from "./reveal";
import { Stage3D } from "./Stage3D";

export type ProceduralViewProps = { view: ViewData; data: StageData; interactive?: boolean; autoRotate?: boolean };

/** Home view (azimuth, polar) per model, so each one is framed three-quarter from its best side. */
const HOME: Record<string, [number, number]> = {
  quadcopter: [Math.PI / 5, Math.PI / 3.2],
  rc_car: [Math.PI / 3.6, Math.PI / 2.7],
  claw: [Math.PI / 7, Math.PI / 2.6],
};

export type BuiltPart = {
  key: string;
  mesh: string;
  lineId: string | null;
  label: string;
  shortLabel: string;
  geometry: BufferGeometry;
  position: Vector3;
  quaternion: Quaternion;
  explode: Vector3;
  natural: Natural | Natural[];
  /** Grey CAD edges while the line is unknown: only for the plain shapes. A detailed solid ghosts instead. */
  edges: boolean;
  order: number;
  primary: boolean;
  top: number;
  /** The part's box in the model's frame (millimetres), as it sits in the assembled model. */
  box: Box3;
};

const ONE = new Vector3(1, 1, 1);

/** Builds the mesh list and the transform that sits the model on the ground, centred, at stage size. */
export function buildModel(allDefs: PartDef[], view: ViewData, data: StageData, hi = true) {
  const lineOf = new Map(view.parts.map((p) => [p.mesh, p.bom_line_id]));
  // An optional part (a GPS) is drawn only when the view maps it to a line.
  const defs = allDefs.filter((d) => !d.optional || lineOf.has(d.mesh));
  const seenLine = new Set<string>();
  const counters = new Map<string, number>();
  const totals = new Map<string, number>();
  // "motor 2 of 4" counts the instances of the piece that carries the mesh's name (not its sub-pieces).
  for (const def of defs) if (!def.label) totals.set(def.mesh, (totals.get(def.mesh) ?? 0) + (def.instances?.length ?? 1));

  const parts: BuiltPart[] = [];
  const bounds = new Box3();
  const m = new Matrix4();
  for (const [d, def] of defs.entries()) {
    const lineId = lineOf.get(def.mesh) ?? null;
    const lineName = (lineId ? data.lines.get(lineId)?.name : null) ?? def.mesh.replace(/_/g, " ");
    const instances = def.instances ?? [{ pos: def.pos, rot: def.rot }];
    // One geometry for every instance of the part: four motors share one set of buffers.
    const { geometry, natural, detailed } = partSolid(def, hi);
    if (!geometry.boundingBox) geometry.computeBoundingBox();
    for (const [i, inst] of instances.entries()) {
      const position = new Vector3(...inst.pos);
      const quaternion = quatOf(inst.rot ?? def.rot);
      const box = geometry.boundingBox!.clone().applyMatrix4(m.compose(position, quaternion, ONE));
      bounds.union(box);
      let label = def.label ? `${lineName} · ${def.label}` : lineName;
      if (!def.label) {
        const n = counters.get(def.mesh) ?? 0;
        counters.set(def.mesh, n + 1);
        label = instanceLabel(lineName, n, totals.get(def.mesh) ?? 1);
      }
      const primary = lineId !== null && !seenLine.has(lineId) && !def.label;
      if (primary && lineId) seenLine.add(lineId);
      parts.push({
        key: `${def.mesh}#${d}.${i}`,
        mesh: def.mesh,
        lineId,
        label,
        shortLabel: def.label ? def.label.charAt(0).toUpperCase() + def.label.slice(1) : label,
        geometry,
        position,
        quaternion,
        explode: new Vector3(...(("explode" in inst && inst.explode) || def.explode)),
        natural,
        edges: !detailed,
        order: def.order,
        primary,
        top: geometry.boundingBox!.max.y,
        box,
      });
    }
  }
  const size = bounds.getSize(new Vector3());
  const centre = bounds.getCenter(new Vector3());
  const scale = STAGE_SIZE / Math.max(size.x, size.y, size.z, 1);
  const offset = new Vector3(-centre.x * scale, -bounds.min.y * scale, -centre.z * scale);
  const maxOrder = Math.max(1, ...parts.map((p) => p.order));
  return { parts, scale, offset, maxOrder };
}

export default function ProceduralScene({ view, data, interactive = true, autoRotate = false }: ProceduralViewProps) {
  const modelName = view.model ?? "";
  const defs = PROCEDURAL_MODELS[modelName] ?? [];
  // Geometry depends on the model and the mesh-to-line map, not on prices or statuses.
  const mapKey = view.parts.map((p) => `${p.mesh}:${p.bom_line_id}`).join(",");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const model = useMemo(() => buildModel(defs, view, data, interactive), [defs, mapKey, interactive]);
  useEffect(() => () => model.parts.forEach((p) => p.geometry.dispose()), [model]);
  const step = useReveal(model.maxOrder, modelName);
  const sized = view.scale && view.scale > 0 ? view.scale : 1;

  return (
    <Stage3D data={data} readyKey={`${modelName}:${model.parts.length}`} interactive={interactive} autoRotate={autoRotate} home={HOME[modelName]}>
      {/* A size variant (the 3-inch build) is the same model scaled by the template's view.scale, on the ground. */}
      <group position={model.offset.clone().multiplyScalar(sized)} scale={model.scale * sized}>
        {model.parts.map((p) => (
          <PartMesh
            key={p.key}
            meshKey={p.key}
            lineId={p.lineId}
            label={p.label}
            shortLabel={p.shortLabel}
            geometry={p.geometry}
            position={p.position}
            quaternion={p.quaternion}
            explode={p.explode}
            stagger={1 - p.order / model.maxOrder}
            natural={p.natural}
            revealed={p.order <= step}
            primary={p.primary}
            labelOffset={[0, p.top, 0]}
            edges={p.edges}
          />
        ))}
      </group>
    </Stage3D>
  );
}
