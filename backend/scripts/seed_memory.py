"""Preload the seed memories (Cognee `remember` is slow; run this before the demo) (PLAN §3.15). Owner: D.

    cd backend && uv run python scripts/seed_memory.py                    # COGNEE_MODE from .env (cloud | local | off)
    uv run python scripts/seed_memory.py --preset electronics_mcu        # also that preset's seed_memories
    uv run python scripts/seed_memory.py --dry-run                       # list what would be remembered

Cloud needs COGNEE_URL and COGNEE_API_KEY. Local needs BOTH the LLM_* and the EMBEDDING_* settings (otherwise Cognee
silently uses OpenAI; the client refuses). Off writes the owned_parts table (SingleStore, or SQLite locally).
Only the PLAN's seed facts and the presets' own seed_memories are written: things the demo user "said".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.integrations.cognee_mem import SEED_MEMORIES, LiveMemory  # noqa: E402


def facts_for(presets: list[str]) -> list[str]:
    facts = list(SEED_MEMORIES)
    for name in presets:
        path = BACKEND / "data" / "projects" / name / "preset.json"
        for f in json.loads(path.read_text(encoding="utf-8")).get("seed_memories", []):
            if f not in facts:
                facts.append(f)
    return facts


def main(argv: list[str] | None = None, memory: object | None = None) -> list[str]:
    ap = argparse.ArgumentParser(description="Remember the demo user's seed facts.")
    ap.add_argument("--preset", action="append", default=[], help="data/projects/<name>/preset.json to add")
    ap.add_argument("--user", default="demo_user")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    facts = facts_for(args.preset)
    if args.dry_run:
        for f in facts:
            print(f"would remember: {f}")
        return facts
    if memory is None:
        from app.config import get_settings

        get_settings()  # loads .env (COGNEE_URL, COGNEE_API_KEY, COGNEE_MODE) before the client reads them
    mem = memory or LiveMemory()

    async def go() -> None:
        for f in facts:
            await mem.remember(f, args.user)  # type: ignore[attr-defined]
            print(f"remembered ({getattr(mem, 'provider', 'cognee')}): {f}")

    asyncio.run(go())
    return facts


if __name__ == "__main__":
    main()
