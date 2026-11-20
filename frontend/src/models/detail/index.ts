// Detailed solids by key (PartDef.detail). Part of the 3D chunk: models/ProceduralView stays light.
import { QUAD_DETAIL } from "./quadcopter";
import { Sculpt, type Sculpted } from "./shop";

const BUILDERS: Record<string, (s: Sculpt) => void> = { ...QUAD_DETAIL };
const cache = new Map<string, Sculpted>();

/**
 * The solid for a key, at full detail or the light one (the start page's small stage). Built once and kept:
 * a disposed geometry only gives up its GPU buffers and uploads again the next time it is drawn.
 */
export function detailFor(key: string | undefined, hi: boolean): Sculpted | null {
  if (!key || !BUILDERS[key]) return null;
  const id = `${key}:${hi ? "hi" : "lo"}`;
  let built = cache.get(id);
  if (!built) {
    const s = new Sculpt(hi);
    BUILDERS[key](s);
    cache.set(id, (built = s.done()));
  }
  return built;
}
