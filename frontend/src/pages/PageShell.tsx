// Shared frame for the cart, receipt and not-found pages: a quiet top bar with the way back.
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { LogoMark } from "@/components/brand/Logo";

export function PageShell({ runId, crumb, children, right }: { runId?: string; crumb: string; children?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-page">
      <header className="sticky top-0 z-30 border-b border-border bg-surface">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-3 px-(--b2c-gutter)">
          <Link to="/" aria-label="Build-to-Cart: start" className="flex size-8 items-center justify-center rounded-md hover:bg-muted">
            <LogoMark />
          </Link>
          {runId ? (
            <Link to={`/run/${runId}`} className="inline-flex items-center gap-1.5 text-body font-medium text-brand hover:text-brand-hover">
              <ArrowLeft className="size-4" strokeWidth={1.75} aria-hidden />
              Back to the model
            </Link>
          ) : null}
          <span className="text-muted-foreground" aria-hidden>
            /
          </span>
          <span className="text-body text-secondary-text">{crumb}</span>
          {runId ? <span className="font-mono text-caption text-muted-foreground">{runId}</span> : null}
          <span className="ml-auto flex items-center gap-2">{right}</span>
        </div>
      </header>
      <main className="flex-1 pb-14">{children}</main>
    </div>
  );
}
