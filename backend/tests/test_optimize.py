"""Cart optimizer (PLAN §3.10): pack units, action-level friction, the two tiers, pins, the budget cap."""

from __future__ import annotations

import time

import pytest
from a_helpers import offer

from app.pipeline.optimize import PartNeed, optimize, optimize_cart, plan_hash, tier_weight


def hero():
    """The SO-101 12V hero numbers (PLAN §3.10 table)."""
    return [
        PartNeed("b1", 6, [offer("o17", "wowrobo", 74.95, 5), offer("o18", "wowrobo", 15.99), offer("o19", "wowrobo", 139.90, 10),
                           offer("o20", "amazon", 109.99, 6, "prefilled_cart"), offer("o21", "seeed", 22.00, 1, "product_link")]),
        PartNeed("b2", 1, [offer("o30", "armdojo", 11.99), offer("o31", "amazon", 10.60, 1, "prefilled_cart")]),
        PartNeed("b4", 1, [offer("o40", "geekworm", 17.00)]),
        PartNeed("b5", 1, [offer("o50", "amazon", 12.48, 2, "prefilled_cart")]),
    ]


def lines(plan):
    return sorted((ln.bom_line_id, ln.offer_id, ln.packs) for ln in plan.lines)


def test_pack_break_a_five_pack_plus_a_single_beats_six_singles():
    plan = optimize([hero()[0]], tier="cheapest", budget=160)
    assert lines(plan) == [("b1", "o17", 1), ("b1", "o18", 1)] and plan.total_usd == 90.94
    assert [ln.qty for ln in plan.lines] == [5, 1]  # units bought per plan line


def test_cheapest_tier_hero_plan():
    plan = optimize(hero(), tier="cheapest", budget=160)
    assert plan.feasible and plan.total_usd == 131.02  # 90.94 + 10.60 (Amazon is already in the cart for the clamps) + 17.00 + 12.48
    assert plan.stores == ["wowrobo", "geekworm", "amazon"] and plan.checkouts == 3
    assert plan.by_level == {"agent_cart": 2, "prefilled_cart": 1, "product_link": 0} and plan.items_by_hand == 0
    assert plan.plan_sha256 == plan_hash("cheapest", plan.lines, plan.total_usd) and plan.plan_id == f"p_{plan.plan_sha256[:12]}"


def test_fewest_checkouts_collapses_stores_then_minimises_price():
    plan = optimize(hero(), tier="fewest_checkouts", budget=160)
    assert plan.checkouts == 2 and set(plan.stores) == {"geekworm", "amazon"} and plan.total_usd == 150.07
    assert tier_weight("fewest_checkouts", 160) == 161 and tier_weight("cheapest", 160) == 0.01
    with pytest.raises(ValueError):
        tier_weight("fastest", 160)


def test_friction_only_breaks_ties_agent_cart_wins_at_the_same_price():
    parts = [PartNeed("b1", 1, [offer("link", "seeed", 10.0, 1, "product_link"), offer("pre", "amazon", 10.0, 1, "prefilled_cart"), offer("cart", "wowrobo", 10.0)])]
    assert lines(optimize(parts, tier="cheapest", budget=50)) == [("b1", "cart", 1)]
    cheaper_link = [PartNeed("b1", 1, [offer("link", "seeed", 9.5, 1, "product_link"), offer("cart", "wowrobo", 10.0)])]
    assert lines(optimize(cheaper_link, tier="cheapest", budget=50)) == [("b1", "link", 1)]  # a real saving still wins on Cheapest
    plan = optimize(cheaper_link, tier="cheapest", budget=50)
    assert plan.items_by_hand == 1 and plan.by_level["product_link"] == 1


def test_pins_from_cart_edits():
    swapped = optimize(hero(), tier="cheapest", budget=160, require={"o20"}, ban={"o17", "o18"})
    assert ("b1", "o20", 1) in lines(swapped) and not any(o in ("o17", "o18") for _, o, _ in lines(swapped))
    banned = optimize(hero(), tier="cheapest", budget=160, ban={"o31"})
    assert ("b2", "o30", 1) in lines(banned) and banned.total_usd == 132.41
    parts = hero()
    parts[0].qty = 7  # an edited quantity: one 5-pack + two singles
    assert sorted(lines(optimize(parts, tier="cheapest", budget=200)))[:2] == [("b1", "o17", 1), ("b1", "o18", 2)]


def test_over_budget_returns_the_cheapest_plan_marked_infeasible():
    plan = optimize(hero(), tier="cheapest", budget=160, cap=100)
    assert not plan.feasible and plan.total_usd == 131.02 and plan.over_budget_by == 31.02
    assert optimize(hero(), tier="cheapest", budget=160, cap=140).feasible
    assert not optimize(hero(), tier="cheapest", budget=100).feasible  # the signed budget is a cap too


def test_unknown_shipping_is_zero_known_shipping_is_counted_never_invented():
    a = [PartNeed("b1", 1, [offer("x", "wowrobo", 10.0), offer("y", "adafruit", 8.0, shipping_usd=4.5)])]
    plan = optimize(a, tier="cheapest", budget=50)
    assert lines(plan) == [("b1", "x", 1)] and plan.total_usd == 10.0
    only = optimize([PartNeed("b1", 1, [offer("y", "adafruit", 8.0, shipping_usd=4.5)])], tier="cheapest", budget=50)
    assert only.total_usd == 12.5


def test_parts_without_offers_are_left_out_and_an_empty_cart_is_valid():
    plan = optimize([PartNeed("b1", 2, []), PartNeed("b2", 1, [offer("o", "wowrobo", 3.0)])], tier="cheapest", budget=50)
    assert [ln.bom_line_id for ln in plan.lines] == ["b2"]
    empty = optimize([], tier="cheapest", budget=50)
    assert empty.feasible and empty.total_usd == 0 and empty.checkouts == 0


def test_replan_is_fast_enough_for_a_slider():
    parts = [PartNeed(f"b{i}", 1 + i % 4, [offer(f"o{i}_{s}", s, 5 + (i * 7 + j * 3) % 11, 1 + (i + j) % 3, lv)
                                           for j, (s, lv) in enumerate([("wowrobo", "agent_cart"), ("armdojo", "agent_cart"), ("amazon", "prefilled_cart"),
                                                                        ("seeed", "product_link"), ("adafruit", "product_link"), ("geekworm", "agent_cart")])])
             for i in range(12)]
    t0 = time.perf_counter()
    for tier in ("cheapest", "fewest_checkouts"):
        assert optimize(parts, tier=tier, budget=1000).feasible
    assert time.perf_counter() - t0 < 2.0


def test_public_entry_names_an_unknown_run():
    with pytest.raises(NotImplementedError, match="PLAN §3.10"):
        optimize_cart("r_nope", "cheapest")
