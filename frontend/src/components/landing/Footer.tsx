// Landing footer (PLAN §11.5 A).
export const REPO_URL = import.meta.env.VITE_REPO_URL || null;

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto flex max-w-[1280px] flex-wrap items-center gap-x-6 gap-y-2 px-(--b2c-gutter) py-6 pl-40 text-small text-muted-foreground">
        <span>Built at the tokens&amp; Personal Agents Hackathon, Nov 20, 2026</span>
        <span>No real payments are made by this app</span>
        {REPO_URL ? (
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="ml-auto text-brand hover:text-brand-hover">
            GitHub
          </a>
        ) : null}
      </div>
    </footer>
  );
}
