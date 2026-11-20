// Chip questions (PLAN §3.17, §11.5 A): up to three, each a row of pill buttons, with "Skip, use defaults".
// The default of each question is marked, so skipping is an informed choice. Works with Tab and Enter.
import { Button } from "@/components/ui/button";
import type { Intake } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ChipQuestions({
  intake,
  answers,
  onAnswer,
  onSkip,
  disabled,
}: {
  intake: Intake;
  answers: Record<string, string>;
  onAnswer: (questionId: string, value: string) => void;
  onSkip: () => void;
  disabled?: boolean;
}) {
  const questions = intake.questions.slice(0, 3);
  if (!questions.length) return null;
  const open = questions.some((q) => !(answers[q.id] ?? q.answer));
  return (
    <div className="space-y-3">
      {questions.map((q) => {
        const value = answers[q.id] ?? q.answer ?? null;
        return (
          <fieldset key={q.id} className="space-y-1.5" disabled={disabled}>
            <legend className="text-small font-medium text-foreground">{q.text}</legend>
            <div role="radiogroup" aria-label={q.text} className="flex flex-wrap gap-1.5">
              {q.chips.map((chip) => {
                const picked = value === chip.value;
                return (
                  <button
                    key={chip.value}
                    type="button"
                    role="radio"
                    aria-checked={picked}
                    onClick={() => onAnswer(q.id, chip.value)}
                    className={cn(
                      "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-small transition-colors duration-150 disabled:opacity-60",
                      picked ? "border-ink bg-ink text-white" : "border-border-strong bg-surface text-foreground hover:border-ink",
                    )}
                  >
                    {chip.label}
                    {chip.value === q.default && !picked ? <span className="text-caption text-muted-foreground">default</span> : null}
                  </button>
                );
              })}
            </div>
          </fieldset>
        );
      })}
      {open ? (
        <Button type="button" variant="ghost" size="sm" onClick={onSkip} disabled={disabled} className="-ml-2 text-secondary-text">
          Skip, use defaults
        </Button>
      ) : null}
    </div>
  );
}
