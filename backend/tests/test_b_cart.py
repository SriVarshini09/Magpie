"""Universal Cart (PLAN §12.3): build, run order, the approval gate, edits through A's replanner, hand-offs,
the guided checkout run (done / skip / undo, bought and remaining), reopen, price refresh and CSV."""

from __future__ import annotations

import asyncio
import csv
import io

import pytest
from b_support import b_env, offer, set_mode  # noqa: F401

from app.checkout import cart as cart_mod
from app.checkout import handoff, refresh
from app.checkout.cart import BOOK, CartContext, CartError
from app.checkout.export import cart_csv, export_csv
from app.models import BOMLine, CartEditRequest, CartPlan, PlanLine
from app.stores.base import RefreshSkipped, now_iso

RUN = "r_cart_test"
GID = "gid://shopify/ProductVariant/"


def prov(name: str) -> dict:
    return {"type": "assumption", "statement": name, "basis": "test", "confirmed_by_user": True}


def bom() -> list[BOMLine]:
    rows = [("b1", "STS3215 servo 12V", 6, "part", "offers", None, None), ("b2", "Bus servo adapter", 1, "part", "offers", None, None),
            ("b3", "USB-C cable", 2, "part", "owned", "cable", "owns two"), ("b4", "12V 5A PSU", 1, "part", "chosen", "power", None),
            ("b5", "Table clamp", 2, "part", "chosen", "mechanical", None), ("b6", "Screwdriver set", 1, "tool", "owned", "tool", "owns one"),
            ("b7", "3D-printed parts (11)", 1, "part", "skipped", "printed", "owns a printer")]
    return [BOMLine(bom_line_id=i, raw_name=n, qty=q, provenance=prov(n), line_kind=k, status=s, category=c, owned_note=note)
            for i, n, q, k, s, c, note in rows]


def offers(seen: str) -> dict:
    o = [
        offer("w5", "wowrobo", 74.95, units=5, ids={"variant_gid": GID + "48037575065817", "seller_domain": "f0c6d4-21.myshopify.com"}, seen_at=seen),
        offer("w1", "wowrobo", 15.99, ids={"variant_gid": GID + "48037575033049", "seller_domain": "f0c6d4-21.myshopify.com"}, seen_at=seen),
        offer("a1", "armdojo", 11.99, ids={"variant_gid": GID + "50874126958831"}, seen_at=seen),
        offer("g1", "geekworm", 17.00, ids={"variant_gid": GID + "1234"}, seen_at=seen),
        offer("ada352", "adafruit", 24.95, level="product_link", source_api="adafruit", ids={"sku": "352"}, seen_at=seen, title="=HYPERLINK(evil)"),
        offer("amz1", "amazon", 12.48, level="prefilled_cart", source_api="serpapi:amazon", ids={"asin": "B0CLAMP001"}, seen_at=seen,
              url="https://www.amazon.com/dp/B0CLAMP001"),
        offer("ali1", "alibaba.com", 3.00, level="product_link", source_api="serpapi:google_shopping", refused="merchant_not_in_mandate", seen_at=seen),
        offer("seeed2a", "seeed", 7.00, level="product_link", source_api="magento", ids={"sku": "x"}, seen_at=seen),
    ]
    return {x.offer_id: x for x in o}


def plan(lines: list[tuple[str, str, str, int, int, float]], plan_id: str = "p1") -> CartPlan:
    pls = [PlanLine(bom_line_id=b, offer_id=o, store_id=s, packs=p, qty=q, line_usd=u) for b, o, s, p, q, u in lines]
    stores = sorted({pl.store_id for pl in pls})
    return CartPlan(plan_id=plan_id, tier="cheapest", total_usd=round(sum(pl.line_usd for pl in pls), 2), stores=stores, checkouts=len(stores),
                    by_level={"agent_cart": 3, "prefilled_cart": 1, "product_link": 0}, items_by_hand=0, feasible=True, plan_sha256="ab" * 32, lines=pls)


BASE_LINES = [("b1", "w5", "wowrobo", 1, 5, 74.95), ("b1", "w1", "wowrobo", 1, 1, 15.99), ("b2", "a1", "armdojo", 1, 1, 11.99),
              ("b4", "g1", "geekworm", 1, 1, 17.0), ("b5", "amz1", "amazon", 1, 2, 12.48)]


@pytest.fixture()
def run(b_env):
    state = {"ctx": CartContext(run_id=RUN, plan=plan(BASE_LINES), offers=offers(now_iso()), bom=bom(), budget_usd=160.0,
                                line_offers={"b1": ["w5", "w1"], "b2": ["a1"], "b4": ["g1", "ada352", "ali1", "seeed2a"], "b5": ["amz1"]},
                                rejected={"seeed2a": "R2: 2 A < 5 A"}, allowed_merchants=["wowrobo", "armdojo", "geekworm", "amazon", "adafruit", "seeed"])}
    calls = []

    def replanner(run_id, pins):
        calls.append(pins)
        ctx = state["ctx"]
        lines = [ln for ln in BASE_LINES if ln[0] not in pins["removed"]]
        for b, oid in pins["swap_in"].items():
            o = ctx.offers[oid]
            lines = [ln for ln in lines if ln[0] != b] + [(b, oid, o.store_id, 1, 1, o.price_usd)]
        for b, q in pins["qty"].items():
            lines = [(lb, lo, ls, (q if lb == b else lp), lq, lu) for lb, lo, ls, lp, lq, lu in lines]
        state["ctx"] = CartContext(**{**ctx.__dict__, "plan": plan(lines, plan_id=f"p{len(calls) + 1}")})
        return state["ctx"].plan

    cart_mod.configure(context=lambda run_id: state["ctx"], replanner=replanner)
    state["replans"] = calls
    return state


def kinds(run_id=RUN) -> list[str]:
    return [r["kind"] for r in BOOK.get(run_id).records]


def test_draft_cart_groups_in_run_order_with_totals(run):
    c = cart_mod.get_cart(RUN)
    assert c.state == "draft" and c.editable and c.plan_id == "p1"
    assert [g.store_id for g in c.stores] == ["wowrobo", "geekworm", "armdojo", "amazon"]
    assert [g.order for g in c.stores] == [1, 2, 3, 4]
    w = c.stores[0]
    assert w.subtotal_usd == 90.94 and [i.qty for i in w.items] == [5, 1] and w.action_level == "agent_cart"
    assert c.total_usd == 132.41 and c.remaining_usd == 132.41 and c.bought_usd == 0
    amz = c.stores[-1]
    assert amz.action_level == "prefilled_cart"  # mock mode: the mock link builder
    assert c.counts.model_dump() == {"stores": 4, "done": 0, "agent_cart": 3, "prefilled_cart": 1, "product_link": 0, "items_by_hand": 0}
    assert {lo.bom_line_id: lo.reason for lo in c.left_out} == {"b3": "owned", "b6": "owned", "b7": "print_at_home"}
    g = next(g for g in c.stores if g.store_id == "geekworm")
    assert g.items[0].alternatives == 1, "refused and rejected offers are not alternatives"


def test_live_mode_unverified_prefilled_store_is_shown_as_product_links(run, monkeypatch):
    set_mode(monkeypatch, "live")
    c = cart_mod.build_cart(RUN)
    amz = next(g for g in c.stores if g.store_id == "amazon")
    assert amz.action_level == "product_link" and "real browser" in amz.downgrade_reason
    assert [g.store_id for g in c.stores][-1] == "amazon" and c.counts.items_by_hand == 1
    monkeypatch.setenv("CART_LINKS_VERIFIED", "amazon")
    assert next(g for g in cart_mod.build_cart(RUN).stores if g.store_id == "amazon").action_level == "prefilled_cart"


def test_approval_gate(run):
    ctx = run["ctx"]
    assert cart_mod.approval_blockers(RUN, "p1") == []
    run["ctx"] = CartContext(**{**ctx.__dict__, "open_assumptions": ["b5"]})
    err = cart_mod.approval_blockers(RUN, "p1")[0]
    assert err.error == "assumption_unconfirmed" and err.status == 409 and err.refusal["rule"] == "assumption_unconfirmed" and err.bom_line_ids == ["b5"]
    run["ctx"] = CartContext(**{**ctx.__dict__, "offers": offers("2026-01-01T00:00:00-08:00")})
    errs = {e.error for e in cart_mod.approval_blockers(RUN, "p1")}
    assert "stale_price" in errs
    run["ctx"] = ctx
    assert {e.error for e in cart_mod.approval_blockers(RUN, "p_old")} == {"stale_plan"}
    run["ctx"] = CartContext(**{**ctx.__dict__, "budget_usd": 100.0})
    assert cart_mod.approval_blockers(RUN, "p1")[0].refusal["rule"] == "budget"


def test_edits_are_validated_pinned_replanned_and_recorded(run):
    with pytest.raises(CartError) as exc:
        asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="swap_offer", bom_line_id="b4", offer_id="ali1")))
    assert exc.value.status == 409 and exc.value.refusal["rule"] == "merchant_allowed"
    with pytest.raises(CartError, match="compatibility"):
        asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="swap_offer", bom_line_id="b4", offer_id="seeed2a")))
    with pytest.raises(CartError) as exc:
        asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="swap_offer", bom_line_id="b4", offer_id="w5")))
    assert exc.value.refusal["rule"] == "unknown_offer"
    assert run["replans"] == [], "a refused edit never reaches the optimizer"

    c = asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="swap_offer", bom_line_id="b4", offer_id="ada352")))
    assert run["replans"][-1]["swap_in"] == {"b4": "ada352"} and "g1" in run["replans"][-1]["swap_out"]
    ada = next(g for g in c.stores if g.store_id == "adafruit")
    assert ada.action_level == "product_link" and ada.items[0].edited_by_user is True and c.plan_id == "p2"
    assert [g.store_id for g in c.stores][-1] == "adafruit"
    c = asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="move_store", bom_line_id="b4", store_id="geekworm")))
    assert any(g.store_id == "geekworm" for g in c.stores)
    c = asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="remove", bom_line_id="b5")))
    assert {lo.bom_line_id: lo.reason for lo in c.left_out}["b5"] == "removed_by_you"
    c = asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="restore", bom_line_id="b5")))
    assert any(g.store_id == "amazon" for g in c.stores)
    asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="set_qty", bom_line_id="b1", qty=2)))
    ev = BOOK.get(RUN).events[-1]
    assert ev["type"] == "cart.edited" and ev["severity"] == "warn" and "needs 6" in ev["detail"]
    with pytest.raises(CartError):
        asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="set_qty", bom_line_id="b1", qty=0)))
    assert kinds().count("cart_edit") == 5


def sign(handoffs, cart):
    return {"type": "b2c.mandate.closed", "handoffs": [h.model_dump() for h in handoffs], "total_usd": cart.total_usd, "signature": {"jws": "x"}}


def test_approve_creates_handoffs_locks_the_cart_and_runs_the_checkout(run):
    done_hook = []
    cart_mod.configure(on_complete=lambda run_id, bought: done_hook.append(bought))
    result = asyncio.run(handoff.approve(RUN, "p1", sign=sign))
    c = result.cart
    assert c.state == "approved" and not c.editable and BOOK.get(RUN).closed_mandate_sha256
    levels = {h.store_id: h.action_level for h in result.handoffs}
    assert levels == {"wowrobo": "agent_cart", "geekworm": "agent_cart", "armdojo": "agent_cart", "amazon": "prefilled_cart"}
    for h in result.handoffs:
        assert len(h.url_sha256) == 64 and h.url.startswith("https://mock.invalid/")
        assert all(i.qty >= 1 and "email" not in i.ids for i in h.items)
    assert c.current_store_id == "wowrobo" and all(g.handoff and g.handoff.state == "ready" for g in c.stores)
    with pytest.raises(CartError, match="locked"):
        asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="remove", bom_line_id="b5")))
    with pytest.raises(CartError):
        asyncio.run(handoff.approve(RUN, "p1", sign=sign))

    c = handoff.update_handoff(RUN, "wowrobo", "opened")
    assert c.state == "checking_out"
    c = handoff.update_handoff(RUN, "wowrobo", "done")
    assert c.bought_usd == 90.94 and c.remaining_usd == 41.47 and c.counts.done == 1 and c.current_store_id == "geekworm"
    assert next(g for g in c.stores if g.store_id == "wowrobo").handoff.done_via == "user"
    c = handoff.update_handoff(RUN, "geekworm", "skipped")
    assert c.bought_usd == 90.94 and c.current_store_id == "armdojo"
    c = handoff.update_handoff(RUN, "geekworm", "ready")  # undo
    assert c.current_store_id == "geekworm"
    with pytest.raises(CartError):
        handoff.update_handoff(RUN, "geekworm", "done", order_id="jane@example.com")
    with pytest.raises(CartError):
        handoff.update_handoff(RUN, "nowhere", "done")
    for sid in ("geekworm", "armdojo"):
        handoff.update_handoff(RUN, sid, "done", order_id="#1042" if sid == "armdojo" else None)
    c = handoff.update_handoff(RUN, "amazon", "skipped")
    assert c.state == "complete" and c.current_store_id is None and c.bought_usd == 119.93 and c.remaining_usd == 12.48
    assert len(done_hook) == 1 and {b["store_id"] for b in done_hook[0]} == {"wowrobo", "geekworm", "armdojo"}
    assert BOOK.get(RUN).events[-1]["type"] == "run.done"
    c = handoff.update_handoff(RUN, "amazon", "ready")  # undo after complete goes back to the run
    assert c.state == "checking_out"
    assert kinds().count("handoff") == 4 + 8  # 4 created, then 8 transitions (the two refused ones record nothing)


def test_create_carts_needs_the_one_time_token(run):
    with pytest.raises(CartError) as exc:
        asyncio.run(handoff.create_carts(RUN, "p1", "forged"))
    assert exc.value.refusal["rule"] == "approval_required"
    token = handoff.issue_approval_token(RUN, "p1")
    asyncio.run(handoff.create_carts(RUN, "p1", token))
    BOOK.get(RUN).pending = {}
    with pytest.raises(CartError):
        asyncio.run(handoff.create_carts(RUN, "p1", token))  # used once
    with pytest.raises(CartError):
        handoff.update_handoff(RUN, "wowrobo", "opened")  # still a draft


def test_signing_failure_cancels_the_new_carts(run, monkeypatch):
    from app import registry

    cancelled = []
    ucp = registry.get("shopify_ucp")
    monkeypatch.setattr(ucp, "cancel_cart", lambda cart_id, business=None: _async(cancelled.append(cart_id)))

    def bad_sign(h, c):
        raise RuntimeError("signing key missing")

    with pytest.raises(RuntimeError):
        asyncio.run(handoff.approve(RUN, "p1", sign=bad_sign))
    assert len(cancelled) == 3 and BOOK.get(RUN).state == "draft" and not BOOK.get(RUN).pending


async def _async(value=None):
    return value


def test_reopen_cancels_open_shopify_carts_and_returns_to_draft(run, monkeypatch):
    from app import registry

    cancelled = []
    ucp = registry.get("shopify_ucp")
    monkeypatch.setattr(ucp, "cancel_cart", lambda cart_id, business=None: _async(cancelled.append((cart_id, business))))
    asyncio.run(handoff.approve(RUN, "p1", sign=sign))
    handoff.update_handoff(RUN, "wowrobo", "done")
    c = asyncio.run(cart_mod.reopen(RUN))
    assert c.state == "draft" and c.editable and all(g.handoff is None for g in c.stores)
    assert len(cancelled) == 2, "the done store keeps its cart; the other two Shopify carts are cancelled"
    assert BOOK.get(RUN).records[-1]["action"] == "reopen"
    assert asyncio.run(handoff.approve(RUN, "p1", sign=sign)).cart.state == "approved"  # a new approval works


class FakeAdapter:
    def __init__(self, fn):
        self.fn = fn

    async def refresh(self, o, ctx):
        assert ctx.bypass_cache is True
        return self.fn(o)


def test_price_refresh_flags_changes_and_gates_approval(run):
    def fresh(o):
        if o.store_id == "geekworm":
            return o.model_copy(update={"price_usd": 18.5, "seen_at": now_iso()})
        if o.store_id == "amazon":
            raise RefreshSkipped("SerpAPI price is under 30 minutes old")
        return o.model_copy(update={"seen_at": now_iso()})

    res = asyncio.run(refresh.refresh_prices(RUN, adapter_for=lambda src: FakeAdapter(fresh)))
    assert [(c.offer_id, c.old_usd, c.new_usd) for c in res.changes] == [("g1", 17.0, 18.5)]
    assert "kept as seen" in res.note and "price_refresh" in kinds()
    errs = cart_mod.approval_blockers(RUN, "p1")
    assert [e.error for e in errs] == ["price_changed"], "a change must be seen before Approve"
    assert cart_mod.approval_blockers(RUN, "p1", acknowledged=["price_changes"]) == []
    c = cart_mod.get_cart(RUN)  # viewing the cart marks the change seen
    g = next(g for g in c.stores if g.store_id == "geekworm")
    assert g.items[0].unit_price_usd == 18.5 and g.items[0].changed.old_usd == 17.0 and c.total_usd == 133.91
    assert cart_mod.approval_blockers(RUN, "p1") == []


def test_stale_unrefreshable_prices_need_an_acknowledgement(run):
    old = "2026-01-01T00:00:00-08:00"
    run["ctx"] = CartContext(**{**run["ctx"].__dict__, "offers": offers(old)})

    def fresh(o):
        if o.store_id == "amazon":
            raise RefreshSkipped("SerpAPI quota")
        return o.model_copy(update={"seen_at": now_iso()})

    assert "stale_price" in {e.error for e in cart_mod.approval_blockers(RUN, "p1")}
    asyncio.run(refresh.refresh_prices(RUN, adapter_for=lambda src: FakeAdapter(fresh)))
    assert [e.error for e in cart_mod.approval_blockers(RUN, "p1")] == ["stale_price"]
    assert cart_mod.approval_blockers(RUN, "p1", acknowledged=["stale_price"]) == []


def test_replay_refresh_never_touches_the_network(run, monkeypatch):
    set_mode(monkeypatch, "replay")
    res = asyncio.run(refresh.refresh_prices(RUN, adapter_for=lambda src: pytest.fail("no adapter in replay")))
    assert res.note.startswith("Replay: prices as recorded at") and res.changes == []
    run["ctx"] = CartContext(**{**run["ctx"].__dict__, "offers": offers("2026-01-01T00:00:00-08:00")})
    assert cart_mod.approval_blockers(RUN, "p1") == [], "the age check is off in replay"


def test_csv_export(run):
    text = export_csv(RUN)
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["line", "part", "store", "action level", "qty", "unit price", "line total", "seen at", "source", "URL"]
    assert rows[1][:7] == ["b1", "STS3215 servo 12V", "WowRobo", "Agent cart", "5", "74.95", "74.95"]
    assert len(rows) == 6 and rows[-1][3] == "Prefilled cart" and rows[-1][8] == "via SerpAPI (amazon)"
    asyncio.run(cart_mod.apply_edit(RUN, CartEditRequest(op="swap_offer", bom_line_id="b4", offer_id="ada352")))
    rows = list(csv.reader(io.StringIO(export_csv(RUN))))
    assert any(r[0] == "b4" and r[1] == "12V 5A PSU" and r[8] == "Adafruit catalog" for r in rows)
    c = cart_mod.build_cart(RUN)
    assert "'=HYPERLINK" in cart_csv(c, {}), "a title that looks like a formula is escaped"


def test_live_create_carts_downgrades_a_failed_store(run, monkeypatch):
    from app import registry
    from app.stores.shopify_ucp import LiveShopifyUCP, UcpError

    set_mode(monkeypatch, "live")
    calls = []

    async def runner(argv):
        calls.append(argv)
        business = argv[argv.index("--business") + 1]
        if "geekworm" in business:
            raise UcpError("anonymous carts refused")
        return {"result": {"id": "gid://shopify/Cart/abc123?key=k1", "continue_url": f"{business}/cart/c/abc123", "currency": "USD",
                           "totals": [{"type": "subtotal", "amount": 100}]}}

    registry._instances[("shopify_ucp", "live")] = LiveShopifyUCP(runner=runner)
    monkeypatch.setenv("CART_LINKS_VERIFIED", "amazon")
    token = handoff.issue_approval_token(RUN, "p1")
    hs = {h.store_id: h for h in asyncio.run(handoff.create_carts(RUN, "p1", token))}
    assert hs["wowrobo"].action_level == "agent_cart" and hs["wowrobo"].url.startswith("https://f0c6d4-21.myshopify.com/")
    assert hs["geekworm"].action_level == "product_link" and "Couldn't create a cart at Geekworm" in hs["geekworm"].caveat
    assert hs["amazon"].url == "https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=B0CLAMP001&Quantity.1=1"
    assert hs["armdojo"].url.startswith("https://xee8tz-dc.myshopify.com/")
    wow = next(c for c in calls if "f0c6d4" in c[c.index("--business") + 1])
    assert '"quantity":1' in wow[wow.index("--input") + 1]
    warn = [e for e in BOOK.get(RUN).events if e["type"] == "handoff.created" and e["severity"] == "warn"]
    assert [e["store_id"] for e in warn] == ["geekworm"]
