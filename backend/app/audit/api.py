"""Route bodies for D's endpoints (PLAN §4.2), for A to call from `app/main.py` in non-mock modes. Owner: D.

    GET /api/runs/{id}/receipt          -> receipt_body(run_id)
    GET /api/runs/{id}/verify           -> verify_body(run_id)
    GET /api/kb/search?q=               -> await kb_search_body(q)
    GET /api/runs/{id}/prices/{line}    -> await prices_body(run_id, bom_line_id)
    GET /api/data/stats                 -> data_stats_body()        (requested new route, Data drawer)

Each returns a dict that validates against its response model, or raises HTTPException 404 with the
`ApiError` shape. A may pass the run's own mandates and records to `receipt_body` (they win over what D
recorded at signing time).
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app import registry
from app.audit import verify as verify_mod


def _not_found(run_id: str, why: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "run_not_found", "message": f"{run_id}: {why}", "bom_line_ids": []})


def receipt_body(run_id: str, **overrides: Any) -> dict[str, Any]:
    try:
        rec = verify_mod.receipt(run_id, **overrides)
    except (LookupError, ValueError) as exc:
        raise _not_found(run_id, str(exc)) from exc
    return rec.model_dump(mode="json", by_alias=True, exclude_none=True)


def verify_body(run_id: str, **overrides: Any) -> dict[str, Any]:
    try:
        res = verify_mod.verify_run(run_id, **overrides)
    except (LookupError, ValueError) as exc:
        raise _not_found(run_id, str(exc)) from exc
    return res.model_dump(mode="json")


def verify_detail_body(run_id: str, **overrides: Any) -> dict[str, Any]:
    """Verify with the per-check list (`checks`), for the CLI and a future UI field."""
    try:
        return verify_mod.verify_run_detail(run_id, **overrides)
    except (LookupError, ValueError) as exc:
        raise _not_found(run_id, str(exc)) from exc


async def kb_search_body(q: str, kind: str | None = None) -> dict[str, Any]:
    res = await registry.get("singlestore").hybrid_search(q, kind=kind)
    return res.model_dump(mode="json")


async def prices_body(run_id: str, bom_line_id: str) -> dict[str, Any]:
    res = await registry.get("singlestore").prices(run_id, bom_line_id)
    return res.model_dump(mode="json")


def data_stats_body() -> dict[str, Any]:
    return registry.get("singlestore").stats()
