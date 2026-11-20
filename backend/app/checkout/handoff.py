"""Hand-offs after approval only: agent cart, prefilled cart link, product links (PLAN §3.6 create_carts, §12.3).

Owner: B. Each hand-off is bound to the closed mandate by `url_sha256`:
- agent_cart      `ucp cart create` -> continue_url. A store whose cart cannot be created drops to product links,
                  with the reason shown ("Couldn't create a cart at Geekworm. Showing product links instead").
- prefilled_cart  cartlinks.py builds the link in the store's own format; never requested by us.
- product_link    the item URLs. `url` is the first item's page and `url_sha256` is its hash (what Verify recomputes); every item is bound by its offer id and evidence hash.

create_carts refuses without the one-time approval token issued by `issue_approval_token` (POST /approve).
No buyer data goes anywhere: the person types their details on the merchant's page (PLAN §12.2 rule 9).

The guided checkout run (`update_handoff`): ready -> opened -> done | skipped, and "ready" again is the undo.
Every change is a `handoff` chain record. "Bought" is what the user marked, never "paid".
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from typing import Any

from app import registry as services
from app.checkout import cart as cart_mod
from app.checkout.cart import BOOK, CartContext, CartError, HandoffState, emit_event, emit_record
from app.models import Handoff, HandoffItem, UniversalCart
from app.stores import registry as store_registry
from app.stores.base import now_iso, sha256_hex
from app.stores.cartlinks import ID_KEYS

_ORDER_ID = re.compile(r"^[A-Za-z0-9#_-]{1,40}$")


# --------------------------------------------------------------------------- approval token


def issue_approval_token(run_id: str, plan_id: str, ctx: CartContext | None = None) -> str:
    """A one-time token bound to this run and plan (and the plan's hash). Only POST /approve calls this."""
    ctx = cart_mod.context(run_id, ctx)
    if ctx.plan.plan_id != plan_id:
        raise CartError(409, "stale_plan", "The cart changed since you last saw it. Review it again.")
    token = secrets.token_urlsafe(24)
    BOOK.get(run_id).tokens[sha256_hex(token)] = {"plan_id": plan_id, "plan_sha256": ctx.plan.plan_sha256, "used": False, "at": now_iso()}
    return token


def _consume(run_id: str, plan_id: str, token: str) -> None:
    binding = BOOK.get(run_id).tokens.get(sha256_hex(token or ""))
    if not binding or binding["used"] or binding["plan_id"] != plan_id:
        raise CartError(409, "approval_required", "Hand-offs are created only after you approve the cart",
                        refusal=cart_mod.refusal("approval_required", "PLAN §3.6: create_carts needs the one-time approval token",
                                                 tool="create_carts", triggered_by="agent"))
    binding["used"] = True


# --------------------------------------------------------------------------- creating the hand-offs


def _items(g: Any, offers: dict[str, Any]) -> list[HandoffItem]:
    out = []
    for it in g.items:
        o = offers.get(it.offer_id)
        ids = {k: v for k, v in (o.ids if o else {}).items() if k in cart_mod.ITEM_ID_KEYS or k in ("seller_domain",)}
        out.append(HandoffItem(offer_id=it.offer_id, ids=ids, title=it.title, qty=it.packs, unit_price_usd=it.unit_price_usd,
                               seen_at=it.seen_at, source_api=it.source_api, evidence_sha256=o.evidence_sha256 if o else "",
                               edited_by_user=bool(it.edited_by_user)))
    return out


def _product_links(g: Any, items: list[HandoffItem], reason: str | None, simulated: bool) -> tuple[Handoff, str | None]:
    urls = [it.url for it in g.items]
    url = urls[0] if urls else f"https://{g.domain}"
    caveat = reason or (store_registry.store(g.store_id) or {}).get("caveat")
    return Handoff(store_id=g.store_id, action_level="product_link", cart_id=None, url=url,
                   url_sha256=sha256_hex(url), subtotal_usd=g.subtotal_usd,
                   caveat=caveat, items=items, simulated=simulated), reason


def _business_url(g: Any, offers: dict[str, Any]) -> str | None:
    for it in g.items:
        o = offers.get(it.offer_id)
        if o and o.ids.get("seller_domain"):
            return "https://" + o.ids["seller_domain"]
    return (store_registry.store(g.store_id) or {}).get("business_url")


async def create_carts(run_id: str, plan_id: str, approval_token: str, ctx: CartContext | None = None) -> list[Handoff]:
    """One hand-off per store, strongest first. Refuses without the one-time token from POST /approve."""
    rec = BOOK.get(run_id)
    if rec.state != "draft":
        raise CartError(409, "already_approved", "This cart is already approved")
    _consume(run_id, plan_id, approval_token)
    ctx = cart_mod.context(run_id, ctx)
    offers = {**ctx.offers, **rec.overrides}
    draft = cart_mod.build_cart(run_id, ctx)
    shopify, links = services.get("shopify_ucp"), services.get("cartlinks")
    pending: dict[str, HandoffState] = {}
    out: list[Handoff] = []
    for g in draft.stores:
        items = _items(g, offers)
        simulated = any(i.simulated for i in g.items)
        reason: str | None = g.downgrade_reason
        handoff: Handoff | None = None
        if g.action_level == "agent_cart":
            business = _business_url(g, offers)
            lines = [{"variant_gid": i.ids.get("variant_gid"), "quantity": i.qty} for i in items]
            try:
                if not business:
                    raise CartError(409, "no_business", "no store domain for --business")
                made = await shopify.create_cart(business, lines)
                for i in items:
                    i.ids["business_url"] = made.get("business_url") or business
                handoff = Handoff(store_id=g.store_id, action_level="agent_cart", cart_id=made["cart_id"], url=made["continue_url"],
                                  url_sha256=sha256_hex(made["continue_url"]), subtotal_usd=g.subtotal_usd,
                                  caveat=(store_registry.store(g.store_id) or {}).get("caveat"), items=items,
                                  simulated=bool(made.get("simulated")) or simulated)
                reason = None
            except Exception:  # noqa: BLE001 - any failure is the same downgrade, shown and logged (PLAN §12.6 states)
                reason = f"Couldn't create a cart at {g.display_name}. Showing product links instead"
        elif g.action_level == "prefilled_cart":
            key = ID_KEYS.get(g.store_id, "")
            link = links.link(g.store_id, [(i.ids.get(key, ""), i.qty) for i in items])
            if link.url:
                handoff = Handoff(store_id=g.store_id, action_level="prefilled_cart", cart_id=None, url=link.url,
                                  url_sha256=sha256_hex(link.url), subtotal_usd=g.subtotal_usd,
                                  caveat=(store_registry.store(g.store_id) or {}).get("caveat"), items=items, simulated=simulated)
                reason = None
            else:
                reason = link.downgrade_reason
        if handoff is None:
            handoff, reason = _product_links(g, items, reason, simulated)
        h = emit_record(run_id, "handoff", {"store_id": g.store_id, "action_level": handoff.action_level, "state": "created",
                                            "cart_id": handoff.cart_id, "url_sha256": handoff.url_sha256, "subtotal_usd": handoff.subtotal_usd,
                                            "downgrade_reason": reason, "simulated": handoff.simulated})
        label = {"agent_cart": "Agent cart", "prefilled_cart": "Prefilled cart", "product_link": "Product links"}[handoff.action_level]
        emit_event(run_id, "handoff.created", f"{label} ready: {g.display_name}", severity="warn" if reason else "ok",
                   store_id=g.store_id, provider="shopify" if handoff.action_level == "agent_cart" else None,
                   simulated=handoff.simulated or None, record_hash=h, detail=reason,
                   data={"action_level": handoff.action_level, "subtotal_usd": handoff.subtotal_usd})
        pending[g.store_id] = HandoffState(handoff=handoff, downgrade_reason=reason, history=[{"state": "ready", "at": now_iso()}])
        out.append(handoff)
    rec.pending = pending
    return out


async def discard_pending(run_id: str) -> None:
    """Cancel the carts create_carts made when the approval did not complete (e.g. signing failed)."""
    rec = BOOK.get(run_id)
    shopify = services.get("shopify_ucp")
    for store_id, hs in rec.pending.items():
        h = hs.handoff
        if h.action_level == "agent_cart" and h.cart_id:
            business = next((i.ids.get("business_url") for i in h.items if i.ids.get("business_url")), None)
            try:
                await shopify.cancel_cart(h.cart_id, business)
            except Exception:  # noqa: BLE001
                pass
    rec.pending = {}


@dataclass
class ApprovalResult:
    closed_mandate: Any
    cart: UniversalCart
    handoffs: list[Handoff]


Signer = Callable[[list[Handoff], UniversalCart], Any]


async def approve(run_id: str, plan_id: str, acknowledged: Collection[str] = (), *, sign: Signer,
                  ctx: CartContext | None = None) -> ApprovalResult:
    """The whole of POST /approve for B's part, in order (PLAN §3.1):

    gate (prices, assumptions, budget, plan id) -> one-time token -> create_carts -> `sign(handoffs, draft_cart)`
    (A/D build and sign the closed mandate; return it as a dict or model) -> lock the cart.
    If signing fails the carts just created are cancelled and the cart stays a draft.
    """
    cart_mod.assert_approvable(run_id, plan_id, acknowledged, ctx)
    draft = cart_mod.build_cart(run_id, ctx)
    token = issue_approval_token(run_id, plan_id, ctx)
    handoffs = await create_carts(run_id, plan_id, token, ctx)
    try:
        closed = sign(handoffs, draft)
        if hasattr(closed, "__await__"):
            closed = await closed
    except Exception:
        await discard_pending(run_id)
        raise
    body = closed.model_dump() if hasattr(closed, "model_dump") else dict(closed or {})
    from app.stores.base import canonical

    closed_sha = sha256_hex(canonical(body)) if body else None  # the signed closed mandate, as returned by the signer
    cart = cart_mod.mark_approved(run_id, closed_mandate_sha256=closed_sha, ctx=ctx)
    return ApprovalResult(closed_mandate=closed, cart=cart, handoffs=handoffs)


# --------------------------------------------------------------------------- the guided checkout run


_TRANSITIONS = {
    "ready": {"opened", "done", "skipped"},
    "opened": {"opened", "done", "skipped", "ready"},
    "done": {"ready", "skipped", "opened"},
    "skipped": {"ready", "done", "opened"},
}


def update_handoff(run_id: str, store_id: str, state: str, done_via: str | None = None, order_id: str | None = None) -> UniversalCart:
    """POST /cart/handoff: opened | done | skipped | ready (ready = undo). Each change is a chain record."""
    rec = BOOK.get(run_id)
    if rec.state == "draft":
        raise CartError(409, "approval_required", "Approve the cart before opening a store")
    hs = rec.handoffs.get(store_id)
    if hs is None:
        raise CartError(404, "store_not_in_cart", f"{store_id} is not in this cart")
    if state not in _TRANSITIONS:
        raise CartError(422, "bad_state", f"Unknown hand-off state {state!r}")
    if hs.state in ("done", "skipped") and state == "opened":
        return cart_mod.build_cart(run_id)  # re-opening a finished store's page changes nothing
    if state not in _TRANSITIONS[hs.state]:
        raise CartError(409, "bad_transition", f"Cannot go from {hs.state} to {state}")
    if order_id is not None and not _ORDER_ID.match(order_id):
        raise CartError(422, "bad_order_id", "An order id is letters, digits, # _ - only (no buyer details)")
    prev = hs.state
    hs.state = state
    hs.done_via = (done_via or "user") if state == "done" else None
    hs.order_id = order_id if state == "done" else None
    hs.history.append({"state": state, "at": now_iso(), "from": prev})
    run_state_before = rec.state
    cart_mod.sync_state(rec)
    name = store_registry.display_name(store_id)
    h = emit_record(run_id, "handoff", {"store_id": store_id, "action_level": hs.handoff.action_level, "state": state, "previous": prev,
                                        "done_via": hs.done_via, "order_id": hs.order_id, "by": "user"})
    if state == "opened":
        emit_event(run_id, "handoff.opened", f"Opened {name}", store_id=store_id, record_hash=h)
    elif state == "done":
        emit_event(run_id, "handoff.done", f"{name} marked bought by you", severity="ok", store_id=store_id, record_hash=h,
                   data={"done_via": hs.done_via, "subtotal_usd": hs.handoff.subtotal_usd})
    elif state == "skipped":
        emit_event(run_id, "handoff.done", f"Skipped {name}", store_id=store_id, record_hash=h, data={"skipped": True})
    else:
        emit_event(run_id, "handoff.opened", f"Undo: {name} is back in the run", store_id=store_id, record_hash=h, data={"undo": prev})
    cart = cart_mod.build_cart(run_id)
    if rec.state == "complete" and run_state_before != "complete":
        bought = [{"store_id": g.store_id, "items": [{"bom_line_id": i.bom_line_id, "title": i.title, "qty": i.qty} for i in g.items]}
                  for g in cart.stores if g.handoff and g.handoff.state == "done"]
        emit_event(run_id, "run.done", "Run complete", severity="ok",
                   data={"bought_usd": cart.bought_usd, "remaining_usd": cart.remaining_usd, "stores_done": cart.counts.done})
        if cart_mod.HOOKS.on_complete is not None:
            cart_mod.HOOKS.on_complete(run_id, bought)
    return cart


_ = Awaitable  # re-exported type for A's signer callbacks
