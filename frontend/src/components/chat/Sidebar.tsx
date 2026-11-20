// The chat pages' left sidebar, in the start page's blueprint style: the serif wordmark, New build, the sections
// (Library, Carts, Receipts, then Memory and How it works), and "Recent builds" (the conversations, newest first,
// with a search behind the magnifier). There are no accounts: the chip at the foot says what this is (a local
// session, kept in memory) and which assistant answers.
import { BookOpen, Brain, Layers, MonitorSmartphone, Plus, ReceiptText, Search, ShoppingCart, X, type LucideIcon } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { Link, NavLink } from "react-router";

import { MemoryPanel } from "@/components/chat/MemoryPanel";
import { Skeleton } from "@/components/ui/skeleton";
import { selectIsMock, useAppStore } from "@/lib/store";
import type { ChatSessionSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV: Array<{ to: string; label: string; icon: LucideIcon }> = [
  { to: "/library", label: "Library", icon: Layers },
  { to: "/carts", label: "Carts", icon: ShoppingCart },
  { to: "/receipts", label: "Receipts", icon: ReceiptText },
];

const item =
  "flex h-10 w-full items-center gap-3 rounded-md px-3 text-[15px] text-foreground transition-colors duration-150 hover:bg-muted focus-visible:outline-2 focus-visible:outline-brand";

export function Sidebar({ sessions, error, activeId, agentLabel }: { sessions: ChatSessionSummary[] | null; error: boolean; activeId?: string; agentLabel?: string | null }) {
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const searchBox = useRef<HTMLInputElement>(null);
  const isMock = useAppStore(selectIsMock);
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (sessions ?? []).filter((s) => !q || s.title.toLowerCase().includes(q));
  }, [sessions, query]);

  const closeSearch = () => {
    setQuery("");
    setSearching(false);
  };

  return (
    <aside className="relative flex h-full w-[232px] shrink-0 flex-col border-r border-border bg-surface" aria-label="Builds">
      <div className="px-5 pt-6 pb-5">
        <Link to="/" className="rounded-sm font-serif text-[27px] leading-8 tracking-[-0.01em] text-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand" aria-label="Build-to-Cart: new build">
          Build-to-Cart
        </Link>
      </div>

      <div className="px-3">
        <Link
          to="/"
          className="flex h-11 items-center gap-3 rounded-md bg-blueprint px-4 text-body-lg font-medium text-white shadow-e1 transition-colors duration-150 hover:bg-blueprint-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          <Plus className="size-[18px]" strokeWidth={2} aria-hidden />
          New build
        </Link>
      </div>

      <nav aria-label="Sections" className="mt-4 space-y-0.5 px-3">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) => cn(item, isActive && "bg-muted font-medium")}>
            <n.icon className="size-[18px] shrink-0 text-secondary-text" strokeWidth={1.6} aria-hidden />
            {n.label}
          </NavLink>
        ))}
        <button type="button" onClick={() => setMemoryOpen(true)} aria-haspopup="dialog" className={cn(item, "text-left", memoryOpen && "bg-muted font-medium")}>
          <Brain className="size-[18px] shrink-0 text-secondary-text" strokeWidth={1.6} aria-hidden />
          Memory
        </button>
        <NavLink to="/about" className={({ isActive }) => cn(item, isActive && "bg-muted font-medium")}>
          <BookOpen className="size-[18px] shrink-0 text-secondary-text" strokeWidth={1.6} aria-hidden />
          How it works
        </NavLink>
      </nav>
      <MemoryPanel open={memoryOpen} onOpenChange={setMemoryOpen} />

      <div className="mx-5 mt-4 border-t border-border" />

      <div className="mt-4 flex h-8 items-center justify-between pr-3 pl-5">
        <h2 className="font-serif text-[16px] text-muted-foreground">Recent builds</h2>
        <button
          type="button"
          onClick={() => {
            if (searching) closeSearch();
            else {
              setSearching(true);
              requestAnimationFrame(() => searchBox.current?.focus());
            }
          }}
          aria-label={searching ? "Close the search" : "Search conversations"}
          aria-expanded={searching}
          aria-controls="sidebar-search"
          title={searching ? "Close the search" : "Search conversations"}
          className="flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-brand"
        >
          {searching ? <X className="size-4" strokeWidth={1.75} aria-hidden /> : <Search className="size-4" strokeWidth={1.75} aria-hidden />}
        </button>
      </div>
      {searching ? (
        <label className="relative mx-3 mt-1 block">
          <span className="sr-only">Search conversations</span>
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" strokeWidth={1.75} aria-hidden />
          <input
            id="sidebar-search"
            ref={searchBox}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && closeSearch()}
            placeholder="Search conversations"
            className="h-9 w-full rounded-md border border-border bg-page pr-2.5 pl-8 text-body outline-none placeholder:text-muted-foreground focus-visible:border-brand focus-visible:ring-3 focus-visible:ring-brand/20"
          />
        </label>
      ) : null}

      <div className="relative mt-1 min-h-0 flex-1 overflow-y-auto px-3 pb-3" aria-label="Recent conversations">
        {sessions === null && !error ? (
          <div className="space-y-3 px-3 pt-3" aria-busy="true">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-4 w-40" />
          </div>
        ) : error ? (
          <p className="px-3 pt-2 text-small text-muted-foreground">Couldn’t load conversations. Check that the backend is running.</p>
        ) : !sessions?.length ? (
          <p className="px-3 pt-2 text-small text-muted-foreground">No builds yet. Your conversations will be listed here.</p>
        ) : !shown.length ? (
          <p className="px-3 pt-2 text-small text-muted-foreground">Nothing matches “{query.trim()}”.</p>
        ) : (
          <ul className="space-y-0.5">
            {shown.map((s) => (
              <li key={s.session_id}>
                <Link
                  to={`/c/${s.session_id}`}
                  aria-current={s.session_id === activeId ? "page" : undefined}
                  title={s.title}
                  className={cn(item, "h-9", s.session_id === activeId && "bg-brand-tint font-medium")}
                >
                  <span className="truncate">{s.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={cn("border-t border-border px-3 pt-3", isMock ? "pb-14" : "pb-3")}>
        <div className="flex items-center gap-2.5 rounded-lg px-1.5 py-1">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-muted text-secondary-text">
            <MonitorSmartphone className="size-4" strokeWidth={1.75} aria-hidden />
          </span>
          <span className="min-w-0">
            <span className="block text-small font-medium text-foreground">Local session</span>
            <span className="block truncate text-caption text-muted-foreground" title={agentLabel ?? undefined}>
              {agentLabel ?? "No account · kept in memory"}
            </span>
          </span>
        </div>
      </div>
    </aside>
  );
}
