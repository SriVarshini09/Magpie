// Shared by every 3D view: the stage size and the progressive reveal (PLAN §11.6 core 3).
import { useEffect, useState } from "react";

/** Longest side of a model on the stage, in stage units. */
export const STAGE_SIZE = 3;

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Progressive reveal in assembly order: the model fills in step by step. */
export function useReveal(maxOrder: number, key: string, stepMs = 150): number {
  const reduced = prefersReducedMotion();
  const [step, setStep] = useState(reduced ? maxOrder : 0);
  useEffect(() => {
    if (reduced) return setStep(maxOrder);
    setStep(0);
    let n = 0;
    const id = window.setInterval(() => {
      n += 1;
      setStep(n);
      if (n >= maxOrder) window.clearInterval(id);
    }, stepMs);
    return () => window.clearInterval(id);
  }, [maxOrder, key, stepMs, reduced]);
  return step;
}
