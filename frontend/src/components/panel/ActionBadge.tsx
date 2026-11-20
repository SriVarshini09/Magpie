// Action-level badge (PLAN §3.16, §11.3). Always icon + words; the wording is fixed.
// Agent cart: ink fill, ShoppingCart · Prefilled cart: blue outline, ListPlus · Product link: grey outline, ExternalLink.
import { ExternalLink, ListPlus, ShoppingCart, type LucideIcon } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ACTION_LABEL } from "@/lib/format";
import type { ActionLevel } from "@/lib/types";
import { cn } from "@/lib/utils";

export const ACTION_ICON: Record<ActionLevel, LucideIcon> = {
  agent_cart: ShoppingCart,
  prefilled_cart: ListPlus,
  product_link: ExternalLink,
};

const ACTION_CLASS: Record<ActionLevel, string> = {
  agent_cart: "border-level-agent-cart bg-level-agent-cart text-white",
  prefilled_cart: "border-level-prefilled-cart bg-surface text-level-prefilled-cart",
  product_link: "border-level-product-link bg-surface text-info",
};

export const ACTION_HELP: Record<ActionLevel, string> = {
  agent_cart: "The agent builds a real cart at the store. You open it and pay there.",
  prefilled_cart: "One link fills the store's own cart with these items.",
  product_link: "A link to the exact product page. You add it yourself.",
};

export function ActionBadge({ level, reason, className }: { level: ActionLevel; reason?: string | null; className?: string }) {
  const Icon = ACTION_ICON[level] ?? ExternalLink;
  const badge = (
    <span
      className={cn("inline-flex h-6 shrink-0 items-center gap-1 rounded-full border px-2 text-caption font-medium whitespace-nowrap", ACTION_CLASS[level], className)}
    >
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
      {ACTION_LABEL[level] ?? level}
    </span>
  );
  return (
    <Tooltip>
      <TooltipTrigger asChild>{badge}</TooltipTrigger>
      <TooltipContent className="max-w-64">{reason ? `${ACTION_HELP[level]} ${reason}` : ACTION_HELP[level]}</TooltipContent>
    </Tooltip>
  );
}

/** Icon-only form for tight places (3D chip, diagram node). The label is still there for screen readers. */
export function ActionIcon({ level, className }: { level: ActionLevel; className?: string }) {
  const Icon = ACTION_ICON[level] ?? ExternalLink;
  return (
    <span title={ACTION_LABEL[level]} className={cn("inline-flex", className)}>
      <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
      <span className="sr-only">{ACTION_LABEL[level]}</span>
    </span>
  );
}
