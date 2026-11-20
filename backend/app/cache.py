"""Record/replay cache around every external call (PLAN §3.11). Owner: B.

Key: sha256(tool + canonical_json(args)). One JSON file per key in cache/<key>.json:
    {"key", "tool", "args", "seen_at", "recorded_in", "value"}

Modes (DEMO_MODE, read at call time):
- live    cache first; on a miss, fetch and write the entry (cache-first from the first call: SerpAPI allows
          50 searches an hour for the whole team, so a restart must not spend them again).
- record  the same, and every key used is appended to cache/_recording.jsonl so scripts/record_hero.py can
          list what a hero run needs. Entries keep their ORIGINAL seen_at.
- replay  never touches the network: a miss raises ReplayMiss.
- mock    services are mocks and normally never get here; if one does, entries stay in memory only.

`bypass=True` is for the cart price refresh (the one call that skips the cache read, PLAN §3.11) and for
calls that must never be reused live (creating a Shopify cart, Stripe test objects). In replay it still
reads the recording, because replay never touches the network.

Args must never contain a key or token: callers pass secrets outside `args`. Args are also redacted on
write as a second line of defence.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, get_settings
from app.stores.base import _atomic_write, canonical, now_iso, redact, sha256_hex

CACHE_DIR: Path = Path(os.getenv("B2C_CACHE_DIR") or (BACKEND_DIR / "cache"))
RECORDING_LOG = "_recording.jsonl"

_memory: dict[str, Entry] = {}
_lock = threading.Lock()


class ReplayMiss(RuntimeError):
    """Replay mode asked for a call that was never recorded. Replay never touches the network."""


@dataclass(frozen=True)
class Entry:
    key: str
    tool: str
    value: Any
    seen_at: str
    hit: bool  # True when the value came from the cache (memory, disk or a recording)


def cache_key(tool: str, args: dict[str, Any]) -> str:
    """sha256(tool + canonical_json(args))"""
    return sha256_hex(tool + canonical(args))


def mode() -> str:
    return get_settings().demo_mode


def _path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def read(key: str) -> Entry | None:
    """An entry from memory or disk, or None."""
    with _lock:
        if key in _memory:
            e = _memory[key]
            return Entry(e.key, e.tool, e.value, e.seen_at, True)
    path = _path(key)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = Entry(key, raw.get("tool", ""), raw.get("value"), raw.get("seen_at") or now_iso(), True)
    with _lock:
        _memory[key] = entry
    return entry


def write(key: str, tool: str, args: dict[str, Any], value: Any, seen_at: str, *, persist: bool = True) -> Entry:
    entry = Entry(key, tool, value, seen_at, False)
    with _lock:
        _memory[key] = entry
    if persist:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        body = {"key": key, "tool": tool, "args": redact(args), "seen_at": seen_at, "recorded_in": mode(), "value": value}
        text = json.dumps(body, ensure_ascii=False, sort_keys=True, default=str)
        if len(text) < 200_000:  # small entries stay readable in a diff; the 7.8 MB Adafruit catalog stays compact
            text = json.dumps(body, ensure_ascii=False, indent=1, sort_keys=True, default=str)
        _atomic_write(_path(key), text)
    return entry


def _log_recording(entry: Entry) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"key": entry.key, "tool": entry.tool, "seen_at": entry.seen_at, "logged_at": now_iso()}, ensure_ascii=False)
    with _lock, open(CACHE_DIR / RECORDING_LOG, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


async def cached_entry(tool: str, args: dict[str, Any], fetch: Callable[[], Awaitable[Any]], *, bypass: bool = False) -> Entry:
    """The cache around one external call, with its seen_at and whether it was a hit."""
    key = cache_key(tool, args)
    m = mode()
    if m == "replay":
        entry = read(key)
        if entry is None:
            raise ReplayMiss(f"replay: no recording for {tool} (key {key[:12]}). Record it with DEMO_MODE=record.")
        return entry
    if not bypass:
        entry = read(key)
        if entry is not None:
            if m == "record":
                _log_recording(entry)
            return entry
    value = await fetch()
    entry = write(key, tool, args, value, now_iso(), persist=m in ("live", "record"))
    if m == "record":
        _log_recording(entry)
    return entry


async def cached(tool: str, args: dict[str, Any], fetch: Callable[[], Awaitable[Any]], *, bypass: bool = False) -> Any:
    """live | record | replay behaviour; returns the value only (see `cached_entry` for seen_at)."""
    return (await cached_entry(tool, args, fetch, bypass=bypass)).value


def recorded_keys() -> list[dict[str, Any]]:
    """Every key logged in record mode (scripts/record_hero.py)."""
    path = CACHE_DIR / RECORDING_LOG
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clear_memory() -> None:
    """Forget the in-memory layer (tests; a new recording session)."""
    with _lock:
        _memory.clear()
