// Proof row, "How it works" and the three hand-off levels (PLAN §11.5 A).
import { FileSignature, Quote, ShoppingCart } from "lucide-react";

import { ACTION_HELP, ACTION_ICON } from "@/components/panel/ActionBadge";
import { useStores } from "@/components/workspace/MandateBar";
import { ACTION_LABEL } from "@/lib/format";
import type { ActionLevel } from "@/lib/types";

const PROOF = [
  { icon: Quote, title: "Every part says where it came from", text: "A quote from the page, a reference design, a template row, your photo, or an assumption you confirm. No source, no line." },
  { icon: FileSignature, title: "A mandate you sign, enforced in code", text: "Budget, stores and what may be shared. Anything outside it is refused and logged." },
  { icon: ShoppingCart, title: "One cart for every store", text: "One list you control, then the strongest hand-off each store supports." },
];

const STEPS = [
  { n: "01", title: "Read", text: "Builds the parts list from your sentence, link or photo, with a source for every line." },
  { n: "02", title: "Check", text: "Finds offers across your stores and checks that the parts work together." },
  { n: "03", title: "Refuse", text: "Says no to anything outside your mandate, and shows you why." },
  { n: "04", title: "Cart", text: "One cart on this site, then a real cart, a prefilled cart or a link at each store." },
];

const LEVELS: ActionLevel[] = ["agent_cart", "prefilled_cart", "product_link"];

export function ProofRow() {
  return (
    <section aria-label="What you can rely on" className="mx-auto grid max-w-[1280px] grid-cols-3 gap-6 px-(--b2c-gutter) py-12">
      {PROOF.map((p) => (
        <div key={p.title} className="flex gap-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface">
            <p.icon className="size-5" strokeWidth={1.75} aria-hidden />
          </span>
          <div>
            <h3 className="text-body-lg font-semibold">{p.title}</h3>
            <p className="mt-1 text-body text-secondary-text">{p.text}</p>
          </div>
        </div>
      ))}
    </section>
  );
}

export function HowItWorks() {
  const stores = useStores();
  return (
    <>
      <section id="how" aria-labelledby="how-title" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-[1280px] px-(--b2c-gutter) py-16">
          <h2 id="how-title" className="text-h1 font-semibold tracking-tight">
            How it works
          </h2>
          <ol className="mt-8 grid grid-cols-4 gap-6">
            {STEPS.map((s) => (
              <li key={s.n} className="border-t-2 border-ink pt-4">
                <p className="font-mono text-small text-muted-foreground">{s.n}</p>
                <h3 className="mt-1 text-h3 font-semibold">{s.title}</h3>
                <p className="mt-1 text-body text-secondary-text">{s.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="levels-title" className="mx-auto max-w-[1280px] px-(--b2c-gutter) py-16">
        <h2 id="levels-title" className="text-h2 font-semibold tracking-tight">
          Every store gets the strongest hand-off it supports
        </h2>
        <div className="mt-6 grid grid-cols-3 gap-6">
          {LEVELS.map((level) => {
            const Icon = ACTION_ICON[level];
            const names = stores.filter((s) => s.action_level === level && s.enabled).map((s) => s.display_name);
            return (
              <div key={level} className="rounded-lg border border-border bg-surface p-5">
                <p className="flex items-center gap-2 text-body-lg font-semibold">
                  <Icon className="size-5" strokeWidth={1.75} aria-hidden />
                  {ACTION_LABEL[level]}
                </p>
                <p className="mt-2 text-body text-secondary-text">{ACTION_HELP[level]}</p>
                <p className="mt-3 min-h-5 text-small text-muted-foreground">{names.length ? names.join(", ") : stores.length ? (level === "prefilled_cart" ? "None yet: no store's cart link has been checked in a real browser, so those stores show product links." : "None right now.") : " "}</p>
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}
