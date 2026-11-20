"""Live handlers for A's routes (PLAN §4.2). Owner: A. `app/main.py` calls these outside mock mode.

UI actions (assumptions, owned, variant, replan, cart edit, approve) are human actions: they go through
the same guard, and each one that changes the run appends a record to the chain.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from app import registry, runstate
from app.agent import guard, loop, ports, tools
from app.audit.chain import canonical_json, sha256_hex
from app.config import DATA_DIR, get_settings
from app.intake import clarify, classify
from app.models import (
    ApproveRequest, ApproveResponse, AssumptionRequest, CartEditRequest, ClosedMandate, CreateRunRequest, CreateRunResponse,
    Intake, MandateActions, OpenMandate, PartPanel, ProjectSample, ReplanResponse, RunState, UniversalCart,
)
from app.pipeline import compat, optimize, panel, rank
from app.runstate import Run

RUN_INLINE = False  # tests set this: the agent runs inside POST /api/runs instead of as a background task
ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "airbyte_github": "AIRBYTE_GITHUB_TOKEN", "singlestore": "S2_URL", "sie": "SIE_BASE_URL",
            "cognee": "COGNEE_API_KEY", "amplitude": "AMPLITUDE_AI_API_KEY", "statsig": "STATSIG_SERVER_SECRET", "keenable": "KEENABLE_API_KEY",
            "exa_airbyte": "EXA_API_KEY", "github_search": "AIRBYTE_GITHUB_TOKEN", "stripe": "STRIPE_SECRET_KEY", "serpapi": "SERPAPI_KEY",
            "digikey": "DIGIKEY_CLIENT_ID"}
NO_KEY_NEEDED = {"shopify_ucp", "adafruit", "magento", "cartlinks"}
# Live classes that keep working without their key, on a keyless fallback that serves real data:
# SingleStore -> SQLite (same tables, seeded from data/kb); the GitHub source -> raw fetch of public READMEs.
KEYLESS_FALLBACK = {"singlestore", "airbyte_github"}


def err(status: int, error: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": error, "message": message, **extra})


def run_or_404(run_id: str) -> Run:
    try:
        return runstate.get(run_id)
    except runstate.RunNotFound:
        # fixture runs (r_mock_*) exist only in mock mode: a live backend never serves them
        raise err(404, "run_not_found", f"No run {run_id}") from None


def line_or_404(run: Run, bom_line_id: str) -> Any:
    ln = run.line(bom_line_id)
    if ln is None:
        raise err(404, "line_not_found", f"No BOM line {bom_line_id} in {run.run_id}")
    return ln


def _refuse(run: Run, r: Any, status: int, error: str, message: str, **extra: Any) -> HTTPException:
    run.refuse(r.model_dump(), tools._refusal_title(run, r), bom_line_id=extra.pop("bom_line_id", None))
    return err(status, error, message, refusal=r.model_dump(), **extra)


# ---------------------------------------------------------------------------- health, projects


def health_states() -> tuple[dict[str, str], dict[str, str]]:
    """({integration: state}, {store: state}). `ok` means configured (a key is present), not "answered a ping"."""
    integ, stores = {}, {}
    for name, mode in registry.modes().items():
        if mode == "mock":
            state = "mock"
        elif name in NO_KEY_NEEDED:
            state = "off" if _is_stub(name) else "ok"
        elif any(os.getenv(k) for k in (("SIE_API_KEY", "SIE_BASE_URL") if name == "sie" else (ENV_KEYS.get(name, "-"),))):  # SIE Serverless needs only the key
            state = "fallback" if name == "singlestore" and _s2_on_sqlite() else "ok"
        else:
            state = "fallback" if name in KEYLESS_FALLBACK else "off"
        (stores if registry.SERVICES[name].kind == "store" else integ)[name] = state
    return integ, stores


def _s2_on_sqlite() -> bool:
    """S2_URL is set but the store already fell back to SQLite (unreachable). Never opens a connection itself."""
    try:
        opened = getattr(registry.get("singlestore"), "_backend", None)
        return getattr(opened, "name", None) == "sqlite"
    except Exception:
        return False


def _is_stub(name: str) -> bool:
    """A live class that still raises its TODO has nothing behind it yet."""
    spec = registry.SERVICES[name]
    try:
        import importlib
        import inspect

        src = inspect.getsource(getattr(importlib.import_module(spec.module), spec.live_cls))
        return "raise todo(" in src
    except Exception:
        return True


def projects() -> list[ProjectSample]:
    out = []
    for path in sorted((DATA_DIR / "projects").glob("*/preset.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw = raw.get("sample") if isinstance(raw.get("sample"), dict) else raw  # D keeps the chip under "sample"
            preset = dict(raw.get("mandate_preset") or {})
            if preset.get("allowed_merchants"):
                raw = {**raw, "mandate_preset": {**preset, "allowed_merchants": classify.with_simulated_store(list(preset["allowed_merchants"]))}}
            out.append(ProjectSample.model_validate({k: v for k, v in raw.items() if k in ProjectSample.model_fields}))
        except Exception:
            continue
    if not out:
        raise err(501, "not_implemented", "No project presets yet", todo="TODO(D) — PLAN §13.1: data/projects/<build_type>/preset.json")
    return out


# ---------------------------------------------------------------------------- intake


async def intake(text: str | None, files: list[tuple[str, str | None, bytes]], run_id: str | None) -> Intake:
    try:
        res = await classify.classify(text, files, run_id)
    except classify.IntakeError as exc:
        raise err(exc.status, exc.error, exc.message, **({"refusal": exc.refusal} if exc.refusal else {})) from exc
    kinds = [k for k, v in (("text", res.inputs.text and not res.inputs.source_url), ("link", res.inputs.source_url), ("photo", res.inputs.images)) if v]
    ports.track("track_event", res.intake_id, "request_submitted", {"input_kinds": ",".join(kinds)})
    return res


def answers(intake_id: str, values: dict[str, str], build_type: str | None, skip_defaults: bool | None) -> Intake:
    try:
        return clarify.apply_answers(intake_id, values, build_type, skip_defaults)
    except classify.IntakeError as exc:
        raise err(exc.status, exc.error, exc.message) from exc


# ---------------------------------------------------------------------------- runs


def _stores_word_map(run: Run | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        from app.stores import registry as store_registry

        for s in store_registry.load_registry()["stores"]:
            out[s["store_id"].lower()] = s["store_id"]
            out[str(s.get("display_name") or s["store_id"]).lower()] = s["store_id"]
    except Exception:
        pass
    for meta in (run.line_meta.values() if run else []):
        for lk in meta.get("links") or []:
            host = guard.store_of_host(lk["url"])
            sid, _ = tools.store_for_host(lk["url"])
            out.setdefault(host.split(".")[0], sid)
    for extra in ("alibaba", "aliexpress", "ebay", "temu"):
        out.setdefault(extra, f"{extra}.com")
    return out


async def create_run(body: CreateRunRequest) -> CreateRunResponse:
    if body.intake_id:
        it = runstate.intakes.get(body.intake_id)
        if it is None:
            raise err(404, "intake_not_found", f"No intake {body.intake_id}")
    elif body.source_url:
        it = await intake(body.source_url, [], None)  # the v3 form: a link-only intake
    else:
        raise err(422, "missing_input", "Send intake_id or source_url")
    meta = runstate.intake_meta.get(it.intake_id, {})
    ans, defaulted = clarify.effective_answers(it.intake_id, it)
    preset = body.mandate
    if preset.budget_usd <= 0:
        raise err(422, "bad_budget", "The budget must be more than zero")
    run_id = runstate.new_id("r")
    now = runstate.now_iso()
    text = it.inputs.text
    plain = text if text and text.strip() != (it.inputs.source_url or "") else None
    inputs = {"source_url": it.inputs.source_url, "text_sha256": sha256_hex(plain) if plain else None, "image_sha256": [im.sha256 for im in it.inputs.images]}
    try:
        expires = (datetime.fromisoformat(now) + timedelta(hours=6)).isoformat(timespec="seconds")
    except ValueError:
        expires = now
    mandate_body = {
        "type": "b2c.mandate.open", "version": "0.4", "note": "AP2-inspired (v0.2 open Checkout Mandate shape); not AP2-compliant",
        "mandate_id": runstate.new_id("m"), "run_id": run_id, "user_id": "demo_user", "created_at": now, "expires_at": expires,
        "scope": {"build_type": it.build_type, "build_type_set_by": meta.get("set_by", "classifier"), "goal": it.summary,
                  "intake_sha256": sha256_hex(canonical_json({"inputs": inputs, "build_type": it.build_type, "answers": ans})),
                  "inputs": inputs, "template_id": it.template_id, "reference_search": bool(body.reference_search)},
        "constraints": {"budget_usd": preset.budget_usd, "deadline": preset.deadline, "ship_to_country": preset.ship_to_country,
                        "allowed_merchants": list(preset.allowed_merchants), "data_sharing": preset.data_sharing.model_dump(),
                        "actions": MandateActions().model_dump()},
    }
    mandate_body["simulated"] = bool(it.simulated)
    # sign exactly what the contract model serialises (defaults included, no nulls), so any reader re-derives the same bytes
    full = OpenMandate.model_validate({**mandate_body, "signature": {"jws": "unsigned"}}).model_dump(mode="json", by_alias=True, exclude_none=True)
    full.pop("signature", None)
    signed = ports.sign(full, run_id)
    mandate = OpenMandate.model_validate(signed)
    run = runstate.create(Run(run_id=run_id, intake=it, mandate=mandate, answers=ans, images={im.image_id: im for im in it.inputs.images},
                              simulated=bool(it.simulated) or mandate.simulated))
    setattr(run, "defaulted", defaulted)
    setattr(run, "confirmed_facts", set())
    setattr(run, "mandate_dict", signed)
    run.emit("run.started", "Run started", "info", data={"run_id": run_id})
    rec = run.record("intake", {"inputs": inputs, "build_type": it.build_type, "confidence": it.confidence, "questions": [q.id for q in it.questions],
                                "answers": ans, "defaulted": sorted(defaulted), "changed_by_user": bool(meta.get("changed_by_user")),
                                "classifier": it.source_api})
    run.emit("intake.classified", f"Build type: {classify.BUILD_LABELS[it.build_type]} ({round(it.confidence * 100)}%)", "ok",
             provider="claude" if it.source_api == "claude" else None, record_hash=rec["hash"],
             detail="Keyword router (Claude not connected)" if it.source_api == "keyword_router" else None,
             data={"build_type": it.build_type, "confidence": it.confidence, "changed_by_user": bool(meta.get("changed_by_user"))})
    for q in it.questions:
        label = next((c.label for c in q.chips if c.value == ans.get(q.id)), ans.get(q.id))
        run.emit("intake.answered", f"{q.text} {label}" + (" (default)" if q.id in defaulted else ""), "info", data={"id": q.id, "defaulted": q.id in defaulted})
    rec = run.record("mandate_open", {"mandate": mandate.model_dump(mode="json"), "mandate_sha256": ports.mandate_sha(signed)})
    ds = preset.data_sharing.model_dump()
    shared = [k.replace("_", " ") for k, v in ds.items() if v and k != "photo_to_models"]
    signed = mandate.signature.alg != "none"
    run.emit("mandate.opened", f"Mandate {'signed' if signed else 'recorded (unsigned: signing is not connected)'}: ${preset.budget_usd:g}, "
             f"{len(preset.allowed_merchants)} store{'s' if len(preset.allowed_merchants) != 1 else ''}, shares {' and '.join(shared) + ' only' if shared else 'nothing'}",
             "ok" if signed else "warn", record_hash=rec["hash"])
    ports.track("track_event", run_id, "build_type_set", {"build_type": it.build_type, "confidence": it.confidence, "changed_by_user": bool(meta.get("changed_by_user"))})
    # the request as the session's first turn: only its kind is sent, never the words (Amplitude client, PLAN §3.15)
    ports.track("track_user_message", run_id, "link" if it.inputs.source_url else "photo" if it.inputs.images else "text")
    if RUN_INLINE:
        await loop.run_agent(run_id)
    else:
        run.task = asyncio.create_task(loop.run_agent(run_id))
    return CreateRunResponse(run_id=run_id, mandate=mandate, simulated=run.simulated)


def get_run(run_id: str) -> RunState:
    return runstate.to_state(run_or_404(run_id))


def get_panel(run_id: str, bom_line_id: str) -> PartPanel:
    run = run_or_404(run_id)
    line_or_404(run, bom_line_id)
    return panel.build_panel(run, bom_line_id)  # type: ignore[return-value]


def _commit_plans(run: Run, kind: str, body: dict[str, Any], title: str, event: str = "plan.changed") -> None:
    run.plans = tools.replan(run)
    tools.refresh_lines(run)
    run.checks, _ = compat.run_checks(run, run.plan())
    fixed = {f["rule_id"]: f for f in run.fixes}
    for c in run.checks:
        if c.result == "pass" and c.rule_id in fixed and not c.fix:
            c.fix = fixed[c.rule_id]["fix_text"]
    tools.refresh_lines(run)
    plan = run.plan()
    rec = run.record(kind, {**body, "plan_id": plan.plan_id if plan else None, "plan_sha256": plan.plan_sha256 if plan else None,
                            "total_usd": plan.total_usd if plan else None})
    run.emit(event, title, "info", record_hash=rec["hash"],
             data={"plan_id": plan.plan_id, "total_usd": plan.total_usd, "checkouts": plan.checkouts, "tier": plan.tier} if plan else None)
    runstate.save_run(run)


async def _research(run: Run, ids: list[str]) -> None:
    for bid in ids:
        run.stages.discard(f"offers:{bid}")
        run.stages.discard(f"ranked:{bid}")
        if f"resolved:{bid}" not in run.stages:
            await tools.call_tool(run.run_id, "resolve_part", {"bom_line_id": bid})
        res = await tools.call_tool(run.run_id, "search_offers", {"bom_line_id": bid})
        if not res.get("error"):
            await tools.call_tool(run.run_id, "rank_offers", {"bom_line_id": bid})


async def assumption(run_id: str, body: AssumptionRequest) -> RunState:
    """Confirm, edit or remove an assumption. Only a person can do this: the agent has no such tool."""
    run = run_or_404(run_id)
    ln = line_or_404(run, body.bom_line_id)
    p = ln.provenance
    if p.type != "assumption":
        raise err(409, "not_an_assumption", f"{body.bom_line_id} is not an assumption")
    if run.cart_state != "draft":
        raise err(409, "cart_locked", "An approved cart is locked")
    before = {"spec": ln.spec, "qty": ln.qty, "status": ln.status, "confirmed_by_user": p.confirmed_by_user}
    research = False
    if body.action == "edit":
        if body.qty is not None:
            if body.qty < 1:
                raise err(422, "bad_qty", "Quantity must be at least 1")
            ln.qty = body.qty
        if body.spec and body.spec.strip() and body.spec.strip() != (ln.spec or ""):
            ln.spec = body.spec.strip()[:200]
            meta = run.line_meta.setdefault(ln.bom_line_id, {})
            meta["search_query"] = ln.spec
            if ln.bom_line_id in run.resolved:
                run.resolved[ln.bom_line_id].spec = ln.spec
            research = "plan" in run.stages and ln.status not in ("owned", "skipped", "removed")
    elif body.action == "remove":
        ln.status = "removed"
        run.pins.removed[ln.bom_line_id] = "removed_by_you"
    p.confirmed_by_user, p.confirmed_at = True, runstate.now_iso()
    rec = run.record("assumption", {"bom_line_id": ln.bom_line_id, "action": body.action, "before": before,
                                    "after": {"spec": ln.spec, "qty": ln.qty, "status": ln.status, "confirmed_by_user": True}, "by": "user"})
    run.emit("assumption.resolved", {"confirm": "Confirmed by you", "edit": "Edited and confirmed by you", "remove": "Removed by you"}[body.action] + f": {ln.raw_name}",
             "ok", bom_line_id=ln.bom_line_id, record_hash=rec["hash"])
    ports.track("track_event", run_id, "assumption_resolved", {"action": body.action})
    if research:
        await _research(run, [ln.bom_line_id])
    if "plan" in run.stages and (body.action != "confirm"):
        _commit_plans(run, "plan", {"reason": f"assumption {body.action}", "bom_line_id": ln.bom_line_id}, "Plan updated after your change")
    else:
        runstate.save_run(run)
    return runstate.to_state(run)


async def message(run_id: str, text: str) -> None:
    """Chat and the attack presets. Chat approves nothing: what it asks for goes through the guard."""
    run = run_or_404(run_id)
    run.emit("agent.message", f"You: \"{text[:160]}\"", "info", data={"role": "user"})
    ports.track("track_event", run_id, "user_message", {"chars": len(text)})
    refusals = guard.scan_chat(run.mandate, text, known_stores=_stores_word_map(run))
    for r in refusals:
        title = "Refused: chat can't approve a cart" if r.rule == "approval_required" else tools._refusal_title(run, r)
        run.refuse(r.model_dump(), title)
    if refusals:
        run.emit("agent.message", "I can't do that from chat. You approve the cart with the Approve button and pay at each store yourself; "
                 "your details are shared only as the mandate allows.", "info", data={"role": "agent"})
    else:
        run.emit("agent.message", "Noted. To change the plan use the tier switch, the variant chips or the cart; I can't approve or pay.", "info", data={"role": "agent"})
    runstate.save_run(run)


async def owned(run_id: str, bom_line_id: str, is_owned: bool, note: str | None) -> None:
    run = run_or_404(run_id)
    ln = line_or_404(run, bom_line_id)
    if run.cart_state != "draft":
        raise err(409, "cart_locked", "An approved cart is locked")
    if is_owned:
        ln.status, ln.owned_note = "owned", (note or "You said you have this")[:160]
        run.pins.removed[bom_line_id] = "owned"
        fact = f"owns {ln.raw_name}"
        getattr(run, "confirmed_facts").add(fact)
        await tools.call_tool(run_id, "remember", {"fact": fact}, triggered_by="user_edit")
        run.emit("owned.matched", f"You already have this: {ln.raw_name}", "ok", bom_line_id=bom_line_id)
    else:
        run.pins.removed.pop(bom_line_id, None)
        run.owned.pop(bom_line_id, None)
        ln.status, ln.owned_note = "resolved", None
        if "plan" in run.stages:
            await _research(run, [bom_line_id])
    if "plan" in run.stages:
        _commit_plans(run, "plan", {"reason": "owned" if is_owned else "not owned", "bom_line_id": bom_line_id}, "Plan updated after your change")


async def variant(run_id: str, option: str) -> None:
    """A variant chip (e.g. a voltage class): set the template answer it names and redo the affected steps."""
    run = run_or_404(run_id)
    if run.cart_state != "draft":
        raise err(409, "cart_locked", "An approved cart is locked")
    norm = option.lower().replace(".", "v").replace("-", "_")
    hit = None
    for q in (run.template.questions if run.template else []):
        for chip in q.chips:
            v = chip.value.lower()
            if norm == v or norm.endswith("_" + v) or norm == f"{q.id}_{v}" or norm.replace("_", "").endswith(v.replace("_", "")):
                hit = (q, chip)
    if hit is None:
        raise err(422, "unknown_option", f"No variant {option} for this build type")
    q, chip = hit
    run.answers[q.id] = chip.value
    getattr(run, "defaulted", set()).discard(q.id)
    run.emit("agent.message", f"You picked {chip.label}", "info", data={"variant": option, "role": "user"})
    run.record("intake", {"answers": {q.id: chip.value}, "changed_by_user": True, "reason": "variant"})
    for bid, meta in run.line_meta.items():  # redo from resolve: specs, offers, checks and the plan depend on the answer
        for k in ("require", "spec_attrs", "search_query"):
            meta.pop(k, None)
        ln = run.line(bid)
        if ln is not None and "orig_spec" in meta:
            ln.spec = meta["orig_spec"]
        if ln is not None and ln.status not in ("owned", "skipped", "removed"):
            ln.status, ln.chosen = "extracted", None
    run.resolved.clear()
    run.fixes.clear()
    setattr(run, "emitted_checks", set())
    run.stages = {s for s in run.stages if s in ("source", "template", "photo", "bom", "owned")}
    run.plans, run.checks, run.status = {}, [], "running"
    from app.agent import scripted

    if RUN_INLINE:
        await scripted.run_scripted(run_id, run.active_tier)
    else:
        run.task = asyncio.create_task(scripted.run_scripted(run_id, run.active_tier))


def replan(run_id: str, tier: str, cap: float | None) -> ReplanResponse:
    """Tier switch and budget slider: the optimizer only, no network. It can only tighten the plan."""
    run = run_or_404(run_id)
    if "plan" not in run.stages:
        raise err(409, "no_plan", "The plan is not ready yet")
    r = guard.check(run.mandate, "replan", {"budget_cap_usd": cap}, tools.guard_ctx(run, triggered_by="user_edit"))
    if r is not None:
        raise _refuse(run, r, 422, "budget_above_mandate", "Raising the budget needs a new signed mandate")
    if tier not in optimize.TIERS:
        raise err(422, "unknown_tier", f"Tiers: {', '.join(optimize.TIERS)}. Fastest needs delivery estimates, which most stores quote only at checkout.")
    if cap is not None and cap <= 0:
        raise err(422, "bad_cap", "The budget cap must be more than zero")
    if run.cart_state != "draft":
        raise err(409, "cart_locked", "An approved cart is locked")
    run.active_tier, run.budget_cap = tier, cap
    _commit_plans(run, "plan", {"reason": "replan", "tier": tier, "budget_cap_usd": cap}, f"Plan changed: {tier.replace('_', ' ')}")
    plan = run.plan()
    ports.track("track_event", run_id, "tier_switched", {"tier": tier})
    return ReplanResponse(plan=plan, simulated=plan.simulated)  # type: ignore[arg-type]


def _chosen_map(run: Run) -> dict[str, list[tuple[str, int]]]:
    out: dict[str, list[tuple[str, int]]] = {}
    for pl in (run.plan().lines if run.plan() else []):
        out.setdefault(pl.bom_line_id, []).append((pl.offer_id, pl.packs))
    return out


async def cart_edit(run_id: str, body: CartEditRequest) -> UniversalCart:
    """One cart edit: guard -> optimizer with the edit as a pin -> `cart_edit` record (PLAN §12.3, §3.10)."""
    run = run_or_404(run_id)
    ln = line_or_404(run, body.bom_line_id)
    bid = ln.bom_line_id
    if "plan" not in run.stages:
        raise err(409, "no_plan", "The cart is not ready yet")
    if run.cart_state != "draft":
        raise err(409, "cart_locked", "An approved cart is locked. Edit cart returns it to draft.")
    r = guard.check(run.mandate, "cart_edit", {"offer_id": body.offer_id, "store_id": body.store_id}, tools.guard_ctx(run, triggered_by="user_edit"))
    if r is not None:
        raise _refuse(run, r, 409, r.rule, "That change is outside your mandate" if r.rule == "merchant_allowed" else "That offer was not found in this run", bom_line_id=bid)
    pins = run.pins.copy()
    mine = {o.offer_id for o in run.offers.get(bid, [])}
    ok_offers = rank.acceptable(run.offers.get(bid, []), run.rejected.get(bid, {}))
    note = None
    if body.op == "swap_offer":
        if not body.offer_id or body.offer_id not in mine:
            rr = guard.refusal("unknown_offer", "only offers found for this line in this run", tool="cart_edit", field="offer_id", value=str(body.offer_id), triggered_by="user_edit")
            raise _refuse(run, rr, 409, "unknown_offer", "That offer does not belong to this line", bom_line_id=bid)
        why = run.rejected.get(bid, {}).get(body.offer_id)
        if why:
            raise err(409, "offer_rejected", f"That offer failed a check: {why}", bom_line_ids=[bid])
        for oid in mine:
            pins.require.discard(oid)
            pins.ban.discard(oid)
        pins.store.pop(bid, None)
        pins.require.add(body.offer_id)
        pins.ban |= {oid for oid, _ in _chosen_map(run).get(bid, []) if oid != body.offer_id}
    elif body.op == "move_store":
        if not body.store_id or not any(o.store_id == body.store_id for o in ok_offers):
            raise err(409, "no_offer_in_store", "That store has no acceptable offer for this part", bom_line_ids=[bid])
        for oid in mine:
            pins.require.discard(oid)
            pins.ban.discard(oid)
        pins.store[bid] = body.store_id
    elif body.op == "remove":
        pins.removed[bid] = "removed_by_you"
    elif body.op == "restore":
        pins.removed.pop(bid, None)
        for oid in mine:
            pins.require.discard(oid)
            pins.ban.discard(oid)
        pins.store.pop(bid, None)
        pins.qty.pop(bid, None)
    elif body.op == "set_qty":
        if body.qty is None or body.qty < 1:
            raise err(422, "bad_qty", "Quantity must be at least 1. Use Remove to drop the item.")
        pins.qty[bid] = body.qty
        if body.qty < ln.qty:
            note = f"The project needs {ln.qty}"
    before = {"pins": run.pins.to_dict(), "chosen": {k: v for k, v in _chosen_map(run).items()}, "total_usd": run.plan().total_usd if run.plan() else None}
    restoring = body.op == "restore" and (ln.status in ("removed", "owned") or bid in run.pins.removed)
    run.pins = pins
    run.edited_lines.add(bid)
    if body.op == "remove":
        ln.status, ln.chosen = "removed", None
    if restoring:
        ln.status, ln.owned_note = "resolved", None
        run.owned.pop(bid, None)
        if f"ranked:{bid}" not in run.stages:
            await _research(run, [bid])
        else:
            ln.status = "offers"
    after_plans = tools.replan(run)
    after = {bid2: [(pl.offer_id, pl.packs) for pl in after_plans[run.active_tier].lines if pl.bom_line_id == bid2]
             for bid2 in {pl.bom_line_id for pl in after_plans[run.active_tier].lines}}
    moved = sorted(b for b in set(before["chosen"]) | set(after) if sorted(before["chosen"].get(b, [])) != sorted(after.get(b, [])))
    from app.agent import memory as agent_memory  # the user's own edit is a decision worth remembering (never the agent's picks)

    def stores_of(chosen: list[Any]) -> list[str]:
        return list(dict.fromkeys(run.offer_index[oid].store_id for oid, _ in chosen if oid in run.offer_index))

    await agent_memory.on_cart_edit(run, body.op, ln, stores_of(before["chosen"].get(bid, [])), stores_of(after.get(bid, [])), inline=RUN_INLINE)
    _commit_plans(run, "cart_edit", {"op": body.op, "bom_line_id": bid, "offer_id": body.offer_id, "store_id": body.store_id, "qty": body.qty, "by": "user",
                                     "before": before, "after": {"pins": pins.to_dict(), "chosen": after}, "changed_lines": moved, "note": note},
                  f"Cart edited: {body.op.replace('_', ' ')} on {ln.raw_name.split(',')[0]}" + (f" ({len(moved)} line{'s' if len(moved) != 1 else ''} changed)" if moved else ""),
                  event="cart.edited")
    ports.track("track_event", run_id, "cart_edited", {"op": body.op})
    return ports.build_cart(run)


async def approve(run_id: str, body: ApproveRequest) -> ApproveResponse:
    """Approve cart. 409 while an assumption is open (PLAN §3.18), the plan is stale or over budget, or prices are old.

    Order: A's guard -> B's gate (prices, plan id) -> one-time token -> B's create_carts -> the CLOSED mandate
    (built here, signed by D) -> B locks the cart. Only a person reaches this: it is a route, not a tool.
    """
    from app.checkout import cart as b_cart
    from app.checkout import handoff as b_handoff

    run = run_or_404(run_id)
    if run.closed_mandate is not None and run.cart_state != "draft":
        return ApproveResponse(closed_mandate=run.closed_mandate, cart=ports.build_cart(run), simulated=run.simulated)
    plan = run.plan()
    if plan is None or "plan" not in run.stages:
        raise err(409, "no_plan", "The cart is not ready yet")
    open_lines = run.open_assumptions()
    r = guard.check(run.mandate, "approve", {"offer_ids": [pl.offer_id for pl in plan.lines], "total_usd": plan.total_usd},
                    tools.guard_ctx(run, triggered_by="user_edit"))
    if r is not None:
        msg = {"assumption_unconfirmed": f"Confirm {len(open_lines)} assumption{'s' if len(open_lines) != 1 else ''} first",
               "budget": f"The plan is ${plan.total_usd:.2f}, over your ${run.budget():g} budget"}.get(r.rule, "The cart cannot be approved as it is")
        raise _refuse(run, r, 409, r.rule if r.rule != "budget" else "over_budget", msg, bom_line_ids=open_lines if r.rule == "assumption_unconfirmed" else [])
    if body.plan_id != plan.plan_id:
        raise err(409, "stale_plan", "The cart changed since you last saw it. Review it again.")
    if not plan.feasible or not plan.lines:
        raise err(409, "over_budget" if plan.lines else "empty_cart", "The plan is over budget" if plan.lines else "There is nothing in the cart")
    acked = {a.split()[0] for a in body.acknowledged_warnings}
    need = sorted({c.rule_id for c in run.checks if c.needs_ack and c.rule_id.split()[0] not in acked})
    strict = False
    try:
        gate = getattr(registry.get("statsig"), "check_gate", None)
        strict = bool(gate("strict_compat_rules")) if gate else False
    except Exception:
        strict = False
    if strict and need:
        raise err(409, "warnings_unacknowledged", f"Tick the warnings that need your check first: {', '.join(need)}")

    def signer(handoffs: list[Any], draft: Any) -> dict[str, Any]:
        """Called by B after create_carts: build the closed mandate over exactly these hand-offs and sign it."""
        clean = []
        for h in handoffs:
            payload, stripped = guard.strip_buyer_fields(run.mandate, h.model_dump(mode="json"))
            for rr in stripped:
                run.refuse(rr.model_dump(), f"Refused: your {str(rr.attempted.field).split('.')[-1]} isn't shared under this mandate", store_id=h.store_id)
            clean.append(type(h).model_validate(payload))
        token_sha = next((sha for sha, b in b_cart.BOOK.get(run_id).tokens.items() if b.get("used") and b.get("plan_id") == plan.plan_id), "")
        rec = run.record("approval", {"plan_id": plan.plan_id, "plan_sha256": plan.plan_sha256, "approval_token_sha256": token_sha, "approved_by": "ui_button",
                                      "acknowledged_warnings": sorted(body.acknowledged_warnings), "unacknowledged": need})
        run.emit("approval.granted", "You approved the cart", "ok", record_hash=rec["hash"])
        now = runstate.now_iso()
        seen = [run.offer_index[pl.offer_id].seen_at for pl in plan.lines if pl.offer_id in run.offer_index]
        closed_body = {
            "type": "b2c.mandate.closed", "version": "0.4", "open_mandate_sha256": ports.mandate_sha(getattr(run, "mandate_dict", run.mandate.model_dump(mode="json"))),
            "plan_id": plan.plan_id, "plan_sha256": plan.plan_sha256 or "", "tier": plan.tier, "handoffs": [h.model_dump(mode="json") for h in clean],
            "total_usd": plan.total_usd, "prices_checked_at": min(seen) if seen else now, "approved_by": "ui_button", "approved_at": now,
            "approval_token_sha256": token_sha, "chain_head": run.head_hash, "simulated": run.simulated or any(h.simulated for h in clean),
        }
        run.handoffs = clean
        return ports.sign(closed_body, run_id)

    try:
        result = await b_handoff.approve(run_id, body.plan_id, body.acknowledged_warnings, sign=signer)
    except b_cart.CartError as exc:
        if exc.refusal:
            try:
                rr = guard.refusal(exc.refusal["rule"], exc.refusal["clause"], tool="approve", triggered_by="user_edit")
                run.refuse(rr.model_dump(), tools._refusal_title(run, rr))
            except Exception:
                pass
        raise HTTPException(status_code=exc.status, detail=exc.detail()) from exc
    closed = ClosedMandate.model_validate(result.closed_mandate if isinstance(result.closed_mandate, dict) else result.closed_mandate.model_dump(mode="json"))
    run.closed_mandate, run.cart_state, run.status = closed, "approved", "approved"
    # the payment mandate binds to D's hash of the closed mandate's signed body (what Verify recomputes)
    b_cart.BOOK.get(run_id).closed_mandate_sha256 = ports.mandate_sha(closed.model_dump(mode="json", exclude_none=True))
    rec = run.record("mandate_closed", {"mandate": closed.model_dump(mode="json"), "mandate_sha256": ports.mandate_sha(closed.model_dump(mode="json", exclude_none=True))})
    run.emit("mandate.closed", f"Closed mandate {'signed' if closed.signature.alg != 'none' else 'recorded (unsigned)'}: ${plan.total_usd:.2f}, "
             f"{len(run.handoffs)} hand-off{'s' if len(run.handoffs) != 1 else ''}", "ok", record_hash=rec["hash"])
    ports.track("score", run_id, "user-feedback", 1.0)
    ports.track("track_event", run_id, "cart_approved", {"total_usd": plan.total_usd, "checkouts": plan.checkouts})
    runstate.save_run(run)
    from app.agent import memory as agent_memory  # what you approved becomes preference facts, then one improve pass (background)

    await agent_memory.on_approved(run, plan, inline=RUN_INLINE)
    return ApproveResponse(closed_mandate=closed, cart=result.cart, simulated=closed.simulated)


def after_cart_change(run_id: str, cart: UniversalCart) -> UniversalCart:
    """Keep the run in step with B's cart after a hand-off change: approved -> checking_out -> complete."""
    run = run_or_404(run_id)
    run.cart_state = cart.state
    if cart.state == "complete":
        run.status = "done"
    elif cart.state != "draft" and run.status == "done":
        run.status = "approved"  # an undo re-opened the checkout run
    runstate.save_run(run)
    return cart


async def cart_reopen(run_id: str) -> UniversalCart:
    """The "Edit cart" button: B cancels the open carts and the cart is a draft again. A UI action, never a tool.

    The closed mandate that was signed stays in the chain; the next Approve signs a new one."""
    from app.checkout import cart as b_cart

    run = run_or_404(run_id)
    try:
        cart = await b_cart.reopen(run_id)
    except b_cart.CartError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail()) from exc
    if run.cart_state != "draft":
        run.cart_state, run.closed_mandate, run.handoffs = "draft", None, []
        run.status = "waiting_approval" if "plan" in run.stages else run.status
        ports.track("track_event", run_id, "cart_reopened", {})
    runstate.save_run(run)
    return cart


def receipt_overrides(run_id: str) -> dict[str, Any]:
    """What D's receipt and verify read from the run itself: its records and its mandates as signed."""
    run = run_or_404(run_id)
    out: dict[str, Any] = {"records": run.records, "simulated": run.simulated,
                           "open_mandate": getattr(run, "mandate_dict", None) or run.mandate.model_dump(mode="json", by_alias=True, exclude_none=True)}
    if run.closed_mandate is not None:
        out["closed_mandate"] = run.closed_mandate.model_dump(mode="json", by_alias=True, exclude_none=True)
        try:
            from app.checkout import stripe_test as b_stripe

            pm = b_stripe.payment_mandate(run_id)
            if pm is not None:
                out["payment_mandate"] = pm.model_dump(mode="json", by_alias=True, exclude_none=True)
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------- hooks B's cart needs from the run (checkout/cart.py `configure`)

_hooks_installed = False


def cart_context(run_id: str) -> Any:
    from app.checkout.cart import CartContext
    from app.models import CartPlan

    run = runstate.get(run_id)
    plan = run.plan() or CartPlan(plan_id="", tier=run.active_tier, total_usd=0.0, stores=[], checkouts=0,
                                  by_level={"agent_cart": 0, "prefilled_cart": 0, "product_link": 0}, items_by_hand=0, feasible=True)
    return CartContext(run_id=run_id, plan=plan, offers=run.offer_index, bom=run.bom, budget_usd=run.budget(), open_assumptions=run.open_assumptions(),
                       line_offers={bid: [o.offer_id for o in offs] for bid, offs in run.offers.items()},
                       rejected={oid: why for m in run.rejected.values() for oid, why in m.items()},
                       allowed_merchants=list(run.mandate.constraints.allowed_merchants), edited_lines=set(run.edited_lines))


def cart_replanner(run_id: str, pins: dict[str, Any]) -> Any:
    """B's `apply_edit` path: translate its pins to the optimizer's and re-plan (no network)."""
    run = runstate.get(run_id)
    p = runstate.Pins(require=set((pins.get("swap_in") or {}).values()), ban=set(pins.get("swap_out") or ()),
                      qty={k: int(v) for k, v in (pins.get("qty") or {}).items()}, removed=dict(pins.get("removed") or {}), store=dict(run.pins.store))
    for bid in set(run.pins.removed) - set(p.removed):  # restored through B
        ln = run.line(bid)
        if ln is not None and ln.status in ("removed", "owned"):
            ln.status, ln.owned_note = "offers", None
    run.pins = p
    run.edited_lines |= set(pins.get("swap_in") or {}) | set(p.qty) | set(p.removed)
    for bid in p.removed:
        ln = run.line(bid)
        if ln is not None:
            ln.status, ln.chosen = ("owned" if p.removed[bid] == "owned" else "removed"), None
    run.plans = tools.replan(run)
    tools.refresh_lines(run)
    run.checks, _ = compat.run_checks(run, run.plan())
    tools.refresh_lines(run)
    return run.plan()


def install_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True
    try:
        from app.checkout import cart as b_cart

        def event(run_id: str, ev: dict[str, Any]) -> None:
            run = runstate.runs.get(run_id)
            if run is None:  # a cart B built outside a run (its own tests): B keeps the event on its record
                return
            body = {k: v for k, v in ev.items() if k not in ("ts", "seq", "type", "title", "severity")}
            run.emit(ev["type"], ev["title"], ev.get("severity", "info"), **body)

        def record(run_id: str, kind: str, body: dict[str, Any]) -> Any:
            run = runstate.runs.get(run_id)
            if run is None:  # same as B's default when no hook is set
                from app.audit import chain

                return chain.append(run_id, kind, body)
            return run.record(kind, body)

        def context(run_id: str) -> Any:
            if run_id not in runstate.runs:
                raise b_cart.CartError(404, "run_not_found", f"No run {run_id}")
            return cart_context(run_id)

        b_cart.configure(context=context, replanner=cart_replanner, record=record, event=event)
    except (ImportError, AttributeError, TypeError):
        pass  # B's module is still a stub: ports.fallback_cart is used instead
