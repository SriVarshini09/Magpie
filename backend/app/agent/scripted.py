"""Scripted run: the same tools in a fixed order, with no model in the loop (PLAN §6.5 fallback). Owner: A.

It goes through the same wrapper (`tools.call_tool`), so the guard, the chain and the timeline are the
same as in the model-driven loop. Each step is skipped when its stage is already done, so it also
finishes a run the model loop left half-way.
"""

from __future__ import annotations

from typing import Any

from app import runstate
from app.agent import tools

__all__ = ["run_scripted"]

MAX_FIX_ROUNDS = 3


async def _search_and_rank(run_id: str, ids: list[str]) -> None:
    for bid in ids:
        res = await tools.call_tool(run_id, "search_offers", {"bom_line_id": bid})
        if not res.get("error"):
            await tools.call_tool(run_id, "rank_offers", {"bom_line_id": bid})


async def run_scripted(run_id: str, tier: str = "cheapest") -> dict[str, Any]:
    """Fixed tool order; stops at stage_cart. Returns {"ok": bool, "error"?: str}."""
    run = runstate.get(run_id)
    scope = run.mandate.scope

    def fail(msg: str) -> dict[str, Any]:
        run.status = "error"
        run.emit("error", msg[:140], "error", detail=msg if len(msg) > 140 else None)
        runstate.save_run(run)
        return {"ok": False, "error": msg}

    if scope.inputs.source_url and "source" not in run.stages:
        res = await tools.call_tool(run_id, "ingest_source", {"url": scope.inputs.source_url})
        if res.get("error"):
            return fail(f"Could not read the source: {res.get('message')}")
    if "template" not in run.stages:
        await tools.call_tool(run_id, "load_template", {"build_type": scope.build_type})
    if run.images and "photo" not in run.stages:
        await tools.call_tool(run_id, "identify_parts", {"image_id": next(iter(run.images))})  # a refusal (photo not shared) is logged; the run goes on
    if not scope.inputs.source_url and scope.reference_search and run.reference is None and not getattr(run, "reference_searches", 0) and "bom" not in run.stages:
        await tools.call_tool(run_id, "find_reference_design", {"query": scope.goal})
    if "bom" not in run.stages:
        res = await tools.call_tool(run_id, "extract_bom", {})
        if res.get("error"):
            return fail(f"Could not build the parts list: {res.get('message')}")
        if not run.bom:
            return fail("No parts could be listed from this request. Paste the parts list as text.")
    for ln in run.bom:
        if f"resolved:{ln.bom_line_id}" not in run.stages:
            await tools.call_tool(run_id, "resolve_part", {"bom_line_id": ln.bom_line_id})
    if "owned" not in run.stages:
        await tools.call_tool(run_id, "recall_owned", {"bom_line_ids": [ln.bom_line_id for ln in run.bom]})
    await tools.call_tool(run_id, "check_compatibility", {})  # BOM level: a fix here changes what we search for
    plan_id = None
    for _ in range(MAX_FIX_ROUNDS):
        todo = [ln.bom_line_id for ln in tools.purchasable(run) if f"ranked:{ln.bom_line_id}" not in run.stages]
        await _search_and_rank(run_id, todo)
        res = await tools.call_tool(run_id, "optimize_cart", {"tier": tier})
        if res.get("error"):
            return fail(f"Could not plan the cart: {res.get('message')}")
        plan_id = res["plan"]["plan_id"]
        chk = await tools.call_tool(run_id, "check_compatibility", {})
        if not chk.get("search_again"):
            break
    if plan_id is None:
        return fail("Could not plan the cart")
    await tools.call_tool(run_id, "stage_cart", {"plan_id": run.plans[run.active_tier].plan_id})
    return {"ok": True}
