// The chat composer: one box for text, a pasted link (shown as a chip) and up to two photos (paperclip or drop).
// Two looks, one behaviour. In a conversation: tool chips on the left ("Find reference designs", "Photo",
// "Samples"), send on the right, Saved prompts and Attach file underneath. On the start page (`large`): the
// blueprint box, a serif prompt line, then Photo | Attach file | Find references, and Samples, Saved prompts, the
// assistant chip and a square send button on the right. "Find references" is signed into the mandate either way.
// Enter sends, Shift+Enter adds a line. No microphone: there is no offline speech API to rely on.
import { ArrowRight, ArrowUp, Bookmark, BookOpen, BookOpenCheck, Boxes, Camera, ImageIcon, Link2, Paperclip, Trash2, X } from "lucide-react";
import { Popover } from "radix-ui";
import { useEffect, useImperativeHandle, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent, type ReactNode, type Ref } from "react";

import { ACCEPT_ATTR, checkPhotos, MAX_PHOTOS, PhotoThumbs, resizePhoto } from "@/components/composer/UploadDrop";
import { firstUrl, hostOf, repoOf } from "@/lib/format";
import type { ProjectSample } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ComposerInput = { text: string; link: string | null; photos: File[] };
export type ComposerHandle = { fill: (value: string) => void; focus: () => void };

const SAVED_KEY = "b2c.savedPrompts";

function loadSaved(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]") as unknown;
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string").slice(0, 12) : [];
  } catch {
    return [];
  }
}

const chip =
  "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-small transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand disabled:opacity-50";
const quiet = "inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-small text-secondary-text transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50";
const menu = "z-50 w-80 rounded-lg border border-border bg-popover p-2 shadow-e2";
/** The start page's toolbar buttons: icon and word, like the mockup's Photo | Attach file | Find references. */
const tool =
  "inline-flex h-10 shrink-0 items-center gap-2.5 rounded-md px-3 text-[15px] text-foreground transition-colors duration-150 hover:bg-muted focus-visible:outline-2 focus-visible:outline-brand disabled:opacity-50";
const toolQuiet =
  "inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-small text-secondary-text transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-brand";
const Bar = () => <span className="mx-1 h-6 w-px shrink-0 bg-border-strong" aria-hidden />;

export function ChatComposer({
  ref,
  busy,
  onSend,
  referenceSearch,
  onReferenceSearch,
  attachments = true,
  large = false,
  placeholder,
  samples,
  toolbarEnd,
}: {
  ref?: Ref<ComposerHandle>;
  busy: boolean;
  /** Resolves false when the message was not sent, so the box keeps what was typed. */
  onSend: (input: ComposerInput) => Promise<boolean>;
  referenceSearch: boolean;
  onReferenceSearch: (on: boolean) => void;
  /** Links, photos and reference search belong to a new request; a conversation with a run hides them. */
  attachments?: boolean;
  /** The start page's blueprint box. */
  large?: boolean;
  placeholder: string;
  samples: ProjectSample[] | null;
  /** Shown before the send button in the start page's toolbar (the assistant chip). */
  toolbarEnd?: ReactNode;
}) {
  const [text, setText] = useState("");
  const [link, setLink] = useState<string | null>(null);
  const [photos, setPhotos] = useState<File[]>([]);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [saved, setSaved] = useState<string[]>(loadSaved);
  const [openMenu, setOpenMenu] = useState<"samples" | "saved" | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);

  const fill = (value: string) => {
    const url = attachments ? firstUrl(value) : null;
    setLink(url);
    setText(url ? value.replace(url, "").trim() : value);
    box.current?.focus();
  };
  useImperativeHandle(ref, () => ({ fill, focus: () => box.current?.focus() }));

  // Grow with the text up to a limit, without moving the page around it.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const persist = (next: string[]) => {
    setSaved(next);
    try {
      localStorage.setItem(SAVED_KEY, JSON.stringify(next));
    } catch {
      // Private mode: the list lasts for this page only.
    }
  };

  const addFiles = (files: File[]) => {
    if (!files.length) return;
    const { ok, errors } = checkPhotos(files, photos.length);
    setFileErrors(errors);
    if (ok.length) setPhotos((cur) => [...cur, ...ok]);
  };

  const submit = async () => {
    const t = text.trim();
    if (busy || (!t && !link && !photos.length)) {
      box.current?.focus();
      return;
    }
    const before = { text, link, photos };
    setText("");
    setLink(null);
    setPhotos([]);
    setFileErrors([]);
    const images = await Promise.all(before.photos.map(resizePhoto));
    const sent = await onSend({ text: t, link: before.link, photos: images });
    if (!sent) {
      setText(before.text);
      setLink(before.link);
      setPhotos(before.photos);
    }
    box.current?.focus();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void submit();
    }
  };

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = [...e.clipboardData.files];
    if (attachments && files.length) {
      e.preventDefault();
      addFiles(files);
      return;
    }
    const pasted = e.clipboardData.getData("text").trim();
    if (attachments && !link && /^https?:\/\/\S+$/i.test(pasted)) {
      e.preventDefault();
      setLink(pasted);
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (attachments) addFiles([...e.dataTransfer.files]);
  };

  const canSend = !busy && Boolean(text.trim() || link || photos.length);
  const current = text.trim();
  const pickPhoto = () => picker.current?.click();
  const photoFull = busy || photos.length >= MAX_PHOTOS;

  const samplesMenu = (trigger: ReactNode, align: "start" | "end") => (
    <Popover.Root open={openMenu === "samples"} onOpenChange={(o) => setOpenMenu(o ? "samples" : null)}>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align={align} sideOffset={8} className={menu}>
          <p className="px-2 pt-1 pb-1.5 text-caption font-medium text-muted-foreground">Sample projects fill the box</p>
          {samples === null ? (
            <p className="px-2 py-2 text-small text-muted-foreground">Loading samples…</p>
          ) : samples.length ? (
            samples.map((s) => (
              <button
                key={s.title}
                type="button"
                onClick={() => {
                  fill(s.source_url ?? s.example_text ?? s.title);
                  setOpenMenu(null);
                }}
                className="block w-full rounded-md px-2 py-1.5 text-left hover:bg-muted focus-visible:outline-2 focus-visible:outline-brand"
              >
                <span className="block text-small font-medium text-foreground">{s.title}</span>
                <span className="block text-caption text-muted-foreground">{s.blurb}</span>
              </button>
            ))
          ) : (
            <p className="px-2 py-2 text-small text-muted-foreground">Samples didn’t load. Typing a request still works.</p>
          )}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );

  const savedMenu = (trigger: ReactNode, align: "start" | "end") => (
    <Popover.Root open={openMenu === "saved"} onOpenChange={(o) => setOpenMenu(o ? "saved" : null)}>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align={align} sideOffset={6} className={menu}>
          {saved.length ? (
            <ul>
              {saved.map((p) => (
                <li key={p} className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      fill(p);
                      setOpenMenu(null);
                    }}
                    className="min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-small hover:bg-muted focus-visible:outline-2 focus-visible:outline-brand"
                    title={p}
                  >
                    {p}
                  </button>
                  <button type="button" aria-label={`Delete the saved prompt: ${p}`} onClick={() => persist(saved.filter((x) => x !== p))} className="flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-fail">
                    <Trash2 className="size-3.5" strokeWidth={1.75} aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-2 py-1.5 text-small text-muted-foreground">Nothing saved yet. Prompts are kept in this browser only.</p>
          )}
          <button
            type="button"
            disabled={!current || saved.includes(current)}
            onClick={() => persist([current, ...saved].slice(0, 12))}
            className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-left text-small font-medium hover:bg-muted disabled:opacity-50"
          >
            {current ? (saved.includes(current) ? "Already saved" : "Save what’s in the box") : "Type a prompt to save it"}
          </button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );

  const referenceTitle = referenceSearch
    ? "On: when there is no link, the agent may look for an open reference design. Signed into your mandate."
    : "Off: the agent uses your request and the build-type template only.";

  return (
    <div className="w-full">
      <div
        onDragOver={(e) => {
          if (!attachments) return;
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          large
            ? "rounded-[10px] border-2 bg-surface shadow-[0_14px_36px_-18px_rgb(29_78_216/0.35)] transition-colors duration-150 focus-within:ring-4 focus-within:ring-blueprint/12"
            : "rounded-2xl border bg-surface shadow-e1 transition-colors duration-150 focus-within:border-brand focus-within:ring-3 focus-within:ring-brand/15",
          large ? (dragging ? "border-blueprint bg-brand-tint" : "border-blueprint") : dragging ? "border-brand bg-brand-tint" : "border-border-strong",
        )}
      >
        <label htmlFor="chat-box" className="sr-only">
          Message
        </label>
        <textarea
          id="chat-box"
          ref={box}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onPaste={onPaste}
          onKeyDown={onKeyDown}
          rows={1}
          autoFocus
          placeholder={dragging ? "Drop the photo to add it" : placeholder}
          className={cn(
            "block w-full resize-none bg-transparent text-foreground outline-none placeholder:text-muted-foreground",
            large ? "min-h-[64px] px-6 pt-[18px] pb-2 font-serif text-[23px] leading-[30px] tracking-[-0.005em] placeholder:text-[#8a8e98]" : "min-h-[44px] px-4 pt-3.5 pb-1 text-body",
          )}
        />
        {link || photos.length ? (
          <div className={cn("flex flex-wrap items-center gap-2 pt-1 pb-1", large ? "px-6 pb-2" : "px-4")}>
            {link ? (
              <span className="inline-flex h-7 items-center gap-1.5 rounded-sm border border-border bg-muted pr-1 pl-2 text-small text-brand">
                <Link2 className="size-3.5" strokeWidth={1.75} aria-hidden />
                <span className="max-w-[40ch] truncate" title={link}>
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

        {large ? (
          <>
            <div className="mx-6 border-t border-border" aria-hidden />
            <div className="flex items-center gap-1 py-2 pr-2.5 pl-3">
              {attachments ? (
                <>
                  <button type="button" onClick={pickPhoto} disabled={photoFull} title={`Add a photo (up to ${MAX_PHOTOS}), or drop one on the box`} className={tool}>
                    <ImageIcon className="size-5" strokeWidth={1.5} aria-hidden />
                    Photo
                  </button>
                  <Bar />
                  <button type="button" onClick={pickPhoto} disabled={photoFull} title="Attach a photo file (JPEG, PNG or WebP)" className={tool}>
                    <Paperclip className="size-5" strokeWidth={1.5} aria-hidden />
                    Attach file
                  </button>
                  <Bar />
                  <button type="button" aria-pressed={referenceSearch} onClick={() => onReferenceSearch(!referenceSearch)} title={referenceTitle} className={tool}>
                    {referenceSearch ? <BookOpenCheck className="size-5 text-blueprint" strokeWidth={1.5} aria-hidden /> : <BookOpen className="size-5" strokeWidth={1.5} aria-hidden />}
                    Find references
                    <span className={cn("rounded-sm px-1.5 text-caption leading-5 font-medium", referenceSearch ? "bg-brand-tint text-blueprint" : "bg-muted text-muted-foreground")}>{referenceSearch ? "On" : "Off"}</span>
                  </button>
                </>
              ) : null}
              <div className="ml-auto flex min-w-0 items-center gap-1">
                {toolbarEnd}
                {attachments
                  ? samplesMenu(
                      <button type="button" className={toolQuiet}>
                        <Boxes className="size-4" strokeWidth={1.75} aria-hidden />
                        Samples
                      </button>,
                      "end",
                    )
                  : null}
                {savedMenu(
                  <button type="button" className={toolQuiet}>
                    <Bookmark className="size-4" strokeWidth={1.75} aria-hidden />
                    Saved prompts
                  </button>,
                  "end",
                )}
                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={!canSend}
                  aria-label="Send"
                  title="Send (Enter) · Shift+Enter for a new line"
                  className="ml-1.5 flex h-[42px] w-16 shrink-0 items-center justify-center rounded-md bg-blueprint text-white transition-colors duration-150 hover:bg-blueprint-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:bg-blueprint/55"
                >
                  <ArrowRight className="size-6" strokeWidth={2} aria-hidden />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex items-center gap-1.5 px-2.5 pt-1 pb-2.5">
            {attachments ? (
              <>
                <button
                  type="button"
                  aria-pressed={referenceSearch}
                  onClick={() => onReferenceSearch(!referenceSearch)}
                  title={referenceTitle}
                  className={cn(chip, referenceSearch ? "border-brand bg-brand-tint text-brand" : "border-border bg-surface text-secondary-text hover:border-border-strong")}
                >
                  <BookOpenCheck className="size-4" strokeWidth={1.75} aria-hidden />
                  Find reference designs
                </button>
                <button type="button" onClick={pickPhoto} disabled={photoFull} title={`Add a photo (up to ${MAX_PHOTOS}), or drop one on the box`} className={cn(chip, "border-border bg-surface text-secondary-text hover:border-border-strong")}>
                  <Camera className="size-4" strokeWidth={1.75} aria-hidden />
                  Photo
                </button>
                {samplesMenu(
                  <button type="button" className={cn(chip, "border-border bg-surface text-secondary-text hover:border-border-strong")}>
                    <Boxes className="size-4" strokeWidth={1.75} aria-hidden />
                    Samples
                  </button>,
                  "start",
                )}
              </>
            ) : (
              <span className="px-1.5 text-caption text-muted-foreground">Ask about this cart, or change it. Approving and paying stay with you.</span>
            )}
            <button
              type="button"
              onClick={() => void submit()}
              disabled={!canSend}
              aria-label="Send"
              title="Send (Enter)"
              className="ml-auto flex size-9 shrink-0 items-center justify-center rounded-full bg-ink text-white transition-colors duration-150 hover:bg-ink/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:bg-muted disabled:text-muted-foreground"
            >
              <ArrowUp className="size-4" strokeWidth={2.25} aria-hidden />
            </button>
          </div>
        )}
      </div>

      {fileErrors.map((err) => (
        <p key={err} role="alert" className="mt-1.5 text-small text-fail">
          {err}
        </p>
      ))}

      {large ? null : (
        <div className="mt-2 flex min-h-7 items-center gap-1 px-1">
          {savedMenu(
            <button type="button" className={quiet}>
              <Bookmark className="size-3.5" strokeWidth={1.75} aria-hidden />
              Saved prompts
            </button>,
            "start",
          )}
          {attachments ? (
            <button type="button" className={quiet} onClick={pickPhoto} disabled={photoFull}>
              <Paperclip className="size-3.5" strokeWidth={1.75} aria-hidden />
              Attach file
            </button>
          ) : null}
          <span className="ml-auto text-caption text-muted-foreground">Enter to send · Shift+Enter for a new line</span>
        </div>
      )}
    </div>
  );
}
