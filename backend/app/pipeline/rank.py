"""SIE extract (spec reads), hard filters (mandate, variant, stock, currency, plug, condition, deadline), then SIE score
(PLAN §3.6 `rank_offers`).

Owner: A. Each rejection is logged with a short reason. If no offer is acceptable the line has none:
a near miss is never picked.
"""

from __future__ import annotations

import time
from typing import Any

from app.models import Offer, Rerank
from app.rules import spec_reads
from app.rules.base import listing_attrs, load_pack, num

__all__ = ["hard_filter", "rank_line", "rank_offers", "offer_dict", "acceptable"]

RELEVANCE_MIN = 0.5  # live SIE rerank score below which a listing is not the part asked for


def offer_dict(o: Offer, packs: int = 1) -> dict[str, Any]:
    """The shape rule packs read (`rules/base.py`)."""
    attrs = listing_attrs(o.title, o.description)
    reads = [r.model_dump() for r in o.spec_reads]
    if reads:  # a spec read (SIE extract, or the labelled mock reader) wins over the title pattern for the same attr
        attrs.update(spec_reads.base_attrs(reads))
    return {"offer_id": o.offer_id, "store_id": o.store_id, "title": o.title, "description": o.description, "packs": packs,
            "units_per_pack": o.units_per_pack, "price_usd": o.price_usd, "attrs": attrs, "spec_reads": reads}


def _required(meta: dict[str, Any], attrs: dict[str, Any]) -> str | None:
    """Filters a compatibility fix put on the line (e.g. voltage 12, 5 A or more, 5.5x2.1 plug)."""
    req = meta.get("require") or {}
    v, a = num(attrs.get("voltage_v")), num(attrs.get("current_a"))
    if "voltage_v" in req and v is not None and abs(v - float(req["voltage_v"])) > 0.6:
        return f"{v:g} V, need {float(req['voltage_v']):g} V"
    if "min_current_a" in req and a is not None and a < float(req["min_current_a"]):
        return f"{a:g} A < {float(req['min_current_a']):g} A"
    if "connector" in req:
        fam = str(req["connector"]).split("_")[0].split("-")[0]
        same = [c for c in attrs.get("connectors", []) if str(c).startswith(fam)]
        if same and req["connector"] not in same:
            return f"{same[0]} connector, need {req['connector']}"
    if "plug" in req and attrs.get("plug") and attrs["plug"] != req["plug"]:
        return f"{attrs['plug']} plug, need {req['plug']}"
    if "variant_in" in req and attrs.get("variant") and attrs["variant"] not in req["variant_in"]:
        return f"variant {attrs['variant']}, need {'/'.join(req['variant_in'])}"
    return None


def hard_filter(line: dict[str, Any], offer: Offer, *, plan: dict[str, Any], packs: list[Any], meta: dict[str, Any] | None = None,
                deadline: str | None = None, ship_to: str = "US") -> str | None:
    """Why this offer cannot be used for this line; None when it can. `line` and `plan` are rule-pack dicts."""
    if offer.refused:
        return None  # a mandate refusal, handled and logged separately (never a "rejection")
    if (offer.currency or "USD").upper() != "USD":
        return f"not USD ({offer.currency})"
    if offer.stock == "out_of_stock":
        return "out of stock"
    if offer.condition == "used":
        return "not new (used or auction)"
    if deadline and offer.eta_date and offer.eta_date > deadline:
        return f"arrives {offer.eta_date}, after the deadline {deadline}"
    if offer.price_usd <= 0 or offer.units_per_pack <= 0:
        return "no usable price"
    od = offer_dict(offer)
    for pack in packs:
        fn = getattr(pack, "reject", None)
        if fn is None:
            continue
        try:
            why = fn(line, od, plan)
        except NotImplementedError:
            continue
        if why:
            return why
    return _required(meta or {}, od["attrs"])


async def rank_line(line: dict[str, Any], offers: list[Offer], *, plan: dict[str, Any], pack_names: list[str], meta: dict[str, Any] | None = None,
                    deadline: str | None = None, spec: str | None = None, sie: Any = None) -> tuple[list[Offer], dict[str, str], dict[str, Any]]:
    """Returns (acceptable offers best first, {offer_id: rejection reason}, sie stats)."""
    packs = [p for p in (load_pack(n) for n in pack_names) if p is not None]
    rejected: dict[str, str] = {}
    ok: list[Offer] = []
    read: dict[str, Any] = {}
    if sie is not None:  # specs first, so the rules judge what was read; with no read the title patterns apply
        try:
            read = await spec_reads.read_offers(sie, offers)
        except Exception:
            read = {}
    for o in offers:
        if o.refused:
            continue
        why = hard_filter(line, o, plan=plan, packs=packs, meta=meta, deadline=deadline)
        if why:
            rejected[o.offer_id] = why
        else:
            ok.append(o)
    stats: dict[str, Any] = {"calls": 0, "latency_ms": 0}
    if sie is not None and len(ok) > 1 and spec:
        t0 = time.perf_counter()
        try:
            scores = await sie.score(spec, [f"{o.title}. {o.description or ''}".strip() for o in ok])
            ms = int((time.perf_counter() - t0) * 1000)
            stats = {"calls": 1, "latency_ms": ms}
            mock = type(sie).__name__.startswith("Mock")
            for o, s in zip(ok, scores):
                o.rerank = Rerank(provider="mock" if mock else "sie", model="mock" if mock else "sie-score", score=round(float(s), 3), latency_ms=ms)
            if not mock:
                # Real catalogs return accessories next to the part (servo *cables* for a servo, a power *cable* for a power
                # supply). Measured on live Shopify results: the right items score ~0.9-1.0, those ~0.0-0.3. Mock scores are flat.
                keep = []
                for o in ok:
                    if o.rerank and o.rerank.score < RELEVANCE_MIN:
                        rejected[o.offer_id] = f"Not the part asked for (SIE relevance {o.rerank.score:.2f})"
                    else:
                        keep.append(o)
                ok = keep
        except Exception:  # NotImplementedError while D's client is a stub, or SIE is down: order by price only
            pass
    ok.sort(key=lambda o: (-(o.rerank.score if o.rerank else 0.0), o.price_usd / max(1, o.units_per_pack)))
    if read.get("calls"):  # extract calls count like score calls
        stats = {"calls": stats["calls"] + read["calls"], "latency_ms": stats["latency_ms"] if stats["calls"] else read["latency_ms"]}
    stats["extract"] = {k: read.get(k) for k in ("calls", "cached", "listings", "reads", "provider", "ok")} if read else None
    return ok, rejected, stats


def acceptable(offers: list[Offer], rejected: dict[str, str]) -> list[Offer]:
    return [o for o in offers if not o.refused and o.offer_id not in rejected]


async def rank_offers(run_id: str, bom_line_id: str) -> list[Offer]:
    """Scored offers for one line of a run; each rejection is logged with a reason."""
    from app.agent import tools

    res = await tools.call_tool(run_id, "rank_offers", {"bom_line_id": bom_line_id})
    from app import runstate

    run = runstate.get(run_id)
    return acceptable(run.offers.get(bom_line_id, []), run.rejected.get(bom_line_id, {})) if not res.get("error") else []
