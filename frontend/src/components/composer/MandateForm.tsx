// The mandate form (PLAN §11.5 A, §3.7): budget, deadline, the stores the agent may use, and what it may share.
// Prefilled from the intake. "Sign mandate and run" signs the open mandate; anything outside it is refused in code.
import { Lock } from "lucide-react";
import { useEffect, useState } from "react";

import { ACTION_ICON } from "@/components/panel/ActionBadge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useStores } from "@/components/workspace/MandateBar";
import { ACTION_LABEL } from "@/lib/format";
import type { ActionLevel, DataSharing, Intake, MandatePreset } from "@/lib/types";

const LEVELS: ActionLevel[] = ["agent_cart", "prefilled_cart", "product_link"];
const SHARING: Array<{ key: keyof DataSharing; label: string; hint: string }> = [
  { key: "country", label: "Country", hint: "Stores need it to show prices and stock" },
  { key: "postal_code", label: "Postal code", hint: "For shipping quotes" },
  { key: "email", label: "Email", hint: "" },
  { key: "phone", label: "Phone", hint: "" },
  { key: "name", label: "Name", hint: "" },
  { key: "street_address", label: "Street address", hint: "" },
];

export function MandateForm({ intake, busy, error, onSign }: { intake: Intake; busy: boolean; error?: string | null; onSign: (mandate: MandatePreset) => void }) {
  const stores = useStores();
  const preset = intake.mandate_preset;
  const [budget, setBudget] = useState(String(intake.constraints.budget_usd ?? preset.budget_usd));
  const [deadline, setDeadline] = useState(preset.deadline);
  const [allowed, setAllowed] = useState<string[]>(preset.allowed_merchants);
  const [sharing, setSharing] = useState<DataSharing>(preset.data_sharing);
  const hasPhotos = intake.inputs.images.length > 0;

  useEffect(() => {
    setBudget(String(intake.constraints.budget_usd ?? preset.budget_usd));
    setDeadline(preset.deadline);
    setAllowed(preset.allowed_merchants);
    setSharing(preset.data_sharing);
    // Reset only when a different intake arrives.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intake.intake_id]);

  const amount = Number(budget);
  const valid = Number.isFinite(amount) && amount > 0 && allowed.length > 0 && Boolean(deadline);
  const byId = new Map(stores.map((s) => [s.store_id, s]));
  // Stores from the registry that are switched on, plus anything the preset names that the registry does not list.
  const listed = stores.filter((s) => s.enabled || preset.allowed_merchants.includes(s.store_id));
  const extra = preset.allowed_merchants.filter((id) => !byId.has(id));
  const toggle = (id: string, on: boolean) => setAllowed((cur) => (on ? [...new Set([...cur, id])] : cur.filter((x) => x !== id)));

  return (
    <form
      className="space-y-4 rounded-lg border border-border bg-surface p-4"
      aria-label="Mandate"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid && !busy) onSign({ budget_usd: amount, deadline, ship_to_country: preset.ship_to_country, allowed_merchants: allowed, data_sharing: sharing });
      }}
    >
      <div>
        <h2 className="text-body-lg font-semibold">Your mandate</h2>
        <p className="text-small text-secondary-text">The agent can search and build carts inside these limits. It can’t check out or pay.</p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <label className="text-caption font-medium text-secondary-text">
          Budget (USD)
          <div className="relative mt-1">
            <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-small text-muted-foreground">$</span>
            <Input value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="decimal" aria-invalid={!(Number.isFinite(amount) && amount > 0)} className="tabular h-9 pl-6 font-mono" />
          </div>
        </label>
        <label className="text-caption font-medium text-secondary-text">
          Needed by
          <Input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="mt-1 h-9" />
        </label>
        <label className="text-caption font-medium text-secondary-text">
          Ships to
          <Input value={preset.ship_to_country} readOnly aria-readonly className="mt-1 h-9 bg-muted" />
        </label>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-caption font-medium text-secondary-text">Stores the agent may use ({allowed.length})</legend>
        {LEVELS.map((level) => {
          const group = listed.filter((s) => s.action_level === level);
          if (!group.length) return null;
          const Icon = ACTION_ICON[level];
          return (
            <div key={level} className="flex items-start gap-3">
              <span className="flex w-28 shrink-0 items-center gap-1.5 pt-1 text-caption text-muted-foreground">
                <Icon className="size-3.5" strokeWidth={1.75} aria-hidden />
                {ACTION_LABEL[level]}
              </span>
              <div className="flex flex-wrap gap-x-3 gap-y-1.5">
                {group.map((s) => (
                  <label key={s.store_id} className="flex items-center gap-1.5 text-small" title={s.caveat ?? s.domain}>
                    <Checkbox checked={allowed.includes(s.store_id)} onCheckedChange={(v) => toggle(s.store_id, v === true)} />
                    {s.display_name}
                  </label>
                ))}
              </div>
            </div>
          );
        })}
        {extra.length ? (
          <div className="flex flex-wrap gap-x-3 gap-y-1.5 pl-[124px]">
            {extra.map((id) => (
              <label key={id} className="flex items-center gap-1.5 text-small">
                <Checkbox checked={allowed.includes(id)} onCheckedChange={(v) => toggle(id, v === true)} />
                <span className="font-mono text-caption">{id}</span>
              </label>
            ))}
          </div>
        ) : null}
        {!allowed.length ? <p className="text-caption text-fail">Allow at least one store.</p> : null}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-caption font-medium text-secondary-text">What the agent may share with stores</legend>
        <div className="grid grid-cols-3 gap-x-4 gap-y-2">
          {SHARING.map((item) => (
            <label key={item.key} className="flex items-center gap-2 text-small" title={item.hint || undefined}>
              <Switch checked={sharing[item.key]} onCheckedChange={(v) => setSharing((cur) => ({ ...cur, [item.key]: v }))} />
              {item.label}
            </label>
          ))}
        </div>
        {hasPhotos ? (
          <label className="flex items-center gap-2 text-small">
            <Switch checked={sharing.photo_to_models} onCheckedChange={(v) => setSharing((cur) => ({ ...cur, photo_to_models: v }))} />
            Send my photos to the vision models to find parts
          </label>
        ) : null}
      </fieldset>

      {error ? (
        <p role="alert" className="rounded-sm border border-fail/30 bg-fail-tint px-3 py-2 text-small text-fail">
          {error}
        </p>
      ) : null}

      <div className="flex items-center gap-3">
        <Button type="submit" size="lg" className="h-10 px-4 text-body" disabled={!valid || busy}>
          <Lock aria-hidden /> {busy ? "Signing…" : "Sign mandate and run"}
        </Button>
        <p className="text-caption text-muted-foreground">You approve the cart later. Nothing is bought by signing.</p>
      </div>
    </form>
  );
}
