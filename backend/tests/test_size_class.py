"""G7 size class: a listing for another prop size is rejected, so a 5-inch build never gets 3-inch parts (and back)."""

from app.rules import generic_electrical as ge
from tests.test_integration_e2e import ok, pipeline, start  # noqa: F401  (pipeline is a fixture)


def need(category: str, name: str, prop_in: str) -> dict:
    return {"bom_line_id": "b1", "name": name, "category": category, "attrs": {"prop_in": prop_in}}


def g7(checks) -> list[str]:
    return [c.result for c in checks if c.rule_id.startswith("G7")]


def test_frame_and_props_listing_size_must_match_the_build():
    assert g7(ge.check_offer(need("mechanical", "Frame", "5"), {"title": "3-inch FPV frame, ~140 mm wheelbase"})) == ["fail"]
    assert g7(ge.check_offer(need("mechanical", "Frame", "5"), {"title": "5-inch FPV frame, 220 mm wheelbase"})) == ["pass"]
    assert g7(ge.check_offer(need("mechanical", "Propellers", "3"), {"title": "5-inch 3-blade propellers"})) == ["fail"]
    assert g7(ge.check_offer(need("mechanical", "Propellers", "3"), {"title": "3-inch 3-blade propellers, 2 CW + 2 CCW"})) == ["pass"]
    msg = next(c.message for c in ge.check_offer(need("mechanical", "Frame", "5"), {"title": "3-inch FPV frame"}) if c.rule_id.startswith("G7"))
    assert msg.startswith("G7: 3-inch listing ≠ 5-inch build")


def test_motor_stator_size_decides_the_class():
    assert "fail" in g7(ge.check_offer(need("motor", "Brushless motor", "5"), {"title": "1404 3800KV brushless motor, 4 pcs"}))
    assert "pass" in g7(ge.check_offer(need("motor", "Brushless motor", "5"), {"title": "2207 2400KV brushless motor, 4 pcs"}))
    assert "fail" in g7(ge.check_offer(need("motor", "Brushless motor", "3"), {"title": "2207 2400KV brushless motor"}))
    # an X500's 2216 motors swing 10-inch props: a 22 mm stator is "5-inch or larger", not a mismatch
    assert "pass" in g7(ge.check_offer(need("motor", "Brushless motor", "10"), {"title": "2216 920KV brushless motor"}))


def test_listing_without_a_size_or_line_without_prop_in_is_not_judged():
    assert g7(ge.check_offer(need("mechanical", "Frame", "5"), {"title": "Carbon FPV frame kit"})) == []
    line = {"bom_line_id": "b4", "name": "Flight controller", "category": "board", "attrs": {}}
    assert g7(ge.check_offer(line, {"title": "F7 flight controller, 30x30 mm stack"})) == []


def test_five_inch_drone_run_gets_five_inch_parts(pipeline):  # noqa: F811
    c = pipeline
    _, st, rid = start(c, "a small camera drone under $200", answers={"size_class": "5in"})
    by_name = {ln["raw_name"]: ln for ln in st["bom"]}

    def chosen_titles(name: str) -> list[str]:
        panel = ok(c.get(f"/api/runs/{rid}/parts/{by_name[name]['bom_line_id']}"))
        return [o["title"] for o in panel["offers"] if o["status"] == "chosen"]

    def rejected(name: str) -> list[dict]:
        panel = ok(c.get(f"/api/runs/{rid}/parts/{by_name[name]['bom_line_id']}"))
        return [o for o in panel["offers"] if o["status"] == "rejected"]

    assert chosen_titles("Frame") and all("5-inch" in t for t in chosen_titles("Frame"))
    assert chosen_titles("Brushless motor") and all(t.startswith("2207") for t in chosen_titles("Brushless motor"))
    assert chosen_titles("Propellers") and all("5-inch" in t for t in chosen_titles("Propellers"))
    assert any("3-inch" in o["title"] for o in rejected("Frame"))  # the 3-inch frame is shown as rejected, with the reason
    assert any(o["title"].startswith("1404") for o in rejected("Brushless motor"))


def test_three_inch_drone_run_still_gets_three_inch_parts(pipeline):  # noqa: F811
    c = pipeline
    _, st, rid = start(c, "a small camera drone under $200", answers={"size_class": "3in"})
    frame = next(ln for ln in st["bom"] if ln["raw_name"] == "Frame")
    panel = ok(c.get(f"/api/runs/{rid}/parts/{frame['bom_line_id']}"))
    chosen = [o["title"] for o in panel["offers"] if o["status"] == "chosen"]
    assert chosen and all("3-inch" in t for t in chosen)


def g12(checks) -> list[str]:
    return [c.result for c in checks if c.rule_id.startswith("G12")]


def test_stack_mount_must_match_the_build():
    vtx = {"bom_line_id": "b10", "name": "Video transmitter + antenna", "category": "radio", "attrs": {"mount_mm": "30x30"}}
    assert g12(ge.check_offer(vtx, {"title": "5.8GHz VTX 20x20 with antenna"})) == ["fail"]
    assert g12(ge.check_offer(vtx, {"title": "5.8GHz VTX 30x30 with antenna, 25-400 mW"})) == ["pass"]
    assert g12(ge.check_offer(vtx, {"title": "5.8GHz VTX with antenna"})) == []  # no pattern stated: not judged
    fc = {"bom_line_id": "b4", "name": "Flight controller", "category": "board", "attrs": {"mount_mm": "30x30"}}
    assert g12(ge.check_offer(fc, {"title": "F7 flight controller, 30.5x30.5 mm holes"})) == ["pass"]  # 30.5 holes are a 30x30 stack
    assert g12(ge.check_offer(fc, {"title": "All-in-one F4 flight controller, 25.5x25.5, 2-4S"})) == ["fail"]
    props = {"bom_line_id": "b5", "name": "Propellers", "category": "mechanical", "attrs": {"prop_in": "5"}}
    assert g12(ge.check_offer(props, {"title": "5x4.3x3 propellers"})) == []  # a prop code is not a stack pattern


def test_five_inch_drone_run_gets_a_30x30_vtx(pipeline):  # noqa: F811
    c = pipeline
    _, st, rid = start(c, "a small camera drone under $200", answers={"size_class": "5in"})
    vtx = next(ln for ln in st["bom"] if ln["raw_name"] == "Video transmitter + antenna")
    panel = ok(c.get(f"/api/runs/{rid}/parts/{vtx['bom_line_id']}"))
    chosen = [o["title"] for o in panel["offers"] if o["status"] == "chosen"]
    assert chosen and all("30x30" in t for t in chosen)
    assert any("20x20" in o["title"] and "G12" in (o.get("reason") or "") for o in panel["offers"] if o["status"] == "rejected")


def test_power_distribution_is_on_the_board_for_3_and_5_inch_but_bought_for_x500(pipeline):  # noqa: F811
    c = pipeline
    for size in ("3in", "5in"):
        _, st, _ = start(c, "a small camera drone under $200", answers={"size_class": size})
        pdb = next(ln for ln in st["bom"] if ln["raw_name"] == "Power distribution")
        assert pdb["status"] == "skipped", (size, pdb["status"])  # on the AIO board / 4-in-1 ESC: nothing to buy, never "not found"
    _, st, _ = start(c, "a small camera drone under $200", answers={"size_class": "x500"})
    pdb = next(ln for ln in st["bom"] if ln["raw_name"] == "Power distribution")
    assert pdb["line_kind"] == "part" and pdb["qty"] == 1 and pdb["status"] != "skipped"


def test_esc_is_on_the_aio_board_for_3_inch_and_bought_for_5_inch(pipeline):  # noqa: F811
    c = pipeline
    _, st, _ = start(c, "a small camera drone under $200", answers={"size_class": "3in"})
    esc = next(ln for ln in st["bom"] if ln["raw_name"] == "ESC")
    assert esc["status"] == "skipped"  # part of the all-in-one flight controller: never "not found"
    _, st, _ = start(c, "a small camera drone under $200", answers={"size_class": "5in"})
    esc = next(ln for ln in st["bom"] if ln["raw_name"] == "ESC")
    assert esc["line_kind"] == "part" and esc["status"] in ("chosen", "warning")


def test_a_size_in_the_text_picks_that_chip_and_an_unknown_size_still_asks():
    from app.pipeline import template as templates

    tpl = templates.load_template_sync("quadcopter").template
    assert templates.answers_from_text(tpl, "a 5 inch freestyle quad") == {"size_class": "5in"}
    assert templates.answers_from_text(tpl, "a 3-inch drone") == {"size_class": "3in"}
    assert templates.answers_from_text(tpl, "10 inch X500 dev kit") == {"size_class": "x500"}
    assert templates.answers_from_text(tpl, "a 15 inch drone") == {}  # "5 inch" inside "15 inch" is not a match
    assert templates.answers_from_text(tpl, "a 7 inch long range quad") == {}
    asked = [q.id for q in templates.questions_for(tpl, "a 7 inch long range quad")]
    assert "size_class" in asked  # no chip names 7 inches: ask instead of silently using the default
    assert "size_class" not in [q.id for q in templates.questions_for(tpl, "a 5 inch quad")]


def test_five_inch_in_the_first_message_gives_a_five_inch_run(pipeline):  # noqa: F811
    c = pipeline
    it, st, rid = start(c, "a small camera drone under $200, 5 inch")
    assert "size_class" not in [q["id"] for q in it["questions"]]
    assert it["constraints"]["size_class"] == "5in"
    frame = next(ln for ln in st["bom"] if ln["raw_name"] == "Frame")
    panel = ok(c.get(f"/api/runs/{rid}/parts/{frame['bom_line_id']}"))
    chosen = [o["title"] for o in panel["offers"] if o["status"] == "chosen"]
    assert chosen and all("5-inch" in t for t in chosen)
