// Universal Cart page (PLAN §12.6): route /run/:id/cart. Also the approval screen and the guided checkout.
// Reached from Review cart; "Back to the model" returns with the selection kept.
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { UniversalCart } from "@/components/cart/UniversalCart";
import { NarrowNotice } from "@/components/common/NarrowNotice";
import { InlineError } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useRun } from "@/hooks/useRun";
import { api, ApiFailure } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { PageShell } from "@/pages/PageShell";

function CartSkeleton() {
  return (
    <div className="mx-auto max-w-[1200px] space-y-6 px-(--b2c-gutter) py-8" aria-busy="true" aria-label="Loading the cart">
      <div className="space-y-3">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-12 w-56" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-[minmax(0,64fr)_minmax(0,36fr)] gap-6">
        <div className="space-y-4">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-44 w-full rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-80 w-full rounded-lg" />
      </div>
    </div>
  );
}

export function CartPage() {
  const { id } = useParams();
  const { run } = useRun(id);
  const cart = useAppStore((s) => s.cart);
  const setCart = useAppStore((s) => s.setCart);
  const [error, setError] = useState<ApiFailure | null>(null);

  const load = useCallback(() => {
    if (!id) return;
    let cancelled = false;
    setError(null);
    api
      .cart(id)
      .then((c) => !cancelled && setCart(c))
      .catch((e: unknown) => !cancelled && setError(e instanceof ApiFailure ? e : new ApiFailure(0, { error: "unknown", message: "Couldn't load the cart.", bom_line_ids: [] })));
    return () => {
      cancelled = true;
    };
  }, [id, setCart]);
  useEffect(() => load(), [load]);
  useEffect(() => {
    document.title = "Your cart · Build-to-Cart";
  }, []);

  const mine = cart && cart.run_id === id ? cart : null;

  return (
    <NarrowNotice min={1100}>
      <PageShell runId={id} crumb="Universal Cart">
        {error ? (
          <div className="mx-auto max-w-xl space-y-4 px-6 py-16">
            <InlineError
              title={error.detail.error === "run_not_found" ? "No run with that ID" : error.status === 404 || error.status === 409 ? "There is no cart for this run yet" : "The cart didn't load"}
              message={
                error.detail.error === "run_not_found"
                  ? "Runs live in the backend's memory: it may have restarted since, or the run was started on another machine. Start a new one from the first page."
                  : error.status === 404 || error.status === 409
                    ? "A cart appears once the plan is ready. Go back to the model to see how far the run is."
                    : `${error.message} If the backend was not restarted, the run is still there.`
              }
              onRetry={load}
            />
            <Button asChild variant="outline">
              <Link to={`/run/${id}`}>Back to the model</Link>
            </Button>
          </div>
        ) : mine ? (
          <UniversalCart cart={mine} run={run} onCart={setCart} />
        ) : (
          <CartSkeleton />
        )}
      </PageShell>
    </NarrowNotice>
  );
}
