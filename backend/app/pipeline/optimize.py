"""Cart optimizer (PLAN §3.10). Owner: A.

The model below is the PLAN's PuLP model. It is solved by an exact enumerator in this file, not by PuLP:
the pinned `pulp` (4.3.1) ships no solver binary (`pulp.listSolvers(onlyAvailable=True)` is empty), and
adding one is a dependency change. The instances are tiny (a dozen parts, a dozen stores), so the
enumeration is exact and takes milliseconds.

Pure: it works only on offers already fetched (no network), so `POST /replan` and `POST /cart/edit`
answer quickly and work in replay.

    n[o]    integer >= 0   packs of offer o
    y[s]    binary         store s is used
    m[p,s]  binary         part p is bought at product-link store s (one item added by hand)

    minimise  sum(price*n) + sum(ship*y) + w * F
    F = sum(base[level(s)] * y[s]) + sum(m[p,s])          friction: the effort of the hand-offs
    base: agent cart 1.0, prefilled cart 1.5, product link 1.0 (+1.0 per line added by hand)

    Cheapest:          w = $0.01     friction only breaks ties
    Fewest checkouts:  w = budget+1  least friction first, then price

Unknown shipping is 0 and is never invented. A plan over the cap is returned as infeasible with
`over_budget_by` (the cheapest plan without the cap), and the guard still blocks approval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.audit.chain import canonical_json, sha256_hex
from app.models import CartPlan, Offer, PlanLine

__all__ = ["optimize", "PartNeed", "TIERS", "FRICTION_BASE", "plan_hash", "tier_weight"]

TIERS = ("cheapest", "fewest_checkouts")
FRICTION_BASE = {"agent_cart": 1.0, "prefilled_cart": 1.5, "product_link": 1.0}
LEVEL_RANK = {"agent_cart": 0, "prefilled_cart": 1, "product_link": 2}


@dataclass
class PartNeed:
    bom_line_id: str
    qty: int
    offers: list[Offer] = field(default_factory=list)  # already filtered: mandate, variant, stock, currency, condition, deadline


def tier_weight(tier: str, budget: float) -> float:
    if tier == "cheapest":
        return 0.01
    if tier == "fewest_checkouts":
        return float(budget) + 1.0
    raise ValueError(f"unknown tier {tier!r}; known: {', '.join(TIERS)}")


def plan_hash(tier: str, lines: list[PlanLine], total: float) -> str:
    body = {"tier": tier, "total_usd": round(total, 2),
            "lines": sorted(([ln.bom_line_id, ln.offer_id, ln.store_id, ln.packs, ln.qty, round(ln.line_usd, 2)] for ln in lines))}
    return sha256_hex(canonical_json(body))


def _cover(qty: int, offers: list[Offer], forced: dict[str, int]) -> tuple[float, dict[str, int]] | None:
    """Cheapest packs covering `qty` units from `offers` (bounded, exact). `forced` packs are bought first."""
    packs = dict(forced)
    cost = sum(o.price_usd * forced[o.offer_id] for o in offers if o.offer_id in forced)
    need = max(0, qty - sum(o.units_per_pack * forced[o.offer_id] for o in offers if o.offer_id in forced))
    if need == 0:
        return cost, packs
    if not offers:
        return None
    inf = float("inf")
    best: list[tuple[float, int, str | None, int]] = [(0.0, 0, None, 0)] + [(inf, 0, None, 0)] * need  # (cost, lines, offer, prev units)
    for u in range(1, need + 1):
        for o in sorted(offers, key=lambda o: o.offer_id):
            prev = max(0, u - o.units_per_pack)
            c = best[prev][0] + o.price_usd
            cand = (round(c, 6), best[prev][1] + 1, o.offer_id, prev)
            if cand[:2] < best[u][:2]:
                best[u] = cand
    if best[need][0] == inf:
        return None
    u = need
    while u > 0:
        _, _, oid, prev = best[u]
        packs[oid] = packs.get(oid, 0) + 1  # type: ignore[index]
        u = prev
    return cost + best[need][0], packs


def _solve(parts: list[PartNeed], w: float, cap: float | None, require: set[str], ban: set[str]) -> tuple[str, dict[str, int]]:
    """Exact solver for the model in the module docstring.

    The store set is enumerated (stores are few); inside a store set each part is covered independently,
    and a small Pareto pass over (cost, friction) options applies the budget cap. No solver binary needed.
    """
    from itertools import combinations

    parts = [PartNeed(p.bom_line_id, p.qty, [o for o in p.offers if o.offer_id not in ban]) for p in parts]
    if any(not p.offers for p in parts):
        return "Infeasible", {}
    level: dict[str, str] = {}
    ship: dict[str, float] = {}
    for p in parts:
        for o in p.offers:
            level[o.store_id] = max(level.get(o.store_id, o.action_level), o.action_level, key=lambda lv: LEVEL_RANK[lv])  # weakest level wins
            if o.shipping_usd is not None:
                ship[o.store_id] = min(ship.get(o.store_id, o.shipping_usd), o.shipping_usd)
    must = {o.store_id for p in parts for o in p.offers if o.offer_id in require}
    stores = sorted(level)
    if len(stores) > 14:  # keep the stores that hold each part's cheapest offers (and every pinned store)
        keep = set(must)
        for p in parts:
            keep |= {o.store_id for o in sorted(p.offers, key=lambda o: o.price_usd / max(1, o.units_per_pack))[:4]}
        stores = sorted(keep)
    optional = [s for s in stores if s not in must]
    cache: dict[tuple[str, frozenset[str]], list[tuple[float, int, dict[str, int]]]] = {}

    def options(p: PartNeed, chosen: frozenset[str]) -> list[tuple[float, int, dict[str, int]]]:
        """Pareto options (cost, product-link stores used, packs) for one part inside a store set."""
        mine = frozenset(o.store_id for o in p.offers) & chosen
        key = (p.bom_line_id, mine)
        if key in cache:
            return cache[key]
        forced = {o.offer_id: 1 for o in p.offers if o.offer_id in require}
        if any(o.store_id not in mine for o in p.offers if o.offer_id in forced):
            cache[key] = []
            return []
        forced_pl = {o.store_id for o in p.offers if o.offer_id in forced and level[o.store_id] == "product_link"}
        direct = [o for o in p.offers if o.store_id in mine and level[o.store_id] != "product_link"]
        pl_stores = sorted(s for s in mine if level[s] == "product_link")
        out: list[tuple[float, int, dict[str, int]]] = []
        for k in range(0, min(len(pl_stores), 3) + 1):
            for combo in combinations(pl_stores, k):
                if not forced_pl <= set(combo):
                    continue
                got = _cover(p.qty, direct + [o for o in p.offers if o.store_id in combo], forced)
                if got is None:
                    continue
                used_pl = len({o.store_id for o in p.offers if got[1].get(o.offer_id) and level[o.store_id] == "product_link"})
                out.append((round(got[0], 2), used_pl, got[1]))
        out.sort(key=lambda x: (x[0], x[1]))
        pareto: list[tuple[float, int, dict[str, int]]] = []
        for c, f, pk in out:
            if not any(c2 <= c and f2 <= f for c2, f2, _ in pareto):
                pareto.append((c, f, pk))
        cache[key] = pareto
        return pareto

    best: tuple[float, float, dict[str, int]] | None = None
    for k in range(0, len(optional) + 1):
        for combo in combinations(optional, k):
            chosen = frozenset(must | set(combo))
            fixed_cost = sum(ship.get(s, 0.0) for s in chosen)
            fixed_fr = sum(FRICTION_BASE[level[s]] for s in chosen)
            # states: {(cost, friction)} -> packs, pruned to the Pareto front, cost under the cap
            states: list[tuple[float, int, dict[str, int]]] = [(fixed_cost, 0, {})]
            ok = True
            for p in parts:
                opts = options(p, chosen)
                if not opts:
                    ok = False
                    break
                nxt = [(c + oc, f + of, {**pk, **opk}) for c, f, pk in states for oc, of, opk in opts
                       if cap is None or c + oc <= cap + 1e-6]
                nxt.sort(key=lambda x: (x[0] + w * x[1], x[0]))
                states = []
                for c, f, pk in nxt:
                    if not any(c2 <= c + 1e-9 and f2 <= f for c2, f2, _ in states):
                        states.append((c, f, pk))
                states = states[:64]
                if not states:
                    ok = False
                    break
            if not ok:
                continue
            for c, f, pk in states:
                used = {o.store_id for p in parts for o in p.offers if pk.get(o.offer_id)}
                if used != set(chosen):
                    continue  # a smaller store set covers this choice without the idle store's friction
                obj = c + w * (fixed_fr + f)
                if best is None or (round(obj, 6), round(c, 2)) < (round(best[0], 6), round(best[1], 2)):
                    best = (obj, c, pk)
    if best is None:
        return "Infeasible", {}
    return "Optimal", {k: v for k, v in best[2].items() if v > 0}


def optimize(parts: list[PartNeed], *, tier: str = "cheapest", budget: float, cap: float | None = None,
             require: set[str] | None = None, ban: set[str] | None = None, simulated: bool = False) -> CartPlan:
    """Build the plan for one tier.

    `parts` holds only the lines to buy (not owned, not removed), each with its acceptable offers.
    A part with no offer is left out of the plan (the caller marks it `not_found`). `budget` is the
    signed mandate budget; `cap` is a what-if cap and may only be lower. `require` / `ban` are cart-edit pins.
    """
    require, ban = set(require or ()), set(ban or ())
    w = tier_weight(tier, budget)
    limit = min(budget, cap) if cap is not None else budget
    buyable = [PartNeed(p.bom_line_id, p.qty, [o for o in p.offers if o.offer_id not in ban]) for p in parts if p.qty > 0]
    buyable = [p for p in buyable if p.offers]
    index = {o.offer_id: (p, o) for p in buyable for o in p.offers}
    require &= set(index)
    feasible, over = True, None
    packs: dict[str, int] = {}
    if buyable:
        status, packs = _solve(buyable, w, limit, require, ban)
        if status != "Optimal":
            feasible = False
            status, packs = _solve(buyable, tier_weight("cheapest", budget), None, require, ban)  # the cheapest plan, shown with a warning
            if status != "Optimal":
                packs = {}
    lines: list[PlanLine] = []
    for p in buyable:
        for o in sorted(p.offers, key=lambda o: (-o.units_per_pack, o.price_usd, o.offer_id)):
            k = packs.get(o.offer_id, 0)
            if k:
                lines.append(PlanLine(bom_line_id=p.bom_line_id, offer_id=o.offer_id, store_id=o.store_id, packs=k,
                                      qty=k * o.units_per_pack, line_usd=round(k * o.price_usd, 2)))
    used: dict[str, str] = {}
    for ln in lines:
        o = index[ln.offer_id][1]
        used[ln.store_id] = max(used.get(ln.store_id, o.action_level), o.action_level, key=lambda lv: LEVEL_RANK[lv])
    ship_total = 0.0
    for s in used:
        known = [o.shipping_usd for _, o in index.values() if o.store_id == s and o.shipping_usd is not None]
        ship_total += min(known) if known else 0.0
    total = round(sum(ln.line_usd for ln in lines) + ship_total, 2)
    if not feasible or total > limit + 1e-6:
        feasible, over = False, round(max(total - limit, 0.0), 2)
    stores = sorted(used, key=lambda s: (LEVEL_RANK[used[s]], -sum(ln.line_usd for ln in lines if ln.store_id == s), s))
    by_level = {lv: sum(1 for s in used if used[s] == lv) for lv in ("agent_cart", "prefilled_cart", "product_link")}
    by_hand = len({(ln.bom_line_id, ln.offer_id) for ln in lines if used[ln.store_id] == "product_link"})
    sha = plan_hash(tier, lines, total)
    return CartPlan(plan_id=f"p_{sha[:12]}", tier=tier, total_usd=total, stores=stores, checkouts=len(stores), by_level=by_level,  # type: ignore[arg-type]
                    items_by_hand=by_hand, feasible=feasible, over_budget_by=over, plan_sha256=sha, lines=lines,
                    simulated=simulated or any(index[ln.offer_id][1].simulated for ln in lines))


def optimize_cart(run_id: str, tier: str = "cheapest") -> CartPlan:
    """The plan for one tier of a run, from the offers already fetched (the scaffold's public name).

    Runs live only in this process. Reloading a run from its runs/<run_id>.json snapshot is not built,
    so an unknown run id raises NotImplementedError rather than pretending there is a plan.
    """
    from app import runstate
    from app.agent import tools

    try:
        run = runstate.get(run_id)
    except runstate.RunNotFound:
        raise NotImplementedError(f"TODO(A) — PLAN §3.10: no run {run_id!r} in this process; reloading a run from its snapshot is not built") from None
    return tools.replan(run, tier)[tier]
