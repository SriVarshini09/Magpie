"""Fixture loader. Fixtures are built by scripts/build_fixtures.py; all of them are mock data."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from typing import Any

from app.config import FIXTURES_DIR

MOCK_LABEL = {"source_api": "mock", "simulated": True}


@lru_cache(maxsize=None)
def _read(name: str) -> Any:
    path = (FIXTURES_DIR / name).resolve()
    if FIXTURES_DIR.resolve() not in path.parents or not path.is_file():
        raise FileNotFoundError(name)
    text = path.read_text(encoding="utf-8")
    if name.endswith(".jsonl"):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def load(name: str) -> Any:
    """Return a fresh copy of one fixture (run_so101.json, events_drone.jsonl, ...)."""
    return copy.deepcopy(_read(name))


def names() -> list[str]:
    return sorted(p.name for p in FIXTURES_DIR.glob("*.json*"))
