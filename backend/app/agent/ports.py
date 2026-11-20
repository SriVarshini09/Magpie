"""Calls into B's and D's modules, each with a plain fallback while that module is still a stub.

Owner: A. Every fallback is labelled, so nothing built on a fallback is presented as the real thing:
  chain_append   D `audit.chain.append(run_id, kind, body)`        -> local chain with D's `record_hash`
  sign           D `audit.mandate.sign_mandate(body)`              -> {"alg": "none", "kid": "unsigned"} (not a signature)
  write_evidence D `audit.evidence.write_evidence(run_id, payload)` -> hash only, no file
  cached         B `cache.cached(tool, args, fetch)`               -> direct call
  search_stores  B `stores.registry.adapters()`                    -> adapters that raise are skipped and reported
  build_cart     B `checkout.cart.build_cart(run_id)`              -> `fallback_cart(run)`
  create_carts   B `checkout.handoff.create_carts(run_id, plan_id, approval_token)` -> product-link hand-offs only
  find_reference B `intake.reference.find_reference_design(query, run_id)` -> None
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from app import registry
from app.audit import chain as d_chain
from app.models import (
    CartCounts, CartHandoff, CartItem, Handoff, HandoffItem, LeftOut, Offer, PartQuery, StoreGroup, UniversalCart,
)

FALLBACKS_USED: set[str] = set()  # reported by /api/health so a fallback is never silent


def _stub(exc: BaseException) -> bool:
    return isinstance(exc, NotImplementedError)


def strip_none(obj: Any) -> Any:
    """Drop null values, recursively. Records and mandates carry no nulls, so a reader that drops
    nulls when it re-serialises (D's receipt and verify do) still hashes exactly what was signed."""
    if isinstance(obj, dict):
        return {k: strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, (list, tuple)):
        return [strip_none(v) for v in obj]
    return obj


def chain_append(run: Any, kind: str, body: dict[str, Any]) -> dict[str, Any]:
    body = strip_none(body)
    try:
        rec = d_chain.append(run.run_id, kind, body)
        if rec not in run.records:
            run.records.append(rec)
        return rec
    except NotImplementedError:
        FALLBACKS_USED.add("audit.chain.append")
    from app.runstate import now_iso

    prev = run.records[-1]["hash"] if run.records else d_chain.GENESIS
    rec = {**body, "run_id": run.run_id, "seq": len(run.records) + 1, "ts": now_iso(), "kind": kind, "prev_hash": prev}
    rec["hash"] = d_chain.record_hash(rec, prev)
    run.records.append(rec)
    return rec


def sign(body: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
    """Return the mandate body with its `signature`. The fallback is NOT a signature and says so."""
    from app.audit import mandate as d_mandate

    body = strip_none(body)
    try:
        try:
            signed = d_mandate.sign_mandate(body, run_id=body.get("run_id") or run_id)
        except TypeError:
            signed = d_mandate.sign_mandate(body)
        if isinstance(signed, dict) and "signature" in signed:
            return signed
        if isinstance(signed, dict) and "jws" in signed:
            return {**body, "signature": signed}
    except NotImplementedError:
        FALLBACKS_USED.add("audit.mandate.sign_mandate")
    except Exception:  # no usable key (for example a read-only disk): say so instead of failing the run
        FALLBACKS_USED.add("audit.mandate.sign_mandate:error")
    return {**body, "signature": {"alg": "none", "kid": "unsigned", "jws": ""}}


def mandate_sha(mandate: dict[str, Any]) -> str:
    """D's hash of a mandate's signed body (what `open_mandate_sha256` and the chain records carry)."""
    from app.audit import mandate as d_mandate

    fn = getattr(d_mandate, "mandate_sha256", None)
    if fn is not None:
        try:
            return fn(mandate)
        except Exception:
            pass
    return d_chain.sha256_hex(d_chain.canonical_json({k: v for k, v in mandate.items() if k != "signature"}))


def cart_tokens(run_id: str) -> dict[str, str]:
    """Unused approval tokens B issued for this run: {sha256(token): plan_sha256}."""
    try:
        from app.checkout.cart import BOOK

        return {sha: str(b.get("plan_sha256") or "") for sha, b in BOOK.get(run_id).tokens.items() if not b.get("used")}
    except Exception:
        return {}


def write_evidence(run_id: str, payload: Any) -> tuple[str | None, str]:
    from app.audit import evidence as d_evidence

    try:
        return d_evidence.write_evidence(run_id, payload)
    except NotImplementedError:
        FALLBACKS_USED.add("audit.evidence.write_evidence")
    return None, d_chain.sha256_hex(d_chain.canonical_json(payload))


async def cached(tool: str, args: dict[str, Any], fetch: Callable[[], Awaitable[Any]]) -> Any:
    from app import cache as b_cache

    try:
        return await b_cache.cached(tool, args, fetch)
    except NotImplementedError:
        FALLBACKS_USED.add("cache.cached")
    return await fetch()


async def search_stores(query: PartQuery, ctx: Any, adapters: dict[str, Any] | None = None) -> tuple[list[Offer], dict[str, str]]:
    """Fan out to every enabled adapter. Returns (offers, {adapter: error}) so a broken adapter is visible."""
    if adapters is None:
        from app.stores import registry as store_registry

        adapters = store_registry.adapters()
    offers: list[Offer] = []
    errors: dict[str, str] = {}
    for name, adapter in adapters.items():
        try:
            offers.extend(await adapter.search(query, ctx))
        except NotImplementedError as exc:
            errors[name] = f"not implemented: {str(exc)[:80]}"
        except Exception as exc:  # one adapter failing must not sink the line
            errors[name] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return offers, errors


async def find_reference(query: str, run_id: str) -> dict[str, Any] | None:
    from app.intake import reference as b_reference

    try:
        return await b_reference.find_reference_design(query, run_id)
    except NotImplementedError:
        FALLBACKS_USED.add("intake.reference.find_reference_design")
        return None


def analytics() -> Any:
    try:
        return registry.get("amplitude")
    except Exception:
        return None


def track(method: str, *args: Any, **kw: Any) -> None:
    """Amplitude hook (D implements the client). Never raises into the agent."""
    client = analytics()
    try:
        if client is not None:
            getattr(client, method)(*args, **kw)
    except Exception:
        pass


# ---------------------------------------------------------------------------- cart (B owns the real one)


def _store_info(store_id: str) -> dict[str, Any]:
    try:
        from app.stores import registry as store_registry

        return store_registry.store(store_id) or {}
    except Exception:
        return {}


LEVEL_ORDER = {"agent_cart": 0, "prefilled_cart": 1, "product_link": 2}


def fallback_cart(run: Any) -> UniversalCart:
    """A `UniversalCart` built straight from the active plan. Used until B's `build_cart` exists."""
    from app.runstate import now_iso

    plan = run.plan()
    groups: dict[str, list[CartItem]] = {}
    levels: dict[str, str] = {}
    if plan:
        for pl in plan.lines:
            offer: Offer | None = run.offer_index.get(pl.offer_id)
            if offer is None:
                continue
            alts = sum(1 for o in run.offers.get(pl.bom_line_id, []) if not o.refused and o.offer_id not in run.rejected.get(pl.bom_line_id, {})) - 1
            groups.setdefault(pl.store_id, []).append(CartItem(
                bom_line_id=pl.bom_line_id, offer_id=pl.offer_id, title=offer.title, qty=pl.qty, packs=pl.packs,
                unit_price_usd=offer.price_usd, line_usd=pl.line_usd, seen_at=offer.seen_at, source_api=offer.source_api, url=offer.url,
                added=False if offer.action_level == "product_link" else None,
                edited_by_user=True if (pl.offer_id in run.pins.require or pl.bom_line_id in run.edited_lines) else None,
                alternatives=max(alts, 0), simulated=offer.simulated))
            levels[pl.store_id] = max(levels.get(pl.store_id, offer.action_level), offer.action_level, key=lambda lv: LEVEL_ORDER[lv])
    handoffs = {h.store_id: h for h in run.handoffs}
    ordered = sorted(groups, key=lambda s: (LEVEL_ORDER[levels[s]], -sum(i.line_usd for i in groups[s])))
    stores = []
    for i, sid in enumerate(ordered, 1):
        info, h = _store_info(sid), handoffs.get(sid)
        first = run.offer_index[groups[sid][0].offer_id]
        stores.append(StoreGroup(
            store_id=sid, display_name=info.get("display_name") or first.store_name, domain=info.get("domain") or "",
            action_level=levels[sid], order=i, subtotal_usd=round(sum(it.line_usd for it in groups[sid]), 2), items=groups[sid],
            handoff=CartHandoff(kind=h.action_level, url=h.url, cart_id=h.cart_id, caveat=h.caveat, url_sha256=h.url_sha256, simulated=h.simulated) if h else None))
    seen = [it.seen_at for g in stores for it in g.items]
    total = round(sum(g.subtotal_usd for g in stores), 2)
    by_hand = sum(len(g.items) for g in stores if g.action_level == "product_link")
    return UniversalCart(
        run_id=run.run_id, state=run.cart_state, plan_id=plan.plan_id if plan else "", tier=run.active_tier,
        editable=run.cart_state == "draft", total_usd=total, budget_usd=run.budget(), bought_usd=0.0, remaining_usd=total,
        prices_checked_at=min(seen) if seen else now_iso(),
        counts=CartCounts(stores=len(stores), done=0, agent_cart=sum(g.action_level == "agent_cart" for g in stores),
                          prefilled_cart=sum(g.action_level == "prefilled_cart" for g in stores),
                          product_link=sum(g.action_level == "product_link" for g in stores), items_by_hand=by_hand),
        stores=stores, left_out=[LeftOut(**x) for x in left_out(run)], open_assumptions=run.open_assumptions(),
        current_store_id=stores[0].store_id if stores and run.cart_state != "draft" else None,
        source_api="mock" if run.simulated else None, simulated=run.simulated or any(it.simulated for g in stores for it in g.items))


def left_out(run: Any) -> list[dict[str, Any]]:
    out = []
    in_plan = {pl.bom_line_id for pl in (run.plan().lines if run.plan() else [])}
    for ln in run.bom:
        if ln.bom_line_id in in_plan:
            continue
        if ln.bom_line_id in run.pins.removed or ln.status == "removed":
            reason, note = run.pins.removed.get(ln.bom_line_id, "removed_by_you"), None
        elif ln.status == "owned":
            reason, note = "owned", ln.owned_note
        elif ln.category == "printed" or ln.status == "skipped":
            reason, note = "print_at_home", ln.owned_note
        else:
            reason, note = "not_found", None
        out.append({"bom_line_id": ln.bom_line_id, "name": ln.raw_name, "reason": reason, "note": note})
    return out


def build_cart(run: Any) -> UniversalCart:
    from app.checkout import cart as b_cart

    try:
        cart = getattr(b_cart, "get_cart", b_cart.build_cart)(run.run_id)
        return cart if isinstance(cart, UniversalCart) else UniversalCart.model_validate(cart)
    except NotImplementedError:
        FALLBACKS_USED.add("checkout.cart.build_cart")
    return fallback_cart(run)


async def create_carts(run: Any, plan_id: str, approval_token: str) -> list[Handoff]:
    """B's hand-off builder; the fallback makes product-link hand-offs only (never a cart, never a request)."""
    from app.checkout import handoff as b_handoff

    try:
        res = b_handoff.create_carts(run.run_id, plan_id, approval_token)
        if inspect.isawaitable(res):
            res = await res
        return [h if isinstance(h, Handoff) else Handoff.model_validate(h) for h in res]
    except NotImplementedError:
        FALLBACKS_USED.add("checkout.handoff.create_carts")
    out: list[Handoff] = []
    plan = next((p for p in run.plans.values() if p.plan_id == plan_id), None)
    by_store: dict[str, list[Any]] = {}
    for pl in (plan.lines if plan else []):
        by_store.setdefault(pl.store_id, []).append(pl)
    for sid, lines in by_store.items():
        items = []
        for pl in lines:
            o: Offer = run.offer_index[pl.offer_id]
            items.append(HandoffItem(offer_id=o.offer_id, ids=o.ids, title=o.title, qty=pl.packs, unit_price_usd=o.price_usd,
                                     seen_at=o.seen_at, source_api=o.source_api, evidence_sha256=o.evidence_sha256,
                                     edited_by_user=o.offer_id in run.pins.require))
        url = run.offer_index[lines[0].offer_id].url
        out.append(Handoff(store_id=sid, action_level="product_link", cart_id=None, url=url, url_sha256=d_chain.sha256_hex(url),
                           subtotal_usd=round(sum(pl.line_usd for pl in lines), 2),
                           caveat="Hand-off builder not connected: open each product page and add it yourself", items=items,
                           simulated=any(run.offer_index[pl.offer_id].simulated for pl in lines)))
    return out
