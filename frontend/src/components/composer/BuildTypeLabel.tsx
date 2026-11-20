// Build-type label (PLAN §3.17, §11.5 A): "Quadcopter · change". "change" lists every build type as a pill;
// picking one re-classifies the intake as set by you.
import { useState } from "react";

import { BUILD_TYPE_LABEL } from "@/lib/format";
import type { BuildType, Intake } from "@/lib/types";
import { cn } from "@/lib/utils";

const ALL: BuildType[] = ["quadcopter", "robot_arm", "rc_car", "claw_gripper", "electronics_mcu", "generic"];

export function BuildTypeLabel({ intake, onChange, disabled }: { intake: Intake; onChange?: (type: BuildType) => void; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  // The classifier's own alternatives first.
  const order = [...new Set<BuildType>([intake.build_type, ...intake.alternatives.map((a) => a.build_type), ...ALL])];
  return (
    <div className="space-y-2">
      <p className="flex flex-wrap items-center gap-2 text-body">
        <span className="text-secondary-text">We read this as</span>
        <span className="inline-flex h-7 items-center rounded-sm border border-border bg-surface px-2 font-semibold">{BUILD_TYPE_LABEL[intake.build_type]}</span>
        <span className="tabular text-small text-muted-foreground">{Math.round(intake.confidence * 100)}% sure</span>
        {onChange ? (
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="text-small font-medium text-brand hover:text-brand-hover">
            {open ? "keep it" : "change"}
          </button>
        ) : null}
      </p>
      {intake.summary ? <p className="text-small text-secondary-text">{intake.summary}</p> : null}
      {open && onChange ? (
        <div role="radiogroup" aria-label="Build type" className="flex flex-wrap gap-1.5">
          {order.map((type) => (
            <button
              key={type}
              type="button"
              role="radio"
              aria-checked={type === intake.build_type}
              disabled={disabled}
              onClick={() => {
                setOpen(false);
                if (type !== intake.build_type) onChange(type);
              }}
              className={cn(
                "h-8 rounded-full border px-3 text-small transition-colors duration-150",
                type === intake.build_type ? "border-ink bg-ink text-white" : "border-border-strong bg-surface text-foreground hover:border-ink",
              )}
            >
              {BUILD_TYPE_LABEL[type]}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
