// Placeholder used by every scaffold stub. Delete the usage when you build the component.
import type { ReactNode } from "react";

export type Owner = "A" | "B" | "C" | "D";

export function Todo({ name, owner, plan, children }: { name: string; owner: Owner; plan: string; children?: ReactNode }) {
  return (
    <div data-todo={name} className="rounded-lg border border-dashed border-border bg-surface p-3 text-small text-muted-foreground">
      <span className="font-mono text-caption text-foreground">{name}</span>{" "}
      <span>
        TODO({owner}) — PLAN {plan}
      </span>
      {children ? <div className="mt-2">{children}</div> : null}
    </div>
  );
}
