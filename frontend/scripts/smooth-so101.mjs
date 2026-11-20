// Precomputes smooth (creased) normals for the SO-101 STL meshes, once, so the browser does not have to
// (toCreasedNormals on the model's ~400k triangles took about 22 s on load).
//
//   cd frontend && node scripts/smooth-so101.mjs [creaseAngleDegrees=38]
//
// Reads  public/so101/assets/*.stl
// Writes public/so101/processed/<name>.bin   positions Float32 x3 | normals Int16 x3 (normalised) | pad to 4 | indices Uint32 or Uint16
//        public/so101/processed/manifest.json  { version, crease, meshes: { <name>: { vertices, indices, index: 16|32, bytes } } }
// No Draco and no network: the viewer reads these files from this app's own origin and falls back to the raw STLs.
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { mergeVertices, toCreasedNormals } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "so101");
const source = join(root, "assets");
const out = join(root, "processed");
const crease = Number(process.argv[2] ?? 38);
const UNITS = 1e4;

await mkdir(out, { recursive: true });
const loader = new STLLoader();
const meshes = {};
let before = 0;
let after = 0;

for (const file of (await readdir(source)).filter((f) => f.toLowerCase().endsWith(".stl")).sort()) {
  const started = performance.now();
  const data = await readFile(join(source, file));
  before += data.byteLength;
  const raw = loader.parse(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength));
  for (const name of Object.keys(raw.attributes)) if (name !== "position") raw.deleteAttribute(name);
  // Weld the STL's triangle soup, split the welded mesh again at hard edges, then index what is left.
  // toCreasedNormals matches vertices on a 0.01-unit grid, and the STLs are in metres: at that scale it would
  // blend every normal within a centimetre. So the work is done at 0.1 mm per unit and scaled back afterwards.
  raw.scale(UNITS, UNITS, UNITS);
  const creased = toCreasedNormals(mergeVertices(raw, 1e-4), (crease * Math.PI) / 180);
  const indexed = mergeVertices(creased, 1e-4);
  indexed.scale(1 / UNITS, 1 / UNITS, 1 / UNITS);
  const position = indexed.getAttribute("position");
  const normal = indexed.getAttribute("normal");
  const index = indexed.getIndex();
  const vertices = position.count;
  const wide = vertices > 65535;

  const posBytes = vertices * 12;
  const normBytes = vertices * 6;
  const pad = (4 - ((posBytes + normBytes) % 4)) % 4;
  const indexBytes = index.count * (wide ? 4 : 2);
  const buffer = new ArrayBuffer(posBytes + normBytes + pad + indexBytes);
  new Float32Array(buffer, 0, vertices * 3).set(position.array);
  const normals = new Int16Array(buffer, posBytes, vertices * 3);
  for (let i = 0; i < vertices * 3; i++) normals[i] = Math.max(-32767, Math.min(32767, Math.round(normal.array[i] * 32767)));
  const indices = wide ? new Uint32Array(buffer, posBytes + normBytes + pad, index.count) : new Uint16Array(buffer, posBytes + normBytes + pad, index.count);
  indices.set(index.array);

  const name = file.replace(/\.stl$/i, "");
  await writeFile(join(out, `${name}.bin`), new Uint8Array(buffer));
  meshes[name] = { vertices, indices: index.count, index: wide ? 32 : 16, bytes: buffer.byteLength };
  after += buffer.byteLength;
  console.log(`${name.padEnd(40)} ${String(index.count / 3).padStart(7)} tris ${String(vertices).padStart(7)} verts  ${(buffer.byteLength / 1024).toFixed(0).padStart(6)} KB  ${((performance.now() - started) / 1000).toFixed(1)} s`);
}

await writeFile(join(out, "manifest.json"), `${JSON.stringify({ version: 1, crease, meshes }, null, 2)}\n`);
console.log(`\n${Object.keys(meshes).length} meshes: ${(before / 1048576).toFixed(1)} MB of STL -> ${(after / 1048576).toFixed(1)} MB processed (crease ${crease} deg)`);
