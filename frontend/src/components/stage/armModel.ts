// Loads the SO-101 (PLAN §3.12, §11.12): the URDF and its meshes from /so101, this app's own origin.
// Meshes come from /so101/processed/*.bin when they are there: indexed geometry with creased (smooth) normals,
// made once by `node scripts/smooth-so101.mjs`, a third of the size of the STLs and with no work on load.
// Without them (or if one fails) the raw, faceted STLs load instead. No Draco, no CDN.
// The 17 visual meshes are flattened into one list with world transforms, because hiding a link must not hide
// the links below it.
import { Box3, BufferAttribute, BufferGeometry, LoadingManager, Matrix4, Mesh, Quaternion, Vector3, type Object3D } from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import URDFLoader, { type URDFRobot } from "urdf-loader";

import { meshNameFromFile } from "@/lib/modelMap";

import { STAGE_SIZE } from "./reveal";

export type ArmPart = {
  key: string;
  mesh: string;
  link: string;
  joint: string | null;
  geometry: BufferGeometry;
  position: Vector3;
  quaternion: Quaternion;
  scale: Vector3;
  explode: Vector3;
  centre: Vector3;
  /** Centre of the geometry in the mesh's own frame: where the label sits. */
  local: [number, number, number];
  /** World-aligned size of the mesh, in the URDF's metres. */
  size: Vector3;
  isServo: boolean;
};

export type LoadedArm = { parts: ArmPart[]; scale: number; offset: Vector3; smooth: boolean };

/** The URDF's zero pose (upper arm up, forearm forward) with the jaw half open. */
const POSE: Record<string, number> = { shoulder_pan: 0, shoulder_lift: 0, elbow_flex: 0, wrist_flex: 0, wrist_roll: 0, gripper: 0.5 };

/** URDF is Z up; the stage is Y up. */
const Z_UP_TO_Y_UP = new Matrix4().makeRotationX(-Math.PI / 2);

type Manifest = { version: number; meshes: Record<string, { vertices: number; indices: number; index: 16 | 32; bytes: number }> };

async function loadManifest(base: string): Promise<Manifest | null> {
  try {
    const res = await fetch(`${base}processed/manifest.json`);
    if (!res.ok) return null;
    const manifest = (await res.json()) as Manifest;
    return manifest.version === 1 && manifest.meshes ? manifest : null;
  } catch {
    return null;
  }
}

/** positions Float32 ×3 | normals Int16 ×3, normalised | padding to 4 bytes | indices (see scripts/smooth-so101.mjs). */
async function loadProcessed(url: string, info: Manifest["meshes"][string]): Promise<BufferGeometry> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  const buffer = await res.arrayBuffer();
  if (buffer.byteLength !== info.bytes) throw new Error(`${url}: unexpected size`);
  const posBytes = info.vertices * 12;
  const normBytes = info.vertices * 6;
  const indexAt = posBytes + normBytes + ((4 - ((posBytes + normBytes) % 4)) % 4);
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(new Float32Array(buffer, 0, info.vertices * 3), 3));
  geometry.setAttribute("normal", new BufferAttribute(new Int16Array(buffer, posBytes, info.vertices * 3), 3, true));
  geometry.setIndex(new BufferAttribute(info.index === 32 ? new Uint32Array(buffer, indexAt, info.indices) : new Uint16Array(buffer, indexAt, info.indices), 1));
  return geometry;
}

export async function loadArm(url: string): Promise<LoadedArm> {
  const base = url.replace(/[^/]*$/, "");
  const manifest = await loadManifest(base);
  let smooth = manifest !== null;
  const robot = await new Promise<URDFRobot>((resolve, reject) => {
    const manager = new LoadingManager();
    const loader = new URDFLoader(manager);
    const stl = new STLLoader(manager);
    let result: URDFRobot | null = null;
    let failed = false;
    loader.loadMeshCb = (path, _manager, _material, done) => {
      const name = meshNameFromFile(path);
      const finish = (geometry: BufferGeometry) => {
        const mesh = new Mesh(geometry);
        mesh.userData.file = name;
        done(mesh);
      };
      const raw = () =>
        stl.load(path, finish, undefined, (err) => {
          failed = true;
          done(null as unknown as Object3D, err instanceof Error ? err : new Error(`Couldn't load ${path}`));
        });
      const info = manifest?.meshes[name];
      if (!info) {
        smooth = false;
        return raw();
      }
      // The manager counts this fetch too, so onLoad waits for it.
      const processed = `${base}processed/${name}.bin`;
      manager.itemStart(processed);
      loadProcessed(processed, info)
        .then(finish, () => {
          smooth = false;
          raw();
        })
        .finally(() => manager.itemEnd(processed));
    };
    manager.onError = () => {
      failed = true;
    };
    manager.onLoad = () => (result && !failed ? resolve(result) : reject(new Error("Couldn't load the SO-101 model files.")));
    loader.load(
      url,
      (r) => {
        result = r;
      },
      undefined,
      () => reject(new Error("Couldn't load the SO-101 model description.")),
    );
  });
  return { ...flatten(robot), smooth };
}

function flatten(robot: URDFRobot): Omit<LoadedArm, "smooth"> {
  for (const [joint, value] of Object.entries(POSE)) if (robot.joints[joint]) robot.setJointValue(joint, value);
  robot.updateMatrixWorld(true);

  // The joint a servo drives is the one whose parent is the servo's link.
  const jointOfLink = new Map<string, string>();
  for (const joint of Object.values(robot.joints)) {
    const parent = joint.parent as (Object3D & { urdfName?: string }) | null;
    if (joint.jointType !== "fixed" && parent?.urdfName) jointOfLink.set(parent.urdfName, joint.urdfName ?? joint.name);
  }

  const raw: Array<{ mesh: Mesh; file: string; link: string }> = [];
  robot.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh || !mesh.userData.file) return;
    let link = "";
    for (let p: Object3D | null = mesh.parent; p; p = p.parent) {
      const l = p as Object3D & { isURDFLink?: boolean; urdfName?: string };
      if (l.isURDFLink) {
        link = l.urdfName ?? l.name;
        break;
      }
    }
    raw.push({ mesh, file: mesh.userData.file as string, link });
  });

  const bounds = new Box3();
  const box = new Box3();
  const world = new Matrix4();
  const counters = new Map<string, number>();
  const parts: ArmPart[] = raw.map(({ mesh, file, link }) => {
    const geometry = mesh.geometry;
    geometry.computeBoundingBox();
    world.multiplyMatrices(Z_UP_TO_Y_UP, mesh.matrixWorld);
    const position = new Vector3();
    const quaternion = new Quaternion();
    const scale = new Vector3();
    world.decompose(position, quaternion, scale);
    box.copy(geometry.boundingBox!).applyMatrix4(world);
    bounds.union(box);
    const n = counters.get(file) ?? 0;
    counters.set(file, n + 1);
    const isServo = file.startsWith("sts3215");
    return {
      key: `${file}#${link}.${n}`,
      mesh: file,
      link,
      joint: isServo ? (jointOfLink.get(link) ?? null) : null,
      geometry,
      position,
      quaternion,
      scale,
      explode: new Vector3(),
      centre: box.getCenter(new Vector3()),
      local: geometry.boundingBox!.getCenter(new Vector3()).toArray(),
      size: box.getSize(new Vector3()),
      isServo,
    };
  });

  const size = bounds.getSize(new Vector3());
  const centre = bounds.getCenter(new Vector3());
  const s = STAGE_SIZE / Math.max(size.x, size.y, size.z, 0.001);
  // Explode: every mesh moves away from the model's centre line and up in proportion to its height, so the
  // links separate along the arm and the servos come out of their holders sideways.
  for (const p of parts) {
    p.explode.copy(p.centre).sub(centre).multiplyScalar(0.9).setY((p.centre.y - bounds.min.y) * 0.55);
    if (p.isServo) p.explode.z += (p.centre.z >= centre.z ? 1 : -1) * size.z * 0.45;
  }
  return { parts, scale: s, offset: new Vector3(-centre.x * s, -bounds.min.y * s, -centre.z * s) };
}

const cache = new Map<string, Promise<LoadedArm>>();

/** One load per URL for the whole session; a failed load can be tried again. */
export function armModel(url: string): Promise<LoadedArm> {
  let hit = cache.get(url);
  if (!hit) {
    hit = loadArm(url);
    cache.set(url, hit);
    hit.catch(() => cache.delete(url));
  }
  return hit;
}
