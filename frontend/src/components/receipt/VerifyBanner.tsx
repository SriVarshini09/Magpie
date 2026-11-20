// Verify banner (PLAN §11.5 E, §3.7). Owner: D, with C's components.
// Green "Trail verified: N records, M signatures" or red "Broken at record N". The chain and the
// signatures are reported separately: mock fixtures carry placeholder signatures, and we say so
// honestly (violet, dashed) instead of showing them as a real failure.
import { FlaskConical, ShieldCheck, ShieldX } from "lucide-react";
import { useState } from "react";

import { HashText } from "@/components/common/HashText";
import { InlineError } from "@/components/common/States";
import { TestBadge, ToneBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { api, ApiFailure } from "@/lib/api";
import { plural } from "@/lib/format";
import type { Receipt, VerifyResult } from "@/lib/types";
import { cn } from "@/lib/utils";

import { isPlaceholderJws, signatureCount } from "./receiptFormat";
import { useSimulatedRunLabel } from "@/components/MockDataBadge";

type State = { phase: "idle" } | { phase: "verifying" } | { phase: "done"; result: VerifyResult; at: number } | { phase: "error"; message: string };

export function VerifyBanner({
  runId,
  receipt,
  onResult,
  className,
}: {
  runId: string;
  /** When given, the banner can say how many signatures there are and how many records it will recompute. */
  receipt?: Receipt | null;
  /** Called with each result, so the chain list can mark the broken record. */
  onResult?: (result: VerifyResult | null) => void;
  className?: string;
}) {
  const [state, setState] = useState<State>({ phase: "idle" });
  const simLabel = useSimulatedRunLabel();
  const sigs = receipt ? signatureCount(receipt) : null;

  const verify = () => {
    setState({ phase: "verifying" });
    onResult?.(null);
    api
      .verify(runId)
      .then((result) => {
        setState({ phase: "done", result, at: Date.now() });
        onResult?.(result);
      })
      .catch((e: unknown) => {
        const message = e instanceof ApiFailure ? e.message : "Verify failed. Try again.";
        setState({ phase: "error", message });
      });
  };

  if (state.phase === "error") {
    return <InlineError className={className} title="Couldn't run Verify" message={`${state.message} The receipt below is unchanged.`} onRetry={verify} />;
  }

  const result = state.phase === "done" ? state.result : null;
  const chainOk = result?.ok ?? null;
  // A placeholder signature ("MOCK…") cannot be checked and we say so; any real signature that fails is a real
  // failure, on a mock-store run too (those are signed with the demo key).
  const placeholder = Boolean(receipt && [receipt.open_mandate, receipt.closed_mandate, receipt.payment_mandate].some((m) => m?.signature && isPlaceholderJws(m.signature.jws)));
  const sigPlaceholder = Boolean(result && !result.signatures_ok && result.simulated && placeholder);
  const sigFailed = Boolean(result && !result.signatures_ok && !sigPlaceholder);
  const broken = chainOk === false || sigFailed;

  const tone = result === null ? "border-border bg-surface" : broken ? "border-fail/30 bg-fail-tint" : "border-pass/30 bg-pass-tint";
  const Icon = result && broken ? ShieldX : ShieldCheck;
  const iconTone = result === null ? "text-muted-foreground" : broken ? "text-fail" : "text-pass";

  let title: string;
  let line: string;
  if (state.phase === "verifying") {
    title = "Verifying…";
    line = receipt ? `Recomputing ${plural(receipt.records.length, "record")} and checking the signatures.` : "Recomputing the chain and checking the signatures.";
  } else if (!result) {
    title = "Not verified yet";
    line = "Verify recomputes every record's hash from the one before it and checks each mandate's ES256 signature.";
  } else if (chainOk === false) {
    title = `Broken at record ${result.broken_at ?? "?"}`;
    line = "That record no longer matches its own contents or the record before it, so nothing after it can be trusted.";
  } else if (sigFailed) {
    title = "Signatures don't verify";
    const failed = result.checks.find((c) => !c.ok && c.name !== "chain");
    line = `The chain of ${plural(result.records, "record")} recomputes, but at least one mandate signature or binding does not check out${failed ? ` (${failed.name}: ${failed.detail ?? "failed"})` : ""}.`;
  } else if (sigPlaceholder) {
    title = `Chain verified: ${plural(result.records, "record")}`;
    line = "Every hash recomputes from the record before it. The signatures in this sample are placeholders, so they cannot be checked.";
  } else {
    title = `Trail verified: ${plural(result.records, "record")}${sigs !== null ? `, ${plural(sigs, "signature")}` : ""}`;
    line = "Every hash recomputes from the record before it, and every mandate signature checks out.";
  }

  return (
    <section
      key={state.phase === "done" ? state.at : state.phase}
      aria-live="polite"
      className={cn("relative overflow-hidden rounded-lg border p-4 transition-colors duration-200", tone, result && broken && "shake-once", className)}
    >
      {state.phase === "verifying" ? (
        <span aria-hidden className="absolute inset-x-0 top-0 h-0.5 overflow-hidden">
          <span className="progress-line block h-full w-1/3 bg-brand" />
        </span>
      ) : null}
      <div className="flex flex-wrap items-start gap-3">
        <Icon className={cn("mt-0.5 size-6 shrink-0", iconTone)} strokeWidth={1.75} aria-hidden />
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-body-lg font-semibold text-foreground">{title}</p>
          <p className="text-small text-secondary-text">{line}</p>
          {result ? (
            <div className="flex flex-wrap items-center gap-2 pt-0.5">
              {chainOk ? (
                <ToneBadge tone="pass" icon={ShieldCheck}>
                  Chain recomputes
                </ToneBadge>
              ) : (
                <ToneBadge tone="fail" icon={ShieldX}>
                  Chain broken at {result.broken_at ?? "?"}
                </ToneBadge>
              )}
              {result.signatures_ok ? (
                <ToneBadge tone="pass" icon={ShieldCheck}>
                  Signatures valid
                </ToneBadge>
              ) : sigPlaceholder ? (
                <TestBadge>Signatures: placeholder (mock fixture), not verifiable</TestBadge>
              ) : (
                <ToneBadge tone="fail" icon={ShieldX}>
                  Signatures invalid
                </ToneBadge>
              )}
              <HashText hash={result.head_hash} label="head" />
              {result.simulated ? (
                <span className="inline-flex items-center gap-1 text-caption text-test">
                  <FlaskConical className="size-3" strokeWidth={1.75} aria-hidden />
                  {simLabel.long.toLowerCase()}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
        <Button onClick={verify} disabled={state.phase === "verifying"} variant={result ? "outline" : "default"} size="lg">
          <ShieldCheck aria-hidden />
          {result ? "Verify again" : "Verify"}
        </Button>
      </div>
    </section>
  );
}
