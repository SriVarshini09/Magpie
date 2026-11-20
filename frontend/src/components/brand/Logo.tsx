// Logo mark and wordmark (PLAN §11.8): a hexagon nut outline with a check mark as its hole.
// 24×24 grid, 2 px stroke. The same drawing is public/favicon.svg.
import { cn } from "@/lib/utils";

export function LogoMark({ className, onDark = false }: { className?: string; onDark?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={cn("size-6", onDark ? "text-stage-text" : "text-ink", className)}
    >
      <path d="M12 2.6 20.1 7.3v9.4L12 21.4 3.9 16.7V7.3z" />
      <path d="m8.4 12.3 2.5 2.5 4.7-5.3" />
    </svg>
  );
}

export function Logo({ className, onDark = false }: { className?: string; onDark?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-body-lg font-semibold tracking-tight", onDark ? "text-stage-text" : "text-foreground", className)}>
      <LogoMark onDark={onDark} />
      Build-to-Cart
    </span>
  );
}
