"""Match BOM lines against what the user already owns (Cognee, or the owned_parts table). Owner: A.

PLAN §3.6 `recall_owned`. Memory is D's (`registry.get("cognee")`); this module only decides whether a
recalled memory is really about the line, so a loose recall never removes a part by mistake.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["recall_owned", "match_memory", "recall_for_lines"]

_STOP = {"owns", "own", "have", "has", "the", "and", "two", "three", "four", "one", "set", "pcs", "pieces", "with", "for", "some",
         "prefers", "sellers", "data", "kit", "parts", "part", "board", "module", "supply", "control", "power", "table"}
_OWN = re.compile(r"(?i)\b(owns?|ha(s|ve)|already (have|has|own)|bought)\b")


def _stems(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9-]{2,}", text.lower()):
        w = w[:-1] if w.endswith("s") and len(w) > 4 else w
        if w not in _STOP and not w.isdigit():
            out.add(w)
    return out


def match_memory(name: str, memory_text: str) -> bool:
    """True when the memory says the user owns something that names this line."""
    if not _OWN.search(memory_text):
        return False
    return bool(_stems(name) & _stems(memory_text))


RECALL_CONCURRENCY = 6


async def recall_for_lines(lines: list[tuple[str, str]], *, memory: Any = None, user_id: str = "demo_user") -> tuple[dict[str, dict[str, Any]], str | None]:
    """`lines` is [(bom_line_id, name)]. Returns ({bom_line_id: {memory_text, provider, simulated}}, error)."""
    if memory is None:
        from app import registry

        memory = registry.get("cognee")
    import asyncio

    out: dict[str, dict[str, Any]] = {}
    sem = asyncio.Semaphore(RECALL_CONCURRENCY)

    async def ask(name: str) -> Any:
        async with sem:
            return await memory.recall(name, user_id)

    # one question per line, asked together: a live memory answers in seconds per question, so in turn they add up
    answers = await asyncio.gather(*(ask(name) for _, name in lines), return_exceptions=True)
    for (bid, name), hits in zip(lines, answers):
        if isinstance(hits, NotImplementedError):
            return out, "memory is not connected"
        if isinstance(hits, BaseException):
            return out, f"{type(hits).__name__}: {str(hits)[:100]}"
        for h in hits or []:
            text = h.get("memory_text") or h.get("text") or "" if isinstance(h, dict) else str(h)
            if text and match_memory(name, text):
                provider = h.get("provider", "cognee") if isinstance(h, dict) else "cognee"
                out[bid] = {"memory_text": text, "provider": provider if provider in ("cognee", "owned_parts") else "cognee",
                            "simulated": bool(isinstance(h, dict) and h.get("simulated"))}
                break
    return out, None


async def recall_owned(run_id: str, bom_line_ids: list[str]) -> dict[str, str]:
    """bom_line_id -> memory text, for a run (through the tool wrapper, so it is logged)."""
    from app import runstate
    from app.agent import tools

    await tools.call_tool(run_id, "recall_owned", {"bom_line_ids": bom_line_ids})
    run = runstate.get(run_id)
    return {bid: run.owned[bid].memory_text for bid in bom_line_ids if bid in run.owned}
