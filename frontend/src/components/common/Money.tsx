// Money: one format everywhere (PLAN §11.4, Q6). Tabular numbers, and a tooltip saying when and
// where the price was seen. An unknown value reads "not quoted". A simulated price is underlined
// in dashed violet so mock and test figures are never mistaken for real ones.
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { isNum, money, timeOf, viaText } from "@/lib/format";
import { cn } from "@/lib/utils";

export type MoneyProps = {
  value: number | null | undefined;
  seenAt?: string | null;
  source?: string | null;
  mockOf?: string | null;
  simulated?: boolean | null;
  className?: string;
};

export function Money({ value, seenAt, source, mockOf, simulated, className }: MoneyProps) {
  if (!isNum(value)) return <span className={cn("text-muted-foreground", className)}>not quoted</span>;
  const isSim = Boolean(simulated) || source === "mock";
  const text = (
    <span
      className={cn("tabular font-mono whitespace-nowrap", isSim && "underline decoration-test decoration-dashed underline-offset-4", className)}
      data-simulated={isSim || undefined}
    >
      {money(value)}
    </span>
  );
  if (!seenAt && !source && !isSim) return text;
  const parts = [seenAt ? `seen ${timeOf(seenAt)}` : null, source ? viaText(source, mockOf) : isSim ? "simulated" : null].filter(Boolean);
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="cursor-default rounded-sm">
          {text}
        </span>
      </TooltipTrigger>
      <TooltipContent>{parts.join(" · ")}</TooltipContent>
    </Tooltip>
  );
}

/** "seen 1:04 PM · via SerpAPI" as a visible caption under a price. */
export function SeenLine({ seenAt, source, mockOf, className }: { seenAt?: string | null; source?: string | null; mockOf?: string | null; className?: string }) {
  return (
    <span className={cn("text-caption text-muted-foreground", className)}>
      seen {timeOf(seenAt)} · {viaText(source, mockOf)}
    </span>
  );
}
