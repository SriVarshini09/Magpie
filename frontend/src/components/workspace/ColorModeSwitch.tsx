// Colour modes on the stage (PLAN §11.6 E1): Status · Store · Checkout. Recolours meshes, nodes and tray chips.
import { useAppStore, type ColourMode } from "@/lib/store";
import { cn } from "@/lib/utils";

const MODES: Array<{ id: ColourMode; label: string; hint: string }> = [
  { id: "status", label: "Status", hint: "Colour by what happened to each part" },
  { id: "store", label: "Store", hint: "Colour by the store each part comes from" },
  { id: "checkout", label: "Checkout", hint: "Colour by how you check out" },
];

export function ColorModeSwitch() {
  const mode = useAppStore((s) => s.colourMode);
  const setMode = useAppStore((s) => s.setColourMode);
  return (
    <div role="radiogroup" aria-label="Colour parts by" className="inline-flex rounded-md border border-stage-border bg-stage-surface/90 p-0.5">
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          role="radio"
          aria-checked={mode === m.id}
          title={m.hint}
          onClick={() => setMode(m.id)}
          className={cn(
            "h-7 rounded-sm px-2.5 text-caption font-medium transition-colors duration-150",
            mode === m.id ? "bg-stage-text text-stage" : "text-stage-muted hover:text-stage-text",
          )}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
