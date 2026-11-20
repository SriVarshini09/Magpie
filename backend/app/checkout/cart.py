"""The Universal Cart: the cart of record, grouped by store, and its state machine (PLAN §12.3). Owner: B.

    draft --approve--> approved --first hand-off opened--> checking_out --every store done/skipped--> complete
      ^                   |                                    |
      +---- reopen() -----+------------------------------------+   ("Edit cart": cancels the open Shopify carts)

- Groups are in run order: agent carts, then prefilled carts, then product links; largest subtotal first.
- A store's level only goes down from what its offers carry (PLAN §3.16 rule 2); the reason is kept.
- Edits (draft only) are validated here, then re-optimized by A through the `replanner` hook, with the
  edit kept as a pin (PLAN §3.10). Each edit is a `cart_edit` record.
- After approval the cart is a frozen snapshot; only hand-off and Tier 2 test states change.

B does not own the run state. A registers a `context` hook that returns a CartContext for a run (the
active plan, every offer found in the run, the BOM, the budget, the open assumptions); see `configure`.
Records and events go through hooks too (D's chain, A's SSE); without them they are kept on the record.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.models import (
    BOMLine, CartCounts, CartEditRequest, CartHandoff, CartItem, CartPlan, Handoff, LeftOut, Offer, PriceChange,
    PriceChanged, StoreGroup, StoreTest, TestPayment, UniversalCart,
)
from app.stores import registry as store_registry
from app.stores.base import ACTION_RANK, now, now_iso, parse_ts

ITEM_ID_KEYS = ("variant_gid", "asin", "walmart_id", "bestbuy_sku", "digikey_pn", "ebay_item", "sku")


class CartError(Exception):
    """An HTTP-shaped error for A's routes: `detail()` is the ApiError body (PLAN §4.2, OWNERSHIP decision 6)."""

    def __init__(self, status: int, error: str, message: str, *, refusal: dict[str, Any] | None = None,
                 bom_line_ids: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.status, self.error, self.message = status, error, message
        self.refusal, self.bom_line_ids = refusal, list(bom_line_ids)

    def detail(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": self.error, "message": self.message, "bom_line_ids": self.bom_line_ids}
        if self.refusal:
            body["refusal"] = self.refusal
        return body


def refusal(rule: str, clause: str, *, tool: str, field_: str | None = None, value: str | None = None,
            triggered_by: str = "user_edit") -> dict[str, Any]:
    attempted = {k: v for k, v in {"tool": tool, "field": field_, "value": value}.items() if v is not None}
    return {"kind": "refusal", "rule": rule, "attempted": attempted, "clause": clause, "triggered_by": triggered_by, "ts": now_iso()}


# --------------------------------------------------------------------------- inputs and state


@dataclass
class CartContext:
    """What A hands B to build a run's cart (from RunState and the offers found in the run)."""

    run_id: str
    plan: CartPlan
    offers: Mapping[str, Offer]  # every offer found in this run, by offer_id
    bom: Sequence[BOMLine]
    budget_usd: float
    open_assumptions: Sequence[str] = ()
    line_offers: Mapping[str, Sequence[str]] = field(default_factory=dict)  # bom_line_id -> offer ids found for it
    rejected: Mapping[str, str] = field(default_factory=dict)  # offer_id -> reason ("R2: 2 A < 5 A")
    allowed_merchants: Sequence[str] = ()
    edited_lines: Collection[str] = ()


@dataclass
class CartPins:
    """Edits the optimizer must respect (PLAN §3.10 pins). Kept across edits until the cart is approved."""

    swap_in: dict[str, str] = field(default_factory=dict)  # bom_line_id -> offer_id the user picked
    swap_out: set[str] = field(default_factory=set)  # offer ids the user swapped away from
    qty: dict[str, int] = field(default_factory=dict)  # bom_line_id -> quantity set by the user
    removed: dict[str, str] = field(default_factory=dict)  # bom_line_id -> "removed_by_you" | "owned"

    def as_dict(self) -> dict[str, Any]:
        return {"swap_in": dict(self.swap_in), "swap_out": sorted(self.swap_out), "qty": dict(self.qty), "removed": dict(self.removed)}

    def edited_lines(self) -> set[str]:
        return set(self.swap_in) | set(self.qty) | set(self.removed)


@dataclass
class HandoffState:
    handoff: Handoff
    state: str = "ready"  # ready | opened | done | skipped
    done_via: str | None = None
    order_id: str | None = None
    downgrade_reason: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CartRecord:
    run_id: str
    state: str = "draft"
    plan_id: str | None = None
    snapshot: UniversalCart | None = None  # the approved cart, frozen
    approved_at: str | None = None
    closed_mandate_sha256: str | None = None
    handoffs: dict[str, HandoffState] = field(default_factory=dict)
    pending: dict[str, HandoffState] = field(default_factory=dict)  # created by create_carts, not yet approved
    overrides: dict[str, Offer] = field(default_factory=dict)  # offers re-read by the price refresh
    changed_old: dict[str, float] = field(default_factory=dict)  # offer_id -> price before the refresh
    price_changes: list[PriceChange] = field(default_factory=list)
    prices_version: int = 0
    viewed_version: int = 0
    last_refresh_at: str | None = None
    unrefreshable: dict[str, str] = field(default_factory=dict)  # offer_id -> why it was not re-read
    pins: CartPins = field(default_factory=CartPins)
    added: dict[str, bool] = field(default_factory=dict)  # offer_id -> product-link "added" tick
    test: dict[str, StoreTest] = field(default_factory=dict)
    test_payment: TestPayment | None = None
    payment: dict[str, Any] = field(default_factory=dict)  # Tier 2 session (checkout/stripe_test.py)
    tokens: dict[str, dict[str, Any]] = field(default_factory=dict)  # approval token sha256 -> binding
    records: list[dict[str, Any]] = field(default_factory=list)  # fallback when no chain hook is set
    events: list[dict[str, Any]] = field(default_factory=list)  # fallback when no event hook is set


class CartBook:
    """In-memory cart records by run. A run's cart record lives as long as the process (like RunState)."""

    def __init__(self) -> None:
        self._recs: dict[str, CartRecord] = {}

    def get(self, run_id: str) -> CartRecord:
        if run_id not in self._recs:
            self._recs[run_id] = CartRecord(run_id)
        return self._recs[run_id]

    def drop(self, run_id: str) -> None:
        self._recs.pop(run_id, None)

    def clear(self) -> None:
        self._recs.clear()


BOOK = CartBook()

Replanner = Callable[[str, dict[str, Any]], "CartPlan | Awaitable[CartPlan]"]


@dataclass
class Hooks:
    context: Callable[[str], CartContext] | None = None  # A: run_id -> CartContext
    replanner: Replanner | None = None  # A: (run_id, pins) -> the re-optimized CartPlan (no network)
    record: Callable[[str, str, dict[str, Any]], Any] | None = None  # D: (run_id, kind, body) -> chain record or hash
    event: Callable[[str, dict[str, Any]], Any] | None = None  # A: (run_id, event body) -> SSE
    on_complete: Callable[[str, list[dict[str, Any]]], Any] | None = None  # A/D: (run_id, bought) -> memory write


HOOKS = Hooks()


def configure(**hooks: Any) -> None:
    """A calls this once at startup: configure(context=..., replanner=..., record=..., event=..., on_complete=...)."""
    for name, fn in hooks.items():
        if not hasattr(HOOKS, name):
            raise TypeError(f"unknown cart hook {name!r}")
        setattr(HOOKS, name, fn)


def context(run_id: str, ctx: CartContext | None = None) -> CartContext:
    if ctx is not None:
        return ctx
    if HOOKS.context is None:
        raise CartError(501, "not_implemented", "No cart context provider is registered (A: checkout.cart.configure(context=...))")
    return HOOKS.context(run_id)


def emit_record(run_id: str, kind: str, body: dict[str, Any]) -> str | None:
    """Append a chain record through D's chain (hook, else audit.chain.append, else kept on the cart record)."""
    rec = BOOK.get(run_id)
    payload = {**body, "ts": body.get("ts") or now_iso()}
    try:
        if HOOKS.record is not None:
            out = HOOKS.record(run_id, kind, payload)
        else:
            from app.audit import chain

            out = chain.append(run_id, kind, payload)
    except NotImplementedError:
        out = None
    rec.records.append({"kind": kind, **payload})
    if isinstance(out, dict):
        return out.get("hash")
    return out if isinstance(out, str) else None


def emit_event(run_id: str, type_: str, title: str, *, severity: str = "info", store_id: str | None = None,
               bom_line_id: str | None = None, provider: str | None = None, simulated: bool | None = None,
               record_hash: str | None = None, detail: str | None = None, data: dict[str, Any] | None = None) -> None:
    ev = {k: v for k, v in {"ts": now_iso(), "severity": severity, "type": type_, "title": title, "detail": detail,
                             "store_id": store_id, "bom_line_id": bom_line_id, "provider": provider, "simulated": simulated,
                             "record_hash": record_hash, "data": data}.items() if v is not None}
    BOOK.get(run_id).events.append(ev)
    if HOOKS.event is not None:
        HOOKS.event(run_id, ev)


# --------------------------------------------------------------------------- building the cart


def _item_ids(offer: Offer) -> dict[str, str]:
    return {k: v for k, v in offer.ids.items() if k in ITEM_ID_KEYS}


def _group_level(store_id: str, rows: list[tuple[Any, Offer]]) -> tuple[str, str | None]:
    """The weakest level any of the store's offers carries, then the store-wide link checks."""
    level, reason = "agent_cart", None
    for _, offer in rows:
        new = store_registry.lower(level, offer.action_level)
        if new != level:
            level, reason = new, offer.downgrade_reason
    if level == "agent_cart" and any(not o.ids.get("variant_gid") for _, o in rows):
        return "product_link", store_registry.REASON_NO_VARIANT
    if level == "prefilled_cart":
        from app import registry as services
        from app.stores.cartlinks import ID_KEYS

        key = ID_KEYS.get(store_id)
        items = [(o.ids.get(key or "", ""), int(pl.packs)) for pl, o in rows]
        link = services.get("cartlinks").link(store_id, items)
        if link.action_level != "prefilled_cart":
            return "product_link", link.downgrade_reason
    return level, reason


def _live_offer(rec: CartRecord, ctx: CartContext, offer_id: str) -> Offer:
    offer = rec.overrides.get(offer_id) or ctx.offers.get(offer_id)
    if offer is None:
        raise CartError(409, "unknown_offer", f"The plan names offer {offer_id}, which this run never found",
                        refusal=refusal("unknown_offer", "PLAN §3.6: only offers returned by search_offers", tool="build_cart", value=offer_id))
    return offer


def _left_out(ctx: CartContext, rec: CartRecord) -> list[LeftOut]:
    planned = {pl.bom_line_id for pl in ctx.plan.lines}
    out = []
    for ln in ctx.bom:
        if ln.bom_line_id in planned:
            continue
        pinned = rec.pins.removed.get(ln.bom_line_id)
        if pinned:
            out.append(LeftOut(bom_line_id=ln.bom_line_id, name=ln.raw_name, reason=pinned, note=ln.owned_note))
        elif ln.status == "owned":
            out.append(LeftOut(bom_line_id=ln.bom_line_id, name=ln.raw_name, reason="owned", note=ln.owned_note))
        elif ln.status == "removed":
            out.append(LeftOut(bom_line_id=ln.bom_line_id, name=ln.raw_name, reason="removed_by_you"))
        elif ln.category == "printed":
            out.append(LeftOut(bom_line_id=ln.bom_line_id, name=ln.raw_name, reason="print_at_home", note=ln.owned_note))
        elif ln.status == "not_found":
            out.append(LeftOut(bom_line_id=ln.bom_line_id, name=ln.raw_name, reason="not_found"))
    return out


def _alternatives(ctx: CartContext, bom_line_id: str, chosen: set[str]) -> int:
    n = 0
    for oid in ctx.line_offers.get(bom_line_id, ()):
        o = ctx.offers.get(oid)
        if o is None or oid in chosen or o.refused or oid in ctx.rejected:
            continue
        n += 1
    return n


def _oldest(seen: list[str]) -> str:
    stamps = [(parse_ts(s), s) for s in seen if parse_ts(s) is not None]
    return min(stamps)[1] if stamps else now_iso()


def _build_draft(ctx: CartContext, rec: CartRecord) -> UniversalCart:
    by_store: dict[str, list[tuple[Any, Offer]]] = {}
    for pl in ctx.plan.lines:
        offer = _live_offer(rec, ctx, pl.offer_id)
        by_store.setdefault(offer.store_id, []).append((pl, offer))
    chosen_by_line: dict[str, set[str]] = {}
    for pl in ctx.plan.lines:
        chosen_by_line.setdefault(pl.bom_line_id, set()).add(pl.offer_id)
    edited = set(ctx.edited_lines) | rec.pins.edited_lines()
    groups: list[StoreGroup] = []
    for store_id, rows in by_store.items():
        items = []
        for pl, o in rows:
            packs = int(pl.packs)
            items.append(CartItem(
                bom_line_id=pl.bom_line_id, offer_id=o.offer_id, title=o.title, qty=packs * o.units_per_pack, packs=packs,
                unit_price_usd=o.price_usd, line_usd=round(packs * o.price_usd, 2), seen_at=o.seen_at, source_api=o.source_api,
                url=o.url, added=rec.added.get(o.offer_id) if o.offer_id in rec.added else None,
                changed=PriceChanged(old_usd=rec.changed_old[o.offer_id]) if o.offer_id in rec.changed_old else None,
                edited_by_user=True if pl.bom_line_id in edited else None,
                alternatives=_alternatives(ctx, pl.bom_line_id, chosen_by_line.get(pl.bom_line_id, set())),
                simulated=o.simulated))
        level, reason = _group_level(store_id, rows)
        first = rows[0][1]
        groups.append(StoreGroup(
            store_id=store_id, display_name=store_registry.display_name(store_id, first.store_name),
            domain=store_registry.domain(store_id, first.url), action_level=level, downgrade_reason=reason, order=0,
            subtotal_usd=round(sum(i.line_usd for i in items), 2), items=items))
    groups.sort(key=lambda g: (ACTION_RANK[g.action_level], -g.subtotal_usd, g.store_id))
    for i, g in enumerate(groups, 1):
        g.order = i
    all_items = [i for g in groups for i in g.items]
    total = round(sum(g.subtotal_usd for g in groups), 2)
    simulated = bool(all_items) and all(i.simulated for i in all_items)
    return UniversalCart(
        run_id=ctx.run_id, state="draft", plan_id=ctx.plan.plan_id, tier=ctx.plan.tier, editable=True, total_usd=total,
        budget_usd=ctx.budget_usd, bought_usd=0.0, remaining_usd=total,
        prices_checked_at=_oldest([i.seen_at for i in all_items]), price_changes=list(rec.price_changes),
        counts=CartCounts(stores=len(groups), done=0,
                          agent_cart=sum(g.action_level == "agent_cart" for g in groups),
                          prefilled_cart=sum(g.action_level == "prefilled_cart" for g in groups),
                          product_link=sum(g.action_level == "product_link" for g in groups),
                          items_by_hand=sum(len(g.items) for g in groups if g.action_level == "product_link")),
        stores=groups, left_out=_left_out(ctx, rec), open_assumptions=list(ctx.open_assumptions), current_store_id=None,
        test_payment=None, source_api="mock" if simulated else None, simulated=simulated or any(i.simulated for i in all_items))


def _with_live_state(rec: CartRecord) -> UniversalCart:
    """The frozen approved cart, with the current hand-off and Tier 2 test states."""
    cart = rec.snapshot.model_copy(deep=True)  # type: ignore[union-attr]
    for g in cart.stores:
        hs = rec.handoffs.get(g.store_id)
        if hs is not None:
            h = hs.handoff
            g.action_level = h.action_level
            g.downgrade_reason = hs.downgrade_reason
            g.handoff = CartHandoff(kind=h.action_level, url=h.url, cart_id=h.cart_id, caveat=h.caveat, url_sha256=h.url_sha256,
                                    state=hs.state, done_via=hs.done_via, order_id=hs.order_id, simulated=h.simulated)
        if g.store_id in rec.test:
            g.test = rec.test[g.store_id]
        for it in g.items:
            if it.offer_id in rec.added:
                it.added = rec.added[it.offer_id]
    done = [g for g in cart.stores if g.handoff and g.handoff.state == "done"]
    pending = [g for g in cart.stores if not g.handoff or g.handoff.state not in ("done", "skipped")]
    cart.state = rec.state  # type: ignore[assignment]
    cart.editable = False
    cart.bought_usd = round(sum(g.subtotal_usd for g in done), 2)
    cart.remaining_usd = round(cart.total_usd - cart.bought_usd, 2)
    cart.counts.done = len(done)
    cart.current_store_id = pending[0].store_id if pending else None
    cart.counts.agent_cart = sum(g.action_level == "agent_cart" for g in cart.stores)
    cart.counts.prefilled_cart = sum(g.action_level == "prefilled_cart" for g in cart.stores)
    cart.counts.product_link = sum(g.action_level == "product_link" for g in cart.stores)
    cart.counts.items_by_hand = sum(len(g.items) for g in cart.stores if g.action_level == "product_link")
    cart.test_payment = rec.test_payment
    return cart


def build_cart(run_id: str, ctx: CartContext | None = None) -> UniversalCart:
    """The run's Universal Cart. Draft: built from the active plan. Approved and later: the frozen snapshot."""
    rec = BOOK.get(run_id)
    if rec.state != "draft" and rec.snapshot is not None:
        return _with_live_state(rec)
    return _build_draft(context(run_id, ctx), rec)


def get_cart(run_id: str, ctx: CartContext | None = None) -> UniversalCart:
    """GET /api/runs/{id}/cart. Also marks the current prices as seen (Approve needs that, PLAN §12.3)."""
    cart = build_cart(run_id, ctx)
    BOOK.get(run_id).viewed_version = BOOK.get(run_id).prices_version
    return cart


def part_names(ctx: CartContext) -> dict[str, str]:
    return {ln.bom_line_id: ln.raw_name for ln in ctx.bom}


# --------------------------------------------------------------------------- editing (draft only; P13)


def _assert_draft(rec: CartRecord) -> None:
    if rec.state != "draft":
        raise CartError(409, "cart_locked", "An approved cart is locked. Edit cart returns it to draft.")


def _check_offer(ctx: CartContext, bom_line_id: str, offer_id: str) -> Offer:
    offer = ctx.offers.get(offer_id)
    if offer is None or (ctx.line_offers and offer_id not in ctx.line_offers.get(bom_line_id, ())):
        raise CartError(409, "unknown_offer", "Only offers found in this run for this part can go in the cart",
                        refusal=refusal("unknown_offer", "PLAN §12.3: only offers found in this run", tool="cart_edit", value=offer_id),
                        bom_line_ids=[bom_line_id])
    allowed = set(ctx.allowed_merchants)
    if offer.refused or (allowed and offer.store_id not in allowed):
        raise CartError(409, "merchant_not_allowed", f"{offer.store_name} is not in your signed mandate",
                        refusal=refusal("merchant_allowed", "constraints.allowed_merchants", tool="cart_edit", value=offer.store_id),
                        bom_line_ids=[bom_line_id])
    if offer_id in ctx.rejected:
        raise CartError(409, "compatibility_rejected", f"This offer failed a compatibility rule: {ctx.rejected[offer_id]}",
                        bom_line_ids=[bom_line_id])
    return offer


async def apply_edit(run_id: str, req: CartEditRequest, ctx: CartContext | None = None) -> UniversalCart:
    """POST /cart/edit: validate, pin, re-optimize through A's replanner, record `cart_edit`, return the new cart."""
    rec = BOOK.get(run_id)
    _assert_draft(rec)
    ctx = context(run_id, ctx)
    line = next((ln for ln in ctx.bom if ln.bom_line_id == req.bom_line_id), None)
    if line is None:
        raise CartError(404, "line_not_found", f"No BOM line {req.bom_line_id} in this run")
    before = {"plan_id": ctx.plan.plan_id, "total_usd": ctx.plan.total_usd,
              "lines": [pl.model_dump() for pl in ctx.plan.lines if pl.bom_line_id == req.bom_line_id]}
    pins = rec.pins
    if req.op == "swap_offer":
        if not req.offer_id:
            raise CartError(422, "offer_required", "swap_offer needs offer_id")
        _check_offer(ctx, req.bom_line_id, req.offer_id)
        for pl in ctx.plan.lines:
            if pl.bom_line_id == req.bom_line_id and pl.offer_id != req.offer_id:
                pins.swap_out.add(pl.offer_id)
        pins.swap_out.discard(req.offer_id)
        pins.swap_in[req.bom_line_id] = req.offer_id
    elif req.op == "move_store":
        if not req.store_id:
            raise CartError(422, "store_required", "move_store needs store_id")
        candidates = []
        for oid in ctx.line_offers.get(req.bom_line_id, ()):
            o = ctx.offers.get(oid)
            if o is None or o.store_id != req.store_id:
                continue
            try:
                _check_offer(ctx, req.bom_line_id, oid)
            except CartError:
                continue
            if o.stock != "out_of_stock":
                packs = -(-line.qty // max(o.units_per_pack, 1))
                candidates.append((packs * o.price_usd, oid))
        if not candidates:
            raise CartError(409, "no_valid_offer", f"No valid offer for this part at {store_registry.display_name(req.store_id)}",
                            bom_line_ids=[req.bom_line_id])
        best = min(candidates)[1]
        pins.swap_in[req.bom_line_id] = best
        pins.swap_out.discard(best)
    elif req.op == "remove":
        pins.removed[req.bom_line_id] = "removed_by_you"
    elif req.op == "restore":
        pins.removed.pop(req.bom_line_id, None)
    elif req.op == "set_qty":
        if req.qty is None or req.qty < 1 or req.qty > 999:
            raise CartError(422, "bad_qty", "Quantity must be between 1 and 999")
        pins.qty[req.bom_line_id] = req.qty
    if HOOKS.replanner is None:
        raise CartError(501, "not_implemented", "No replanner is registered (A: pipeline/optimize.py with pins)")
    plan = HOOKS.replanner(run_id, pins.as_dict())
    if hasattr(plan, "__await__"):
        plan = await plan  # type: ignore[misc]
    new_ctx = context(run_id) if HOOKS.context is not None else CartContext(**{**ctx.__dict__, "plan": plan})
    after = {"plan_id": plan.plan_id, "total_usd": plan.total_usd,
             "lines": [pl.model_dump() for pl in plan.lines if pl.bom_line_id == req.bom_line_id]}
    warn = None
    if req.op == "set_qty" and req.qty is not None and req.qty < line.qty:
        warn = f"The project needs {line.qty}"
    h = emit_record(run_id, "cart_edit", {"op": req.op, "bom_line_id": req.bom_line_id, "offer_id": req.offer_id,
                                          "store_id": req.store_id, "qty": req.qty, "before": before, "after": after, "by": "user"})
    emit_event(run_id, "cart.edited", f"Cart edited: {req.op.replace('_', ' ')} on {line.raw_name}", severity="warn" if warn else "info",
               bom_line_id=req.bom_line_id, record_hash=h, detail=warn,
               data={"op": req.op, "total_before": before["total_usd"], "total_after": after["total_usd"]})
    return build_cart(run_id, new_ctx)


def set_item_added(run_id: str, offer_id: str, added: bool) -> UniversalCart:
    """The per-item "added" tick on a product-link store (PLAN §12.3). A UI action, recorded."""
    rec = BOOK.get(run_id)
    rec.added[offer_id] = bool(added)
    emit_record(run_id, "cart_action", {"action": "item_added" if added else "item_unticked", "offer_id": offer_id, "by": "user"})
    return build_cart(run_id)


async def reopen(run_id: str) -> UniversalCart:
    """"Edit cart" on an approved cart: cancel the open Shopify carts, back to draft, a new approval is needed.

    The closed mandate is never edited; the next approval signs a new one (PLAN §3.7).
    """
    rec = BOOK.get(run_id)
    if rec.state == "draft":
        return build_cart(run_id)
    if rec.state == "complete":
        raise CartError(409, "run_complete", "This checkout run is complete. Start a new run to change the cart.")
    from app import registry as services

    shopify = services.get("shopify_ucp")
    cancelled, failed = [], []
    for store_id, hs in {**rec.handoffs, **rec.pending}.items():
        h = hs.handoff
        if h.action_level == "agent_cart" and h.cart_id and hs.state != "done":
            business = next((i.ids.get("business_url") for i in h.items if i.ids.get("business_url")), None)
            try:
                await shopify.cancel_cart(h.cart_id, business or (store_registry.store(store_id) or {}).get("business_url"))
                cancelled.append(store_id)
            except Exception:  # a cart we cannot cancel expires on its own after 30 days (App. A.1)
                failed.append(store_id)
    prior = rec.closed_mandate_sha256
    rec.state, rec.snapshot, rec.handoffs, rec.pending = "draft", None, {}, {}
    rec.approved_at, rec.closed_mandate_sha256, rec.test, rec.test_payment, rec.payment = None, None, {}, None, {}
    h = emit_record(run_id, "cart_action", {"action": "reopen", "cancelled_carts": cancelled, "cancel_failed": failed,
                                            "closed_mandate_sha256": prior, "by": "user"})
    emit_event(run_id, "cart.edited", "Cart back to draft: approve again to get new hand-offs", record_hash=h,
               data={"cancelled": cancelled, "cancel_failed": failed})
    return build_cart(run_id)


# --------------------------------------------------------------------------- approval gate (PLAN §12.3)


def _is_replay() -> bool:
    return get_settings().demo_mode == "replay"


def _age_min(seen_at: str, at: datetime) -> float:
    ts = parse_ts(seen_at)
    return 0.0 if ts is None else max(0.0, (at - ts).total_seconds() / 60.0)


def approval_blockers(run_id: str, plan_id: str, acknowledged: Collection[str] = (), ctx: CartContext | None = None) -> list[CartError]:
    """Why Approve is disabled right now (empty list: it is enabled). The UI shows the same reasons."""
    rec = BOOK.get(run_id)
    if rec.state != "draft":
        return [CartError(409, "already_approved", "This cart is already approved. Edit cart returns it to draft.")]
    ctx = context(run_id, ctx)
    out: list[CartError] = []
    if plan_id != ctx.plan.plan_id:
        out.append(CartError(409, "stale_plan", "The cart changed since you last saw it. Review it again.",
                             refusal=refusal("approval_required", "PLAN §12.3: approve the plan you saw", tool="approve", value=plan_id,
                                             triggered_by="agent")))
    if ctx.open_assumptions:
        lines = list(ctx.open_assumptions)
        out.append(CartError(409, "assumption_unconfirmed", f"Confirm {len(lines)} assumption{'s' if len(lines) != 1 else ''} first",
                             refusal=refusal("assumption_unconfirmed", "PLAN §3.18: Approve is refused while an assumption is open",
                                             tool="approve", triggered_by="agent"), bom_line_ids=lines))
    cart = _build_draft(ctx, rec)
    if cart.total_usd > ctx.budget_usd + 1e-6:
        out.append(CartError(409, "over_budget", f"The cart is ${cart.total_usd - ctx.budget_usd:.2f} over the signed budget",
                             refusal=refusal("budget", "constraints.budget_usd", tool="approve", triggered_by="agent")))
    if not _is_replay():
        max_age = get_settings().price_max_age_min
        at = now()
        refreshed_recently = rec.last_refresh_at is not None and _age_min(rec.last_refresh_at, at) <= max_age
        stale = []
        for g in cart.stores:
            for it in g.items:
                if _age_min(it.seen_at, at) <= max_age:
                    continue
                excused = it.offer_id in rec.unrefreshable and refreshed_recently and "stale_price" in acknowledged
                if not excused:
                    stale.append(it.bom_line_id)
        if stale:
            out.append(CartError(409, "stale_price", f"Some prices are older than {max_age} minutes. Refresh prices first.",
                                 refusal=refusal("stale_price", f"PRICE_MAX_AGE_MIN={max_age} (PLAN §12.3)", tool="approve",
                                                 triggered_by="agent"), bom_line_ids=sorted(set(stale))))
        if rec.prices_version != rec.viewed_version and "price_changes" not in acknowledged:
            out.append(CartError(409, "price_changed", "Prices changed since you last looked at the cart. Review the changes first.",
                                 refusal=refusal("stale_price", "PLAN §12.3: a price change must be seen before Approve", tool="approve",
                                                 triggered_by="store_listing"),
                                 bom_line_ids=sorted({c.offer_id for c in rec.price_changes})))
    return out


def assert_approvable(run_id: str, plan_id: str, acknowledged: Collection[str] = (), ctx: CartContext | None = None) -> None:
    blockers = approval_blockers(run_id, plan_id, acknowledged, ctx)
    if blockers:
        raise blockers[0]


def mark_approved(run_id: str, *, closed_mandate_sha256: str | None = None, ctx: CartContext | None = None) -> UniversalCart:
    """Lock the cart: the hand-offs from create_carts become the run's, the draft becomes a frozen snapshot."""
    rec = BOOK.get(run_id)
    if rec.state != "draft":
        raise CartError(409, "already_approved", "This cart is already approved")
    if not rec.pending:
        raise CartError(409, "approval_required", "create_carts has not run for this approval")
    ctx = context(run_id, ctx)
    rec.snapshot = _build_draft(ctx, rec)
    rec.handoffs, rec.pending = rec.pending, {}
    rec.state, rec.plan_id, rec.approved_at = "approved", ctx.plan.plan_id, now_iso()
    rec.closed_mandate_sha256 = closed_mandate_sha256
    return _with_live_state(rec)


def sync_state(rec: CartRecord) -> str:
    """approved -> checking_out -> complete, from the hand-off states (undo moves back)."""
    if rec.state == "draft" or not rec.handoffs:
        return rec.state
    states = [hs.state for hs in rec.handoffs.values()]
    if all(s in ("done", "skipped") for s in states):
        rec.state = "complete"
    elif any(s != "ready" for s in states):
        rec.state = "checking_out"
    else:
        rec.state = "approved"
    return rec.state
