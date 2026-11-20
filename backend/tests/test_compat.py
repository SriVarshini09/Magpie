"""Compatibility: the attribute parser, the robot_arm pack (R1-R11), and the engine that runs every pack."""

from __future__ import annotations

from app.models import Check
from app.rules import robot_arm as ra
from app.rules.base import PlanContext, LineCtx, listing_attrs, parse_attrs


def chosen(title, packs=1, units=1, description=None):
    return {"offer_id": "o", "store_id": "s", "title": title, "description": description, "packs": packs, "units_per_pack": units,
            "attrs": listing_attrs(title, description)}


def plan(voltage="7v4", servo=None, board=None, psu=None, cable=None, psu_spec="Power Supply", servo_qty=6, instances=6):
    lines = [
        LineCtx("b1", "STS3215 Servo 7.4V, 1/345 gear (C001)", "motor", servo_qty, attrs=parse_attrs("STS3215 Servo 7.4V, 1/345 gear (C001)"), chosen=servo or []),
        LineCtx("b2", "Motor Control Board", "board", 1, chosen=board or []),
        LineCtx("b3", "USB-C Cable 2 pcs", "cable", 1, chosen=cable or []),
        LineCtx("b4", "Power Supply", "power", 1, spec=psu_spec, attrs=parse_attrs(psu_spec), chosen=psu or []),
    ]
    return PlanContext("robot_arm", lines, answers={"voltage_class": voltage}, view_instances={"b1": instances} if instances else {}).to_dict()


def result(checks: list[Check], rule: str) -> str | None:
    return next((c.result for c in checks if c.rule_id.startswith(rule + " ")), None)


def test_parse_attrs_normalises_listing_text():
    assert parse_attrs("4S 650mAh 75C LiPo XT30")["cells"] == 4 and parse_attrs("4 cell LiPo")["cells"] == 4
    assert parse_attrs("14.8V LiPo battery 1500mAh XT-60") == {"voltage_v": 14.8, "capacity_mah": 1500.0, "cells": 4, "connector": "XT60", "connectors": ["XT60"]}
    assert parse_attrs("2300KV motor")["kv"] == 2300 and parse_attrs("motor 2300 kv")["kv"] == 2300 and parse_attrs("XT60H plug")["connector"] == "XT60"
    assert parse_attrs("ESC 20A 3-4S")["cells_range"] == [3, 4] and parse_attrs("JST-PH 2.0 lead")["pitch_mm"] == 2.0
    psu = parse_attrs("AC 100-240V to DC 12V 5A, DC5521 (5.5x2.1mm), US plug")
    assert psu["mains_v"] == [100.0, 240.0] and psu["voltage_v"] == 12.0 and psu["current_a"] == 5.0 and psu["connector"] == "barrel_5.5x2.1" and psu["plug"] == "US"
    assert parse_attrs("5V 4A adapter, UK plug, 220V input")["plug"] == "UK" and parse_attrs("Feetech STS3215 Servo C018 12V")["variant"] == "C018"
    assert parse_attrs("just a clamp") == {}  # a missing value is missing, never a guess
    assert listing_attrs("12V adapter", "Output: 5V 3A")["voltage_v"] == 5.0  # description first, then the title


def test_r1_bom_level_fail_then_fix_then_pass():
    p = plan("12v", psu_spec="5V power supply")
    checks = ra.check(p)
    r1 = next(c for c in checks if c.rule_id == ra.R1)
    assert r1.result == "fail" and r1.kb_refs == [ra.KB_README_12V] and set(r1.bom_line_ids) == {"b1", "b4"} and "12V" in (r1.fix or "")
    fix = ra.fix(r1, p)
    assert fix["bom_line_id"] == "b4" and fix["attrs"] == {"voltage_v": 12.0, "min_current_a": 5.0, "connector": "barrel_5.5x2.1", "plug": "US"}
    assert result(ra.check(plan("12v", psu_spec=fix["spec"])), "R1") == "pass"
    assert result(ra.check(plan("7v4", psu_spec="5V power supply")), "R1") == "pass"  # the README's own build


def test_r1_missing_voltage_is_needs_human_never_a_pass():
    assert result(ra.check(plan("12v", psu_spec="Power Supply")), "R1") == "needs_human"
    assert result(ra.check(plan("12v", psu=[chosen("Universal power adapter")])), "R1") == "needs_human"


def test_r2_current_minimum_for_the_12v_build():
    assert result(ra.check(plan("12v", psu=[chosen("12V 5A supply 5.5x2.1mm US plug")])), "R2") == "pass"
    assert result(ra.check(plan("12v", psu=[chosen("12V 2A wall adapter")])), "R2") == "fail"
    assert result(ra.check(plan("12v", psu=[chosen("12V wall adapter")])), "R2") == "needs_human"
    assert result(ra.check(plan("7v4", psu=[chosen("5V 2A adapter")])), "R2") is None  # no stated minimum for the 5V build


def test_r3_variant_r7_mixed_voltage_r4_count():
    assert result(ra.check(plan("7v4", servo=[chosen("STS3215 C001 7.4V", 6)])), "R3") == "pass"
    assert result(ra.check(plan("7v4", servo=[chosen("STS3215 C046 7.4V 1/147", 6)])), "R3") == "fail"
    assert result(ra.check(plan("12v", servo=[chosen("STS3215 C001 7.4V", 6)])), "R3") == "fail"
    assert result(ra.check(plan("7v4", servo=[chosen("STS3215 servo", 6)])), "R3") == "needs_human"
    assert result(ra.check(plan("12v", servo=[chosen("STS3215 C018 12V", 1, 5), chosen("STS3215 C001 7.4V")])), "R7") == "fail"
    assert result(ra.check(plan(servo_qty=5)), "R4") == "fail" and result(ra.check(plan()), "R4") == "pass"


def test_r5_bus_adapter_r6_plug_r8_data_r9_packs_r11_mains():
    assert result(ra.check(plan(board=[chosen("Waveshare Bus Servo Adapter (A), USB-C")])), "R5") == "pass"
    assert result(ra.check(plan(board=[chosen("Servo Driver HAT (A) for Raspberry Pi, 16-channel PWM")])), "R5") == "fail"
    assert result(ra.check(plan(board=[chosen("Controller board")])), "R5") == "needs_human"
    assert result(ra.check(plan(psu=[chosen("5V 3A, 5.5x2.5mm, US plug")])), "R6") == "fail"
    assert result(ra.check(plan(psu=[chosen("5V 3A adapter")])), "R6") == "needs_human"
    assert result(ra.check(plan(cable=[chosen("USB-C cable, data transfer")])), "R8") == "pass"
    assert result(ra.check(plan(cable=[chosen("USB-C charging cable")])), "R8") == "needs_human"
    assert result(ra.check(plan(servo=[chosen("STS3215 C001 7.4V", 1, 5)])), "R9") == "fail"
    assert result(ra.check(plan(servo=[chosen("STS3215 C001 7.4V", 1, 5), chosen("STS3215 C001 7.4V")])), "R9") == "pass"
    assert result(ra.check(plan(psu=[chosen("5V 4A adapter 5.5x2.1mm, UK plug, 220V input")])), "R11") == "fail"
    assert result(ra.check(plan(psu=[chosen("5V 4A adapter 5.5x2.1mm, US plug")])), "R11") == "pass"
    assert result(ra.check(plan(psu=[chosen("5V 4A adapter 5.5x2.1mm")])), "R11") == "needs_human"


def test_r10_is_a_warn_with_two_sources_and_no_auto_fix():
    r10 = next(c for c in ra.check(plan()) if c.rule_id == ra.R10)
    assert r10.result == "warn" and r10.needs_ack and r10.kb_refs == [ra.KB_README_12V, ra.KB_BOARD_INPUT] and r10.fix is None
    assert ra.fix(r10, plan()) is None  # sources disagree: a human decides


def test_reject_reasons_for_ranking():
    p = plan("12v")
    servo, board, psu = p["lines"][0], p["lines"][1], p["lines"][3]
    assert ra.reject(servo, chosen("STS3215 C001 7.4V 1/345, 5 pcs"), p).startswith("variant_mismatch: 7.4V C001, need 12V")
    assert ra.reject(servo, chosen("STS3215 C018 12V 30kg"), p) is None
    assert ra.reject(board, chosen("Servo Driver HAT (A) for Raspberry Pi"), p).startswith("R5")
    assert ra.reject(psu, chosen("12V 2A wall adapter"), p) == "R2: 2 A < 5 A"
    assert ra.reject(psu, chosen("5V 4A adapter, UK plug, 220V input"), p) == "R11: UK plug, 220V input"
    assert ra.reject(psu, chosen("12V 5A Power Supply, DC5521 (5.5x2.1mm), US plug"), p) is None


def test_respec_follows_the_voltage_chip_and_cites_the_readme():
    p = plan("12v")
    change = ra.respec(p["lines"][0], p)
    assert change["attrs"] == {"voltage_v": 12.0, "variant": "C018"} and change["kb_refs"] == [ra.KB_README_12V]
    assert ra.respec(plan("7v4")["lines"][0], plan("7v4")) is None
    assert ra.respec(p["lines"][3], p)["attrs"]["voltage_v"] == 5.0  # the README's BOM is the 5V build; R1 then fails on it


def test_engine_runs_generic_and_domain_packs_and_never_passes_a_missing_pack(live_mock, client):
    from a_helpers import start_so101

    from app import runstate
    from app.pipeline import compat

    run = runstate.get(start_so101(client))
    assert compat.pack_names(run)[0] == "generic_electrical" and "robot_arm" in compat.pack_names(run)
    checks, state = compat.run_checks(run, run.plan())
    assert state["robot_arm"] == "ok" and result(checks, "R1") == "pass" and result(checks, "R10") == "warn"
    run.template.rule_packs.append("no_such_pack")
    checks, state = compat.run_checks(run, run.plan())
    assert state["no_such_pack"] == "missing"
    assert next(c for c in checks if c.rule_id == "no_such_pack").result == "needs_human"


from a_helpers import live_mock  # noqa: E402,F401  (fixture)
