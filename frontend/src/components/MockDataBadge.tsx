// The "Mock data" badge: visible on every screen whenever the backend reports mock mode.
// Violet + dashed border is reserved for test and mock things (PLAN §11.3). Do not remove it.
import { FlaskConical } from "lucide-react";

import { selectIsMock, useAppStore } from "@/lib/store";

export function MockDataBadge() {
  const isMock = useAppStore(selectIsMock);
  const health = useAppStore((s) => s.health);
  if (!isMock) return null;
  const mode = health?.mode;
  // DEMO_MODE=mock serves fixtures. In any other mode the pipeline is real and some services are mocks:
  // "Mock stores" when the store adapters are among them (prices, carts and hand-offs are simulated).
  const fixtures = !mode || mode === "mock";
  const storesMock = Object.values(health?.stores ?? {}).some((s) => s === "mock");
  const storesLive = Object.values(health?.stores ?? {}).some((s) => s === "ok"); // e.g. real Shopify stores, the rest mock
  const label = fixtures ? "Mock data" : storesMock ? (storesLive ? "Some stores mock" : "Mock stores") : "Mock services";
  const title = fixtures
    ? "The backend is serving fixture data. Prices, stores and carts on screen are simulated."
    : storesMock && storesLive
      ? `The pipeline is real (mode: ${mode}). Some store sources are real (their offers carry no Mock label); the others are mocks, and every simulated offer, price and hand-off is labelled.`
      : storesMock
        ? `The pipeline is real (mode: ${mode}), but the stores are mocks: offers, prices, carts and hand-offs on screen are simulated.`
        : `Mode: ${mode}. Some services are mocks; what they return is labelled simulated.`;
  return (
    <div
      role="status"
      data-testid="mock-data-badge"
      title={title}
      data-mock-kind={fixtures ? "fixtures" : storesMock ? "stores" : "services"}
      className="fixed bottom-3 left-3 z-50 inline-flex items-center gap-1.5 rounded-full border border-dashed border-test bg-test-tint px-3 py-1 text-small font-medium text-test shadow-e1"
    >
      <FlaskConical className="size-4" strokeWidth={1.75} aria-hidden />
      {label}
      {!fixtures ? <span className="font-normal"> · real pipeline</span> : null}
    </div>
  );
}

/** How to name simulated run data: a fixture "Sample" in mock mode, the real pipeline's "Mock stores" otherwise. */
export function useSimulatedRunLabel(): { short: string; long: string } {
  const mode = useAppStore((s) => s.health?.mode);
  const storesLive = useAppStore((s) => Object.values(s.health?.stores ?? {}).some((v) => v === "ok"));
  return !mode || mode === "mock"
    ? { short: "Sample", long: "Sample run (mock data)" }
    : storesLive
      ? { short: "Some stores mock", long: "Real run: some stores real, the others mock (each simulated offer labelled)" }
      : { short: "Mock stores", long: "Real run on mock stores (prices and hand-offs simulated)" };
}

/** Inline label for a single mock value (an offer row, a hand-off, a test-mode step). */
export function SimulatedTag({ label = "Simulated" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-sm border border-dashed border-test bg-test-tint px-1.5 py-0.5 text-caption font-medium text-test">
      <FlaskConical className="size-3" strokeWidth={1.75} aria-hidden />
      {label}
    </span>
  );
}
