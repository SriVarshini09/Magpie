"""Amplitude Agent Analytics (PLAN §3.15). Owner: D; A calls it from the single tool wrapper.

Live calls follow the installed `amplitude-ai` (1.30.0), read from the package source:
    ai = AmplitudeAI(amplitude=Amplitude(AMPLITUDE_AI_API_KEY)); agent = ai.agent("build-to-cart")
    agent.track_tool_call(tool_name=, latency_ms=, success=, user_id=, session_id=run_id, event_properties=)
    agent.track_ai_message(content="", model=, provider="anthropic", latency_ms=, input_tokens=, output_tokens=, …) -> message_id
    agent.track_user_message(content=<input kind only>, user_id=, session_id=)
    agent.score(name="user-feedback", value=1.0|0.0, target_id=<message_id>, target_type="message", source="user", …)
    agent.track_session_end(user_id=, session_id=)                  when the run ends (A calls end_session)
    amplitude.track(BaseEvent(event_type=…, user_id=, event_properties=))   product events (funnel)
    ai.shutdown()                                                    FastAPI lifespan
One Amplitude agent session per run: session_id = run_id. Approval is the feedback score (1.0 approve, 0.0 reject).

No buyer data in any event: properties pass an allow-list (counts, rule ids, tool names, latencies, totals, kinds),
strings are capped at 80 characters and anything that looks like an email, phone number or street address is
dropped. Message contents are never sent (content is ""; a user message sends only its input kind).
Analytics never raises into the agent: an error is counted in `errors` and the call is skipped.
"""

from __future__ import annotations

import os
import re
from typing import Any, Protocol

AGENT_ID = "build-to-cart"
USER_ID = "demo_user"
PRODUCT_EVENTS = (
    "request_submitted", "build_type_set", "question_answered", "assumption_resolved", "bom_extracted", "offer_refused",
    "compat_fixed", "plan_ready", "tier_switched", "cart_edited", "prices_refreshed", "cart_approved",
    "store_checkout_opened", "store_marked_done", "gate_exposure",
)
ALLOWED_PROPS = frozenset({
    "input_kinds", "kind", "build_type", "confidence", "changed_by_user", "question_id", "defaulted", "action", "lines",
    "rule_id", "rule_ids", "tool", "tool_name", "outcome", "latency_ms", "total_usd", "budget_usd", "checkouts", "tier",
    "stores", "store_id", "action_level", "op", "changes", "count", "refusals", "assumptions", "gate", "value",
    "acknowledged", "n_readme_quote", "n_reference_project", "n_template_row", "n_photo_region", "n_assumption",
    "provider", "model", "items", "source", "simulated", "mode", "variant",
})
_PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{8,}\d|\b\d{1,5}\s+\w+\s+(street|st|avenue|ave|road|rd)\b", re.I)


def safe_props(props: dict[str, Any] | None) -> dict[str, Any]:
    """The allow-listed, PII-free version of `props`."""
    out: dict[str, Any] = {}
    for k, v in (props or {}).items():
        if k not in ALLOWED_PROPS:
            continue
        if isinstance(v, bool) or isinstance(v, (int, float)) or v is None:
            out[k] = v
        elif isinstance(v, str):
            if not _PII.search(v):
                out[k] = v[:80]
        elif isinstance(v, (list, tuple)) and all(isinstance(x, (str, int, float)) for x in v):
            vals = [x[:40] if isinstance(x, str) else x for x in v if not (isinstance(x, str) and _PII.search(x))]
            out[k] = vals[:20]
    return out


class Analytics(Protocol):
    def track_tool_call(self, run_id: str, tool: str, latency_ms: int, outcome: str) -> None: ...

    def track_ai_message(self, run_id: str, model: str, input_tokens: int, output_tokens: int, latency_ms: int) -> None: ...

    def track_event(self, run_id: str, name: str, props: dict[str, Any] | None = None) -> None: ...

    def score(self, run_id: str, name: str, value: float) -> None: ...

    def shutdown(self) -> None: ...


class MockAnalytics:
    """Records calls in memory; sends nothing."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def track_tool_call(self, run_id: str, tool: str, latency_ms: int, outcome: str) -> None:
        self.calls.append({"kind": "tool_call", "run_id": run_id, "tool": tool, "latency_ms": latency_ms, "outcome": outcome})

    def track_ai_message(self, run_id: str, model: str, input_tokens: int, output_tokens: int, latency_ms: int) -> None:
        self.calls.append({"kind": "ai_message", "run_id": run_id, "model": model})

    def track_user_message(self, run_id: str, input_kind: str) -> None:
        self.calls.append({"kind": "user_message", "run_id": run_id, "input_kind": input_kind})

    def track_event(self, run_id: str, name: str, props: dict[str, Any] | None = None) -> None:
        self.calls.append({"kind": "event", "run_id": run_id, "name": name, "props": safe_props(props)})

    def score(self, run_id: str, name: str, value: float) -> None:
        self.calls.append({"kind": "score", "run_id": run_id, "name": name, "value": value})

    def end_session(self, run_id: str) -> None:
        self.calls.append({"kind": "session_end", "run_id": run_id})

    def shutdown(self) -> None:
        return None


class LiveAnalytics:
    def __init__(self, ai: Any | None = None, amplitude: Any | None = None, *, api_key: str | None = None,
                 user_id: str = USER_ID, agent_id: str = AGENT_ID) -> None:
        self._ai = ai
        self._amp = amplitude
        self._key = api_key
        self._agent: Any | None = None
        self.user_id = user_id
        self.agent_id = agent_id
        self.last_message: dict[str, str] = {}  # run_id -> last AI message id (the score's target)
        self.sessions: set[str] = set()
        self.errors = 0
        self.last_error: str | None = None
        self.sent = 0

    def configured(self) -> bool:
        return bool(self._ai is not None or self._key or os.getenv("AMPLITUDE_AI_API_KEY"))

    def _client(self) -> tuple[Any, Any]:
        if self._ai is None:
            key = self._key or os.getenv("AMPLITUDE_AI_API_KEY") or ""
            if not key:
                raise RuntimeError("AMPLITUDE_AI_API_KEY is not set")
            from amplitude import Amplitude  # lazy imports: a missing SDK breaks only this service
            from amplitude_ai import AmplitudeAI

            self._amp = Amplitude(key)
            self._ai = AmplitudeAI(amplitude=self._amp)
        if self._agent is None:
            self._agent = self._ai.agent(self.agent_id)
        return self._ai, self._agent

    def _safe(self, fn: Any) -> Any:
        try:
            out = fn()
            self.sent += 1
            return out
        except Exception as exc:  # analytics must never break a run
            self.errors += 1
            self.last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            return None

    def _ids(self, run_id: str) -> dict[str, Any]:
        self.sessions.add(run_id)
        return {"user_id": self.user_id, "session_id": run_id}

    def track_tool_call(self, run_id: str, tool: str, latency_ms: int, outcome: str) -> None:
        """outcome: ok | refused | error. Refused counts as a successful tool call that the guard stopped."""
        def call() -> Any:
            _, agent = self._client()
            return agent.track_tool_call(tool_name=tool, latency_ms=float(latency_ms), success=outcome != "error",
                                         event_properties=safe_props({"outcome": outcome, "tool": tool}), **self._ids(run_id))
        self._safe(call)

    def track_ai_message(self, run_id: str, model: str, input_tokens: int, output_tokens: int, latency_ms: int) -> None:
        def call() -> Any:
            _, agent = self._client()
            return agent.track_ai_message(content="", model=model, provider="anthropic", latency_ms=float(latency_ms),
                                          input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0),
                                          **self._ids(run_id))
        mid = self._safe(call)
        if isinstance(mid, str):
            self.last_message[run_id] = mid

    def track_user_message(self, run_id: str, input_kind: str) -> None:
        """A chat message or preset. Only its kind is sent (text | link | photo | preset), never the text."""
        def call() -> Any:
            _, agent = self._client()
            return agent.track_user_message(content=f"[{input_kind}]", **self._ids(run_id))
        self._safe(call)

    def track_event(self, run_id: str, name: str, props: dict[str, Any] | None = None) -> None:
        """A product event (funnel). Unknown names are still sent but only with allow-listed properties."""
        def call() -> Any:
            self._client()
            from amplitude import BaseEvent

            return self._amp.track(BaseEvent(event_type=name, user_id=self.user_id,
                                             event_properties={"run_id": run_id, **safe_props(props)}))
        self._safe(call)

    def score(self, run_id: str, name: str, value: float, *, target_id: str | None = None) -> None:
        """Approval as a feedback score: name "user-feedback", value 1.0 approve / 0.0 reject (PLAN §3.15)."""
        def call() -> Any:
            _, agent = self._client()
            tid = target_id or self.last_message.get(run_id)
            return agent.score(name=name, value=float(value), target_id=tid or run_id,
                               target_type="message" if tid else "session", source="user", **self._ids(run_id))
        self._safe(call)

    def end_session(self, run_id: str) -> None:
        def call() -> Any:
            _, agent = self._client()
            return agent.track_session_end(**self._ids(run_id))
        self._safe(call)
        self.sessions.discard(run_id)

    def shutdown(self) -> None:
        if self._ai is None:
            return
        for run_id in list(self.sessions):
            self.end_session(run_id)
        self._safe(lambda: self._ai.shutdown())
