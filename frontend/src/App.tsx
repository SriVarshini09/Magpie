import { useEffect } from "react";
import { RouterProvider } from "react-router";

import { MockDataBadge } from "@/components/MockDataBadge";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { router } from "@/routes";

export function App() {
  const setHealth = useAppStore((s) => s.setHealth);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setHealth(h))
      .catch(() => !cancelled && setHealth(null));
    return () => {
      cancelled = true;
    };
  }, [setHealth]);

  return (
    <TooltipProvider>
      <RouterProvider router={router} />
      <MockDataBadge />
      <Toaster position="bottom-right" />
    </TooltipProvider>
  );
}
