// Loads RunState for a route and resets the store when the run changes. Owner: C.
import { useCallback, useEffect, useState } from "react";

import { api, ApiFailure } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function useRun(runId: string | undefined) {
  const run = useAppStore((s) => s.run);
  const [error, setError] = useState<ApiFailure | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    const store = useAppStore.getState();
    if (store.runId !== runId) store.resetRun(runId);
    setError(null);
    api
      .run(runId)
      .then((r) => !cancelled && useAppStore.getState().setRun(r))
      .catch((e: unknown) => !cancelled && setError(e instanceof ApiFailure ? e : new ApiFailure(0, { error: "unknown", message: String(e), bom_line_ids: [] })));
    return () => {
      cancelled = true;
    };
  }, [runId, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { run: run && run.run_id === runId ? run : null, error, loading: !error && !(run && run.run_id === runId), reload };
}
