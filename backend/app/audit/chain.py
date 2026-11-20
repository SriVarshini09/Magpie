"""Hash chain (PLAN §3.7, §3.14). Owner: D.

The wire format is fixed (the fixture builder and the tests depend on it):

    hash = "sha256:" + sha256(prev_hash + canonical_json(record without "hash"))
    canonical JSON: sorted keys, no whitespace, UTF-8
    the first record's prev_hash is GENESIS ("sha256:" + 64 zeros)

`append` is the only way a record enters a run's chain. The chain is append-only: records are
stored as JSON round-tripped copies, callers get their own copy back, and nothing here edits or
deletes a record. Each append also goes to:
  - the SingleStore `audit_events` table (SQLite with no S2_URL) when the singlestore service is live,
  - `runs/<run_id>/chain.jsonl` when persistence is on (on by default outside DEMO_MODE=mock).
A sink that fails never breaks the agent: the error is counted in `SINK_ERRORS` and the in-memory
chain stays the source of truth for the running process.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, get_args

GENESIS = "sha256:" + "0" * 64
RESERVED = ("run_id", "seq", "kind", "prev_hash", "hash")
_RUN_ID = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def record_hash(record: dict[str, Any], prev_hash: str) -> str:
    body = {k: v for k, v in record.items() if k != "hash"}
    return "sha256:" + sha256_hex(prev_hash + canonical_json(body))


def recompute(records: list[dict[str, Any]]) -> tuple[bool, int | None, str]:
    """Return (ok, broken_at_seq, head_hash) for a list of chain records."""
    prev = GENESIS
    for rec in records:
        if rec.get("prev_hash") != prev or rec.get("hash") != record_hash(rec, prev):
            return False, rec.get("seq"), prev
        prev = rec["hash"]
    return True, None, prev


# --------------------------------------------------------------------------- helpers


def now_iso() -> str:
    """Wall-clock time with the local offset, e.g. 2026-11-20T13:04:35-08:00."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def jsonable(obj: Any) -> Any:
    """Plain JSON values: pydantic models are dumped (by alias), tuples become lists."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", by_alias=True, exclude_none=True)
    return json.loads(json.dumps(obj, default=_default, ensure_ascii=False))


def _default(o: Any) -> Any:
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    if isinstance(o, Path):
        return o.as_posix()
    if isinstance(o, bytes):
        return {"sha256": sha256_hex(o), "bytes": len(o)}  # never inline raw bytes into the chain
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def under_pytest() -> bool:
    """True inside a pytest run: D's runtime files then go to a temp folder, never into backend/."""
    return bool(os.getenv("PYTEST_CURRENT_TEST"))


def runtime_dir(name: str) -> Path:
    """`backend/<name>` normally; a per-process temp folder under pytest (tests must not write into the repo)."""
    if under_pytest():
        return Path(tempfile.gettempdir()) / f"b2c-pytest-{os.getpid()}" / name
    from app.config import BACKEND_DIR

    return BACKEND_DIR / name


def check_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not _RUN_ID.match(run_id):
        raise ValueError(f"bad run_id {run_id!r}")
    return run_id


def _record_kinds() -> frozenset[str]:
    from app.models import RecordKind

    return frozenset(get_args(RecordKind))


# --------------------------------------------------------------------------- the store


class ChainStore:
    """In-memory chains, one list per run, guarded by one lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, list[dict[str, Any]]] = {}

    def append(self, run_id: str, kind: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        check_run_id(run_id)
        if kind not in _record_kinds():
            raise ValueError(f"unknown record kind {kind!r} (models.RecordKind)")
        payload = jsonable(body or {})
        if not isinstance(payload, dict):
            raise TypeError("a record body must be a JSON object")
        with self._lock:
            chain = self._runs.setdefault(run_id, [])
            prev = chain[-1]["hash"] if chain else GENESIS
            rec = {k: v for k, v in payload.items() if k not in RESERVED}
            rec.update(run_id=run_id, seq=len(chain) + 1, kind=kind, prev_hash=prev)
            if not rec.get("ts"):
                rec["ts"] = now_iso()
            rec = json.loads(canonical_json(rec))  # exactly what any reader will hash
            rec["hash"] = record_hash(rec, prev)
            chain.append(rec)
        return json.loads(json.dumps(rec))

    def records(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return json.loads(json.dumps(self._runs.get(run_id, [])))

    def head(self, run_id: str) -> str:
        with self._lock:
            chain = self._runs.get(run_id)
            return chain[-1]["hash"] if chain else GENESIS

    def has(self, run_id: str) -> bool:
        with self._lock:
            return bool(self._runs.get(run_id))

    def load(self, run_id: str, records: list[dict[str, Any]]) -> tuple[bool, int | None, str]:
        """Restore a run's chain (after a restart, from disk or SingleStore). Refuses a broken chain."""
        check_run_id(run_id)
        ok, broken_at, head = recompute(records)
        if not ok:
            raise ValueError(f"chain for {run_id} is broken at seq {broken_at}; not loaded")
        with self._lock:
            if self._runs.get(run_id):
                raise ValueError(f"chain for {run_id} already exists; append-only")
            self._runs[run_id] = json.loads(json.dumps(records))
        return ok, broken_at, head

    def reset(self, run_id: str | None = None) -> None:
        """Tests only: forget one run or all runs (the chain itself is never edited)."""
        with self._lock:
            if run_id is None:
                self._runs.clear()
            else:
                self._runs.pop(run_id, None)


STORE = ChainStore()
SINK_ERRORS: dict[str, int] = {}
_PERSIST: dict[str, Any] = {"enabled": None, "dir": None}


def configure(*, persist: bool | None = None, runs_dir: str | Path | None = None) -> None:
    """Turn disk persistence on or off (None = default: on unless DEMO_MODE=mock) and pick the folder."""
    _PERSIST["enabled"] = persist
    _PERSIST["dir"] = Path(runs_dir) if runs_dir is not None else None


def runs_dir() -> Path:
    if _PERSIST["dir"] is not None:
        return _PERSIST["dir"]
    return runtime_dir("runs")


def _persist_on() -> bool:
    if _PERSIST["enabled"] is not None:
        return bool(_PERSIST["enabled"])
    try:
        from app.config import get_settings

        return not get_settings().is_mock
    except Exception:
        return False


def chain_path(run_id: str) -> Path:
    return runs_dir() / check_run_id(run_id) / "chain.jsonl"


def _sink(rec: dict[str, Any]) -> None:
    if _persist_on():
        try:
            path = chain_path(rec["run_id"])
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(canonical_json(rec) + "\n")
        except OSError as exc:
            SINK_ERRORS["disk"] = SINK_ERRORS.get("disk", 0) + 1
            SINK_ERRORS["disk_last"] = str(exc)[:200]  # type: ignore[assignment]
    try:
        from app import registry

        if registry.impl_mode("singlestore") == "live":
            registry.get("singlestore").insert_audit_sync(rec)
    except Exception as exc:  # the sink must never break the agent
        SINK_ERRORS["singlestore"] = SINK_ERRORS.get("singlestore", 0) + 1
        SINK_ERRORS["singlestore_last"] = f"{type(exc).__name__}: {str(exc)[:160]}"  # type: ignore[assignment]


# --------------------------------------------------------------------------- public API


def append(run_id: str, kind: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append one record to the run's chain and to SingleStore `audit_events`. Returns the record.

    `body` keys `run_id`, `seq`, `kind`, `prev_hash` and `hash` are set here and ignored if given;
    `ts` is kept when the caller gives it, else it is now.
    """
    rec = STORE.append(run_id, kind, body)
    _sink(rec)
    return rec


def records(run_id: str) -> list[dict[str, Any]]:
    """The run's chain (in memory; see `load_records` for disk and SingleStore)."""
    return STORE.records(run_id)


def head(run_id: str) -> str:
    return STORE.head(run_id)


def read_disk(run_id: str) -> list[dict[str, Any]]:
    path = chain_path(run_id)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_records(run_id: str) -> tuple[list[dict[str, Any]], str]:
    """Records for Verify: (records, where). Order: SingleStore when live, memory, then disk.

    PLAN §7: "Verify reads the chain from SingleStore". When SingleStore is not live the
    in-memory chain (or its disk copy after a restart) is what we have.
    """
    check_run_id(run_id)
    try:
        from app import registry

        if registry.impl_mode("singlestore") == "live":
            got = registry.get("singlestore").audit_events_sync(run_id)
            if got:
                return got, registry.get("singlestore").backend_name
    except Exception:
        pass
    mem = STORE.records(run_id)
    if mem:
        return mem, "memory"
    disk = read_disk(run_id)
    return disk, ("disk" if disk else "none")
