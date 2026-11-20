// Composer strip (PLAN §11.5 B, §11.13): one line under the mandate bar with the request as entered (text,
// link chip, photo thumbnails), the build-type label with "change", and the answered chips as small pills.
// Typing here starts a new intake for a new run; the current run stays where it is.
import { ChevronUp, CornerDownLeft, Link2, MessageSquareText } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";

import { api } from "@/lib/api";
import { BUILD_TYPE_LABEL, firstUrl, repoOf } from "@/lib/format";
import type { RunState } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ComposerStrip({ run }: { run: RunState }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(true);
  const [draft, setDraft] = useState("");
  const inputs = run.intake.inputs;
  const url = inputs.source_url ?? run.source?.url ?? (inputs.text ? firstUrl(inputs.text) : null);
  const text = inputs.text && inputs.text !== url ? inputs.text : null;
  const answered = run.intake.questions.filter((q) => q.answer);

  const startNew = (q: string) => navigate(`/?q=${encodeURIComponent(q)}`);

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="flex h-6 w-full shrink-0 items-center gap-2 border-b border-border bg-page px-(--b2c-gutter) text-caption text-muted-foreground hover:text-foreground">
        <MessageSquareText className="size-3.5" strokeWidth={1.75} aria-hidden />
        <span className="truncate">{text ?? (url ? repoOf(url) : run.intake.summary)}</span>
        <span className="ml-auto">Show the request</span>
      </button>
    );
  }

  return (
    <div className="flex h-11 shrink-0 items-center gap-2.5 border-b border-border bg-page px-(--b2c-gutter) text-small">
      <MessageSquareText className="size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} aria-hidden />
      {text ? <span className="max-w-[28ch] truncate font-medium text-foreground" title={text}>“{text}”</span> : null}
      {url ? (
        <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex h-6 shrink-0 items-center gap-1 rounded-sm border border-border bg-surface px-1.5 text-caption text-brand hover:text-brand-hover">
          <Link2 className="size-3.5" strokeWidth={1.75} aria-hidden />
          {repoOf(url)}
        </a>
      ) : null}
      {inputs.images.map((im) => (
        <img key={im.image_id} src={api.uploadUrl(im.image_id)} alt="Your photo" className="size-7 shrink-0 rounded-sm border border-border object-cover" />
      ))}
      <span className="inline-flex h-6 shrink-0 items-center gap-1.5 rounded-sm border border-border bg-surface px-2 text-caption">
        <span className="font-medium text-foreground">{BUILD_TYPE_LABEL[run.build_type]}</span>
        <span className="text-muted-foreground">{run.build_type_set_by === "user" ? "set by you" : `${Math.round(run.intake.confidence * 100)}% sure`}</span>
        <button type="button" className="text-brand hover:text-brand-hover" onClick={() => startNew(text ?? url ?? "")}>
          change
        </button>
      </span>
      <div className="flex min-w-0 items-center gap-1.5 overflow-hidden">
        {answered.map((q) => (
          <span key={q.id} title={q.text} className={cn("inline-flex h-6 shrink-0 items-center rounded-full bg-muted px-2 text-caption text-secondary-text")}>
            {q.chips.find((c) => c.value === q.answer)?.label ?? q.answer}
          </span>
        ))}
      </div>
      <form
        className="ml-auto flex shrink-0 items-center gap-1"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim()) startNew(draft.trim());
        }}
      >
        <label className="relative">
          <span className="sr-only">Start another build</span>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Start another build…"
            className="h-7 w-56 rounded-sm border border-border-strong bg-surface pr-7 pl-2 text-caption placeholder:text-muted-foreground"
          />
          <CornerDownLeft className="pointer-events-none absolute top-1.5 right-2 size-3.5 text-muted-foreground" strokeWidth={1.75} aria-hidden />
        </label>
        <button type="button" onClick={() => setOpen(false)} aria-label="Hide the request" className="flex size-7 items-center justify-center rounded-sm text-muted-foreground hover:bg-muted hover:text-foreground">
          <ChevronUp className="size-4" strokeWidth={1.75} aria-hidden />
        </button>
      </form>
    </div>
  );
}
