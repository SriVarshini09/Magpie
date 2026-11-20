"""Warm the SIE models so the cold-start 503 PROVISIONING happens here, not on stage (PLAN §3.15). Owner: D.

    cd backend && uv run python scripts/warm_sie.py          # needs SIE_API_KEY (and SIE_BASE_URL unless Serverless)
                                                            # and SIE_EMBED_MODEL / SIE_RERANK_MODEL / SIE_EXTRACT_MODEL

One small call per model: encode, score, extract and grounding-dino-base detection. Run it at 11:15 and again
at 4:45. A model whose name is not set is reported and skipped; nothing is retried forever.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.integrations.sie import LiveSIE  # noqa: E402


def main(argv: list[str] | None = None, client: LiveSIE | None = None) -> dict:
    sie = client or LiveSIE()
    if not sie.configured():
        print("SIE is not configured: set SIE_API_KEY (and SIE_BASE_URL unless you use SIE Serverless)")
        return {}

    async def go() -> dict:
        try:
            return await sie.warm()
        finally:
            await sie.aclose()

    out = asyncio.run(go())
    for step, r in out.items():
        print(f"{step:8} " + (f"ok in {r['ms']} ms" if r.get("ok") else f"FAILED: {r.get('error')}"))
    return out


if __name__ == "__main__":
    main()
