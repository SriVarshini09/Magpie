// Loading, empty and error states (PLAN §11.7). Errors are inline, in place, with what you can do.
import { CircleAlert, RotateCw, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function InlineError({ title, message, onRetry, className }: { title?: string; message: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("flex items-start gap-3 rounded-lg border border-fail/30 bg-fail-tint p-3 text-small", className)}>
      <CircleAlert className="mt-0.5 size-4 shrink-0 text-fail" strokeWidth={1.75} aria-hidden />
      <div className="min-w-0 flex-1">
        {title ? <p className="font-medium text-foreground">{title}</p> : null}
        <p className="text-secondary-text">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw aria-hidden /> Retry
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action, className }: { icon?: LucideIcon; title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-6 py-10 text-center", className)}>
      {Icon ? <Icon className="size-5 text-muted-foreground" strokeWidth={1.75} aria-hidden /> : null}
      <p className="text-body font-medium text-foreground">{title}</p>
      {children ? <p className="max-w-sm text-small text-muted-foreground">{children}</p> : null}
      {action}
    </div>
  );
}
