// Status is never colour alone: every badge has an icon and a word (PLAN §11.3).
import {
  Ban,
  CircleCheck,
  CircleDashed,
  CircleSlash,
  FlaskConical,
  Loader,
  PackageCheck,
  Search,
  ShieldX,
  TriangleAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { STATUS_LABEL } from "@/lib/format";
import type { BomStatus, CheckResult } from "@/lib/types";
import { cn } from "@/lib/utils";

export type Tone = "pass" | "warn" | "fail" | "info" | "test" | "brand";

export const TONE_CLASS: Record<Tone, string> = {
  pass: "border-pass/30 bg-pass-tint text-pass",
  warn: "border-warn/40 bg-warn-tint text-warn",
  fail: "border-fail/30 bg-fail-tint text-fail",
  info: "border-border bg-info-tint text-info",
  // Violet + dashed is reserved for test and mock things.
  test: "border-dashed border-test bg-test-tint text-test",
  brand: "border-brand/30 bg-brand-tint text-brand",
};

export function ToneBadge({ tone, icon: Icon, children, className, title }: { tone: Tone; icon: LucideIcon; children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cn("inline-flex h-6 shrink-0 items-center gap-1 rounded-full border px-2 text-caption font-medium whitespace-nowrap", TONE_CLASS[tone], className)}
    >
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
      {children}
    </span>
  );
}

export const STATUS_META: Record<BomStatus, { tone: Tone; icon: LucideIcon }> = {
  extracted: { tone: "info", icon: CircleDashed },
  resolved: { tone: "info", icon: Search },
  offers: { tone: "info", icon: Loader },
  chosen: { tone: "pass", icon: CircleCheck },
  owned: { tone: "info", icon: PackageCheck },
  warning: { tone: "warn", icon: TriangleAlert },
  needs_human: { tone: "warn", icon: TriangleAlert },
  not_found: { tone: "info", icon: CircleSlash },
  skipped: { tone: "info", icon: Ban },
  removed: { tone: "info", icon: XCircle },
};

export function StatusBadge({ status, label, className }: { status: BomStatus; label?: string; className?: string }) {
  const meta = STATUS_META[status] ?? STATUS_META.extracted;
  return (
    <ToneBadge tone={meta.tone} icon={meta.icon} className={className}>
      {label ?? STATUS_LABEL[status] ?? status}
    </ToneBadge>
  );
}

const CHECK_META: Record<CheckResult, { tone: Tone; icon: LucideIcon; label: string }> = {
  pass: { tone: "pass", icon: CircleCheck, label: "Pass" },
  warn: { tone: "warn", icon: TriangleAlert, label: "Needs your check" },
  needs_human: { tone: "warn", icon: TriangleAlert, label: "Needs your check" },
  fail: { tone: "fail", icon: XCircle, label: "Fail" },
};

export function CheckBadge({ result, className }: { result: CheckResult; className?: string }) {
  const meta = CHECK_META[result] ?? CHECK_META.warn;
  return (
    <ToneBadge tone={meta.tone} icon={meta.icon} className={className}>
      {meta.label}
    </ToneBadge>
  );
}

export function RefusedBadge({ className, children = "Refused" }: { className?: string; children?: ReactNode }) {
  return (
    <ToneBadge tone="fail" icon={ShieldX} className={className}>
      {children}
    </ToneBadge>
  );
}

/** Inline label for anything simulated: violet, dashed, with the flask. */
export function TestBadge({ className, children = "Test mode" }: { className?: string; children?: ReactNode }) {
  return (
    <ToneBadge tone="test" icon={FlaskConical} className={className}>
      {children}
    </ToneBadge>
  );
}
