// The shared 3D stage (PLAN §11.6, §11.12): canvas, offline studio lighting, ground, camera, picking,
// ambient occlusion, the leader-line labels and the isolate / hide chips.
// Every 3D view (the SO-101 arm, the procedural models, the kit view) renders inside it.
// Offline rules (CLAUDE.md §3): RoomEnvironment through PMREM, no drei presets, no Draco, no <Text>.
import { Bvh, CameraControls, ContactShadows, Grid } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import type CameraControlsImpl from "camera-controls";
import { Eye, EyeOff, Focus, Layers } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { Box3, PMREMGenerator, Sphere, Spherical, Vector3, type Group, type Object3D, type PerspectiveCamera } from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

import { useAppStore } from "@/lib/store";
import { token, type StageData } from "@/lib/stage";

import { StageEffects } from "./Effects";
import { createLabelBus, LeaderLabelLayer, LeaderLabelProjector } from "./LeaderLabels";
import { prefersReducedMotion } from "./reveal";
import { useStageView } from "./viewStore";
import "./stage.css";

export type StageEntry = { lineId: string | null; label: string; shortLabel: string; primary: boolean; object: Object3D };

type AnchorEntry = { object: Object3D; node: ReactNode };

export type StageContextValue = {
  data: StageData;
  interactive: boolean;
  register: (meshKey: string, entry: StageEntry | null) => void;
  /** Pins a DOM label to a 3D object (see <Anchor>). */
  anchor: (id: string, entry: AnchorEntry | null) => void;
};

const StageContext = createContext<StageContextValue | null>(null);

export function useStage(): StageContextValue {
  const ctx = useContext(StageContext);
  if (!ctx) throw new Error("useStage must be used inside <Stage3D>");
  return ctx;
}

/**
 * A DOM label pinned to a point in the scene. The label is drawn in one overlay beside the canvas and moved
 * every frame, which keeps it crisp and avoids a React root per label (drei's <Html>).
 * `deps` says when the label's content changed.
 */
export function Anchor({ id, position, deps, children }: { id: string; position?: [number, number, number]; deps: string; children: ReactNode }) {
  const { anchor } = useStage();
  const ref = useRef<Group>(null);
  useEffect(() => {
    if (ref.current) anchor(id, { object: ref.current, node: children });
    // `deps` stands for the children.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, deps, anchor]);
  useEffect(() => () => anchor(id, null), [id, anchor]);
  return <group ref={ref} position={position} />;
}

const projected = new Vector3();

function AnchorProjector({ anchors, elements }: { anchors: Map<string, AnchorEntry>; elements: RefObject<Map<string, HTMLDivElement>> }) {
  useFrame(({ camera, size }) => {
    for (const [id, entry] of anchors) {
      const el = elements.current.get(id);
      if (!el) continue;
      projected.setFromMatrixPosition(entry.object.matrixWorld).project(camera);
      const visible = projected.z < 1 && Math.abs(projected.x) < 1.2 && Math.abs(projected.y) < 1.2;
      el.style.visibility = visible ? "visible" : "hidden";
      el.style.transform = `translate(${((projected.x + 1) / 2) * size.width}px, ${((1 - projected.y) / 2) * size.height}px) translate(-50%, -50%)`;
    }
  });
  return null;
}

/** three's RoomEnvironment through PMREM: studio reflections with no file and no network. */
function StudioEnvironment() {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  useEffect(() => {
    const pmrem = new PMREMGenerator(gl);
    const room = new RoomEnvironment();
    const texture = pmrem.fromScene(room, 0.04).texture;
    scene.environment = texture;
    scene.environmentIntensity = 0.55;
    // The stage draws the scene more than once a frame (floor shadow, colour, occlusion). The key light's shadow
    // map is the same for all of them: it is drawn once, on the first, instead of once each.
    gl.shadowMap.autoUpdate = false;
    return () => {
      gl.shadowMap.autoUpdate = true;
      scene.environment = null;
      texture.dispose();
      room.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return null;
}

/** Development only: `window.__b2cView()` returns the stage's renderer, scene, camera and controls, for stills and counts. */
/** Asks for the shadow map once, before anything else is drawn this frame. */
function ShadowOncePerFrame() {
  useFrame(({ gl }) => {
    gl.shadowMap.needsUpdate = true;
  }, -1);
  return null;
}

function DevHandle() {
  const get = useThree((s) => s.get);
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const w = window as unknown as { __b2cView?: typeof get };
    w.__b2cView = get;
    return () => {
      if (w.__b2cView === get) delete w.__b2cView;
    };
  }, [get]);
  return null;
}

const tmpBox = new Box3();
const tmpSphere = new Sphere();
const corner = new Vector3();
const centre = new Vector3();
const toCamera = new Vector3();
const right = new Vector3();
const upward = new Vector3();
const UP = new Vector3(0, 1, 0);
const spherical = new Spherical();
/** Corners of the boxes being framed: eight per object, reused between fits. */
const cloud: Vector3[] = [];
let cloudSize = 0;

function addBox(box: Box3) {
  for (let i = 0; i < 8; i++) {
    const v = cloud[cloudSize] ?? (cloud[cloudSize] = new Vector3());
    v.set(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z);
    cloudSize += 1;
  }
}

/** Fills `cloud` with the box corners of the visible objects. False when there are none. */
function collect(objects: Object3D[]): boolean {
  cloudSize = 0;
  for (const o of objects) {
    if (o.parent && !o.parent.visible) continue;
    o.updateWorldMatrix(true, false);
    tmpBox.setFromObject(o);
    if (!tmpBox.isEmpty()) addBox(tmpBox);
  }
  return cloudSize > 0;
}

/** A box in stage units. */
export type StageFrame = { min: [number, number, number]; max: [number, number, number] };

type RigProps = { entries: RefObject<Map<string, StageEntry>>; readyKey: string; autoRotate: boolean; home: [number, number]; frame?: StageFrame; reduced: boolean };

/** Space around the whole model in the home view, and around a focused part (1 = edge to edge). */
const HOME_PAD = 1.16;
const FOCUS_PAD = 3;
/** A focused part never fills the view on its own: the view stays at least this tall (stage units, half height). */
const FOCUS_MIN = 1.5;

/**
 * Frames the model three-quarter on load with a short orbit-in, flies to the selected part, pulls back as the
 * model is pulled apart, and returns on Esc or a background click.
 */
function CameraRig({ entries, readyKey, autoRotate, home, frame, reduced }: RigProps) {
  const controls = useThree((s) => s.controls) as unknown as CameraControlsImpl | null;
  const selectedLineId = useAppStore((s) => s.selectedLineId);
  const selectedMeshKey = useAppStore((s) => s.selectedMeshKey);
  const isolatedLineId = useStageView((s) => s.isolatedLineId);
  const hidden = useStageView((s) => s.hidden);
  const labelsOn = useStageView((s) => s.labelsOn);
  const framed = useRef("");
  const dragging = useRef(false);
  const lastExplode = useRef(0);
  const follow = useRef({ until: 0, next: 0 });

  /**
   * Moves the camera so the points in `cloud` fill the view from the angle the camera is heading for. The
   * viewing angle is kept (camera-controls' fitToBox would snap to the nearest face), and the fit is to the
   * parts' own boxes as seen from that angle: far tighter than one bounding sphere for an L-shaped arm.
   */
  const fitCloud = useCallback(
    (animate: boolean, pad: number, minHalf = 0) => {
      if (!controls || !cloudSize) return;
      const camera = controls.camera as PerspectiveCamera;
      const tan = Math.tan((camera.fov * Math.PI) / 360);
      tmpBox.makeEmpty();
      for (let i = 0; i < cloudSize; i++) tmpBox.expandByPoint(cloud[i]);
      tmpBox.getCenter(centre);
      let distance: number;
      if (autoRotate) {
        // Turning: the fit has to hold from every side.
        distance = Math.max(tmpBox.getBoundingSphere(tmpSphere).radius * pad * 0.78, minHalf) / Math.sin(Math.atan(tan * Math.min(1, camera.aspect)));
      } else {
        controls.getSpherical(spherical, true);
        toCamera.setFromSpherical(spherical).normalize();
        right.crossVectors(UP, toCamera).normalize();
        upward.crossVectors(toCamera, right);
        // Centre what the camera will see, not the box.
        let minX = Infinity;
        let maxX = -Infinity;
        let minY = Infinity;
        let maxY = -Infinity;
        for (let i = 0; i < cloudSize; i++) {
          corner.copy(cloud[i]).sub(centre);
          const x = corner.dot(right);
          const y = corner.dot(upward);
          minX = Math.min(minX, x);
          maxX = Math.max(maxX, x);
          minY = Math.min(minY, y);
          maxY = Math.max(maxY, y);
        }
        centre.addScaledVector(right, (minX + maxX) / 2).addScaledVector(upward, (minY + maxY) / 2);
        // The label columns take the edges of the stage: the model keeps clear of them.
        const sides = useStageView.getState().labelsOn ? 1.55 : 1;
        // A small part keeps some of the model around it, so the reader can see where it sits.
        distance = minHalf / tan;
        for (let i = 0; i < cloudSize; i++) {
          corner.copy(cloud[i]).sub(centre);
          const depth = corner.dot(toCamera);
          distance = Math.max(distance, depth + (Math.abs(corner.dot(upward)) * pad) / tan, depth + (Math.abs(corner.dot(right)) * pad * sides) / (tan * camera.aspect));
        }
      }
      void controls.moveTo(centre.x, centre.y, centre.z, animate);
      void controls.dollyTo(Math.min(Math.max(distance, controls.minDistance), controls.maxDistance), animate);
    },
    [controls, autoRotate],
  );

  const fit = useCallback(
    (objects: Object3D[], animate: boolean, pad: number, minHalf = 0) => {
      if (collect(objects)) fitCloud(animate, pad, minHalf);
    },
    [fitCloud],
  );

  const fitAll = useCallback(
    (animate: boolean, grow = 1) => {
      if (frame && useAppStore.getState().explode === 0) {
        cloudSize = 0;
        tmpBox.min.set(...frame.min);
        tmpBox.max.set(...frame.max);
        addBox(tmpBox);
        return fitCloud(animate, grow);
      }
      fit([...entries.current.values()].map((e) => e.object), animate, HOME_PAD * grow);
    },
    [entries, frame, fit, fitCloud],
  );

  // The first frame: three-quarter, from a little further round and further out, easing into the home view.
  useEffect(() => {
    if (!controls || !entries.current.size || framed.current === readyKey) return;
    framed.current = readyKey;
    if (reduced) {
      void controls.rotateTo(home[0], home[1], false);
      return fitAll(false);
    }
    void controls.rotateTo(home[0] - 0.85, Math.max(0.3, home[1] - 0.24), false);
    fitAll(false, 1.4);
    const settle = controls.smoothTime;
    controls.smoothTime = 0.85;
    void controls.rotateTo(home[0], home[1], true);
    fitAll(true);
    // Not cleared on re-render: the easing has to be put back whatever happens.
    window.setTimeout(() => (controls.smoothTime = settle), 1300);
  }, [controls, entries, readyKey, fitAll, home, reduced]);

  // Click to focus; isolating a line frames that line; clearing either frames the whole model again.
  useEffect(() => {
    if (!controls || framed.current !== readyKey) return;
    const all = [...entries.current.entries()];
    if (selectedLineId) {
      const exact = selectedMeshKey ? all.filter(([key]) => key === selectedMeshKey) : [];
      const targets = (exact.length ? exact : all.filter(([, e]) => e.lineId === selectedLineId)).map(([, e]) => e.object);
      if (targets.length) return fit(targets, true, FOCUS_PAD, FOCUS_MIN);
    }
    if (isolatedLineId) {
      const targets = all.filter(([, e]) => e.lineId === isolatedLineId).map(([, e]) => e.object);
      if (targets.length) return fit(targets, true, 1.5, FOCUS_MIN * 0.6);
    }
    const id = window.setTimeout(() => fitAll(true), 0);
    return () => window.clearTimeout(id);
    // `hidden` and `labelsOn` are here so that hiding a part, or the labels arriving, re-frames what is left.
  }, [controls, entries, readyKey, selectedLineId, selectedMeshKey, isolatedLineId, hidden, labelsOn, fit, fitAll]);

  useEffect(() => {
    if (!controls) return;
    const start = () => (dragging.current = true);
    const end = () => (dragging.current = false);
    controls.addEventListener("controlstart", start);
    controls.addEventListener("controlend", end);
    return () => {
      controls.removeEventListener("controlstart", start);
      controls.removeEventListener("controlend", end);
    };
  }, [controls]);

  useFrame(({ clock }, delta) => {
    if (!controls) return;
    if (autoRotate && !dragging.current && !selectedLineId) void controls.rotate(delta * 0.12, 0, false);
    // Pull back (or come in again) while the parts are moving apart, and once more after they settle.
    const explode = useAppStore.getState().explode;
    const now = clock.elapsedTime;
    if (explode !== lastExplode.current) {
      lastExplode.current = explode;
      follow.current.until = now + 0.9;
    }
    if (now < follow.current.until && now >= follow.current.next && !selectedLineId && !isolatedLineId && framed.current === readyKey) {
      follow.current.next = now + 0.1;
      fitAll(true);
    }
  });
  return null;
}

function Chip({ icon: Icon, onClick, children, title }: { icon: typeof Eye; onClick: () => void; children: ReactNode; title?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="pointer-events-auto inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-full border border-stage-border bg-stage-surface/95 px-3 text-caption font-medium text-stage-text shadow-e1 transition-colors duration-150 hover:border-stage-muted focus-visible:outline-2 focus-visible:outline-brand"
    >
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
      {children}
    </button>
  );
}

/** Isolate, hide and "Unhide all": the anatomy-viewer controls, bottom left of the stage. */
function StageTools({ entries }: { entries: RefObject<Map<string, StageEntry>> }) {
  const selectedLineId = useAppStore((s) => s.selectedLineId);
  const selectedMeshKey = useAppStore((s) => s.selectedMeshKey);
  const isolatedLineId = useStageView((s) => s.isolatedLineId);
  const hiddenCount = useStageView((s) => s.hidden.size);
  const { isolate, hide, unhideAll } = useStageView.getState();

  // Esc with nothing selected leaves the isolated view.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      if (useAppStore.getState().selectedLineId === null) useStageView.getState().isolate(null);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  const hideSelected = () => {
    if (!selectedLineId) return;
    const keys = selectedMeshKey && entries.current.has(selectedMeshKey) ? [selectedMeshKey] : [...entries.current.entries()].filter(([, e]) => e.lineId === selectedLineId).map(([key]) => key);
    hide(keys);
    if (isolatedLineId === selectedLineId) isolate(null);
    useAppStore.getState().clearSelection();
  };

  const idle = !selectedLineId && !isolatedLineId && !hiddenCount;
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap items-center gap-2">
      {selectedLineId && isolatedLineId !== selectedLineId ? (
        <Chip icon={Focus} onClick={() => isolate(selectedLineId)} title="Fade every other part (or double-click the part)">
          Isolate
        </Chip>
      ) : null}
      {isolatedLineId ? (
        <Chip icon={Layers} onClick={() => isolate(null)} title="Bring the other parts back (Esc)">
          Show all
        </Chip>
      ) : null}
      {selectedLineId ? (
        <Chip icon={EyeOff} onClick={hideSelected} title="Hide this part (or Ctrl-click it)">
          Hide
        </Chip>
      ) : null}
      {hiddenCount ? (
        <Chip icon={Eye} onClick={unhideAll}>
          Unhide all <span className="tabular text-stage-muted">· {hiddenCount}</span>
        </Chip>
      ) : null}
      {idle ? <p className="rounded-full bg-stage/60 px-2.5 py-1 text-caption text-stage-muted backdrop-blur-sm">Double-click isolates a part · Ctrl-click hides it</p> : null}
    </div>
  );
}

export type Stage3DProps = {
  data: StageData;
  /** Changes when the set of meshes changes (model name, part count): triggers the initial frame. */
  readyKey: string;
  interactive?: boolean;
  autoRotate?: boolean;
  /** Azimuth and polar angle (radians) of the home view. */
  home?: [number, number];
  /** What the home view frames, when it is not simply everything on the stage (the kit grid, before the parts land). */
  frame?: StageFrame;
  shadowScale?: number;
  /** Leader-line labels and the isolate / hide chips. Off for the kit view, which has its own tags. */
  tools?: boolean;
  children: ReactNode;
};

const HOME: [number, number] = [Math.PI / 5, Math.PI / 2.9];

export function Stage3D({ data, readyKey, interactive = true, autoRotate = false, home = HOME, frame, shadowScale = 8, tools = true, children }: Stage3DProps) {
  const entries = useRef(new Map<string, StageEntry>());
  const register = useCallback((meshKey: string, entry: StageEntry | null) => {
    if (entry) entries.current.set(meshKey, entry);
    else entries.current.delete(meshKey);
  }, []);
  const [anchors, setAnchors] = useState(() => new Map<string, AnchorEntry>());
  const elements = useRef(new Map<string, HTMLDivElement>());
  const anchor = useCallback((id: string, entry: AnchorEntry | null) => {
    setAnchors((cur) => {
      if (!entry && !cur.has(id)) return cur;
      const next = new Map(cur);
      if (entry) next.set(id, entry);
      else next.delete(id);
      return next;
    });
  }, []);
  const ctx = useMemo(() => ({ data, interactive, register, anchor }), [data, interactive, register, anchor]);
  const clearSelection = useAppStore((s) => s.clearSelection);
  const reduced = prefersReducedMotion();
  const bus = useMemo(createLabelBus, []);
  const withTools = interactive && tools;
  // Isolated and hidden parts belong to one model: a new model starts clean.
  useEffect(() => () => useStageView.getState().reset(), [readyKey]);

  return (
    <div className="relative size-full overflow-hidden">
      <Canvas
        dpr={[1, 1.5]}
        shadows="percentage"
        camera={{ fov: 35, near: 0.05, far: 80, position: [4, 3, 5] }}
        // Anti-aliasing is SMAA in the effect pass, so the canvas itself is not multisampled.
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
        onPointerMissed={() => interactive && clearSelection()}
        aria-label="3D view of the parts. The parts list beside it shows the same parts."
        role="img"
      >
        <StudioEnvironment />
        <ShadowOncePerFrame />
        <DevHandle />
        <hemisphereLight args={[token("--b2c-light-sky"), token("--b2c-light-ground"), 0.45]} />
        <directionalLight position={[4, 7, 5]} intensity={1.25} castShadow shadow-mapSize={[1024, 1024]} shadow-bias={-0.0004} shadow-normalBias={0.02}>
          <orthographicCamera attach="shadow-camera" args={[-4, 4, 4, -4, 0.1, 24]} />
        </directionalLight>
        {/* Cool rim light from behind. */}
        <directionalLight position={[-5, 4, -6]} intensity={0.9} color={token("--b2c-light-rim")} />

        <StageContext.Provider value={ctx}>
          <Bvh firstHitOnly>{children}</Bvh>
        </StageContext.Provider>

        <ContactShadows position={[0, -0.001, 0]} opacity={0.45} blur={2.2} scale={shadowScale} far={3} resolution={512} frames={Infinity} />
        <Grid
          position={[0, -0.004, 0]}
          infiniteGrid
          cellSize={0.25}
          sectionSize={1}
          cellThickness={0.6}
          sectionThickness={1}
          cellColor={token("--b2c-stage-border")}
          sectionColor={token("--b2c-stage-border")}
          fadeDistance={11}
          fadeStrength={2.5}
        />

        <CameraControls makeDefault smoothTime={reduced ? 0 : 0.3} minDistance={0.8} maxDistance={18} maxPolarAngle={Math.PI / 2.02} enabled={interactive || autoRotate} />
        <CameraRig entries={entries} readyKey={readyKey} autoRotate={autoRotate && !reduced} home={home} frame={frame} reduced={reduced} />
        <AnchorProjector anchors={anchors} elements={elements} />
        {withTools ? <LeaderLabelProjector bus={bus} entries={entries} /> : null}
        <StageEffects />
      </Canvas>
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        {[...anchors].map(([id, entry]) => (
          <div
            key={id}
            ref={(el) => {
              if (el) elements.current.set(id, el);
              else elements.current.delete(id);
            }}
            className="absolute top-0 left-0 will-change-transform"
            style={{ visibility: "hidden" }}
          >
            {entry.node}
          </div>
        ))}
      </div>
      {withTools ? <LeaderLabelLayer bus={bus} entries={entries} data={data} readyKey={readyKey} /> : null}
      {withTools ? <StageTools entries={entries} /> : null}
    </div>
  );
}
