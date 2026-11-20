// The composer (PLAN §3.17, §11.5 A, §11.13): "What do you want to build?"
// One multi-line box: type a sentence, paste a link (it becomes a chip), or drop up to two photos. Sample chips
// fill the box. After "Build my cart" the box collapses to one line and the build-type label, up to three chip
// questions ("Skip, use defaults") and the mandate form appear; "Sign mandate and run" starts the run.
// Keyboard: Enter submits, Shift+Enter adds a line, Tab walks the chips.
import { Link2, Paperclip, Pencil, ShieldX, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiFailure } from "@/lib/api";
import { firstUrl, hostOf, repoOf } from "@/lib/format";
import type { BuildType, Intake, MandatePreset, ProjectSample } from "@/lib/types";
import { cn } from "@/lib/utils";

import { BuildTypeLabel } from "./BuildTypeLabel";
import { ChipQuestions } from "./ChipQuestions";
import { MandateForm } from "./MandateForm";
import { ACCEPT_ATTR, checkPhotos, MAX_PHOTOS, PhotoThumbs, resizePhoto } from "./UploadDrop";

type Failure = { message: string; refusal?: string | null };

function failureOf(e: unknown, fallback: string): Failure {
  if (!(e instanceof ApiFailure)) return { message: fallback };
  if (e.status === 501) return { message: `${e.message}. This part of the backend isn't connected yet; the sample projects work.` };
  if (e.detail.error === "intake_not_found") return { message: "This request is no longer on the backend (it may have restarted). Click Edit, then Build my cart again." };
  return { message: e.message, refusal: e.detail.refusal?.clause ?? null };
}

export function Composer({ initialText = "", autoSubmit = false, onIntake }: { initialText?: string; autoSubmit?: boolean; onIntake?: (intake: Intake | null) => void }) {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [photos, setPhotos] = useState<File[]>([]);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [samples, setSamples] = useState<ProjectSample[] | null>(null);
  const [intake, setIntake] = useState<Intake | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [phase, setPhase] = useState<"idle" | "reading" | "answering" | "signing">("idle");
  const [failure, setFailure] = useState<Failure | null>(null);
  const [signError, setSignError] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const auto = useRef(false);
  const readBack = useRef<HTMLDivElement>(null);
  const intakeId = intake?.intake_id;

  // Q10: the textarea unmounts when the request is read; keep keyboard focus in the flow (the next Tab is "Edit",
  // then the build type and the chips) instead of dropping it to the top of the page.
  useEffect(() => {
    if (intakeId) readBack.current?.focus({ preventScroll: true });
  }, [intakeId]);

  useEffect(() => {
    let cancelled = false;
    api
      .projects()
      .then((p) => !cancelled && setSamples(p))
      .catch(() => !cancelled && setSamples([]));
    return () => {
      cancelled = true;
    };
  }, []);

  const fill = useCallback((value: string) => {
    const url = firstUrl(value);
    setLink(url);
    setText(url ? value.replace(url, "").trim() : value);
    setFailure(null);
  }, []);

  const update = useCallback(
    (next: Intake | null) => {
      setIntake(next);
      onIntake?.(next);
    },
    [onIntake],
  );

  const submit = useCallback(
    async (override?: { text: string; link: string | null }) => {
      const t = (override?.text ?? text).trim();
      const l = override ? override.link : link;
      const request = [t, l].filter(Boolean).join(" ");
      if (!request && !photos.length) {
        setFailure({ message: "Type what you want to build, paste a link, or add a photo." });
        box.current?.focus();
        return;
      }
      setPhase("reading");
      setFailure(null);
      try {
        const images = await Promise.all(photos.map(resizePhoto));
        const result = await api.intake({ text: request || undefined, images });
        setAnswers(Object.fromEntries(result.questions.filter((q) => q.answer).map((q) => [q.id, q.answer as string])));
        update(result);
      } catch (e) {
        setFailure(failureOf(e, "Couldn't read that request. Check the backend is running, then try again."));
      } finally {
        setPhase("idle");
      }
    },
    [text, link, photos, update],
  );

  // A request handed over in the URL (?q=…) from the workspace's composer strip.
  useEffect(() => {
    if (!initialText || auto.current) return;
    auto.current = true;
    fill(initialText);
    if (autoSubmit) {
      const url = firstUrl(initialText);
      void submit({ text: url ? initialText.replace(url, "").trim() : initialText, link: url });
    }
  }, [initialText, autoSubmit, fill, submit]);

  const addFiles = (files: File[]) => {
    const { ok, errors } = checkPhotos(files, photos.length);
    setFileErrors(errors);
    if (ok.length) setPhotos((cur) => [...cur, ...ok].slice(0, MAX_PHOTOS));
  };

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = [...e.clipboardData.files];
    if (files.length) {
      e.preventDefault();
      return addFiles(files);
    }
    const pasted = e.clipboardData.getData("text").trim();
    // A pasted URL becomes a link chip instead of text in the box.
    if (/^https?:\/\/\S+$/i.test(pasted)) {
      e.preventDefault();
      setLink(pasted);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void submit();
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    addFiles([...e.dataTransfer.files]);
  };

  const send = async (body: { answers: Record<string, string>; build_type?: BuildType; skip_defaults?: boolean }) => {
    if (!intake) return;
    setPhase("answering");
    setFailure(null);
    try {
      const next = await api.answers(intake.intake_id, body);
      setAnswers(Object.fromEntries(next.questions.filter((q) => q.answer).map((q) => [q.id, q.answer as string])));
      update(next);
    } catch (e) {
      setFailure(failureOf(e, "Couldn't save that answer. Try again."));
    } finally {
      setPhase("idle");
    }
  };

  const answer = (questionId: string, value: string) => {
    if (!intake) return;
    const next = { ...answers, [questionId]: value };
    setAnswers(next);
    // Send once every question has an answer; until then the picks stay local.
    if (intake.questions.every((q) => next[q.id])) void send({ answers: next });
  };

  const sign = async (mandate: MandatePreset) => {
    if (!intake) return;
    setPhase("signing");
    setSignError(null);
    try {
      const { run_id } = await api.createRun({ intake_id: intake.intake_id, mandate });
      toast("Mandate signed. The run has started.");
      navigate(`/run/${run_id}`);
    } catch (e) {
      setSignError(failureOf(e, "Couldn't start the run. Nothing was signed.").message);
      setPhase("idle");
    }
  };

  const edit = () => {
    update(null);
    setAnswers({});
    setSignError(null);
    window.setTimeout(() => box.current?.focus(), 0);
  };

  const busy = phase !== "idle";

  if (intake) {
    const request = intake.inputs.text && intake.inputs.text !== intake.inputs.source_url ? intake.inputs.text : text;
    const url = intake.inputs.source_url ?? link;
    return (
      <div className="space-y-5">
        <div ref={readBack} tabIndex={-1} aria-label="Your request, as we read it" className="flex min-h-12 items-center gap-2.5 rounded-lg border border-border bg-surface px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-brand/40">
          <span className="min-w-0 flex-1 truncate text-body">{request ? `“${request}”` : url ? "A project link" : "Your photos"}</span>
          {url ? (
            <span className="inline-flex h-6 shrink-0 items-center gap-1 rounded-sm border border-border bg-muted px-1.5 text-caption text-brand">
              <Link2 className="size-3.5" strokeWidth={1.75} aria-hidden />
              {repoOf(url)}
            </span>
          ) : null}
          {photos.length ? <span className="shrink-0 text-caption text-muted-foreground">{photos.length === 1 ? "1 photo" : `${photos.length} photos`}</span> : null}
          <Button type="button" variant="ghost" size="sm" onClick={edit} disabled={busy}>
            <Pencil aria-hidden /> Edit
          </Button>
        </div>

        <BuildTypeLabel intake={intake} disabled={busy} onChange={(type) => void send({ answers, build_type: type })} />
        <ChipQuestions intake={intake} answers={answers} onAnswer={answer} onSkip={() => void send({ answers, skip_defaults: true })} disabled={busy} />
        {failure ? <FailureNote failure={failure} /> : null}
        {phase === "answering" ? <Skeleton className="h-64 w-full" /> : intake.ready ? <MandateForm intake={intake} busy={phase === "signing"} error={signError} onSign={(m) => void sign(m)} /> : <p className="text-small text-muted-foreground">Answer the questions above, or skip them, to set your mandate.</p>}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "relative rounded-lg border bg-surface shadow-e1 transition-colors duration-150 focus-within:border-brand focus-within:ring-2 focus-within:ring-brand/25",
          dragging ? "border-dashed border-brand bg-brand-tint" : "border-border-strong",
        )}
      >
        {phase === "reading" ? (
          <span className="absolute inset-x-0 top-0 h-0.5 overflow-hidden rounded-t-lg bg-muted" role="progressbar" aria-label="Reading your request">
            <span className="progress-line block h-full w-1/4 bg-brand" />
          </span>
        ) : null}
        <label htmlFor="composer-box" className="sr-only">
          What do you want to build?
        </label>
        <textarea
          id="composer-box"
          ref={box}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (failure) setFailure(null);
          }}
          onPaste={onPaste}
          onKeyDown={onKeyDown}
          disabled={busy}
          rows={3}
          placeholder="a small camera drone under $200 · a GitHub link · or drop a photo"
          className="block w-full resize-none rounded-lg bg-transparent px-4 pt-3.5 pb-2 text-body-lg text-foreground outline-none placeholder:text-muted-foreground"
        />
        {link || photos.length ? (
          <div className="flex flex-wrap items-center gap-2 px-4 pb-2">
            {link ? (
              <span className="inline-flex h-7 items-center gap-1.5 rounded-sm border border-border bg-muted pr-1 pl-2 text-small text-brand">
                <Link2 className="size-3.5" strokeWidth={1.75} aria-hidden />
                <span className="max-w-[36ch] truncate" title={link}>
                  {repoOf(link) || hostOf(link)}
                </span>
                <button type="button" onClick={() => setLink(null)} aria-label="Remove the link" className="flex size-5 items-center justify-center rounded-sm text-muted-foreground hover:bg-surface hover:text-foreground">
                  <X className="size-3" strokeWidth={2} aria-hidden />
                </button>
              </span>
            ) : null}
            <PhotoThumbs photos={photos} onRemove={(i) => setPhotos((cur) => cur.filter((_, n) => n !== i))} disabled={busy} />
          </div>
        ) : null}
        <div className="flex items-center gap-2 px-2.5 pb-2.5">
          <input
            ref={picker}
            type="file"
            accept={ACCEPT_ATTR}
            multiple
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={(e) => {
              addFiles([...(e.target.files ?? [])]);
              e.target.value = "";
            }}
          />
          <Button type="button" variant="ghost" size="icon-lg" onClick={() => picker.current?.click()} disabled={busy || photos.length >= MAX_PHOTOS} aria-label={`Add a photo (up to ${MAX_PHOTOS})`} title={`Add a photo (up to ${MAX_PHOTOS}), or drop one here`}>
            <Paperclip className="size-5" strokeWidth={1.75} aria-hidden />
          </Button>
          <span className="text-caption text-muted-foreground">{dragging ? "Drop the photo to add it" : "Enter to build · Shift+Enter for a new line"}</span>
          <Button type="button" size="lg" className="ml-auto h-10 px-4 text-body font-semibold" onClick={() => void submit()} disabled={busy}>
            {phase === "reading" ? "Reading…" : "Build my cart"}
          </Button>
        </div>
      </div>

      {fileErrors.map((err) => (
        <p key={err} role="alert" className="text-small text-fail">
          {err}
        </p>
      ))}
      {failure ? <FailureNote failure={failure} /> : null}

      <div className="flex min-h-8 flex-wrap items-center gap-1.5">
        <span className="mr-1 text-small text-muted-foreground">Try a sample:</span>
        {samples === null ? (
          <>
            <Skeleton className="h-8 w-36 rounded-full" />
            <Skeleton className="h-8 w-44 rounded-full" />
            <Skeleton className="h-8 w-40 rounded-full" />
          </>
        ) : samples.length ? (
          samples.map((s) => (
            <button
              key={s.title}
              type="button"
              disabled={busy}
              title={s.blurb}
              onClick={() => {
                fill(s.source_url ?? s.example_text ?? s.title);
                box.current?.focus();
              }}
              className="h-8 rounded-full border border-border bg-surface px-3 text-small text-foreground transition-colors duration-150 hover:border-ink"
            >
              {s.title}
            </button>
          ))
        ) : (
          <span className="text-small text-muted-foreground">Samples didn’t load. Typing a request still works.</span>
        )}
      </div>
      <p className="text-caption text-muted-foreground">Photos stay on this machine. They go to Claude and Superlinked for analysis only if your mandate allows it.</p>
    </div>
  );
}

function FailureNote({ failure }: { failure: Failure }) {
  return (
    <p role="alert" className="flex items-start gap-2 rounded-lg border border-fail/30 bg-fail-tint px-3 py-2 text-small text-fail">
      {failure.refusal ? <ShieldX className="mt-0.5 size-4 shrink-0" strokeWidth={1.75} aria-hidden /> : null}
      <span>
        {failure.refusal ? "Refused: " : ""}
        {failure.message}
        {failure.refusal ? <span className="text-secondary-text"> Rule: {failure.refusal}.</span> : null}
      </span>
    </p>
  );
}
