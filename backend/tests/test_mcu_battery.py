"""Pack mcu_battery (PLAN §13.3): the connector normalizer, the R12/R13/R14 stage flow, R15-R17."""

from __future__ import annotations

import pytest

from app.rules import generic_electrical as ge
from app.rules import mcu_battery as m

BATTERY = {"bom_line_id": "b5", "row_id": "battery", "name": "Battery", "category": "battery",
           "rules": ["R12", "R13", "R14"]}

# Listings from research/second-demo.md (titles and descriptions shortened; prices drift and are not used here).
AMERIDROID = {"title": "3.7V 2000mAh 103450 LiPo Battery w/ JST 1.25 Connector", "description": "Micro JST 1.25mm 2-pin (SH1.25)"}
ROKLAND_125 = {"title": "1S 1C LiPo Battery with Micro JST 1.25 Plug", "description": None}
SPECIALTY_3PIN = {"title": "Specialty 3-pin JST PH 3.7V 1200mAh battery", "description": "will not work with boards that need 2-pin"}
TWO_S = {"title": "7.4V 450mAh LiPo with JST PH 2", "description": ""}
CABLE = {"title": "RAK Battery Cable with Power Switch", "description": "JST-PH 2.0 cable"}
ADAFRUIT_1578 = {"title": "Lithium Ion Polymer Battery - 3.7v 500mAh", "description": "Comes with a 2-pin JST-PH connector"}
PKCELL = {"title": "PKCELL Flat 3.7V 2000mAh 803860 Battery with JST Type PH 2.0 Plug", "description": "Check polarity match"}
HARUTECH = {"title": "3.7V 5000mAh LiPo with JST Connector", "description": "2P PH1.25mm Pitch"}
ATLAVOX = {"title": "3.7V 1200mAh LiPo", "description": "JST-PH 2-pin reverse polarity connector"}


def by_rule(checks):
    return {c.rule_id.split()[0]: c for c in checks}


@pytest.mark.parametrize("text", ["JST-PH2.0", "JST PH 2.0", "PH2.0mm", "JST Type PH 2.0"])
def test_ph_forms_are_one_value(text):
    a = ge.parse_attrs(text)
    assert (a["connector_family"], a["pitch_mm"]) == ("PH", 2.0)


@pytest.mark.parametrize("text", ["JST 1.25", "Micro JST 1.25", "SH1.25", "PH1.25"])
def test_1mm25_forms_do_not_match(text):
    assert ge.parse_attrs(text).get("connector_family") != "PH"


def test_stage_flow_rejects_what_would_not_plug_in():
    kept, rejected = m.filter_batteries(BATTERY, [ROKLAND_125, AMERIDROID, SPECIALTY_3PIN, TWO_S, CABLE, ADAFRUIT_1578,
                                                  HARUTECH, ATLAVOX, PKCELL])
    reasons = {o["title"]: r for o, r in rejected}
    assert reasons[ROKLAND_125["title"]] == "R12 FAIL: JST 1.25 mm ≠ JST-PH 2.0 mm."
    assert reasons[AMERIDROID["title"]].startswith("R12 FAIL: JST 1.25 mm")
    assert reasons[HARUTECH["title"]].startswith("R12 FAIL: JST 1.25 mm")  # "JST" in the title, PH1.25 in the description
    assert "3-pin" in reasons[SPECIALTY_3PIN["title"]]
    assert reasons[TWO_S["title"]].startswith("R13 FAIL: 2S")
    assert "not a battery" in reasons[CABLE["title"]]
    assert "reverse polarity" in reasons[ATLAVOX["title"]]
    # the cheapest valid cell is kept first; PKCELL (pin count not stated) stays in, after the full passes
    assert kept == [ADAFRUIT_1578, PKCELL]


def test_adafruit_1578_passes_r12_r13_with_polarity_warning():
    c = by_rule(m.check_offer(BATTERY, ADAFRUIT_1578))
    assert c["R12"].result == "pass" and c["R13"].result == "pass"
    assert c["R14"].result == "warn" and c["R14"].needs_ack and "polarity" in c["R14"].message.lower()


def test_r12_fail_has_the_auto_fix_filter():
    c = by_rule(m.check_offer(BATTERY, ROKLAND_125))["R12"]
    f = m.fix(c)
    assert f["connector_family"] == "PH" and f["pitch_mm"] == 2.0 and f["pins"] == 2 and f["cells"] == 1
    assert "reverse polarity" in f["exclude_text"]


def test_r12_missing_pins_is_needs_human_not_pass():
    c = by_rule(m.check_offer(BATTERY, PKCELL))
    assert c["R12"].result == "needs_human" and c["R12"].needs_ack


def test_r13_2s_fails_and_r14_never_passes():
    c = by_rule(m.check_offer(BATTERY, TWO_S))
    assert c["R13"].result == "fail" and "8.4 V" in c["R13"].message
    for offer in (ADAFRUIT_1578, PKCELL, TWO_S, ROKLAND_125):
        assert by_rule(m.check_offer(BATTERY, offer))["R14"].result != "pass"


def test_bom_level_battery_from_readme_line():
    # README L60: "3.7V LiPo w/ JST-PH2.0 connector": no offer yet, pins not stated -> needs a check, never a pass
    c = by_rule(m.check({"lines": [{**BATTERY, "spec": "3.7V LiPo w/ JST-PH2.0 connector"}]}))
    assert c["R12"].result == "needs_human" and c["R13"].result == "pass" and c["R14"].result == "warn"


DISPLAY = {"bom_line_id": "b2", "row_id": "display", "name": "E-paper display", "category": "board", "rules": ["R15"]}


def test_r15_pass_v2_raw_panel():
    c = m.check_offer(DISPLAY, {"title": "Waveshare 800×480, 7.5\" E-Ink Raw Display",
                                "description": "Display Color: Black/White; 7.5 inch e-Paper V2 raw panel"})
    assert [x.result for x in c] == ["pass"]


@pytest.mark.parametrize("offer", [
    {"title": "Waveshare 7.5 inch E-Ink Display 800x480 E-Paper with Hat", "description": "seven-color ACeP photo frame"},
    {"title": "Waveshare 7.5inch 4 Color e-Paper display (H)", "description": ""},
    {"title": "7.5\" E-Paper (B) Red/Black/White 800x480", "description": ""},
    {"title": "7.5 inch e-paper panel", "description": ""},
])
def test_r15_fail_matches_model_not_size(offer):
    c = m.check_offer(DISPLAY, offer)
    assert [x.result for x in c] == ["fail"]
    assert "7.5in e-paper (v2)" in m.fix(c[0])["model"]


SENSOR = {"bom_line_id": "b4", "row_id": "sensor", "name": "Sensor", "category": "sensor", "rules": ["R16"]}


def test_r16_bme280_pass_bmp280_fail():
    assert [c.result for c in m.check_offer(SENSOR, {"title": "Waveshare BME280 Environmental Sensor"})] == ["pass"]
    bad = m.check_offer(SENSOR, {"title": "Grove - Barometer Sensor (BMP280)", "description": "pressure and temperature"})
    assert [c.result for c in bad] == ["fail"] and "BME280" in m.fix(bad[0])["query"]


ADAPTER = {"bom_line_id": "b3", "row_id": "adapter", "name": "Adapter board", "category": "board", "rules": ["R17"]}


def test_r17_despi_pass_hat_warn():
    assert [c.result for c in m.check_offer(ADAPTER, {"title": "GooDisplay DESPI-C02 24-Pin Serial E-Paper HAT Adapter"})] == ["pass"]
    c = m.check_offer(ADAPTER, {"title": "800x480, 7.5-inch E-Ink display HAT for Raspberry Pi"})
    assert [x.result for x in c] == ["warn"] and c[0].needs_ack and "PWR" in c[0].message


def test_pack_rule_ids_and_lines_by_category_without_rules():
    plan = {"lines": [{"bom_line_id": "b5", "name": "Battery", "category": "battery", "offer": ROKLAND_125},
                      {"bom_line_id": "b4", "name": "Sensor", "category": "sensor", "offer": {"title": "BMP280"}}]}
    ids = {c.rule_id for c in m.check(plan)}
    assert {"R12 BATTERY_CONNECTOR", "R13 BATTERY_CELLS", "R14 BATTERY_POLARITY", "R16 SENSOR_HUMIDITY"} <= ids
    assert set(m.RULES) == {"R12", "R13", "R14", "R15", "R16", "R17"}
