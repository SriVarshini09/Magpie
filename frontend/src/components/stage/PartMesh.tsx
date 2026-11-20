// One mesh of one part, in any 3D view (PLAN §11.6 core 1–3, §11.12).
// Hover: pointer cursor, emissive tint, blue outline, the row in the list highlights (two-way).
// Click: select, the camera flies in, the part panel opens. Unknown lines are grey edges until they resolve.
// Ctrl-click hides the mesh; double-click isolates its line (the others drop to 10% and stop taking clicks).
// A part may carry several materials: `natural` is then a list, one entry per group of the geometry, and a
// material with `vertexColours` takes its colours from the geometry (a motor's copper, steel and black in one
// draw call). Hover, tint, ghosting, hiding and isolating act on every material of the part together.
import { Edges, Outlines, useCursor } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { easing } from "maath";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Color, MathUtils, MeshPhysicalMaterial, MeshStandardMaterial, Vector3, type BufferGeometry, type Group, type Mesh, type Quaternion } from "three";

import { ActionIcon } from "@/components/panel/ActionBadge";
import { money } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import { isPending, paintFor, token } from "@/lib/stage";

import { Anchor, useStage } from "./Stage3D";
import { useStageView } from "./viewStore";

export type Natural = {
  colour: string;
  roughness: number;
  metalness: number;
  opacity?: number;
  /** A clear coat over the base (carbon plate, a prop, a lens): 0..1. */
  clearcoat?: number;
  clearcoatRoughness?: number;
  /** The geometry's `color` attribute carries the colours; `colour` is then a tint, normally white. */
  vertexColours?: boolean;
  /**
   * The geometry's `finish` attribute (roughness, metalness, clear coat, carbon weave) sets the finish per
   * vertex, so steel, copper, plastic and carbon share one draw call. Needs `vertexColours` and a clear coat.
   */
  vertexFinish?: boolean;
};

type Skin = { material: MeshStandardMaterial; natural: Natural; flat: { value: number } };

const N = "\n";
/** Unknown, or painted in a store's or a status colour: the baked colours give way, their lightness stays. */
const FLAT = "vec3( 0.42 + 0.58 * sqrt( dot( vColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) ) ) )";
/** Carbon plate: a 2/2 twill of 1.6 mm tows, in the part's own millimetres, fading out before it can shimmer. */
const WEAVE = [
  "float b2cWeave = 1.0;",
  "if ( vFinish.w > 0.5 ) {",
  "  vec2 q = vB2cPos.xz / 1.6;",
  "  vec2 cell = floor( q );",
  "  float warp = step( mod( cell.x + cell.y, 4.0 ), 1.5 );",
  "  float across = fract( mix( q.y, q.x, warp ) );",
  "  float tow = mix( 0.62, 1.5, warp ) * ( 0.72 + 0.4 * sin( 3.14159 * across ) );",
  "  b2cWeave = mix( 1.0, tow, 1.0 - smoothstep( 0.2, 0.75, fwidth( q.x ) + fwidth( q.y ) ) );",
  "}",
].join(N);

/**
 * One material of a part. With vertex colours, `flat` (0..1) swaps the baked colours for the material's own
 * colour, keeping only their lightness: that is how a detailed part turns grey while unknown, or takes a store's
 * or a status colour, and still shows its windings and pads.
 */
function makeSkin(natural: Natural): Skin {
  const base = { color: token("--b2c-mat-unknown"), roughness: natural.roughness, metalness: natural.metalness, transparent: true, opacity: 0.06, vertexColors: Boolean(natural.vertexColours) };
  const material = natural.clearcoat ? new MeshPhysicalMaterial({ ...base, clearcoat: natural.clearcoat, clearcoatRoughness: natural.clearcoatRoughness ?? 0.1 }) : new MeshStandardMaterial(base);
  const flat = { value: 1 };
  if (natural.vertexColours) {
    const finish = Boolean(natural.vertexFinish);
    material.onBeforeCompile = (shader) => {
      shader.uniforms.uFlat = flat;
      if (finish) {
        shader.vertexShader = shader.vertexShader
          .replace("#include <common>", `#include <common>${N}attribute vec4 finish;${N}varying vec4 vFinish;${N}varying vec3 vB2cPos;`)
          .replace("#include <begin_vertex>", `#include <begin_vertex>${N}vFinish = finish;${N}vB2cPos = position;`);
      }
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", `#include <common>${N}uniform float uFlat;${finish ? `${N}varying vec4 vFinish;${N}varying vec3 vB2cPos;` : ""}`)
        .replace("#include <color_fragment>", `#ifdef USE_COLOR${N}${finish ? WEAVE : "float b2cWeave = 1.0;"}${N}diffuseColor.rgb *= b2cWeave * mix( vColor.rgb, ${FLAT}, uFlat );${N}#endif`);
      if (finish) {
        shader.fragmentShader = shader.fragmentShader
          .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>${N}roughnessFactor *= vFinish.x;`)
          .replace("#include <metalnessmap_fragment>", `#include <metalnessmap_fragment>${N}metalnessFactor *= vFinish.y;`)
          .replace("#include <lights_physical_fragment>", `#include <lights_physical_fragment>${N}#ifdef USE_CLEARCOAT${N}material.clearcoat *= vFinish.z;${N}#endif`);
      }
    };
    material.customProgramCacheKey = () => (finish ? "b2c-finish" : "b2c-flat");
  }
  return { material, natural, flat };
}

export type PartMeshProps = {
  /** Unique per mesh instance, e.g. "motor#2". */
  meshKey: string;
  lineId: string | null;
  /** "motor 2 of 4" or "servo 2 of 6 · shoulder_lift". */
  label: string;
  /** The piece's own name, for the leader-line labels ("under arm", "top plate"). Defaults to `label`. */
  shortLabel?: string;
  geometry: BufferGeometry;
  position: Vector3;
  quaternion?: Quaternion;
  scale?: Vector3;
  /** Offset at full explode, in the parent's units. */
  explode?: Vector3;
  /** 0..1: where this part's stage starts on the explode slider. 0 leaves first (the last part assembled). */
  stagger?: number;
  /** One material, or one per group of the geometry. */
  natural: Natural | Natural[];
  /** False until the intro reveal reaches this part's assembly order. */
  revealed: boolean;
  /** The first mesh of its line: carries the chip when the line was selected from the list. */
  primary: boolean;
  /** Where the label sits, in the mesh's own units. */
  labelOffset?: [number, number, number];
  /** Scale pop on reveal. Off for meshes whose origin is far from their geometry (URDF meshes). */
  pop?: boolean;
  /** Grey CAD edges while the line is unknown. Off for heavy STL meshes, which ghost instead. */
  edges?: boolean;
  /** Outline width in the mesh's own units (millimetres for procedural models, metres for the URDF). */
  outline?: number;
  /** Where the mesh starts before it flies to `position` (the kit view: from the assembled pose to the grid). */
  from?: Vector3;
  /** The scale the mesh starts at before it eases to `scale` (the kit view sizes each line to its cell). */
  fromScale?: Vector3;
  /** Seconds the move to `position` takes to settle. */
  travel?: number;
  /** Height of the hop on the way to `position`, in the parent's units. */
  hop?: number;
};

const target = new Color();
const targetPos = new Vector3();
const BLACK = new Color(0, 0, 0);
const ONE = new Vector3(1, 1, 1);
/** Each explode stage takes this share of the slider; the stages overlap, so outer parts lead. */
const STAGE_WINDOW = 0.55;

export function PartMesh({ meshKey, lineId, label, shortLabel, geometry, position, quaternion, scale, explode, stagger = 0, natural, revealed, primary, labelOffset, pop = true, edges = true, outline = 1.1, from, fromScale, travel = 0.22, hop = 0 }: PartMeshProps) {
  const { data, interactive, register } = useStage();
  const line = lineId ? data.lines.get(lineId) : undefined;
  const mode = useAppStore((s) => s.colourMode);
  const hovered = useAppStore((s) => interactive && lineId !== null && s.hoveredLineId === lineId);
  const selected = useAppStore((s) => interactive && lineId !== null && s.selectedLineId === lineId);
  const anySelected = useAppStore((s) => interactive && s.selectedLineId !== null);
  const carriesChip = useAppStore((s) => interactive && lineId !== null && s.selectedLineId === lineId && (s.selectedMeshKey ? s.selectedMeshKey === meshKey : primary));
  const faded = useStageView((s) => interactive && s.isolatedLineId !== null && s.isolatedLineId !== lineId);
  const isolated = useStageView((s) => interactive && lineId !== null && s.isolatedLineId === lineId);
  const hidden = useStageView((s) => interactive && s.hidden.has(meshKey));
  const labelsOn = useStageView((s) => s.labelsOn);
  const [over, setOver] = useState(false);
  // A faded or hidden mesh lets the pointer through to whatever is behind it.
  const inert = faded || hidden;
  useCursor(over && !inert);
  useEffect(() => {
    if (inert) setOver(false);
  }, [inert]);

  const group = useRef<Group>(null);
  const mesh = useRef<Mesh>(null);
  const skins = useMemo(
    () => (Array.isArray(natural) ? natural : [natural]).map(makeSkin),
    // The materials are created once; their colour and opacity are eased every frame.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const material = useMemo(() => (Array.isArray(natural) ? skins.map((s) => s.material) : skins[0].material), [natural, skins]);
  useEffect(() => () => skins.forEach((s) => s.material.dispose()), [skins]);

  useEffect(() => {
    if (mesh.current) register(meshKey, { lineId, label, shortLabel: shortLabel ?? label, primary, object: mesh.current });
    return () => register(meshKey, null);
  }, [meshKey, lineId, label, shortLabel, primary, register]);

  // The group's position is eased in useFrame and never set from props, so a new target is a move, not a jump.
  const flat = useRef(new Vector3());
  const hopTo = useRef(new Vector3(Infinity, 0, 0));
  const hopSpan = useRef(0);
  useLayoutEffect(() => {
    flat.current.copy(from ?? position);
    group.current?.position.copy(flat.current);
    group.current?.scale.copy(fromScale ?? scale ?? ONE);
    // Once, on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pending = !revealed || (line ? isPending(line.status) : false);
  const paint = paintFor(line, mode, data);
  const dimmed = anySelected && !selected && !isolated;
  const brand = useMemo(() => new Color(token("--b2c-brand")), []);
  const popFrom = useRef(pop ? 0.9 : 1);

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    const lit = !inert && (hovered || selected);
    const painted = pending || paint.token !== null;
    let seen = 0;
    for (const { material, natural, flat } of skins) {
      // Colour: grey while unknown, then the mode's colour (or the part's own material).
      target.set(pending ? token("--b2c-mat-unknown") : paint.token ? token(paint.token) : natural.colour);
      easing.dampC(material.color, target, 0.18, delta);
      flat.value += ((painted ? 1 : 0) - flat.value) * Math.min(1, delta * 7);
      const baseOpacity = natural.opacity ?? 1;
      const opacity = hidden ? 0 : faded ? Math.min(0.1, baseOpacity) : pending ? (edges ? 0.06 : 0.14) : (paint.ghost ? 0.35 : baseOpacity) * (dimmed ? 0.4 : 1);
      easing.damp(material, "opacity", opacity, hidden ? 0.08 : 0.15, delta);
      const solid = material.opacity > 0.985;
      // A faded part must not hide the isolated one behind it: no depth write (PLAN §11.12).
      const depthWrite = !faded && !hidden && (solid || baseOpacity >= 1);
      if (material.transparent === solid || material.depthWrite !== depthWrite) {
        material.transparent = !solid;
        material.depthWrite = depthWrite;
        material.needsUpdate = true;
      }
      seen = Math.max(seen, material.opacity);
      easing.dampC(material.emissive, lit ? brand : BLACK, 0.1, delta);
      material.emissiveIntensity = lit ? 0.22 : 0;
    }
    g.visible = !(hidden && seen < 0.02);

    // Explode: pos + explode × t (PLAN §3.20), staged so the last part assembled leaves first.
    const t = useAppStore.getState().explode;
    targetPos.copy(position);
    if (explode && t > 0) {
      const k = MathUtils.smootherstep((t - stagger * (1 - STAGE_WINDOW)) / STAGE_WINDOW, 0, 1);
      targetPos.addScaledVector(explode, k);
    }
    easing.damp3(flat.current, targetPos, travel, delta);
    if (fromScale && scale) easing.damp3(g.scale, scale, travel, delta);
    g.position.copy(flat.current);
    if (hop > 0) {
      // A hop on the way: highest mid-flight, zero at both ends.
      if (targetPos.distanceToSquared(hopTo.current) > 1e-10) {
        hopTo.current.copy(targetPos);
        hopSpan.current = Math.hypot(targetPos.x - flat.current.x, targetPos.z - flat.current.z);
      }
      const left = Math.hypot(targetPos.x - flat.current.x, targetPos.z - flat.current.z);
      if (hopSpan.current > 1e-6) g.position.y += hop * Math.sin(Math.PI * Math.min(1, left / hopSpan.current));
    }

    if (pop && mesh.current) {
      const s = pending ? 0.9 : 1;
      popFrom.current += (s - popFrom.current) * Math.min(1, delta * 9);
      mesh.current.scale.setScalar(popFrom.current);
    }
  });

  const events = interactive && lineId
    ? {
        onPointerOver: (e: ThreeEvent<PointerEvent>) => {
          if (inert) return;
          e.stopPropagation();
          setOver(true);
          useAppStore.getState().hover(lineId);
        },
        onPointerOut: () => {
          setOver(false);
          const s = useAppStore.getState();
          if (s.hoveredLineId === lineId) s.hover(null);
        },
        onClick: (e: ThreeEvent<MouseEvent>) => {
          if (inert) return;
          e.stopPropagation();
          if (e.nativeEvent.ctrlKey || e.nativeEvent.metaKey) {
            // Ctrl-click hides this mesh. "Unhide all" brings it back.
            useStageView.getState().hide([meshKey]);
            const s = useAppStore.getState();
            if (s.hoveredLineId === lineId) s.hover(null);
            if (s.selectedMeshKey === meshKey) s.clearSelection();
            return;
          }
          useAppStore.getState().select(lineId, meshKey, undefined, label);
        },
        onDoubleClick: (e: ThreeEvent<MouseEvent>) => {
          if (inert || e.nativeEvent.ctrlKey || e.nativeEvent.metaKey) return;
          e.stopPropagation();
          const view = useStageView.getState();
          view.isolate(view.isolatedLineId === lineId ? null : lineId);
        },
      }
    : {};

  const showOutline = !pending && !inert && (hovered || selected);
  const showChip = carriesChip && !pending && !hidden;
  const showHoverLabel = over && !showChip && !inert && !labelsOn;

  return (
    <group ref={group} quaternion={quaternion}>
      <mesh ref={mesh} geometry={geometry} material={material} castShadow receiveShadow {...events}>
        {pending && edges ? <Edges threshold={28} color={token("--b2c-mat-unknown")} lineWidth={1} /> : null}
        {showOutline ? <Outlines thickness={selected ? outline * 1.35 : outline} color={token("--b2c-brand")} angle={Math.PI} /> : null}
        {showChip || showHoverLabel ? (
          <Anchor id={`label:${meshKey}`} position={labelOffset} deps={`${label}|${showChip}|${line?.storeName}|${line?.price}|${line?.status}`}>
            <div className="-translate-y-10 rounded-md border border-stage-border bg-stage-surface/95 px-2.5 py-1.5 text-caption whitespace-nowrap text-stage-text shadow-e2">
              <p className="font-medium">{label}</p>
              {showChip && line ? (
                <p className="mt-0.5 flex items-center gap-1.5 text-stage-muted">
                  {line.storeName ? (
                    <>
                      {line.level ? <ActionIcon level={line.level} /> : null}
                      <span>{line.storeName}</span>
                      <span className="tabular font-mono text-stage-text">{money(line.price)}</span>
                      {line.qty > 1 ? <span>for {line.qty}</span> : null}
                    </>
                  ) : (
                    <span>{line.status === "owned" ? "you own it" : line.status === "skipped" ? "left out of the cart" : "nothing to buy"}</span>
                  )}
                </p>
              ) : null}
            </div>
          </Anchor>
        ) : null}
      </mesh>
    </group>
  );
}
