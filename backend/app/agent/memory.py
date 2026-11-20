"""The user's decisions -> memory, and memory -> the next run (PLAN §3.15).

Written: only what the USER decided. Approving a cart writes "chose <part> from <store> for a <build>" facts;
removing a line, swapping an offer or moving a line to another store writes a "you rejected ..." fact. The agent's
own picks (the optimizer's plan before approval) are never written. Every fact passes `check_fact` (no buyer data),
and each one is also handed to the memory as a rated decision, which one `improve` pass after approval reads.

Used: at run start the remembered preferences are put on the timeline, and `tie_break` prefers a remembered store
when that costs nothing (same total or lower, no extra checkout). A preference never widens the mandate: only
stores in `constraints.allowed_merchants` and only offers that already passed the rules are considered.

Part and store names come from the run's own data; nothing here names a store or a build.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Callable

from app import registry
from app.integrations.cognee_mem import check_fact
from app.pipeline import rank

__all__ = ["approval_facts", "edit_fact", "on_approved", "on_cart_edit", "learn", "recall_preferences", "preferred_stores",
           "tie_break", "announce_tie_breaks", "drain"]

MAX_FACTS = 8  # per approval: the largest lines; memory stays a short list of facts
MAX_SHOWN = 3  # preferences put on the timeline at run start
MAX_TRIES = 8  # extra optimizer calls one tie-break may spend
RECALL_TIMEOUT_S = 10.0
_tasks: set[asyncio.Task[Any]] = set()  # keeps background learning alive until it finishes


def _name(ln: Any) -> str:
    return str(ln.raw_name).split(",")[0].strip()[:70]


def _build(run: Any) -> str:
    from app.intake import classify

    label = classify.BUILD_LABELS.get(run.mandate.scope.build_type, "build")
    label = label if label.isupper() or label[:2].isupper() else label[0].lower() + label[1:]
    return f"{'an' if label[:1].lower() in 'aeiou' else 'a'} {label}"


def _store_name(run: Any, store_id: str) -> str:
    for o in run.offer_index.values():
        if o.store_id == store_id:
            return o.store_name
    try:
        from app.stores import registry as store_registry

        return store_registry.display_name(store_id)
    except Exception:
        return store_id


def _session(run: Any) -> str:
    return f"b2c_{run.run_id}"


def _mem_label(mem: Any) -> dict[str, Any]:
    """Event labels: which provider answered, and whether it was the in-process mock."""
    provider = getattr(mem, "provider", "cognee")
    return {"provider": "cognee" if provider == "cognee" else None, "simulated": True if getattr(mem, "mode", "") == "mock" else None}


# ----------------------------------------------------------------------------- facts from user decisions


def approval_facts(run: Any, plan: Any) -> list[str]:
    """One fact per (line, store) the user just approved, largest lines first."""
    out: list[str] = []
    for pl in sorted(plan.lines, key=lambda p: -p.line_usd):
        ln = run.line(pl.bom_line_id)
        if ln is None:
            continue
        fact = f"chose {_name(ln)} from {_store_name(run, pl.store_id)} for {_build(run)}"
        if fact not in out:
            out.append(fact)
    return out[:MAX_FACTS]


def edit_fact(run: Any, op: str, ln: Any, before: list[str], after: list[str]) -> str | None:
    """The "you rejected ..." fact for one cart edit. `before` / `after` are the store ids of the line's offers."""
    name = _name(ln)
    if op == "remove":
        return f"you rejected {name} for {_build(run)}: removed from the cart"
    if op not in ("swap_offer", "move_store") or not before or not after:
        return None
    left = [s for s in before if s not in after]
    if left:
        return f"you rejected {_store_name(run, left[0])} for {name} and chose {_store_name(run, after[0])} instead"
    if op == "swap_offer":
        return f"you rejected one {_store_name(run, after[0])} offer for {name} and chose another"
    return None


async def learn(run: Any, facts: list[str], *, positive: bool, source: str, improve: bool = False) -> list[str]:
    """Write the facts, rate them, optionally run one improve pass. Never raises; returns the facts that were stored."""
    try:
        mem = registry.get("cognee")
    except Exception:
        return []
    user, label, written = run.mandate.user_id, None, []
    for raw in facts:
        try:
            fact = check_fact(raw)
        except ValueError:
            continue  # it looks like buyer data (or is empty): never stored
        try:
            await mem.remember(fact, user, kind="preference", source=source, run_id=run.run_id)
        except Exception:
            continue
        label = label or _mem_label(mem)
        written.append(fact)
        rec = run.record("memory_write", {"fact": fact, "text": fact, "kind": "preference", "source": source, "by": "user_decision",
                                          "provider": getattr(mem, "provider", "cognee"), "stored": True})
        run.emit("memory.written", f"Remembered: {fact[:110]}", "ok", record_hash=rec["hash"], **label)
        try:
            if await mem.feedback(fact, user, session_id=_session(run), positive=positive):
                rated = getattr(run, "memory_rated", None) or []
                setattr(run, "memory_rated", [*rated, fact])  # every decision of this run that improve will read
        except Exception:
            pass  # the fact is stored; only its rating for improve is missing
    if improve and written:
        try:
            res = await mem.improve(user, session_ids=[_session(run)], run_id=run.run_id, feedback=list(getattr(run, "memory_rated", None) or []))
            stages = ", ".join(f"{s['stage']} {s['status']}" for s in res.get("stages", [])[:4])
            run.emit("agent.message", f"Memory improve pass: {stages or 'no stages reported'}"[:140], "info",
                     data={"role": "memory", "improve": res}, **(label or {}))
        except Exception as exc:
            run.emit("agent.message", f"Memory improve pass did not run: {type(exc).__name__}", "warn", data={"role": "memory"})
    if written:
        try:
            from app import runstate

            runstate.save_run(run)
        except Exception:
            pass
    return written


def _spawn(coro: Any, inline: bool) -> Any:
    if inline:
        return coro
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    async def done() -> None:
        return None

    return done()


async def on_approved(run: Any, plan: Any, *, inline: bool = False) -> None:
    """After the Approve button: preference facts, then one improve pass. In the background unless `inline` (tests)."""
    try:
        facts = approval_facts(run, plan)
        await _spawn(learn(run, facts, positive=True, source=f"approved cart {run.run_id}", improve=True), inline)
    except Exception:
        pass  # memory never fails an approval


async def on_cart_edit(run: Any, op: str, ln: Any, before: list[str], after: list[str], *, inline: bool = False) -> None:
    """After the user's own cart edit (the cart buttons, or the same edit asked for in chat)."""
    try:
        fact = edit_fact(run, op, ln, before, after)
        if fact:
            await _spawn(learn(run, [fact], positive=False, source=f"you rejected, cart {run.run_id}"), inline)
    except Exception:
        pass


async def drain() -> None:
    """Wait for background learning (tests, shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


# ----------------------------------------------------------------------------- preferences into a run


def _mentions(text: str, store_name: str) -> tuple[bool, bool]:
    """(liked, rejected): does this memory say the user chose, or rejected, this store?"""
    n = re.escape(store_name.strip())
    if not n:
        return False, False
    liked = re.search(rf"(?i)\b(chose|from|prefers?)\s+(the\s+)?{n}(?!\w)", text) is not None
    rejected = re.search(rf"(?i)\b(rejected|avoids?)\s+(the\s+)?{n}(?!\w)", text) is not None
    return liked, rejected


def _catalogue() -> dict[str, str]:
    try:
        from app.stores import registry as store_registry

        return {s["store_id"]: s["display_name"] for s in store_registry.load_registry()["stores"]}
    except Exception:
        return {}


async def recall_preferences(run: Any) -> list[str]:
    """At run start: ask memory what the user chose or rejected before and say it on the timeline. Never raises."""
    try:
        mem = registry.get("cognee")
        ask = getattr(mem, "preferences", None)
        if ask is None:
            return []
        hits = await asyncio.wait_for(ask(run.mandate.user_id, _build(run).split(" ", 1)[1]), timeout=RECALL_TIMEOUT_S)
    except Exception:
        return []
    texts: list[str] = []
    here = _build(run).split(" ", 1)[1].lower()
    for h in hits or []:
        t = ((h.get("memory_text") if isinstance(h, dict) else str(h)) or "").strip()
        scoped = re.search(r"\bfor an? ([^:]+?)(?::|$)", t)
        if scoped and scoped.group(1).strip().lower() != here:
            continue  # a choice made for another kind of build ("… for a robot arm" on a drone run) says nothing here
        if t and t not in texts:
            texts.append(t)
    setattr(run, "memory_prefs", texts[:MAX_FACTS * 2])
    allowed, names, label = set(run.mandate.constraints.allowed_merchants), _catalogue(), _mem_label(mem)
    for t in texts[:MAX_SHOWN]:
        outside = sorted(name for sid, name in names.items() if sid not in allowed and _mentions(t, name)[0])
        title = "Memory: " + (f"last time you {t}" if t.lower().startswith("chose") else t)
        run.emit("agent.message", title[:160], "info",
                 detail=f"{', '.join(outside)} is outside this mandate, so that preference is not used." if outside else None,
                 data={"role": "memory", "memory_text": t[:300], "used": not outside}, **label)
    return texts


def preferred_stores(run: Any) -> set[str]:
    """Store ids the remembered decisions favour, among the stores of THIS run's offers and inside the mandate."""
    texts = getattr(run, "memory_prefs", None) or []
    if not texts:
        return set()
    allowed = set(run.mandate.constraints.allowed_merchants)
    names = {o.store_id: o.store_name for o in run.offer_index.values()}
    liked, rejected = set(), set()
    for sid, name in names.items():
        for t in texts:
            a, b = _mentions(t, name)
            if a:
                liked.add(sid)
            if b:
                rejected.add(sid)
    return (liked - rejected) & allowed


def tie_break(run: Any, plan: Any, solve: Callable[[set[str], set[str]], Any], pins: Any, tier: str) -> Any:
    """Move a line to a remembered store when the plan gets no worse: total not higher, no extra checkout.

    `solve(require, ban)` re-runs the optimizer. Lines the user pinned or edited are left alone, and only offers
    that already passed the rules, from stores inside the mandate, are tried.
    """
    applied: dict[str, str] = {}
    try:
        pref = preferred_stores(run)
        if pref and plan.feasible and plan.lines:
            require, ban, tries = set(pins.require), set(pins.ban), 0
            for bid in list(dict.fromkeys(pl.bom_line_id for pl in plan.lines)):
                cur = [pl for pl in plan.lines if pl.bom_line_id == bid]
                if len(cur) != 1 or cur[0].store_id in pref or bid in pins.store or bid in run.edited_lines or cur[0].offer_id in require:
                    continue
                cands = [o for o in rank.acceptable(run.offers.get(bid, []), run.rejected.get(bid, {}))
                         if o.store_id in pref and o.offer_id not in ban]
                for o in sorted(cands, key=lambda o: (o.price_usd, o.offer_id))[:2]:
                    if tries >= MAX_TRIES:
                        break
                    tries += 1
                    new = solve(require | {o.offer_id}, ban | {cur[0].offer_id})
                    kept = [pl for pl in new.lines if pl.bom_line_id == bid]
                    if (new.feasible and new.total_usd <= plan.total_usd + 1e-9 and new.checkouts <= plan.checkouts
                            and kept and all(pl.store_id in pref for pl in kept)):
                        plan, require, ban = new, require | {o.offer_id}, ban | {cur[0].offer_id}
                        applied[bid] = o.store_id
                        break
    except Exception:
        applied = {}
    book = getattr(run, "memory_tie_breaks", None) or {}
    book[tier] = applied
    setattr(run, "memory_tie_breaks", book)
    return plan


def announce_tie_breaks(run: Any) -> None:
    """One timeline line per line a remembered store won on a tie, for the active tier."""
    try:
        applied = (getattr(run, "memory_tie_breaks", None) or {}).get(run.active_tier, {})
        label = _mem_label(registry.get("cognee")) if applied else {}
        for bid, sid in applied.items():
            ln = run.line(bid)
            if ln is not None:
                run.emit("agent.message", f"Memory: kept {_name(ln)} at {_store_name(run, sid)}, a store you chose before (same total)"[:160],
                         "info", bom_line_id=bid, store_id=sid, data={"role": "memory", "tie_break": True}, **label)
    except Exception:
        pass


async def on_mock_approved(run_id: str, run: dict[str, Any], cart: dict[str, Any]) -> None:
    """DEMO_MODE=mock: the same loop over the fixture cart the user approved. Mock memory only; never raises."""
    try:
        from app.intake import classify

        mem = registry.get("cognee")
        names = {ln["bom_line_id"]: str(ln["raw_name"]).split(",")[0].strip()[:70] for ln in run.get("bom", [])}
        label = classify.BUILD_LABELS.get(run["mandate"]["scope"]["build_type"], "build")
        label = label if label[:2].isupper() else label[0].lower() + label[1:]
        build = f"{'an' if label[:1].lower() in 'aeiou' else 'a'} {label}"
        rows = sorted(((it["line_usd"], names.get(it["bom_line_id"]), g["display_name"]) for g in cart["stores"] for it in g["items"]),
                      key=lambda r: -r[0])
        user, session, written = run["mandate"].get("user_id", "demo_user"), f"b2c_{run_id}", []
        for _, name, store in rows:
            if not name or len(written) >= MAX_FACTS:
                continue
            try:
                fact = check_fact(f"chose {name} from {store} for {build}")
            except ValueError:
                continue
            if fact not in written:
                await mem.remember(fact, user, kind="preference", source=f"approved cart {run_id}", run_id=run_id)
                await mem.feedback(fact, user, session_id=session, positive=True)
                written.append(fact)
        if written:
            await mem.improve(user, session_ids=[session], run_id=run_id, feedback=written)
    except Exception:
        pass
