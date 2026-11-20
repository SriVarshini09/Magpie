"""Cart edits and replan (PLAN §12.3, §3.10): guard -> optimizer with pins -> `cart_edit` record. No network."""

from __future__ import annotations

from a_helpers import live_mock, start_so101  # noqa: F401

from app import runstate
from app.audit.chain import recompute


def edit(client, rid, **body):
    return client.post(f"/api/runs/{rid}/cart/edit", json=body)


def chosen(client, rid, bid):
    line = next(ln for ln in client.get(f"/api/runs/{rid}").json()["bom"] if ln["bom_line_id"] == bid)
    return sorted((c["offer_id"], c["packs"]) for c in line.get("chosen") or [])


def test_swap_offer_pins_it_and_reoptimizes(live_mock, client):
    rid = start_so101(client)
    assert chosen(client, rid, "b1") == [("o17", 1), ("o18", 1)]
    r = edit(client, rid, op="swap_offer", bom_line_id="b1", offer_id="o20")
    assert r.status_code == 200, r.text
    cart = r.json()
    assert cart["state"] == "draft" and cart["editable"] and cart["total_usd"] == 150.07
    assert chosen(client, rid, "b1") == [("o20", 1)]
    items = [it for g in cart["stores"] for it in g["items"] if it["bom_line_id"] == "b1"]
    assert [it["offer_id"] for it in items] == ["o20"] and items[0]["edited_by_user"] is True
    run = runstate.get(rid)
    rec = [r for r in run.records if r["kind"] == "cart_edit"][-1]
    assert rec["op"] == "swap_offer" and rec["by"] == "user" and rec["before"]["chosen"]["b1"] != rec["after"]["chosen"]["b1"]
    assert run.events[-1].type == "cart.edited" and recompute(run.records)[0]
    panel = client.get(f"/api/runs/{rid}/parts/b1").json()
    assert panel["why"]["edited_by_user"] is True and panel["why"]["reason_codes"][0] == "edited_by_user"


def test_refused_and_rejected_targets_are_409_with_the_reason(live_mock, client):
    rid = start_so101(client)
    before = client.get(f"/api/runs/{rid}").json()["refusals"]
    outside = edit(client, rid, op="swap_offer", bom_line_id="b1", offer_id="o24")  # RobotShop: not in the mandate
    assert outside.status_code == 409 and outside.json()["detail"]["refusal"]["rule"] == "merchant_allowed"
    assert outside.json()["detail"]["refusal"]["clause"] == "constraints.allowed_merchants"
    rejected = edit(client, rid, op="swap_offer", bom_line_id="b1", offer_id="o22")  # 7.4V C001 in a 12V build
    assert rejected.status_code == 409 and rejected.json()["detail"]["error"] == "offer_rejected" and "variant_mismatch" in rejected.json()["detail"]["message"]
    unknown = edit(client, rid, op="swap_offer", bom_line_id="b1", offer_id="o_made_up")
    assert unknown.status_code == 409 and unknown.json()["detail"]["refusal"]["rule"] == "unknown_offer"
    wrong_line = edit(client, rid, op="swap_offer", bom_line_id="b1", offer_id="o40")  # found in this run, but for the supply
    assert wrong_line.status_code == 409 and wrong_line.json()["detail"]["error"] == "unknown_offer"
    assert client.get(f"/api/runs/{rid}").json()["refusals"] == before + 3  # each refusal is logged
    assert chosen(client, rid, "b1") == [("o17", 1), ("o18", 1)]  # nothing changed
    assert edit(client, rid, op="swap_offer", bom_line_id="b99", offer_id="o17").status_code == 404


def test_move_store_remove_restore_and_quantity(live_mock, client):
    rid = start_so101(client)
    moved = edit(client, rid, op="move_store", bom_line_id="b2", store_id="armdojo").json()
    assert chosen(client, rid, "b2") == [("o30", 1)] and moved["total_usd"] == 132.41
    assert edit(client, rid, op="move_store", bom_line_id="b2", store_id="geekworm").status_code == 409  # no offer for that part there
    removed = edit(client, rid, op="remove", bom_line_id="b5").json()
    assert {"bom_line_id": "b5", "reason": "removed_by_you"}.items() <= next(x for x in removed["left_out"] if x["bom_line_id"] == "b5").items()
    assert all(it["bom_line_id"] != "b5" for g in removed["stores"] for it in g["items"]) and removed["total_usd"] == 119.93
    restored = edit(client, rid, op="restore", bom_line_id="b5").json()
    assert any(it["bom_line_id"] == "b5" for g in restored["stores"] for it in g["items"])
    more = edit(client, rid, op="set_qty", bom_line_id="b1", qty=7)
    assert more.status_code == 200 and chosen(client, rid, "b1") == [("o17", 1), ("o18", 2)]
    fewer = edit(client, rid, op="set_qty", bom_line_id="b1", qty=5)  # below the BOM quantity: allowed, logged with a note
    assert fewer.status_code == 200 and chosen(client, rid, "b1") == [("o17", 1)]
    assert [r for r in runstate.get(rid).records if r["kind"] == "cart_edit"][-1]["note"] == "The project needs 6"
    assert edit(client, rid, op="set_qty", bom_line_id="b1", qty=0).status_code == 422


def test_replan_tier_switch_and_budget_cap(live_mock, client):
    rid = start_so101(client)
    few = client.post(f"/api/runs/{rid}/replan", json={"tier": "fewest_checkouts"})
    assert few.status_code == 200 and few.json()["plan"]["checkouts"] == 2 and few.json()["plan"]["tier"] == "fewest_checkouts"
    state = client.get(f"/api/runs/{rid}").json()
    assert state["active_tier"] == "fewest_checkouts" and set(state["plans"]) == {"cheapest", "fewest_checkouts"}
    over = client.post(f"/api/runs/{rid}/replan", json={"tier": "cheapest", "budget_cap_usd": 500})
    assert over.status_code == 422 and over.json()["detail"]["refusal"]["rule"] == "budget"  # raising the budget needs a new mandate
    tight = client.post(f"/api/runs/{rid}/replan", json={"tier": "cheapest", "budget_cap_usd": 100}).json()["plan"]
    assert tight["feasible"] is False and tight["over_budget_by"] == 31.02
    assert client.post(f"/api/runs/{rid}/replan", json={"tier": "fastest"}).status_code == 422
    assert client.post(f"/api/runs/{rid}/replan", json={"tier": "cheapest"}).json()["plan"]["total_usd"] == 131.02
    run = runstate.get(rid)
    assert sum(1 for e in run.events if e.type == "plan.changed") == 3 and recompute(run.records)[0]


def test_an_approved_cart_is_locked(live_mock, client):
    rid = start_so101(client)
    state = client.get(f"/api/runs/{rid}").json()
    acks = sorted({c["rule_id"].split()[0] for c in state["checks"] if c["needs_ack"]}) + ["stale_price", "price_changes"]
    ok = client.post(f"/api/runs/{rid}/approve", json={"plan_id": state["plans"]["cheapest"]["plan_id"], "acknowledged_warnings": acks})
    assert ok.status_code == 200, ok.text
    assert edit(client, rid, op="remove", bom_line_id="b5").status_code == 409
    assert client.post(f"/api/runs/{rid}/replan", json={"tier": "fewest_checkouts"}).status_code == 409
