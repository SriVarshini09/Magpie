// Below 1280 px (1100 for the workspace and the cart, which also fit 1440 px at 125% zoom) the product shows a "Best on a laptop" notice instead of a broken layout (PLAN §11.5).
// The reader can still choose to continue.
import { MonitorSmartphone } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";

const MIN = 1280;

export function NarrowNotice({ children, min = MIN }: { children: ReactNode; min?: number }) {
  const [narrow, setNarrow] = useState(() => typeof window !== "undefined" && window.innerWidth < min);
  const [anyway, setAnyway] = useState(false);
  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth < min);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [min]);

  if (!narrow || anyway) return <>{children}</>;
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-page px-6 text-center">
      <Logo />
      <MonitorSmartphone className="size-6 text-muted-foreground" strokeWidth={1.75} aria-hidden />
      <h1 className="text-h2 font-semibold tracking-tight">Best on a laptop</h1>
      <p className="max-w-sm text-body text-secondary-text">This screen shows a 3D part map beside a parts list and a timeline. It needs a window at least {min} px wide.</p>
      <Button variant="outline" onClick={() => setAnyway(true)}>
        Show it anyway
      </Button>
    </div>
  );
}
