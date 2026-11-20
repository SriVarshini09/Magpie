// The TEST MODE pill (PLAN §11.3, §12.2): violet, dashed, FlaskConical.
// `fixed` pins it to the top right of the viewport so it cannot be scrolled away (Q7).
import { FlaskConical } from "lucide-react";

import { cn } from "@/lib/utils";

export function TestModeBadge({ fixed = false, className }: { fixed?: boolean; className?: string }) {
  return (
    <span
      role="status"
      data-testid="test-mode-badge"
      title="Stripe test mode. No real money moves in this app."
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-full border border-dashed border-test bg-test-tint px-3 text-caption font-semibold tracking-wide text-test",
        fixed && "fixed top-3 right-4 z-50 shadow-e1",
        className,
      )}
    >
      <FlaskConical className="size-3.5" strokeWidth={1.75} aria-hidden />
      TEST MODE
    </span>
  );
}
