// SO-101 URDF arm viewer (PLAN §3.12, §11.6, §11.12): the heavy half, loaded on demand by workspace/ArmViewer.
// Recipe: armModel loads the URDF and its meshes from /so101 → mesh name → BOM line (the six servos share one
// line) → the shared stage.
import { useEffect, useMemo, useState } from "react";

import { token, type StageData } from "@/lib/stage";
import type { ViewData } from "@/lib/types";

import { armModel, type ArmPart, type LoadedArm } from "./armModel";
import { PartMesh, type Natural } from "./PartMesh";
import { useReveal } from "./reveal";
import { Stage3D } from "./Stage3D";
import { StageLoading } from "./StageLoading";

export type ArmViewerProps = { view: ViewData; data: StageData; interactive?: boolean; autoRotate?: boolean; onError?: (message: string) => void };

export type BuiltArmPart = ArmPart & { lineId: string | null; label: string; shortLabel: string; primary: boolean; order: number; natural: Natural };

/** Loads the arm once per URL. `null` while loading. */
export function useArm(url: string | null, onError?: (message: string) => void): LoadedArm | null {
  const [loaded, setLoaded] = useState<LoadedArm | null>(null);
  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    armModel(url)
      .then((l) => !cancelled && setLoaded(l))
      .catch((e: Error) => !cancelled && onError?.(e.message));
    return () => {
      cancelled = true;
    };
    // onError is read at call time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);
  return loaded;
}

/** Gives every mesh its BOM line, its label and its place in the assembly order. */
export function buildArm(loaded: LoadedArm, view: ViewData, data: StageData): BuiltArmPart[] {
  const lineOf = new Map(view.parts.map((p) => [p.mesh, p.bom_line_id]));
  const orderOf = new Map(view.parts.map((p) => [p.mesh, p.order]));
  // A mesh the template does not list still belongs to "3D-printed parts" when that line exists.
  const printedLine = [...data.lines.values()].find((l) => l.category === "printed")?.id ?? null;
  const servoTotal = loaded.parts.filter((p) => p.isServo).length;
  const seen = new Set<string>();
  let servoIndex = 0;
  // Smooth normals pick up the studio reflections, so the printed plastic gets a soft sheen instead of flat facets.
  const printed: Natural = { colour: token("--b2c-mat-printed"), roughness: loaded.smooth ? 0.62 : 0.85, metalness: 0 };
  const servo: Natural = { colour: token("--b2c-mat-servo"), roughness: loaded.smooth ? 0.42 : 0.5, metalness: 0.25 };
  // Assembly order: base to gripper, by height of the link.
  const sorted = [...loaded.parts].sort((a, b) => a.centre.y - b.centre.y);
  const rank = new Map(sorted.map((p, i) => [p.key, i]));
  return loaded.parts.map((p) => {
    const lineId = lineOf.get(p.mesh) ?? (p.isServo ? null : printedLine);
    const lineName = (lineId ? data.lines.get(lineId)?.name : null) ?? p.mesh;
    const piece = p.mesh.replace(/_so101.*$|_v\d+$/gi, "").replace(/_/g, " ");
    let label = `${lineName} · ${piece}`;
    let shortLabel = piece.charAt(0).toUpperCase() + piece.slice(1);
    if (p.isServo) {
      servoIndex += 1;
      label = `Servo ${servoIndex} of ${servoTotal}${p.joint ? ` · ${p.joint}` : ""}`;
      shortLabel = `Servo ${servoIndex}${p.joint ? ` · ${p.joint.replace(/_/g, " ")}` : ""}`;
    }
    const primary = lineId !== null && !seen.has(lineId);
    if (primary && lineId) seen.add(lineId);
    const order = Math.floor(((rank.get(p.key) ?? 0) / Math.max(1, loaded.parts.length)) * 6) + (orderOf.get(p.mesh) ?? 1) - 1;
    return { ...p, lineId, label, shortLabel, primary, order, natural: p.isServo ? servo : printed };
  });
}

export default function ArmScene({ view, data, interactive = true, autoRotate = false, onError }: ArmViewerProps) {
  const loaded = useArm(view.urdf_url ?? "/so101/so101_new_calib.urdf", onError);
  // Statuses and prices change often; the mesh list depends only on the mapping.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const built = useMemo(() => (loaded ? buildArm(loaded, view, data) : null), [loaded, view.parts]);
  const maxOrder = built ? Math.max(1, ...built.map((p) => p.order)) : 1;
  const step = useReveal(maxOrder, built ? "arm" : "loading", 170);

  if (!loaded || !built) return <StageLoading>Loading the SO-101 model from this app’s own files…</StageLoading>;

  return (
    <Stage3D data={data} readyKey={`arm:${built.length}`} interactive={interactive} autoRotate={autoRotate} home={[Math.PI / 3.4, Math.PI / 2.6]}>
      <group position={loaded.offset} scale={loaded.scale}>
        {built.map((p) => (
          <PartMesh
            key={p.key}
            meshKey={p.key}
            lineId={p.lineId}
            label={p.label}
            shortLabel={p.shortLabel}
            geometry={p.geometry}
            position={p.position}
            quaternion={p.quaternion}
            scale={p.scale}
            explode={p.explode}
            stagger={1 - p.order / maxOrder}
            natural={p.natural}
            revealed={p.order <= step}
            primary={p.primary}
            labelOffset={p.local}
            pop={false}
            edges={false}
            outline={0.0013}
          />
        ))}
      </group>
    </Stage3D>
  );
}
