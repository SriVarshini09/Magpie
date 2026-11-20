// The polish pass (PLAN §11.12): ambient occlusion (N8AO at half resolution) and SMAA anti-aliasing, with the
// renderer's tone mapping moved into the pass. A frame counter watches the result: if the stage cannot hold
// about 45 fps with occlusion on, occlusion is dropped for the rest of the session (the PLAN's rule).
// The counter is also the measuring tool: window.__b2cStage = { fps, ao, frames }, and ?fps shows it on screen.
import { EffectComposer, N8AO, SMAA, ToneMapping } from "@react-three/postprocessing";
import { useFrame, useThree } from "@react-three/fiber";
import { ToneMappingMode } from "postprocessing";
import { Suspense, useEffect, useRef, useState } from "react";

import { token } from "@/lib/stage";

declare global {
  interface Window {
    __b2cStage?: { fps: number; ao: boolean; frames: number };
    /** Renders `frames` frames back to back and returns the milliseconds each one took, GPU included. */
    __b2cBench?: (frames?: number) => number;
  }
}

/** Below this, over three windows in a row, occlusion goes. `?ao=on` and `?ao=off` pin it, for measuring. */
const MIN_FPS = 42;
const WINDOW = 90;
/** One decision for the whole session: a second stage does not re-test a GPU that already failed. */
let aoAllowed = true;

function useFpsGuard(onSlow: () => void) {
  const state = useRef({ frames: 0, time: 0, slow: 0, total: 0, readout: null as HTMLElement | null });
  const advance = useThree((s) => s.advance);
  const gl = useThree((s) => s.gl);
  // A bench that does not depend on the browser's frame clock (a background tab gets two frames a second):
  // it draws frames back to back and waits for the GPU to finish them.
  useEffect(() => {
    const bench = (frames = 60) => {
      const context = gl.getContext();
      const pixel = new Uint8Array(4);
      advance(performance.now());
      context.finish();
      const start = performance.now();
      for (let i = 0; i < frames; i++) advance(start + i * 16.7);
      // Reading a pixel back blocks until everything queued has been drawn.
      context.readPixels(0, 0, 1, 1, context.RGBA, context.UNSIGNED_BYTE, pixel);
      return (performance.now() - start) / frames;
    };
    window.__b2cBench = bench;
    // A canvas is torn down a moment after its successor is up: leave the successor's bench alone.
    return () => {
      if (window.__b2cBench === bench) delete window.__b2cBench;
    };
  }, [advance, gl]);
  useFrame((_, delta) => {
    const s = state.current;
    // A hidden tab, a debugger pause or a first-load hitch is not the GPU being slow.
    if (delta > 0.25 || document.visibilityState !== "visible") return;
    s.total += 1;
    if (s.total < 45) return;
    s.frames += 1;
    s.time += delta;
    if (s.frames < WINDOW) return;
    const fps = s.frames / s.time;
    s.frames = 0;
    s.time = 0;
    window.__b2cStage = { fps: Math.round(fps * 10) / 10, ao: aoAllowed, frames: s.total };
    if (window.location.search.includes("fps")) {
      if (!s.readout) {
        s.readout = document.createElement("div");
        s.readout.style.cssText = "position:fixed;right:8px;bottom:36px;z-index:50;padding:2px 8px;border-radius:6px;background:var(--b2c-stage-surface);color:var(--b2c-stage-text);font:12px var(--b2c-font-mono)";
        document.body.appendChild(s.readout);
      }
      s.readout.textContent = `${fps.toFixed(0)} fps · AO ${aoAllowed ? "on" : "off"}`;
    }
    s.slow = fps < MIN_FPS ? s.slow + 1 : 0;
    if (s.slow >= 3 && aoAllowed && !window.location.search.includes("ao=on")) {
      aoAllowed = false;
      onSlow();
    }
  });
}

/** The frame counter and the bench. Apart from the passes, so that it runs while they are still loading. */
function Guard({ onSlow }: { onSlow: () => void }) {
  useFpsGuard(onSlow);
  return null;
}

export function StageEffects() {
  const [ao, setAo] = useState(() => aoAllowed && !window.location.search.includes("ao=off"));
  // The stage units are about a third of a metre: a radius of 0.4 darkens the gaps between neighbouring parts
  // (servo in its holder, board on its standoffs) without a halo around the whole model.
  // SMAA decodes its lookup images before its first frame: the scene is drawn plainly until then, not held back.
  return (
    <>
      <Guard onSlow={() => setAo(false)} />
      <Suspense fallback={null}>
        {ao ? (
          <EffectComposer multisampling={0} enableNormalPass={false}>
            <N8AO halfRes aoRadius={0.4} distanceFalloff={0.7} intensity={2.2} quality="medium" color={token("--b2c-stage")} />
            <SMAA />
            <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
          </EffectComposer>
        ) : (
          <EffectComposer multisampling={0} enableNormalPass={false}>
            <SMAA />
            <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
          </EffectComposer>
        )}
      </Suspense>
    </>
  );
}
