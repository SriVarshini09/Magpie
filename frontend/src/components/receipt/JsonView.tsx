// "View JSON" for a mandate or a chain record (PLAN §11.5 E). Owner: D.
import { Braces, ChevronRight, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

export function JsonBlock({ data, className }: { data: unknown; className?: string }) {
  const text = JSON.stringify(data, null, 2);
  const copy = () => {
    void navigator.clipboard
      ?.writeText(text)
      .then(() => toast("JSON copied"))
      .catch(() => toast("Couldn't copy. Select the text instead."));
  };
  return (
    <div className={cn("relative rounded-sm border border-border bg-muted", className)}>
      <button
        type="button"
        onClick={copy}
        aria-label="Copy JSON"
        className="absolute top-1.5 right-1.5 inline-flex items-center gap-1 rounded-sm border border-border bg-surface px-1.5 py-0.5 text-caption text-muted-foreground transition-colors duration-150 hover:text-foreground"
      >
        <Copy className="size-3" strokeWidth={1.75} aria-hidden />
        Copy
      </button>
      <pre className="max-h-96 overflow-auto p-3 pr-16 font-mono text-caption leading-relaxed whitespace-pre text-foreground">{text}</pre>
    </div>
  );
}

/** A small "View JSON" disclosure. Closed by default so the page stays readable. */
export function JsonDisclosure({ data, label = "View JSON", className }: { data: unknown; label?: string; className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className={className}>
      <CollapsibleTrigger asChild>
        <button type="button" className="inline-flex items-center gap-1 rounded-sm text-caption font-medium text-brand transition-colors duration-150 hover:text-brand-hover">
          <ChevronRight className={cn("size-3.5 transition-transform duration-150", open && "rotate-90")} strokeWidth={1.75} aria-hidden />
          <Braces className="size-3.5" strokeWidth={1.75} aria-hidden />
          {open ? "Hide JSON" : label}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2">{open ? <JsonBlock data={data} /> : null}</CollapsibleContent>
    </Collapsible>
  );
}
