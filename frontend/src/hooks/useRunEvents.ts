// SSE hook for GET /api/runs/{id}/events (PLAN §4.2). Owner: C.
// One `message` per Event, JSON in `data`, `id` = seq. Events land in the zustand store.
import { useEffect } from "react";

import { api } from "@/lib/api";
import { useAppStore, type StreamState } from "@/lib/store";
import type { Event } from "@/lib/types";

export function useRunEvents(runId: string | undefined, onEvent?: (event: Event) => void): StreamState {
  const stream = useAppStore((s) => s.stream);

  useEffect(() => {
    if (!runId) return;
    const { pushEvent, setStream, lastSeq } = useAppStore.getState();
    setStream("connecting");
    // `after` resumes where the store already is (remount, StrictMode); the browser's own
    // reconnect sends Last-Event-ID, which the backend also honours.
    const source = new EventSource(api.eventsUrl(runId, lastSeq));
    source.onopen = () => setStream("open");
    source.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as Event;
        if (event.simulated) useAppStore.getState().setMockSeen(true);
        pushEvent(event);
        onEvent?.(event);
      } catch {
        // A malformed frame is dropped; the stream stays up.
      }
    };
    source.onerror = () => setStream(source.readyState === EventSource.CLOSED ? "closed" : "error");
    return () => {
      source.close();
      setStream("closed");
    };
    // onEvent is read at call time on purpose: pass a stable callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  return stream;
}
