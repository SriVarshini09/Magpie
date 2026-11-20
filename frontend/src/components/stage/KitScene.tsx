// Kit view (PLAN §3.20 P18, §11.12, Appendix C.5): the heavy half, loaded on demand by workspace/KitView.
// Every part of the model flies out of its assembled place into a tidy grid on the floor, one block per BOM
// line, each with a tag: name, quantity, price. A line with no mesh in the model (a cable, a power supply), and
// every line of a build with no model, gets its category's token instead. Blocks are in category order.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Box3, Matrix4, Quaternion, Vector3, type BufferGeometry } from "three";

import { ActionIcon } from "@/components/panel/ActionBadge";
import { kitTokensFor } from "@/components/workspace/KitView";
import { money } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { StageData } from "@/lib/stage";
import type { PartCategory, ViewData } from "@/lib/types";
import { cn } from "@/lib/utils";
import { naturalOf, partGeometry, quatOf } from "@/models/geometry";
import { KIT_ORDER, kitTokens } from "@/models/kitTokens";
import { PROCEDURAL_MODELS } from "@/models/ProceduralView";

import { buildArm, useArm } from "./ArmScene";
import { PartMesh, type Natural } from "./PartMesh";
import { buildModel } from "./ProceduralScene";
import { useReveal } from "./reveal";
import { Anchor, Stage3D, type StageFrame } from "./Stage3D";
import { StageLoading } from "./StageLoading";

export type KitViewProps = { view: ViewData; data: StageData; interactive?: boolean };

/** One mesh before it is given a place: where it starts, and the box it takes up, in stage units. */
type Piece = {
  key: string;
  label: string;
  geometry: BufferGeometry;
  quaternion: Quaternion;
  scale: Vector3;
  natural: Natural | Natural[];
  /** Assembled position of the mesh's origin; null for a token, which appears in place. */
  from: Vector3 | null;
  /** From the mesh's origin to the centre of its box. */
  toCentre: Vector3;
  size: Vector3;
  outline: number;
  edges: boolean;
  owned: boolean;
  /** A token piece only: its box relative to the token's origin. The token's pieces stay together. */
  tokenBox?: Box3;
};

type Placed = Piece & { position: Vector3; finalScale: Vector3; order: number };
type Block = { lineId: string; label: string; qty: number; pieces: Placed[]; tag: [number, number, number]; order: number };

/** Millimetres to stage units for tokens when there is no model to take the scale from. */
const TOKEN_SCALE = 0.011;
/** The longest side of the laid-out kit, in stage units. */
const KIT_SIZE = 5.6;
/** Pixels a block needs across so that its tag does not touch its neighbour's, and in front of it for the tag. */
const TAG_PITCH = 134;
const TAG_ROOM = 64;
/** One cell of the grid, in table units: width, depth, the tallest a piece may stand, the gap, how full it gets. */
const CELL = { w: 1, d: 0.72, h: 0.8, gap: 0.16, fill: 0.88 };
/** Azimuth and polar angle of the kit camera, and how much it foreshortens depth on the table. */
const KIT_HOME: [number, number] = [0, Math.PI / 7.5];
const FORESHORTEN = Math.cos(KIT_HOME[1]);
/** Perspective, measured at this camera: the share of the stage's width the far row comes to. */
const FAR_ROW = 0.86;
/** Table units kept clear behind the far row, where the stage's own controls sit. */
const TOP_ROOM = 0.22;

const m = new Matrix4();

function tokenPieces(lineId: string, category: PartCategory, label: string, scale: number): Piece[] {
  return (kitTokens[category] ?? kitTokens.mechanical).map((def, d): Piece => {
    const geometry = partGeometry(def);
    geometry.computeBoundingBox();
    const quaternion = quatOf(def.rot);
    const origin = new Vector3(...def.pos).multiplyScalar(scale);
    const box = geometry.boundingBox!.clone().applyMatrix4(m.compose(origin, quaternion, new Vector3(scale, scale, scale)));
    // A token's pieces keep their places relative to each other: `toCentre` is measured from the token's own origin.
    return { key: `kit:${lineId}#${d}`, label, geometry, quaternion, scale: new Vector3(scale, scale, scale), natural: naturalOf(def), from: null, toCentre: origin.clone().negate(), size: box.getSize(new Vector3()), outline: 1.1, edges: true, owned: true, tokenBox: box };
  });
}

type Group = { lineId: string; label: string; qty: number; pieces: Piece[]; token: boolean };
type Cell = { piece: Piece; x: number; y: number; z: number };

/** Arranges one line's pieces on shelves, deepest first, to roughly the given width over depth. */
function arrange(group: Group, aspect: number): { w: number; d: number; h: number; cells: Cell[] } {
  if (group.token) {
    // A token's pieces stay together, resting on the table.
    const box = new Box3();
    for (const p of group.pieces) if (p.tokenBox) box.union(p.tokenBox);
    const centre = box.getCenter(new Vector3());
    const size = box.getSize(new Vector3());
    return { w: size.x, d: size.z, h: size.y, cells: group.pieces.map((piece) => ({ piece, x: -centre.x - piece.toCentre.x, z: -centre.z - piece.toCentre.z, y: -box.min.y - piece.toCentre.y })) };
  }
  const pieces = [...group.pieces].sort((a, b) => b.size.z - a.size.z || b.size.x - a.size.x);
  const gap = 0.07 * Math.max(...pieces.map((p) => Math.max(p.size.x, p.size.z)));
  const area = pieces.reduce((sum, p) => sum + (p.size.x + gap) * (p.size.z + gap), 0);
  const limit = Math.max(...pieces.map((p) => p.size.x), Math.sqrt(area * aspect) * 1.08);
  const shelves: Array<{ items: Piece[]; w: number; d: number }> = [];
  for (const piece of pieces) {
    let shelf = shelves[shelves.length - 1];
    if (!shelf || shelf.w + gap + piece.size.x > limit) shelves.push((shelf = { items: [], w: -gap, d: 0 }));
    shelf.items.push(piece);
    shelf.w += gap + piece.size.x;
    shelf.d = Math.max(shelf.d, piece.size.z);
  }
  const w = Math.max(...shelves.map((sh) => sh.w));
  const d = shelves.reduce((sum, sh) => sum + sh.d, 0) + gap * (shelves.length - 1);
  const cells: Cell[] = [];
  let back = -d / 2;
  for (const shelf of shelves) {
    let x = -shelf.w / 2;
    for (const piece of shelf.items) {
      // Front-aligned on its shelf, the bottom of its box on the table.
      cells.push({ piece, x: x + piece.size.x / 2 - piece.toCentre.x, z: back + shelf.d - piece.size.z / 2 - piece.toCentre.z, y: piece.size.y / 2 - piece.toCentre.y });
      x += piece.size.x + gap;
    }
    back += shelf.d + gap;
  }
  return { w, d, h: Math.max(...pieces.map((p) => p.size.y)), cells };
}

/**
 * The knolling grid: every line gets a cell of the same size (two cells across for a line with many pieces),
 * and its pieces are scaled to fill it. So a 30 mm board reads as clearly as a 300 mm arm link, the tags line
 * up in rows, and the whole thing can be read from the back of a room.
 */
function layout(groups: Group[], stage: { width: number; height: number }): { blocks: Block[]; scale: number; frame: StageFrame; maxOrder: number; tagWidth: number } {
  // The stage decides the shape: a wide stage gets long rows, the narrow workspace stage gets more of them.
  // The kit camera looks almost straight down, so depth on the table is barely foreshortened, and the far row
  // comes out a little narrower on screen than the near one.
  const usable = Math.max(240, stage.height - 130);
  const maxCols = Math.max(2, Math.floor((stage.width * FAR_ROW) / TAG_PITCH));
  const flow = (cols: number, wide: boolean) => {
    // A line with many pieces may take two cells across, when the grid has the columns for it.
    const spanOf = (g: Group) => (wide && !g.token && g.pieces.length > 6 && cols > 2 ? 2 : 1);
    // First fit: a wide block that does not fit the row waits, and the next narrow one takes the gap.
    const waiting = groups.map((group) => ({ group, span: spanOf(group) }));
    const rows: Array<typeof waiting> = [];
    while (waiting.length) {
      const row: typeof waiting = [];
      let used = 0;
      for (let k = 0; k < waiting.length && used < cols; ) {
        if (used + waiting[k].span <= cols) {
          used += waiting[k].span;
          row.push(...waiting.splice(k, 1));
        } else k += 1;
      }
      rows.push(row);
    }
    const width = cols * CELL.w + (cols - 1) * CELL.gap;
    // Pixels per table unit when the width decides, and the room that leaves in front of each row for its
    // tags (a size in pixels). If the grid is then too deep for the stage, the height decides instead.
    let pixels = (stage.width * FAR_ROW) / width;
    let tagRoom = TAG_ROOM / (pixels * FORESHORTEN);
    if (rows.length * (CELL.d + tagRoom) * FORESHORTEN * pixels > usable) {
      pixels = Math.max(usable - rows.length * TAG_ROOM, usable * 0.25) / (rows.length * CELL.d * FORESHORTEN);
      tagRoom = TAG_ROOM / (pixels * FORESHORTEN);
    }
    return { rows, width, depth: rows.length * (CELL.d + tagRoom), tagRoom, pixels };
  };
  // The best grid is the one whose cells come out largest on screen.
  let best = flow(1, false);
  for (let cols = 2; cols <= Math.min(maxCols, Math.max(2, groups.length)); cols++) {
    for (const wide of [true, false]) {
      const tried = flow(cols, wide);
      if (tried.pixels > best.pixels * 1.02) best = tried;
    }
  }

  const blocks: Block[] = [];
  let order = 0;
  let z = -best.depth / 2;
  for (const row of best.rows) {
    const rowWidth = row.reduce((sum, c) => sum + c.span * CELL.w + (c.span - 1) * CELL.gap, 0) + (row.length - 1) * CELL.gap;
    let x = -rowWidth / 2;
    const front = z + CELL.d;
    for (const { group, span } of row) {
      order += 1;
      const w = span * CELL.w + (span - 1) * CELL.gap;
      const placed = arrange(group, (w / CELL.d) * 0.9);
      // Fill the cell, whichever side runs out first. A single small part is not blown up past all recognition.
      // A token (a generic stand-in for a line with no part on the model) stays small: a hint, not a part.
      const fill = Math.min((w * CELL.fill) / placed.w, (CELL.d * CELL.fill) / placed.d, CELL.h / placed.h) * (group.token ? 0.5 : 1);
      const cx = x + w / 2;
      const cz = front - CELL.d / 2;
      blocks.push({
        lineId: group.lineId,
        label: group.label,
        qty: group.qty,
        order,
        tag: [cx, 0, front + best.tagRoom * 0.18],
        pieces: placed.cells.map((c, i) => ({
          ...c.piece,
          position: new Vector3(cx + c.x * fill, c.y * fill, cz + c.z * fill),
          finalScale: c.piece.scale.clone().multiplyScalar(fill),
          order: order + Math.min(i, 6) * 0.3,
        })),
      });
      x += w + CELL.gap;
    }
    z = front + best.tagRoom;
  }
  const scale = KIT_SIZE / Math.max(best.width, best.depth);
  // The frame is the table top the grid covers, with room in front for the last row of tags.
  const frame: StageFrame = { min: [(-best.width / 2) * scale, 0, (-best.depth / 2 - TOP_ROOM) * scale], max: [(best.width / 2) * scale, CELL.h * 0.6 * scale, (best.depth / 2) * scale] };
  // No tag is wider than one cell comes to on screen.
  const tagWidth = Math.round(Math.min(196, Math.max(88, best.pixels * (CELL.w + CELL.gap) - 10)));
  return { blocks, scale, frame, maxOrder: order + 2, tagWidth };
}

function Tag({ lineId, label, qty, data, shown, width }: { lineId: string; label: string; qty: number; data: StageData; shown: boolean; width: number }) {
  const line = data.lines.get(lineId);
  const active = useAppStore((s) => s.selectedLineId === lineId || s.hoveredLineId === lineId);
  return (
    <div
      className={cn(
        "min-w-[84px] translate-y-1/2 rounded-md border px-2 py-1 text-center leading-tight shadow-e2 transition-[opacity,border-color] duration-300",
        active ? "border-brand bg-stage-surface text-stage-text" : "border-stage-border bg-stage-surface/95 text-stage-text",
        shown ? "opacity-100" : "opacity-0",
      )}
      style={{ maxWidth: width }}
      title={label}
    >
      <p className="truncate text-caption font-medium text-stage-muted">
        {label}
        {qty > 1 ? <span> ×{qty}</span> : null}
      </p>
      <p className="flex items-center justify-center gap-1 truncate text-small text-stage-muted">
        {line?.storeName ? (
          <>
            {line.level ? <ActionIcon level={line.level} /> : null}
            <span className="tabular font-mono text-body font-semibold text-stage-text">{money(line.price)}</span>
          </>
        ) : line?.status === "owned" ? (
          "you own it"
        ) : line?.status === "skipped" ? (
          "left out"
        ) : (
          "no offer yet"
        )}
      </p>
    </div>
  );
}

export default function KitScene({ view, data, interactive = true }: KitViewProps) {
  const modelName = view.model ?? "";
  const isArm = view.kind === "urdf";
  const arm = useArm(isArm ? (view.urdf_url ?? "/so101/so101_new_calib.urdf") : null);
  const lineKey = [...data.lines.values()].map((l) => `${l.id}:${l.category}:${l.status === "removed"}`).join(",");

  // The grid is shaped to the stage, so the stage is measured first. Small changes of size keep the layout.
  const box = useRef<HTMLDivElement>(null);
  const [stage, setStage] = useState<{ width: number; height: number } | null>(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width < 50 || height < 50) return;
      setStage((cur) => (cur && Math.abs(cur.width - width) < 80 && Math.abs(cur.height - height) < 80 ? cur : { width, height }));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const built = useMemo(() => {
    if (!stage || (isArm && !arm)) return null;
    const byLine = new Map<string, Piece[]>();
    const add = (lineId: string | null, piece: Piece) => {
      if (!lineId) return;
      byLine.set(lineId, [...(byLine.get(lineId) ?? []), piece]);
    };
    let tokenScale = TOKEN_SCALE;
    if (isArm && arm) {
      const s = arm.scale;
      tokenScale = s / 1000;
      for (const p of buildArm(arm, view, data)) {
        add(p.lineId, { key: `kit:${p.key}`, label: p.label, geometry: p.geometry, quaternion: p.quaternion, scale: p.scale.clone().multiplyScalar(s), natural: p.natural, from: p.position.clone().multiplyScalar(s).add(arm.offset), toCentre: p.centre.clone().sub(p.position).multiplyScalar(s), size: p.size.clone().multiplyScalar(s), outline: 0.0013, edges: false, owned: false });
      }
    } else if (view.kind === "procedural" && PROCEDURAL_MODELS[modelName]?.length) {
      const model = buildModel(PROCEDURAL_MODELS[modelName], view, data);
      const s = model.scale;
      tokenScale = s;
      for (const p of model.parts) {
        add(p.lineId, { key: `kit:${p.key}`, label: p.label, geometry: p.geometry, quaternion: p.quaternion, scale: new Vector3(s, s, s), natural: p.natural, from: p.position.clone().multiplyScalar(s).add(model.offset), toCentre: p.box.getCenter(new Vector3()).sub(p.position).multiplyScalar(s), size: p.box.getSize(new Vector3()).multiplyScalar(s), outline: 1.1, edges: p.edges, owned: true });
      }
    }
    const rank = (c: PartCategory | null | undefined) => {
      const i = c ? KIT_ORDER.indexOf(c) : -1;
      return i < 0 ? KIT_ORDER.length : i;
    };
    const tokens = kitTokensFor(view, data);
    const groups = tokens
      .map((t) => {
        const meshes = byLine.get(t.bom_line_id);
        return meshes?.length
          ? { lineId: t.bom_line_id, label: t.label, qty: t.qty, pieces: meshes, token: false, category: t.category }
          : { lineId: t.bom_line_id, label: t.label, qty: t.qty, pieces: tokenPieces(t.bom_line_id, t.category, t.label, tokenScale), token: true, category: t.category };
      })
      .sort((a, b) => rank(a.category) - rank(b.category));
    if (!groups.length) return null;
    return { ...layout(groups, stage), count: groups.length };
    // The layout follows the model, the set of lines and the stage's shape, not prices or statuses.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isArm, arm, modelName, view.kind, lineKey, view.tokens, stage]);

  // Geometry built here (tokens, procedural parts) is ours to free; the arm's is cached for the session.
  useEffect(
    () => () => {
      built?.blocks.forEach((b) => b.pieces.forEach((p) => p.owned && p.geometry.dispose()));
    },
    [built],
  );

  // The model stands assembled for a beat, then the blocks leave one after another.
  const HOLD = 3;
  const step = useReveal((built?.maxOrder ?? 1) + HOLD, `kit:${built?.count ?? 0}:${modelName}`, 110);

  if (!built) {
    return (
      <div ref={box} className="size-full">
        <StageLoading>{isArm ? "Loading the SO-101 model from this app’s own files…" : undefined}</StageLoading>
      </div>
    );
  }

  return (
    <div ref={box} className="size-full">
    <Stage3D data={data} readyKey={`kit:${modelName}:${built.count}:${stage?.width}`} interactive={interactive} home={KIT_HOME} frame={built.frame} shadowScale={11} tools={false}>
      <group scale={built.scale}>
        {built.blocks.map((block) => (
          <group key={block.lineId}>
            {block.pieces.map((p, i) => {
              const away = step - HOLD >= p.order;
              return (
                <PartMesh
                  key={p.key}
                  meshKey={p.key}
                  lineId={block.lineId}
                  label={p.label}
                  geometry={p.geometry}
                  position={p.from && !away ? p.from : p.position}
                  from={p.from ?? undefined}
                  quaternion={p.quaternion}
                  scale={p.finalScale}
                  fromScale={p.from ? p.scale : undefined}
                  natural={p.natural}
                  revealed={p.from ? true : away}
                  primary={i === 0}
                  pop={!p.from && i === 0}
                  edges={p.edges}
                  outline={p.outline}
                  travel={0.42}
                  hop={p.from ? 0.55 : 0}
                />
              );
            })}
            <Anchor id={`tag:${block.lineId}`} position={block.tag} deps={`${block.label}|${data.lines.get(block.lineId)?.price}|${data.lines.get(block.lineId)?.status}|${step - HOLD >= block.order + 2}|${built.tagWidth}`}>
              <Tag lineId={block.lineId} label={block.label} qty={block.qty} data={data} shown={step - HOLD >= block.order + 2} width={built.tagWidth} />
            </Anchor>
          </group>
        ))}
      </group>
    </Stage3D>
    </div>
  );
}
