// Legend for the active colour mode (PLAN §11.6 E1). Every entry is a swatch and words.
import { ACTION_ICON } from "@/components/panel/ActionBadge";
import { ACTION_LABEL } from "@/lib/format";
import { useAppStore } from "@/lib/store";
import { LEVEL_TOKEN, type StageData } from "@/lib/stage";
import type { ActionLevel } from "@/lib/types";

function Swatch({ tokenName, ghost = false, ring = false }: { tokenName: string; ghost?: boolean; ring?: boolean }) {
  return (
    <span
      aria-hidden
      className="size-2.5 shrink-0 rounded-full"
      style={{ background: ring ? "transparent" : `var(${tokenName})`, opacity: ghost ? 0.45 : 1, boxShadow: ring ? `inset 0 0 0 1.5px var(${tokenName})` : undefined }}
    />
  );
}

const LEVELS: ActionLevel[] = ["agent_cart", "prefilled_cart", "product_link"];

export function Legend({ data }: { data: StageData }) {
  const mode = useAppStore((s) => s.colourMode);
  const lines = [...data.lines.values()];
  const item = "flex items-center gap-1.5 text-caption text-stage-muted";

  if (mode === "store") {
    const stores = [...data.storeSlot.entries()].filter(([id]) => lines.some((l) => l.storeId === id));
    return (
      <ul className="space-y-1" aria-label="Legend: stores">
        {stores.map(([id, slot]) => (
          <li key={id} className={item}>
            <Swatch tokenName={`--b2c-store-${slot}`} />
            {data.storeNames.get(id) ?? id}
          </li>
        ))}
        <li className={item}>
          <Swatch tokenName="--b2c-mat-ghost" ghost />
          Nothing to buy
        </li>
      </ul>
    );
  }

  if (mode === "checkout") {
    return (
      <ul className="space-y-1" aria-label="Legend: how you check out">
        {LEVELS.map((level) => {
          const Icon = ACTION_ICON[level];
          return (
            <li key={level} className={item}>
              <Swatch tokenName={LEVEL_TOKEN[level]} />
              <Icon className="size-3" strokeWidth={1.75} aria-hidden />
              {ACTION_LABEL[level]}
            </li>
          );
        })}
        <li className={item}>
          <Swatch tokenName="--b2c-mat-ghost" ghost />
          Nothing to buy
        </li>
      </ul>
    );
  }

  const anyPrinted = lines.some((l) => l.category === "printed");
  return (
    <ul className="space-y-1" aria-label="Legend: status">
      <li className={item}>
        <Swatch tokenName="--b2c-stage-muted" ring />
        Chosen (its own colour)
      </li>
      <li className={item}>
        <Swatch tokenName="--b2c-mat-ghost" ghost />
        Owned or left out
      </li>
      <li className={item}>
        <Swatch tokenName="--b2c-warn" />
        Needs your check
      </li>
      <li className={item}>
        <Swatch tokenName="--b2c-fail" />
        Refused or failed
      </li>
      {anyPrinted ? (
        <li className={item}>
          <Swatch tokenName="--b2c-mat-printed" />
          Print at home
        </li>
      ) : null}
    </ul>
  );
}
