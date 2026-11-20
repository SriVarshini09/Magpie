"""Statsig gate `strict_compat_rules` (PLAN §3.15, P8). Owner: D.

Live calls follow the installed `statsig-python-core` (0.24.2), read from its type stubs:
    s = Statsig(STATSIG_SERVER_SECRET, StatsigOptions()); s.initialize().wait()
    s.check_gate(StatsigUser(user_id=…), "strict_compat_rules") -> bool      (logs the exposure itself)
    s.log_event(StatsigUser(…), "cart_approved", value, metadata)            (compare the two arms)
    s.shutdown().wait()
Gate on: every WARN that needs a human check (R10, R14 and the generic rules marked "human check") must be
acknowledged with a checkbox before Approve is enabled. Gate off: the warning shows but does not block.
When Statsig is not configured or cannot answer, the gate falls back to its DEFAULT (strict: on), never to the
looser policy, and `source` says so.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

GATES = {"strict_compat_rules": True}  # safe defaults when Statsig cannot answer
EVENT_META = frozenset({"rule_ids", "acknowledged", "total_usd", "build_type", "tier", "stores", "outcome"})


class FeatureGates(Protocol):
    def check_gate(self, gate: str, user_id: str = "demo_user") -> bool: ...


class MockGates:
    """Every gate is off, except the ones listed here. Mock: nothing is sent to Statsig."""

    ON = frozenset({"strict_compat_rules"})

    def check_gate(self, gate: str, user_id: str = "demo_user") -> bool:
        return gate in self.ON

    def log_event(self, name: str, user_id: str = "demo_user", value: Any = None, metadata: dict[str, Any] | None = None) -> None:
        return None

    def shutdown(self) -> None:
        return None


class LiveGates:
    def __init__(self, statsig: Any | None = None, *, secret: str | None = None) -> None:
        self._s = statsig
        self._secret = secret
        self.last_source: dict[str, str] = {}  # gate -> "statsig" | "default"
        self.last_error: str | None = None

    def configured(self) -> bool:
        return bool(self._s is not None or self._secret or os.getenv("STATSIG_SERVER_SECRET"))

    def _client(self) -> Any:
        if self._s is None:
            secret = self._secret or os.getenv("STATSIG_SERVER_SECRET") or ""
            if not secret:
                raise RuntimeError("STATSIG_SERVER_SECRET is not set")
            from statsig_python_core import Statsig, StatsigOptions  # lazy

            s = Statsig(secret, StatsigOptions())
            s.initialize().wait()
            self._s = s
        return self._s

    @staticmethod
    def _user(user_id: str) -> Any:
        from statsig_python_core import StatsigUser

        return StatsigUser(user_id=user_id)

    def check_gate(self, gate: str, user_id: str = "demo_user") -> bool:
        try:
            on = bool(self._client().check_gate(self._user(user_id), gate))
            self.last_source[gate] = "statsig"
            return on
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {str(exc)[:160]}"
            self.last_source[gate] = "default"
            return GATES.get(gate, False)

    def log_event(self, name: str, user_id: str = "demo_user", value: Any = None, metadata: dict[str, Any] | None = None) -> None:
        meta = {k: str(v)[:80] for k, v in (metadata or {}).items() if k in EVENT_META}
        try:
            self._client().log_event(self._user(user_id), name, value, meta or None)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {str(exc)[:160]}"

    def shutdown(self) -> None:
        if self._s is not None:
            try:
                self._s.shutdown().wait()
            except Exception:
                pass
