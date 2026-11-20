// The start page: a chat-first shell. Left, the sidebar (New build, the run lists, recent builds, the local-session
// chip). Right, either the blueprint start state ("What do you want to build?" over our drone in a blueprint sky,
// the composer, three sample-build cards) or a conversation with the shopping agent, whose messages are blocks
// (components/chat/Blocks). The chat can refine a cart; approving, signing and paying stay buttons a person presses.
import { ArrowRight, Box, Keyboard, Link2, ShoppingCart, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { LogoMark } from "@/components/brand/Logo";
import { Block, type BlockContext } from "@/components/chat/Blocks";
import { ChatComposer, type ComposerHandle, type ComposerInput } from "@/components/chat/ChatComposer";
import { RunsList, type RunsView } from "@/components/chat/RunsList";
import { SampleBuilds } from "@/components/chat/SampleBuilds";
import { Sidebar } from "@/components/chat/Sidebar";
import { Crosshair, HeroArt } from "@/components/chat/StartArt";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiFailure } from "@/lib/api";
import { firstUrl, hostOf, plural, repoOf, timeOf } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import type { AssumptionRequest, ChatMessage, ChatSendResponse, ChatSession, ChatSessionSummary, MandatePreset, ProjectSample } from "@/lib/types";
import { cn } from "@/lib/utils";

const KEYWORD_LABEL = "Keyword assistant (no AI key)";

// The three starting points. Used as they are if the samples endpoint is unreachable; they are real flows either way.
const FALLBACK: ProjectSample[] = [
  { build_type: "quadcopter", title: "Small camera drone", example_text: "a small camera drone under $200", source_url: null, blurb: "Typed request, template rows, a procedural model", view_kind: "procedural", simulated: false } as ProjectSample,
  { build_type: "robot_arm", title: "SO-101 robot arm (link)", example_text: null, source_url: "https://github.com/TheRobotStudio/SO-ARM100", blurb: "Every part quoted from the README, the project's own 3D model", view_kind: "urdf", simulated: false } as ProjectSample,
  { build_type: "electronics_mcu", title: "E-paper weather display (link)", example_text: null, source_url: "https://github.com/lmarzen/esp32-weather-epd", blurb: "Electronics only, shown as a board diagram", view_kind: "diagram", simulated: false } as ProjectSample,
];
const ORDER = ["quadcopter", "robot_arm", "electronics_mcu"];

function failure(e: unknown, fallback: string): string {
  if (!(e instanceof ApiFailure)) return fallback;
  if (e.detail.error === "session_not_found") return "This conversation is no longer on the backend (it may have restarted). Start a new build.";
  if (e.status === 501) return `${e.message}. This part of the backend isn't connected in this mode.`;
  return e.message;
}

function AgentPill({ label }: { label: string }) {
  const keyword = label.startsWith("Keyword");
  const Icon = keyword ? Keyboard : Sparkles;
  return (
    <span
      title={keyword ? "No Anthropic key is set, so a keyword router answers: it matches phrases and calls the same backend functions." : "Claude answers with tools that call the same backend functions. It has no tool to approve, pay or sign."}
      className="inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full border border-border bg-page px-2 text-caption font-medium text-secondary-text"
    >
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
      {label}
    </span>
  );
}

function UserBubble({ text, link, images, photos }: { text?: string | null; link?: string | null; images?: ChatMessage["images"]; photos?: number }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[78%] space-y-2 rounded-2xl rounded-br-md bg-muted px-4 py-2.5">
        {text ? <p className="text-body leading-6 break-words whitespace-pre-wrap text-foreground">{text}</p> : null}
        {link ? (
          <a href={link} target="_blank" rel="noopener noreferrer" className="inline-flex h-7 max-w-full items-center gap-1.5 rounded-sm border border-border bg-surface px-2 text-small text-brand hover:text-brand-hover" title={link}>
            <Link2 className="size-3.5 shrink-0" strokeWidth={1.75} aria-hidden />
            <span className="truncate">{repoOf(link) || hostOf(link)}</span>
          </a>
        ) : null}
        {images?.length ? (
          <ul className="flex gap-2" aria-label="Photos in this request">
            {images.map((im, i) => (
              <li key={im.image_id}>
                <img src={api.uploadUrl(im.image_id)} alt={`Photo ${i + 1} of this request`} width={64} height={64} className="size-16 rounded-md border border-border object-cover" />
              </li>
            ))}
          </ul>
        ) : photos ? (
          <p className="text-small text-secondary-text">{plural(photos, "photo")} attached</p>
        ) : null}
      </div>
    </div>
  );
}

function AgentRow({ label, time, children }: { label: string; time?: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-surface">
        <LogoMark className="size-4" />
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        <p className="pt-1.5 text-caption text-muted-foreground">
          {label}
          {time ? ` · ${time}` : ""}
        </p>
        {children}
      </div>
    </div>
  );
}

export function ChatPage({ view }: { view?: RunsView }) {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const health = useAppStore((s) => s.health);
  const [session, setSessionState] = useState<ChatSession | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [pending, setPending] = useState<{ text: string; link: string | null; photos: number } | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSessionSummary[] | null>(null);
  const [sessionsError, setSessionsError] = useState(false);
  const [samples, setSamples] = useState<ProjectSample[] | null>(null);
  const [referenceSearch, setReferenceSearch] = useState(true);
  const current = useRef<ChatSession | null>(null);
  const composer = useRef<ComposerHandle>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);
  const auto = useRef(false);

  const setSession = useCallback((next: ChatSession | null) => {
    current.current = next;
    setSessionState(next);
  }, []);

  const refreshSessions = useCallback(() => {
    api
      .chatSessions()
      .then((list) => {
        setSessions(list);
        setSessionsError(false);
      })
      .catch(() => setSessionsError(true));
  }, []);

  const merge = useCallback(
    (res: ChatSendResponse) => {
      const cur = current.current;
      if (!cur || cur.session_id !== res.session.session_id) return;
      const fresh = res.messages.filter((m) => !cur.messages.some((x) => x.message_id === m.message_id));
      setSession({ ...cur, ...res.session, messages: [...cur.messages, ...fresh], awaiting_summary: res.awaiting_summary, agent: res.agent, agent_label: res.agent_label });
      refreshSessions();
    },
    [refreshSessions, setSession],
  );

  useEffect(() => {
    refreshSessions();
    let cancelled = false;
    api
      .projects()
      .then((p) => !cancelled && setSamples(p))
      .catch(() => !cancelled && setSamples([]));
    return () => {
      cancelled = true;
    };
  }, [refreshSessions]);

  // Load the conversation named in the address, unless it is the one already on screen.
  useEffect(() => {
    setLoadError(null);
    setSendError(null);
    if (!sessionId) {
      setSession(null);
      return;
    }
    if (current.current?.session_id === sessionId) return;
    let cancelled = false;
    setSession(null);
    api
      .chatSession(sessionId)
      .then((s) => {
        if (cancelled) return;
        setSession(s);
        setReferenceSearch(s.reference_search);
      })
      .catch((e) => !cancelled && setLoadError(failure(e, "Couldn't load this conversation. Check that the backend is running.")));
    return () => {
      cancelled = true;
    };
  }, [sessionId, setSession]);

  useEffect(() => {
    document.title = view ? `${view[0].toUpperCase()}${view.slice(1)} · Build-to-Cart` : session?.messages.length ? `${session.title} · Build-to-Cart` : "Build-to-Cart · What do you want to build?";
  }, [view, session?.title, session?.messages.length]);

  const count = session?.messages.length ?? 0;
  useEffect(() => {
    // Scroll the conversation itself; scrollIntoView would also move every clipped ancestor.
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [count, pending, sending]);

  const send = useCallback(
    async (input: ComposerInput): Promise<boolean> => {
      if (sending) return false;
      setSending(true);
      setSendError(null);
      setPending({ text: input.text, link: input.link, photos: input.photos.length });
      try {
        let s = current.current;
        if (!s) {
          s = await api.chatCreate(referenceSearch);
          setSession(s);
          navigate(`/c/${s.session_id}`);
        }
        const res = await api.chatSend(s.session_id, { text: input.text || undefined, link: input.link, images: input.photos, referenceSearch: s.run_id ? undefined : referenceSearch });
        setPending(null);
        merge(res);
        return true;
      } catch (e) {
        setPending(null);
        setSendError(failure(e, "Couldn't send that. Check that the backend is running, then try again."));
        return false;
      } finally {
        setSending(false);
      }
    },
    [sending, referenceSearch, navigate, merge, setSession],
  );

  // A request handed over in the address (?q=…) from the workspace's composer strip starts a new conversation.
  useEffect(() => {
    const q = params.get("q");
    if (!q || auto.current || sessionId || view) return;
    auto.current = true;
    setParams({}, { replace: true });
    const url = firstUrl(q);
    void send({ text: url ? q.replace(url, "").trim() : q, link: url, photos: [] });
  }, [params, sessionId, view, send, setParams]);

  const onRunStopped = useCallback(() => {
    const s = current.current;
    if (!s?.awaiting_summary || syncing.current) return;
    syncing.current = true;
    api
      .chatSync(s.session_id)
      .then(merge)
      .catch((e) => setSendError(failure(e, "The run stopped, but its summary couldn't be loaded. Ask “show the parts” to see it.")))
      .finally(() => {
        syncing.current = false;
      });
  }, [merge]);

  const onSign = useCallback(
    async (mandate: MandatePreset): Promise<string | null> => {
      const s = current.current;
      if (!s) return "There is no conversation to sign for.";
      try {
        merge(await api.chatSign(s.session_id, mandate));
        return null;
      } catch (e) {
        return failure(e, "Couldn't start the run. Check the backend is running, then try again.");
      }
    },
    [merge],
  );

  const onAssumption = useCallback(
    async (body: AssumptionRequest) => {
      const s = current.current;
      if (!s) return;
      try {
        merge(await api.chatAssumption(s.session_id, body));
      } catch (e) {
        setSendError(failure(e, "Couldn't save that. Try again."));
      }
    },
    [merge],
  );

  const onReply = useCallback((text: string) => void send({ text, link: null, photos: [] }), [send]);

  // Which interactive cards are still the current ones. Older copies stay in the conversation as a record.
  const live = useMemo(() => {
    const msgs = session?.messages ?? [];
    const last = { intake: -1, mandate: "", assumptions: "", progressAfterMandate: false };
    msgs.forEach((m, mi) =>
      m.blocks.forEach((b, bi) => {
        if (b.kind === "build_type") last.intake = mi;
        if (b.kind === "mandate") {
          last.mandate = `${mi}:${bi}`;
          last.progressAfterMandate = false;
        }
        if (b.kind === "progress") last.progressAfterMandate = true;
        if (b.kind === "assumptions") last.assumptions = `${mi}:${bi}`;
      }),
    );
    return last;
  }, [session?.messages]);

  const hasRun = Boolean(session?.run_id);
  const agentLabel = session?.agent_label ?? (health && health.mode !== "mock" && health.integrations?.anthropic === "ok" ? "Claude" : KEYWORD_LABEL);
  const shortAgent = agentLabel.startsWith("Keyword") ? "Keyword assistant" : agentLabel;
  const cards = useMemo(() => {
    const list = samples && samples.length ? samples : samples === null ? null : FALLBACK;
    return list ? [...list].sort((a, b) => (ORDER.indexOf(a.build_type) + 9) % 9 - (ORDER.indexOf(b.build_type) + 9) % 9).slice(0, 3) : null;
  }, [samples]);

  const started = Boolean(session?.messages.length) || pending !== null;
  // The blueprint start state has no header bar: the hero's headline is the page's h1.
  const startState = !view && !loadError && !(sessionId && !session) && !started;
  const composerEl = (
    <ChatComposer
      ref={composer}
      busy={sending}
      onSend={send}
      referenceSearch={referenceSearch}
      onReferenceSearch={setReferenceSearch}
      attachments={!hasRun}
      large={!started}
      placeholder={hasRun ? "Make it cheaper · I already have a battery · why this part?" : started ? "Answer a question, or describe the build another way" : "A small camera drone under $200…"}
      samples={samples}
      toolbarEnd={started ? undefined : <AgentPill label={agentLabel} />}
    />
  );
  const errorEl = sendError ? (
    <p role="alert" className="mb-2 flex items-start gap-2 rounded-lg border border-fail/30 bg-fail-tint px-3 py-2 text-small text-fail">
      <span className="flex-1">{sendError}</span>
      <button type="button" onClick={() => setSendError(null)} aria-label="Dismiss" className="flex size-5 shrink-0 items-center justify-center rounded-sm hover:bg-surface">
        <X className="size-3.5" strokeWidth={2} aria-hidden />
      </button>
    </p>
  ) : null;

  return (
    <div className="relative flex h-screen min-w-[1024px] overflow-hidden bg-page">
      <Sidebar sessions={sessions} error={sessionsError} activeId={view ? undefined : sessionId} agentLabel={agentLabel} />

      <div className="flex min-w-0 flex-1 flex-col">
        <header className={cn("flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-6", startState && "hidden")}>
          <h1 className="min-w-0 truncate text-body font-semibold" title={session?.title}>
            {view ? `${view[0].toUpperCase()}${view.slice(1)}` : started && session ? session.title : "New build"}
          </h1>
          {!view ? <AgentPill label={agentLabel} /> : null}
          <div className="ml-auto flex shrink-0 items-center gap-2">
            {hasRun && session?.run_id && !view ? (
              <>
                <Button asChild variant="outline" className="h-9 px-3">
                  <Link to={`/run/${session.run_id}`}>
                    <Box aria-hidden /> Open 3D workspace
                  </Link>
                </Button>
                <Button asChild className="h-9 px-3.5">
                  <Link to={`/run/${session.run_id}/cart`}>
                    <ShoppingCart aria-hidden /> Review cart
                  </Link>
                </Button>
              </>
            ) : (
              <>
                <Button asChild variant="outline" className="h-9 px-3.5">
                  <Link to="/about">
                    How it works <ArrowRight aria-hidden />
                  </Link>
                </Button>
              </>
            )}
          </div>
        </header>

        {view ? (
          <main className="relative min-h-0 flex-1 overflow-y-auto">
            <RunsList view={view} />
          </main>
        ) : loadError ? (
          <main className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
            <p role="alert" className="max-w-md text-body text-secondary-text">
              {loadError}
            </p>
            <Button asChild className="h-9 px-4">
              <Link to="/">New build</Link>
            </Button>
          </main>
        ) : sessionId && !session ? (
          <main className="mx-auto w-full max-w-[820px] flex-1 space-y-4 px-6 py-8" aria-busy="true">
            <Skeleton className="ml-auto h-10 w-64 rounded-2xl" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-40 w-full" />
          </main>
        ) : !started ? (
          <main className="relative min-h-0 flex-1 overflow-y-auto blueprint-grid">
            <div className="mx-auto flex min-h-full w-full max-w-[1560px] flex-col pr-2 pl-6">
              {/* 360 px tall on a 900 px screen, 295 px on 800: the cards and the note below them stay in view. */}
              <div className="relative h-[clamp(256px,calc(65vh-225px),364px)] shrink-0">
                <HeroArt className="absolute top-2 right-0 bottom-0 left-[26%]" />
                <Crosshair className="absolute top-[14px] left-[-8px]" />
                <div className="relative z-10 pt-[clamp(44px,9.5vh,90px)]">
                  <h1 className="font-serif text-[clamp(52px,5vw,80px)] leading-[0.92] tracking-[-0.035em] text-ink">
                    What do you
                    <br />
                    want to build?
                  </h1>
                  <p className="mt-[clamp(12px,2vh,20px)] font-serif text-[clamp(19px,1.8vw,27px)] leading-[1.17] tracking-[-0.01em] text-foreground/80">
                    Describe your idea, paste a GitHub link,
                    <br />
                    or add a photo.
                  </p>
                </div>
                <div aria-hidden className="absolute bottom-1.5 left-[-8px] flex w-[30%] items-center gap-1">
                  <Crosshair size={18} />
                  <span className="h-[5px] flex-1 border-b border-blueprint-line/25 bg-[repeating-linear-gradient(90deg,rgb(33_73_184/0.22)_0_1px,transparent_1px_8px)]" />
                </div>
              </div>
              <div className="flex flex-1 flex-col pr-4">
                <div className="mt-5">
                  {errorEl}
                  {composerEl}
                </div>
                <SampleBuilds cards={cards} busy={sending} onStart={(s) => void send({ text: s.source_url ? "" : (s.example_text ?? s.title), link: s.source_url ?? null, photos: [] })} />
                <p className="mt-auto pt-3 pb-2.5 text-caption text-muted-foreground">
                  The agent searches and builds carts inside the mandate you sign. It can’t approve, check out or pay, and photos stay on this machine unless your mandate shares them.
                </p>
              </div>
            </div>
          </main>
        ) : (
          <main className="flex min-h-0 flex-1 flex-col">
            <div ref={scroller} className="relative min-h-0 flex-1 overflow-y-auto" aria-label="Conversation">
              <div className="mx-auto w-full max-w-[820px] space-y-6 px-6 py-6" aria-live="polite">
                {(session?.messages ?? []).map((m, mi) =>
                  m.role === "user" ? (
                    <UserBubble key={m.message_id} text={m.text} link={m.link} images={m.images} />
                  ) : (
                    <AgentRow key={m.message_id} label={m.agent === "claude" ? "Claude" : "Keyword assistant"} time={timeOf(m.ts)}>
                      {m.blocks.map((b, bi) => {
                        const key = `${mi}:${bi}`;
                        const isLive =
                          b.kind === "build_type" || b.kind === "questions"
                            ? !hasRun && mi === live.intake
                            : b.kind === "mandate"
                              ? key === live.mandate && !live.progressAfterMandate
                              : b.kind === "assumptions"
                                ? key === live.assumptions
                                : true;
                        const ctx: BlockContext = { busy: sending, live: isLive, onReply, onSign, onAssumption, onRunStopped };
                        return <Block key={key} block={b} ctx={ctx} />;
                      })}
                    </AgentRow>
                  ),
                )}
                {pending ? <UserBubble text={pending.text} link={pending.link} photos={pending.photos} /> : null}
                {sending ? (
                  <AgentRow label={shortAgent}>
                    <p className="flex h-6 items-center gap-1.5 text-body text-secondary-text" role="status">
                      <span className={cn("size-1.5 animate-pulse rounded-full bg-secondary-text motion-reduce:animate-none")} aria-hidden />
                      Working on it…
                    </p>
                  </AgentRow>
                ) : null}
              </div>
            </div>
            <div className="shrink-0 border-t border-border bg-page">
              <div className="mx-auto w-full max-w-[820px] px-6 pt-3 pb-3">
                {errorEl}
                {composerEl}
              </div>
            </div>
          </main>
        )}
      </div>
    </div>
  );
}
