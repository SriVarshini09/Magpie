// "How it works" at /about: the former landing (PLAN §11.5 A, §11.13). The start page is the chat (pages/ChatPage).
// top bar, the hero with the composer on the left and the live view on the
// dark stage on the right, the proof row, how it works, the hand-off levels and the footer.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { Logo } from "@/components/brand/Logo";
import { Composer } from "@/components/composer/Composer";
import { Footer, REPO_URL } from "@/components/landing/Footer";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks, ProofRow } from "@/components/landing/HowItWorks";
import type { Intake } from "@/lib/types";

export function LandingPage() {
  const [params] = useSearchParams();
  const q = params.get("q") ?? "";
  const [intake, setIntake] = useState<Intake | null>(null);

  useEffect(() => {
    document.title = "How it works · Build-to-Cart";
  }, []);

  return (
    <div className="min-h-screen bg-page">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-(--b2c-gutter)">
          <Link to="/" className="rounded-sm">
            <Logo />
          </Link>
          <nav aria-label="Site" className="flex items-center gap-6 text-body text-secondary-text">
            <a href="#how" className="hover:text-foreground">
              How it works
            </a>
            <Link to="/" className="font-medium text-foreground hover:text-brand">
              Start a build
            </Link>
            {REPO_URL ? (
              <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="hover:text-foreground">
                GitHub
              </a>
            ) : null}
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto grid max-w-[1280px] grid-cols-1 items-start gap-12 px-(--b2c-gutter) pt-14 pb-6 min-[1100px]:grid-cols-2">
          <div className="space-y-6">
            <p className="inline-flex h-7 items-center rounded-full border border-border bg-surface px-3 text-small text-secondary-text">Type it, paste it, or snap it. Get carts you can trust.</p>
            <h1 className="text-display font-semibold tracking-tight text-balance min-[1100px]:text-hero">What do you want to build?</h1>
            {intake ? null : (
              <p className="max-w-[560px] text-body-lg text-secondary-text">
                Build-to-Cart turns a sentence, a project link or a photo into a parts list where every line says where it came from, checks every part across the stores you allow, and puts it all in one cart. You approve once. It can’t spend a cent without you.
              </p>
            )}
            <div className="max-w-[600px]">
              <Composer initialText={q} autoSubmit={Boolean(q)} onIntake={setIntake} />
            </div>
          </div>
          <div className="min-[1100px]:sticky min-[1100px]:top-6">
            <Hero buildType={intake?.build_type} />
          </div>
        </section>
        <ProofRow />
        <HowItWorks />
      </main>
      <Footer />
    </div>
  );
}
