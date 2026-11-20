"""Cognee memory: owned parts, preferences, purchases written back (PLAN §3.15). Owner: D.

Live calls follow the installed `cognee` (1.6.10), read from the package source:
    await cognee.serve(url=COGNEE_URL, api_key=COGNEE_API_KEY)      cloud mode: every later call goes to the instance
    await cognee.remember(text, dataset_name=user_id)               write one fact
    await cognee.recall(query_text=…, datasets=[user_id], top_k=…)  -> list of entries; each graph entry has `text`
    await cognee.remember(cognee.QAEntry(question=…, answer=…, feedback_text=…, feedback_score=1..5),
                          dataset_name=user_id, session_id=…)       one rated session turn (the user's decision)
    await cognee.improve(user_id, session_ids=[…])                  -> ImproveResult.stages (feedback_weights first)
    await cognee.forget(dataset=user_id)                            -> dict; removes the user's whole dataset
  forget and improve both forward to the instance after `serve()` (they check `get_remote_client()` first).
  Cognee has no "list what I remembered" call that works in every mode, so `list_facts` answers from a LEDGER of the
  facts this app wrote (text, kind, source, run), kept beside the runs. It is our own record, not a read of Cognee.
COGNEE_MODE
    cloud  COGNEE_URL (+ COGNEE_API_KEY). No LLM or embedding key needed.
    local  Runs Cognee in-process. Cognee silently defaults BOTH its LLM and its embedder to OpenAI, so this client
           refuses to start unless LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, EMBEDDING_PROVIDER, EMBEDDING_MODEL and
           EMBEDDING_DIMENSIONS are all set, and sets both configs explicitly (PLAN §3.3, R1 §3c).
    off    The `owned_parts` table in SingleStore (SQLite locally): "your inventory" (PLAN §2.1 2:15 fallback).
Only facts the user stated or confirmed are remembered; never the photo, never buyer data (a fact that looks like
an email address, phone number or street address is refused).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from app.integrations.base import MOCK_LABEL

SEED_MEMORIES = [  # PLAN §3.15
    "owns a precision screwdriver set",
    "owns two USB-C data cables",
    "owns a 3D printer and PLA",
    "owns a soldering iron and jumper wires",
    "prefers US sellers; no Alibaba or AliExpress",
]
LOCAL_REQUIRED = ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS")
_BUYER_DATA = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{8,}\d|\b\d{1,5}\s+\w+\s+(street|st|avenue|ave|road|rd|lane|ln|drive|dr)\b",
                         re.I)


class CogneeConfigError(RuntimeError):
    pass


class Memory(Protocol):
    async def remember(self, text: str, user_id: str = "demo_user") -> None:
        """Only facts the user stated or confirmed. Never the photo itself."""
        ...

    async def recall(self, query: str, user_id: str = "demo_user") -> list[dict[str, Any]]: ...


def check_fact(text: str) -> str:
    t = (text or "").strip()
    if not t:
        raise ValueError("empty memory")
    if len(t) > 500:
        raise ValueError("a memory is one short fact (500 characters at most)")
    if _BUYER_DATA.search(t):
        raise ValueError("refused: a memory may not contain an email address, phone number or street address")
    return t


FEEDBACK_QUESTION = "What did the user decide about this cart?"
SCOPES = ("everything", "preferences")
_PREFERENCE = re.compile(r"(?i)^\s*(you\s+)?(chose|rejected|prefers?|avoids?)\b")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fact_kind(text: str) -> str:
    """owned | preference | purchase, read from how the fact starts (the facts this app writes are templated)."""
    t = (text or "").strip().lower()
    if _PREFERENCE.match(t):
        return "preference"
    return "purchase" if t.startswith("bought") else "owned"


def is_preference(entry: dict[str, Any]) -> bool:
    return entry.get("kind") == "preference" or fact_kind(str(entry.get("text", ""))) == "preference"


def ledger_entry(text: str, *, kind: str | None = None, source: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    return {"text": text, "kind": kind or fact_kind(text), "source": source, "run_id": run_id, "at": now_iso()}


def _check_scope(scope: str) -> str:
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {', '.join(SCOPES)}")
    return scope


def _seed_entries() -> list[dict[str, Any]]:
    return [{"text": f, "kind": "seed", "source": "seed", "run_id": None, "at": None} for f in SEED_MEMORIES]


class MockMemory:
    """In-process memory: nothing leaves this process and nothing here is Cognee. Everything is labelled simulated."""

    provider = "cognee"
    mode = "mock"

    def __init__(self) -> None:
        self._ledger: dict[str, list[dict[str, Any]]] = {}  # user_id -> facts (seeded on first use)
        self._feedback: dict[str, list[dict[str, Any]]] = {}
        self._last_improve: dict[str, dict[str, Any]] = {}

    def _entries(self, user_id: str) -> list[dict[str, Any]]:
        if user_id not in self._ledger:
            self._ledger[user_id] = _seed_entries()
        return self._ledger[user_id]

    async def remember(self, text: str, user_id: str = "demo_user", *, kind: str | None = None, source: str | None = None,
                       run_id: str | None = None) -> None:
        fact = check_fact(text)
        entries = self._entries(user_id)
        if not any(e["text"] == fact for e in entries):
            entries.append(ledger_entry(fact, kind=kind, source=source, run_id=run_id))

    async def recall(self, query: str, user_id: str = "demo_user") -> list[dict[str, Any]]:
        words = {w for w in query.lower().split() if len(w) > 3}
        return [{"memory_text": e["text"], "provider": "cognee", **MOCK_LABEL} for e in self._entries(user_id)
                if words & set(e["text"].lower().split())]

    async def list_facts(self, user_id: str = "demo_user") -> list[dict[str, Any]]:
        return [{**e, "provider": "cognee", "simulated": True} for e in self._entries(user_id)]

    async def preferences(self, user_id: str = "demo_user", topic: str | None = None) -> list[dict[str, Any]]:
        return [{"memory_text": e["text"], "provider": "cognee", **MOCK_LABEL} for e in self._entries(user_id) if is_preference(e)]

    async def feedback(self, text: str, user_id: str = "demo_user", *, session_id: str, positive: bool = True) -> bool:
        self._feedback.setdefault(user_id, []).append({"text": check_fact(text), "session_id": session_id, "score": 5 if positive else 1})
        return True

    async def improve(self, user_id: str = "demo_user", *, session_ids: list[str] | None = None, run_id: str | None = None,
                      feedback: list[str] | None = None) -> dict[str, Any]:
        sessions = set(session_ids or [])
        kept = [f for f in self._feedback.get(user_id, []) if f["session_id"] in sessions]
        out = {"at": now_iso(), "run_id": run_id, "feedback": list(feedback) if feedback is not None else [f["text"] for f in kept],
               "stages": [{"stage": "feedback_weights", "status": "simulated",
                           "reason": f"mock mode: Cognee was not called; {len(kept)} rated decision{'s' if len(kept) != 1 else ''} kept in this process"}],
               "provider": "cognee", "simulated": True}
        self._last_improve[user_id] = out
        return out

    def last_improve(self, user_id: str = "demo_user") -> dict[str, Any] | None:
        return self._last_improve.get(user_id)

    async def forget(self, user_id: str = "demo_user", scope: str = "everything") -> dict[str, Any]:
        _check_scope(scope)
        entries = self._entries(user_id)
        gone = [e for e in entries if scope == "everything" or is_preference(e)]
        self._ledger[user_id] = [e for e in entries if not (scope == "everything" or is_preference(e))]
        self._feedback.pop(user_id, None)
        self._last_improve.pop(user_id, None)
        return {"scope": scope, "forgotten": len(gone), "provider": "cognee", "simulated": True,
                "detail": f"Mock memory: {len(gone)} fact{'s' if len(gone) != 1 else ''} cleared from this process. Cognee was not called."}


def _entry_text(item: Any) -> str | None:
    d = item.model_dump() if hasattr(item, "model_dump") else (item if isinstance(item, dict) else {"text": str(item)})
    if d.get("source") == "system":  # "memory still warming up" markers are not facts
        return None
    for key in ("text", "content", "answer"):
        v = d.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _field(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def stage_rows(result: Any) -> list[dict[str, Any]]:
    """Cognee's `ImproveResult` (or the dict a remote server returned) as [{stage, status, reason}], in its order."""
    rows = []
    for st in _field(result, "stages") or []:
        counts = _field(st, "counts") or {}
        why = _field(st, "reason") or _field(st, "error") or (", ".join(f"{k}={v}" for k, v in counts.items()) if counts else None)
        rows.append({"stage": str(_field(st, "stage")), "status": str(_field(st, "status")), "reason": str(why)[:200] if why else None})
    if not rows:  # an older server answers with a legacy mapping that carries no stage detail
        rows.append({"stage": "improve", "status": str(_field(result, "status") or "unknown"), "reason": "Cognee returned no stage detail"})
    return rows


def default_ledger_path() -> Path:
    from app.config import BACKEND_DIR

    return Path(os.getenv("MEMORY_LEDGER_PATH") or BACKEND_DIR / "runs" / "memory_ledger.json")


_NO_ANSWER = re.compile(r"(?i)\b(?:could not|couldn't|can ?not|can't|unable to|did not|didn't) (?:find|answer|locate)|"
                        r"\bno (?:relevant |matching )?(?:information|answer|memor(?:y|ies)|data) (?:was |were )?(?:found|available)")


# improve() persists session Q&A into the dataset; chunk search then returns those logs ("Session ID: …\n\nQuestion: …")
_SESSION_LOG = re.compile(r"(?is)^\s*(?:session id:|question:)")


def _dataset_missing(exc: BaseException) -> bool:
    """Cognee Cloud answers 404 "Dataset(s) not found" for a user it holds no memories for yet."""
    msg = str(exc).lower()
    return "not found" in msg and "dataset" in msg


class LiveMemory:
    """Cognee Cloud, Cognee local, or the owned_parts table, by COGNEE_MODE."""

    def __init__(self, cognee: Any | None = None, *, mode: str | None = None, fallback: Any | None = None, top_k: int = 5,
                 ledger_path: Path | str | None = None) -> None:
        self._cognee = cognee
        self._mode = mode
        self._fallback = fallback
        self._ready = False
        self.top_k = top_k
        self.writes = 0
        # The ledger of facts this app wrote. An injected module (tests) keeps it in memory unless a path is given.
        self._ledger_path = Path(ledger_path) if ledger_path else (None if cognee is not None else default_ledger_path())
        self._ledger: dict[str, Any] | None = None

    # ------------------------------------------------------------------ the ledger (our own record of what we wrote)

    def _book(self) -> dict[str, Any]:
        if self._ledger is None:
            self._ledger = {"facts": {}, "improve": {}}
            if self._ledger_path is not None and self._ledger_path.is_file():
                try:
                    got = json.loads(self._ledger_path.read_text(encoding="utf-8"))
                    self._ledger = {"facts": dict(got.get("facts") or {}), "improve": dict(got.get("improve") or {})}
                except (OSError, ValueError, AttributeError):
                    pass
        return self._ledger

    def _save(self) -> None:
        if self._ledger_path is None:
            return
        try:
            self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
            self._ledger_path.write_text(json.dumps(self._book(), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        except OSError:
            pass  # the ledger is a convenience; a locked file (OneDrive) must not fail a write to memory

    @property
    def mode(self) -> str:
        m = (self._mode or os.getenv("COGNEE_MODE") or "cloud").strip().lower()
        if m not in ("cloud", "local", "off"):
            raise CogneeConfigError(f"COGNEE_MODE must be cloud, local or off, got {m!r}")
        return m

    @property
    def provider(self) -> str:
        return "owned_parts" if self.mode == "off" else "cognee"

    def fallback(self) -> Any:
        if self._fallback is None:
            from app.integrations.s2 import OwnedPartsMemory

            self._fallback = OwnedPartsMemory()
        return self._fallback

    def _module(self) -> Any:
        if self._cognee is None:
            # Cognee's SDK sends usage telemetry (to prometh.ai) unless this is set; off in every mode, before the import
            os.environ.setdefault("TELEMETRY_DISABLED", "true")
            import cognee  # lazy: heavy import, and a missing SDK breaks only this service

            self._cognee = cognee
        return self._cognee

    @staticmethod
    def local_settings() -> dict[str, dict[str, Any]]:
        missing = [n for n in LOCAL_REQUIRED if not (os.getenv(n) or "").strip()]
        if missing:
            raise CogneeConfigError("COGNEE_MODE=local needs " + ", ".join(missing)
                                    + ": without BOTH the LLM and the embedding settings Cognee silently uses OpenAI")
        return {"llm": {"llm_provider": os.environ["LLM_PROVIDER"], "llm_model": os.environ["LLM_MODEL"],
                        "llm_api_key": os.environ["LLM_API_KEY"]},
                "embedding": {"embedding_provider": os.environ["EMBEDDING_PROVIDER"],
                              "embedding_model": os.environ["EMBEDDING_MODEL"],
                              "embedding_dimensions": int(os.environ["EMBEDDING_DIMENSIONS"])}}

    async def _ensure(self) -> Any:
        cg = self._module()
        if self._ready:
            return cg
        if self.mode == "cloud":
            url = (os.getenv("COGNEE_URL") or "").strip()
            if not url:
                raise CogneeConfigError("COGNEE_MODE=cloud needs COGNEE_URL (https://<tenant>.aws.cognee.ai) and COGNEE_API_KEY")
            await cg.serve(url=url, api_key=(os.getenv("COGNEE_API_KEY") or None))
        else:
            cfg = self.local_settings()
            os.environ.setdefault("TELEMETRY_DISABLED", "true")
            cg.config.set_llm_config(cfg["llm"])
            cg.config.set_embedding_config(cfg["embedding"])
        self._ready = True
        return cg

    async def remember(self, text: str, user_id: str = "demo_user", *, kind: str | None = None, source: str | None = None,
                       run_id: str | None = None) -> None:
        fact = check_fact(text)
        if self.mode == "off":
            fb = self.fallback()
            if hasattr(fb, "list_facts"):
                await fb.remember(fact, user_id, kind=kind or fact_kind(fact), source=source)
            else:  # a fallback with the two-argument Memory signature
                await fb.remember(fact, user_id)
        else:
            cg = await self._ensure()
            await cg.remember(fact, dataset_name=user_id)
            facts = self._book()["facts"].setdefault(user_id, [])
            if not any(e.get("text") == fact for e in facts):
                facts.append(ledger_entry(fact, kind=kind, source=source, run_id=run_id))
                self._save()
        self.writes += 1

    async def list_facts(self, user_id: str = "demo_user") -> list[dict[str, Any]]:
        """Off: the owned_parts rows. Cloud / local: the ledger of facts this app wrote (Cognee is not asked)."""
        if self.mode == "off":
            return await self.fallback().list_facts(user_id)
        return [{**e, "provider": "cognee", "simulated": False} for e in self._book()["facts"].get(user_id, [])]

    async def preferences(self, user_id: str = "demo_user", topic: str | None = None) -> list[dict[str, Any]]:
        """What the user chose or rejected before. Cloud / local: asked of Cognee (the answer may be paraphrased)."""
        if self.mode == "off":
            return [{"memory_text": f["text"], "provider": "owned_parts", "simulated": False}
                    for f in await self.fallback().list_facts(user_id) if is_preference(f)]
        return await self.recall(f"Which stores and offers did the user choose or reject before{' for a ' + topic if topic else ''}?", user_id)

    async def feedback(self, text: str, user_id: str = "demo_user", *, session_id: str, positive: bool = True) -> bool:
        """One user decision as a rated session turn, which `improve(session_ids=[…])` reads. False when Cognee is off."""
        fact = check_fact(text)
        if self.mode == "off":
            return False
        cg = await self._ensure()
        entry = cg.QAEntry(question=FEEDBACK_QUESTION, answer=fact, feedback_text=fact, feedback_score=5 if positive else 1)
        await cg.remember(entry, dataset_name=user_id, session_id=session_id)
        return True

    async def improve(self, user_id: str = "demo_user", *, session_ids: list[str] | None = None, run_id: str | None = None,
                      feedback: list[str] | None = None) -> dict[str, Any]:
        """One `cognee.improve()` pass over the user's dataset. Returns a `MemoryImprove` body with Cognee's own stages."""
        if self.mode == "off":
            stages = [{"stage": "improve", "status": "skipped", "reason": "COGNEE_MODE=off: the owned_parts table has no improve step"}]
        else:
            cg = await self._ensure()
            try:
                stages = stage_rows(await cg.improve(user_id, session_ids=list(session_ids or [])))
            except Exception as exc:  # the panel shows the failed pass rather than nothing
                stages = [{"stage": "improve", "status": "errored", "reason": f"{type(exc).__name__}: {str(exc)[:120]}"}]
        out = {"at": now_iso(), "run_id": run_id, "feedback": list(feedback or []), "stages": stages, "provider": self.provider, "simulated": False}
        self._book()["improve"][user_id] = out
        self._save()
        return out

    def last_improve(self, user_id: str = "demo_user") -> dict[str, Any] | None:
        return self._book()["improve"].get(user_id)

    async def forget(self, user_id: str = "demo_user", scope: str = "everything") -> dict[str, Any]:
        """everything: `cognee.forget(dataset=user_id)` (off: the user's owned_parts rows). preferences: only where rows
        can be told apart (off). Cognee forgets by dataset or data id, and we keep no data ids, so that scope is refused."""
        _check_scope(scope)
        book = self._book()
        if self.mode == "off":
            n = await self.fallback().forget(user_id, scope)
            book["improve"].pop(user_id, None)
            self._save()
            return {"scope": scope, "forgotten": n, "provider": "owned_parts", "simulated": False,
                    "detail": f"Deleted {n} row{'s' if n != 1 else ''} from your owned-parts list."}
        if scope == "preferences":
            return {"scope": scope, "forgotten": 0, "provider": "cognee", "simulated": False,
                    "detail": "Nothing was forgotten: Cognee forgets a whole dataset, not one kind of fact. Use Forget everything."}
        cg = await self._ensure()
        try:
            await cg.forget(dataset=user_id)
        except Exception as exc:
            if not _dataset_missing(exc):  # nothing stored yet: already forgotten
                raise
        n = len(book["facts"].pop(user_id, []))
        book["improve"].pop(user_id, None)
        self._save()
        return {"scope": scope, "forgotten": None, "provider": "cognee", "simulated": False,
                "detail": f"Cognee removed your dataset (it does not report a count). {n} fact{'s' if n != 1 else ''} this app had written are off its list."}

    async def recall(self, query: str, user_id: str = "demo_user") -> list[dict[str, Any]]:
        if self.mode == "off":
            return await self.fallback().recall(query, user_id)
        cg = await self._ensure()
        # CHUNKS: the stored facts word for word, by vector similarity, with no LLM answer. Measured on Cognee Cloud:
        # ~1 s against ~4.5 s, and the default answer mode can echo the question ("Got it: Frame."), which a
        # "do you own this?" check must never read as a memory.
        kind = getattr(getattr(cg, "SearchType", None), "CHUNKS", None)
        extra = {"query_type": kind} if kind is not None else {}
        try:
            got = await cg.recall(query_text=query, datasets=[user_id], top_k=self.top_k, **extra)
        except Exception as exc:
            if _dataset_missing(exc):  # a user Cognee has no memories for yet: nothing to recall, not a failure
                return []
            raise
        out, seen = [], set()
        for item in got or []:
            text = _entry_text(item)
            if text and (_NO_ANSWER.search(text) or _SESSION_LOG.match(text)):
                continue  # "I could not find an answer…" and Cognee's own session Q&A logs are not memories
            if text and text not in seen:
                seen.add(text)
                out.append({"memory_text": text, "provider": "cognee", "simulated": False})
        return out

    async def seed(self, facts: list[str] | None = None, user_id: str = "demo_user") -> int:
        """Preload the seed memories (remember is slow: run scripts/seed_memory.py before the demo)."""
        n = 0
        for f in facts or SEED_MEMORIES:
            await self.remember(f, user_id)
            n += 1
        return n


async def memory_body(user_id: str = "demo_user") -> dict[str, Any]:
    """GET /api/memory (`MemoryResponse`). Mock mode answers from `MockMemory`: no network."""
    from app import registry

    mem = registry.get("cognee")
    facts = await mem.list_facts(user_id)
    return {"facts": [{k: f.get(k) for k in ("text", "kind", "source", "run_id", "at", "provider", "simulated")} for f in facts],
            "mode": mem.mode, "provider": mem.provider, "last_improve": mem.last_improve(user_id),
            "simulated": isinstance(mem, MockMemory)}


async def forget_body(scope: str = "everything", user_id: str = "demo_user") -> dict[str, Any]:
    """POST /api/memory/forget (`ForgetResponse`)."""
    from app import registry

    return await registry.get("cognee").forget(user_id, scope)
