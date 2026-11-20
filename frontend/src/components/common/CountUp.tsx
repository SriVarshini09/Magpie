// Money that counts up or down to its new value (PLAN §11.4): the cart total, bought and remaining.
import { animate } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { money } from "@/lib/format";
import { cn } from "@/lib/utils";

export function CountUpMoney({ value, className }: { value: number; className?: string }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (from.current === value) return;
    // No animation frames run in a hidden tab: show the new value at once rather than a stale total.
    if (document.hidden || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      from.current = value;
      return setShown(value);
    }
    const controls = animate(from.current, value, {
      duration: 0.3,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setShown(v),
      onComplete: () => {
        from.current = value;
        setShown(value);
      },
    });
    return () => {
      controls.stop();
      from.current = value;
    };
  }, [value]);
  return <span className={cn("tabular font-mono", className)}>{money(shown)}</span>;
}
