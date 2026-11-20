"""Pack generic_electrical (PLAN §3.8): parsers, one passing and one failing test per rule G1-G11, and the
promises the UI makes: a missing attribute never passes, rule-of-thumb rows only warn, every kb_ref resolves."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models import Check
from app.rules import generic_electrical as ge
from app.rules import mcu_battery

KB_DIR = Path(__file__).resolve().parents[1] / "data" / "kb"


def line(bid: str, category: str, name: str | None = None, **kw):
    return {"bom_line_id": bid, "category": category, "name": name or bid, **kw}


def run(rule: str, *lines, edges=None) -> list[Check]:
    plan = {"lines": list(lines)}
    if edges:
        plan["edges"] = edges
    return [c for c in ge.check(plan) if c.rule_id.split()[0] == rule]


def results(checks: list[Check]) -> list[str]:
    return [c.result for c in checks]


# --------------------------------------------------------------------------- parsers


@pytest.mark.parametrize("text, key, value", [
    ("4S 1500mAh", "cells", 4),
    ("4 cell pack", "cells", 4),
    ("4-cell", "cells", 4),
    ("14.8V LiPo", "cells", 4),
    ("2300KV", "kv", 2300),
    ("2300 kv", "kv", 2300),
    ("KV880", "kv", 880),
    ("XT-60", "connector", "XT60"),
    ("XT60H plug", "connector", "XT60"),
    ("xt30 lead", "connector", "XT30"),
    ("1045 props", "prop_in", 10.0),
    ("5 inch props", "prop_in", 5.0),
    ("Working Current 15mA", "current_a", 0.015),
    ("12V 5A+ power supply", "current_a", 5.0),
    ("12V 5A+ power supply", "voltage_v", 12.0),
    ("5.5x2.1mm barrel", "barrel", "5.5x2.1"),
    ("5.5 x 2.5 mm DC plug", "barrel", "5.5x2.5"),
    ("Anker 10,000 maH", "capacity_mah", 10000),
    ("1800mAh 2S 20C", "c_rating", 20.0),
    ("2-pin JST-PH", "pins", 2),
    ("3 pin connector", "pins", 3),
])
def test_parser_normalizes(text, key, value):
    assert ge.parse_attrs(text)[key] == value


def test_14v8_is_four_cells_only_when_no_explicit_count():
    a = ge.parse_attrs("14.8V")
    assert a["cells"] == 4 and a["cells_from"] == "voltage"
    b = ge.parse_attrs("3S 14.8V")  # an explicit S count wins
    assert b["cells"] == 3 and b["cells_from"] == "count"


@pytest.mark.parametrize("text", ["JST-PH2.0", "JST PH 2.0", "PH2.0mm", "JST Type PH 2.0", "JST-PH", "jst ph 2"])
def test_jst_ph_forms_normalize_to_one_value(text):
    a = ge.parse_attrs(text)
    assert (a["connector"], a["connector_family"], a["pitch_mm"]) == ("JST-PH", "PH", 2.0)


@pytest.mark.parametrize("text", ["JST 1.25", "Micro JST 1.25", "SH1.25", "PH1.25", "2P PH1.25mm Pitch"])
def test_1mm25_forms_never_read_as_ph_2(text):
    a = ge.parse_attrs(text)
    assert a.get("connector_family") != "PH" and a["pitch_mm"] == 1.25


@pytest.mark.parametrize("text, rng", [("VIN 7 – 12 V", [7.0, 12.0]), ("3.3-5.5V DC", [3.3, 5.5]), ("9~12.6V", [9.0, 12.6])])
def test_voltage_ranges(text, rng):
    assert ge.parse_attrs(text)["voltage_range"] == rng


def test_cell_ranges_and_mains_are_not_supply_voltage():
    assert ge.parse_attrs("20A BLHeli S ESC 3-4S")["cells_range"] == [3, 4]
    a = ge.parse_attrs("AC 100-240V to DC 12V 5A")
    assert a["mains_range"] == [100.0, 240.0] and a["voltage_v"] == 12.0 and "voltage_range" not in a


def test_flags():
    a = ge.parse_attrs("JST-PH 2-pin reverse polarity connector, check polarity")
    assert a["reverse_polarity"] is True and a["polarity_note"] is True
    assert ge.parse_attrs("onboard voltage level translator, compatible with 3.3V/5V")["level_shifter"] is True


def test_attrs_reads_description_before_title():
    a = ge.attrs({"title": "3.7V 5000mAh LiPo with JST Connector", "description": "2P PH1.25mm Pitch"})
    assert a["pitch_mm"] == 1.25 and a["_from"]["pitch_mm"] == "description"
    b = ge.attrs({"title": "4S 1500mAh XT60", "description": "Comes with an XT30 plug"})
    assert b["connector"] == "XT30" and b["cells"] == 4 and b["_from"]["cells"] == "title"


def test_vague_description_jst_does_not_override_title_family():
    a = ge.attrs({"title": "3.7V LiPo JST-PH 2.0", "description": "with JST plug"})
    assert a["connector"] == "JST-PH"


def test_template_attrs_are_coerced():
    ln = ge.to_line(line("b2", "motor", attrs={"cells": "4S", "kv": "3500-4500", "max_current_a": None}))
    assert ln.a["cells"] == 4 and ln.a["kv_range"] == [3500, 4500] and "max_current_a" not in ln.a
    ln = ge.to_line(line("b4", "esc_driver", attrs={"cells_range": "2-4S", "connector": "XT-30"}))
    assert ln.a["cells_range"] == [2, 4] and ln.a["connector"] == "XT30"


# --------------------------------------------------------------------------- G1 SUPPLY_VOLTAGE


def test_g1_pass_battery_inside_board_range():
    c = run("G1", line("b1", "board", "Arduino Uno", attrs={"voltage_range": "7-12"}),
            line("b2", "battery", "2S LiPo", attrs={"cells": "2S"}))
    assert results(c) == ["pass"]


def test_g1_fail_battery_above_board_range_with_fix():
    c = run("G1", line("b1", "board", "Arduino Uno", attrs={"voltage_range": "7-12"}),
            line("b2", "battery", "3S LiPo", attrs={"cells": "3S"}))
    assert results(c) == ["fail"] and "12.6" in c[0].message and set(c[0].bom_line_ids) == {"b1", "b2"}
    assert ge.fix(c[0]) == {"bom_line_id": "b2", "category": "battery", "voltage_min": 7.0, "voltage_max": 12.0}


def test_g1_range_from_title_only_needs_a_check():
    c = run("G1", line("b1", "sensor", "DHT22", offer={"title": "DHT22 sensor 3.3-5.5V", "description": "Great sensor"}),
            line("b2", "power", "5V supply", attrs={"voltage_v": 5}))
    assert results(c) == ["needs_human"] and c[0].needs_ack


# --------------------------------------------------------------------------- G2 CURRENT_BUDGET


def test_g2_pass_known_loads_under_80_percent():
    c = run("G2", line("p", "power", "5V 2A supply", attrs={"voltage_v": 5, "current_a": 2}),
            line("s", "sensor", "HC-SR04", qty=2, attrs={"current_a": "15mA"}))
    assert results(c) == ["pass"]


def test_g2_warn_over_battery_discharge_limit():
    c = run("G2", line("bat", "battery", "LiPo", attrs={"cells": "2S", "capacity_mah": 1800, "c_rating": 20}),
            line("m", "motor", "Motor", qty=2, attrs={"max_current_a": 20}))
    assert results(c) == ["warn"] and "40" in c[0].message and "36" in c[0].message and c[0].needs_ack


def test_g2_unknown_load_is_at_least_and_needs_human():
    c = run("G2", line("p", "power", "PSU", attrs={"voltage_v": 12, "current_a": 5}),
            line("s", "motor", "Servo", qty=6), line("b", "board", "Board", attrs={"current_a": 0.1}))
    assert results(c) == ["needs_human"] and "at least 0.1 a" in c[0].message.lower() and c[0].needs_ack


# --------------------------------------------------------------------------- G3 CELL_COUNT


def test_g3_pass():
    c = run("G3", line("b7", "battery", "4S LiPo", attrs={"cells": "4S"}),
            line("b4", "esc_driver", "AIO board", attrs={"cells_range": "2-4S"}))
    assert results(c) == ["pass"] and not c[0].needs_ack


def test_g3_fail_with_fix():
    c = run("G3", line("b7", "battery", "6S LiPo", attrs={"cells": "6S"}),
            line("b4", "esc_driver", "ESC", attrs={"cells_range": "2-4S"}))
    assert results(c) == ["fail"]
    assert ge.fix(c[0]) == {"bom_line_id": "b7", "category": "battery", "cells_min": 2, "cells_max": 4}


def test_g3_rule_of_thumb_row_only_warns():
    c = run("G3", line("b7", "battery", "6S LiPo", attrs={"cells": "6S"}, basis="rule_of_thumb"),
            line("b4", "esc_driver", "ESC", attrs={"cells_range": "2-4S"}, basis="rule_of_thumb"))
    assert results(c) == ["warn"] and "rule-of-thumb" in c[0].message and c[0].needs_ack


def test_g3_missing_cells_is_needs_human_naming_the_attribute():
    c = run("G3", line("b7", "battery", "LiPo"), line("b4", "esc_driver", "ESC", attrs={"cells_range": "2-4S"}))
    assert results(c) == ["needs_human"] and "cells" in c[0].message


# --------------------------------------------------------------------------- G4 LOGIC_LEVEL


def test_g4_known_levels_agree_is_still_a_human_check():
    c = run("G4", line("mcu", "board", "ESP32 DevKitC"), line("s", "sensor", "BME280", attrs={"logic_v": 3.3}))
    assert results(c) == ["needs_human"] and c[0].needs_ack and "pass" not in results(c)


def test_g4_warn_and_proposes_level_shifter():
    c = run("G4", line("mcu", "board", "ESP32 DevKitC"), line("s", "sensor", "HC-SR04", attrs={"logic_v": 5}))
    assert results(c) == ["warn"] and "level shifter" in c[0].message.lower()
    assert ge.fix(c[0])["add_line"]["provenance"] == "assumption"


def test_g4_shifter_in_bom_clears_the_warning():
    c = run("G4", line("mcu", "board", "ESP32 DevKitC"), line("s", "sensor", "HC-SR04", attrs={"logic_v": 5}),
            line("ls", "board", "Logic level shifter"))
    assert results(c) == ["needs_human"]


# --------------------------------------------------------------------------- G5 CONNECTOR_MATCH


def test_g5_pass_on_edge():
    c = run("G5", line("b7", "battery", "LiPo", row_id="battery", attrs={"connector": "XT30"}),
            line("b4", "esc_driver", "AIO", row_id="esc", attrs={"connector": "XT30"}),
            edges=[{"from": "battery", "to": "esc", "label": "XT30", "rules": ["G5", "G6"]}])
    assert results(c) == ["pass"]


def test_g5_fail_xt30_vs_xt60_with_fix():
    c = run("G5", line("b7", "battery", "LiPo", row_id="battery", attrs={"connector": "XT60"}),
            line("b4", "esc_driver", "AIO", row_id="esc", attrs={"connector": "XT30"}),
            edges=[{"from": "battery", "to": "esc", "label": "XT30", "rules": ["G5"]}])
    assert results(c) == ["fail"] and "XT60 ≠ XT30" in c[0].message
    assert ge.fix(c[0])["connector"] == "XT30"


def test_g5_without_edges_pairs_battery_with_power_module():
    pdb = line("pdb", "power", "PDB", spec="XT60 plug for battery & XT30 plug for ESCs & peripherals", rules=["G5"])
    ok = run("G5", line("bat", "battery", "4S", attrs={"connector": "XT60"}, rules=["G5"]), pdb,
             line("esc", "esc_driver", "ESC", attrs={"connector": "XT30"}, rules=["G5"]))
    assert set(results(ok)) == {"pass"}
    bad = run("G5", line("p", "power", "PSU", attrs={"barrel": "5.5x2.5"}, rules=["G5"]),
              line("c", "board", "Controller", attrs={"barrel": "5.5x2.1"}, rules=["G5"]))
    assert results(bad) == ["fail"] and "5.5x2.5" in bad[0].message


def test_g5_missing_connector_needs_human():
    c = run("G5", line("b7", "battery", "LiPo", row_id="battery"), line("b4", "esc_driver", "AIO", row_id="esc",
            attrs={"connector": "XT30"}), edges=[{"from": "battery", "to": "esc", "label": "XT30"}])
    assert results(c) == ["needs_human"] and "connector" in c[0].message


# --------------------------------------------------------------------------- G6 CONNECTOR_CURRENT


def test_g6_pass_xt60_under_30a():
    c = run("G6", line("b", "battery", "LiPo", attrs={"connector": "XT60", "expected_current_a": 25}))
    assert results(c) == ["pass"]


def test_g6_warn_over_rating():
    c = run("G6", line("b", "battery", "LiPo", attrs={"connector": "XT60", "expected_current_a": 45}))
    assert results(c) == ["warn"] and "30 A" in c[0].message and c[0].needs_ack


def test_g6_xt30_is_always_a_human_check():
    c = run("G6", line("b", "battery", "LiPo", attrs={"connector": "XT30", "expected_current_a": 5}))
    assert results(c) == ["needs_human"] and "unverified" in c[0].message


# --------------------------------------------------------------------------- G7 KV_PROP_CELLS


def g7_lines(kv: str, cells: str, prop: str):
    return (line("m", "motor", "Motor", attrs={"kv": kv}), line("bat", "battery", "LiPo", attrs={"cells": cells}),
            line("pr", "mechanical", "Propellers", row_id="props", spec=prop))


def test_g7_inside_usual_range_is_never_a_bare_pass():
    c = run("G7", *g7_lines("2400", "4S", "5-inch, 3-blade"))
    assert results(c) == ["needs_human"] and "inside" in c[0].message and c[0].needs_ack


def test_g7_outside_usual_range_warns_never_fails():
    c = run("G7", *g7_lines("1800", "4S", "5-inch"))
    assert results(c) == ["warn"] and "outside" in c[0].message and ge.fix(c[0]) is None


def test_g7_10_inch_cites_both_sources_and_3_inch_has_none():
    c = run("G7", *g7_lines("900", "4S", "1045 props"))
    assert results(c) == ["needs_human"] and any("holybro_x500_kv" in r for r in c[0].kb_refs)
    c3 = run("G7", *g7_lines("4000", "4S", "3-inch"))
    assert results(c3) == ["needs_human"] and "3-inch" in c3[0].message


# --------------------------------------------------------------------------- G8 ESC_CURRENT


def test_g8_pass():
    c = run("G8", line("e", "esc_driver", "ESC", attrs={"current_a": 20}), line("m", "motor", "2216 motor",
            attrs={"max_current_a": 18}))
    assert results(c) == ["pass"]


def test_g8_fail():
    c = run("G8", line("e", "esc_driver", "ESC", attrs={"current_a": 20}), line("m", "motor", "Motor",
            attrs={"max_current_a": 28}))
    assert results(c) == ["fail"] and ge.fix(c[0])["current_min_a"] == 28


def test_g8_missing_motor_max_current_needs_human():
    c = run("G8", line("e", "esc_driver", "ESC", attrs={"current_a": 20}), line("m", "motor", "Motor"))
    assert results(c) == ["needs_human"] and "max_current_a" in c[0].message and c[0].needs_ack


# --------------------------------------------------------------------------- G9 DRIVER_CURRENT


def test_g9_pass_tb6612_with_known_stall():
    c = run("G9", line("d", "esc_driver", "TB6612FNG motor driver"),
            line("m", "motor", "TT gear motor", qty=2, attrs={"stall_current_a": 1.0}),
            line("bat", "battery", "2S LiPo", attrs={"cells": "2S"}))
    assert results(c) == ["pass"]


def test_g9_fail_stall_over_channel_and_supply_over_vmax():
    c = run("G9", line("d", "esc_driver", "TB6612FNG motor driver"),
            line("m", "motor", "DC gear motor", attrs={"stall_current_a": 2.5}),
            line("bat", "battery", "4S LiPo", attrs={"cells": "4S"}))
    assert results(c) == ["fail", "fail"]
    assert any("15 V" in x.message for x in c) and any("2.5 A" in x.message for x in c)


def test_g9_missing_stall_needs_human():
    c = run("G9", line("d", "esc_driver", "L298N driver"), line("m", "motor", "DC gear motor"))
    assert results(c) == ["needs_human"] and "stall_current_a" in c[0].message


# --------------------------------------------------------------------------- G10 SERVO_SUPPLY


def test_g10_pass_own_rail_inside_range():
    c = run("G10", line("s", "motor", "MG90 servo", attrs={"voltage_range": "4.8-6V"}),
            line("p", "power", "5V servo supply", attrs={"voltage_v": 5}))
    assert results(c) == ["pass"]


def test_g10_warn_when_powered_from_logic_pin():
    c = run("G10", line("s", "motor", "Servo", attrs={"voltage_range": "4.8-6V", "powered_from": "arduino 5V pin"}))
    assert results(c) == ["warn"] and "own rail" in c[0].message
    assert ge.fix(c[0])["add_line"]["category"] == "power"


def test_g10_sg90_numbers_need_a_check():
    c = run("G10", line("s", "motor", "SG90 micro servo"), line("p", "power", "5V supply", attrs={"voltage_v": 5}))
    assert results(c) == ["needs_human"] and "SG90" in c[0].message


# --------------------------------------------------------------------------- G11 PIN_CURRENT


def test_g11_driver_present_is_still_a_human_check():
    c = run("G11", line("m", "motor", "DC motor 6V"), line("d", "esc_driver", "L293D driver"),
            line("mcu", "board", "Arduino Uno"))
    assert results(c) == ["needs_human"] and c[0].needs_ack


def test_g11_warn_without_driver():
    c = run("G11", line("r", "mechanical", "5V relay coil"), line("mcu", "board", "Arduino Uno"))
    assert results(c) == ["warn"] and "20 mA" in c[0].message


# --------------------------------------------------------------------------- pack-level promises


def test_human_check_rules_never_bare_pass():
    plan = {"lines": [line("mcu", "board", "ESP32 DevKitC"), line("s", "sensor", "BME280", attrs={"logic_v": 3.3}),
                      line("m", "motor", "Motor", attrs={"kv": "2400"}), line("bat", "battery", "LiPo", attrs={"cells": "4S"}),
                      line("pr", "mechanical", "Props", row_id="props", spec="5-inch"),
                      line("dc", "motor", "DC motor"), line("d", "esc_driver", "L298N driver")]}
    for c in ge.check(plan):
        rid = c.rule_id.split()[0]
        if ge.RULES[rid]["human_check"] == "always":
            assert c.result != "pass", c


def test_rule_ids_match_fixture_format_and_every_check_cites_kb():
    c = run("G3", line("b7", "battery", "4S", attrs={"cells": "4S"}), line("b4", "esc_driver", "ESC", attrs={"cells_range": "2-4S"}))
    assert c[0].rule_id == "G3 CELL_COUNT" and c[0].kb_refs[0] == "kb://compat_rules_generic#g3"


def test_rules_listed_on_a_line_are_the_only_ones_that_read_it():
    # The battery lists only G1: G3 must not read it.
    c = run("G3", line("b7", "battery", "6S", attrs={"cells": "6S"}, rules=["G1"]),
            line("b4", "esc_driver", "ESC", attrs={"cells_range": "2-4S"}, rules=["G3"]))
    assert c == []


def test_check_accepts_pydantic_like_input_and_never_raises_on_junk():
    assert ge.check({"lines": []}) == []
    out = ge.check({"lines": [{"bom_line_id": "x", "category": "battery", "attrs": {"cells": "lots"}}]})
    assert isinstance(out, list)


def test_check_offer_rejects_wrong_connector_and_cells():
    need = line("b7", "battery", "LiPo", attrs={"cells": "4S", "connector": "XT30"}, rules=["G3", "G5"])
    bad = ge.check_offer(need, {"title": "6S 1300mAh 120C LiPo XT60", "description": None})
    assert {c.rule_id.split()[0]: c.result for c in bad} == {"G3": "fail", "G5": "fail"}
    assert any(c.message == "G5: XT60 ≠ XT30." for c in bad)
    good = ge.check_offer(need, {"title": "4S 650mAh 95C LiPo", "description": "XT30 plug"})
    assert {c.result for c in good} == {"pass"}


def test_check_offer_motor_kv_outside_window_only_warns():
    need = line("b2", "motor", "Brushless motor", attrs={"kv": "3500-4500", "cells": "4S"}, rules=["G3", "G7"])
    c = ge.check_offer(need, {"title": "2207 2400KV brushless motor", "description": ""})
    assert [x.result for x in c if x.rule_id.startswith("G7")] == ["warn"]


def _kb_chunks() -> set[str]:
    refs = set()
    for path in KB_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^doc_id:\s*(\S+)", text, re.M)
        if not m:
            continue
        for cid in re.findall(r"^## chunk: ([a-z0-9_]+)\s*$", text, re.M):
            refs.add(f"kb://{m.group(1)}#{cid}")
    return refs


def test_every_kb_ref_in_both_packs_resolves_to_a_kb_chunk():
    known = _kb_chunks()
    for pack in (ge, mcu_battery):
        for rid, info in pack.RULES.items():
            for ref in info["kb_refs"]:
                assert ref in known, f"{pack.PACK_ID} {rid}: {ref} is not a chunk in data/kb/*.md"


def test_kb_sources_listed_in_rule_chunks_resolve():
    known = _kb_chunks()
    for name in ("compat_rules_generic.md", "compat_rules_mcu_battery.md"):
        for ref in re.findall(r"kb://[a-z0-9_]+#[a-z0-9_]+", (KB_DIR / name).read_text(encoding="utf-8")):
            assert ref in known, f"{name}: {ref}"


def test_rule_table_matches_plan():
    assert set(ge.RULES) == {f"G{i}" for i in range(1, 13)}  # G12 STACK_MOUNT added with the 5-inch drone fix
    assert ge.MVP_RULES == ("G1", "G3", "G5", "G7")
    assert {r for r, i in ge.RULES.items() if i["human_check"] != "never"} >= {"G2", "G4", "G6", "G7", "G8", "G9", "G10", "G11"}
