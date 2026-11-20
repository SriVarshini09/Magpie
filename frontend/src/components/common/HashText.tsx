// HashText: mono, middle-truncated, click to copy (PLAN §11.4).
import { Copy } from "lucide-react";
import { toast } from "sonner";

import { shortHash } from "@/lib/format";
import { cn } from "@/lib/utils";

export function HashText({ hash, label, className, onDark = false }: { hash: string | null | undefined; label?: string; className?: string; onDark?: boolean }) {
  if (!hash) return <span className={cn("font-mono text-caption text-muted-foreground", className)}>no hash</span>;
  const copy = () => {
    void navigator.clipboard
      ?.writeText(hash)
      .then(() => toast("Hash copied"))
      .catch(() => toast("Couldn't copy. Select the text instead."));
  };
  return (
    <button
      type="button"
      onClick={copy}
      title={`${hash} (click to copy)`}
      aria-label={`Copy ${label ?? "hash"} ${shortHash(hash)}`}
      className={cn(
        "group/hash inline-flex items-center gap-1 rounded-sm font-mono text-caption transition-colors duration-150",
        onDark ? "text-stage-muted hover:text-stage-text" : "text-muted-foreground hover:text-foreground",
        className,
      )}
    >
      {label ? <span>{label}</span> : null}
      <span>{shortHash(hash)}</span>
      <Copy className="size-3 opacity-0 transition-opacity duration-150 group-hover/hash:opacity-100 group-focus-visible/hash:opacity-100" strokeWidth={1.75} aria-hidden />
    </button>
  );
}
