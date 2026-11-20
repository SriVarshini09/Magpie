// ProviderTag: a small text tag naming the system behind an event, e.g. "via Airbyte" (PLAN §11.4).
// Text only, no logos. Simulated things are violet and dashed.
import { sourceName } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ProviderTag({ provider, simulated, className }: { provider: string | null | undefined; simulated?: boolean | null; className?: string }) {
  if (!provider) return null;
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-sm border px-1.5 text-caption whitespace-nowrap",
        simulated ? "border-dashed border-test/60 text-test" : "border-border text-muted-foreground",
        className,
      )}
    >
      via {sourceName(provider)}
      {simulated ? " (mock)" : ""}
    </span>
  );
}
