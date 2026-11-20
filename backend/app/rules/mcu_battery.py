"""Rule pack `mcu_battery`: the electronics / second-demo rules (PLAN §13.3). Owner: D.

R12 and R13 are G5 and G3 with this project's sources; the parsers are the generic pack's
(`rules/generic_electrical.py`, PLAN §13.5). Same interface as the generic pack:

    PACK_ID, RULES, check(plan) -> Check[], check_offer(line, offer) -> Check[], fix(check) -> filter | None

Plan input shape: as in `generic_electrical` (`{"lines": [{bom_line_id, row_id?, name, category, attrs, rules?,
offer?: {title, description}}], "edges"?: [...]}`). Which line each rule reads:

    R12, R13, R14   battery lines (category "battery")
    R15             the e-paper display line (name or row_id: display / panel / e-paper / epd)
    R16             sensor lines (category "sensor")
    R17             the display adapter line (name or row_id: adapter / DESPI / HAT)

A line that lists `rules` is read only by the rules it lists. The listing description is read before the
title: one real listing says "JST" in its title and "PH1.25mm" in its description (SD §5).
"""

from __future__ import annotations

import re
from typing import Any

from app.models import Check
from app.rules import generic_electrical as ge

PACK_ID = "mcu_battery"

_RULE_DOC = "kb://compat_rules_mcu_battery#"
_README = "kb://esp32_weather_epd#"
_SRC = "kb://electrical_notes#"

RULES: dict[str, dict[str, Any]] = {
    "R12": {"name": "BATTERY_CONNECTOR", "mvp": True, "human_check": "never",
            "kb_refs": [_RULE_DOC + "r12", _README + "l60_battery", _SRC + "dfrobot_ph2_power", _SRC + "jst_ph_pitch"],
            "summary": "Battery plug must be JST PH, 2.0 mm pitch, 2-pin."},
    "R13": {"name": "BATTERY_CELLS", "mvp": True, "human_check": "never",
            "kb_refs": [_RULE_DOC + "r13", _SRC + "dfrobot_ph2_power", _SRC + "lipo_cell_voltage"],
            "summary": "Single cell: 3.7 V nominal, at most 4.2 V full. A 2S 7.4 V pack fails."},
    "R14": {"name": "BATTERY_POLARITY", "mvp": True, "human_check": "always",
            "kb_refs": [_RULE_DOC + "r14", _README + "l136_polarity"],
            "summary": "JST-PH polarity is not standardized: always WARN 'check polarity'; reject listings that say "
                       "'reverse polarity'."},
    "R15": {"name": "PANEL_SUPPORTED", "mvp": False, "human_check": "conditional",
            "kb_refs": [_RULE_DOC + "r15", _README + "l57_display", _README + "l75_panel_support"],
            "summary": "Panel must match a model in the README Panel Support table, by exact model, not by size."},
    "R16": {"name": "SENSOR_HUMIDITY", "mvp": False, "human_check": "never",
            "kb_refs": [_RULE_DOC + "r16", _README + "l59_sensor", _SRC + "bosch_bme280"],
            "summary": "Sensor must measure humidity; a BMP280 is rejected."},
    "R17": {"name": "EPD_ADAPTER", "mvp": False, "human_check": "conditional",
            "kb_refs": [_RULE_DOC + "r17", _README + "l58_adapter", _README + "l138_l142_adapter_notes"],
            "summary": "Prefer the DESPI-C02 adapter; a Waveshare HAT gets a warning and a setup note."},
}

# README Panel Support (L73-L83). Only the L75 row is transcribed here: the other eight rows are not in
# PLAN, so they are NOT allowlisted [human check: transcribe the rest from the pinned README before relying
# on R15 for any other panel].
PANEL_SUPPORT: list[dict[str, Any]] = [
    {"model": "Waveshare 7.5in e-paper (v2)", "readme_line": 75, "recommended": True,
     "kb_ref": _README + "l75_panel_support",
     "search_query": "Waveshare 7.5 inch e-paper v2 800x480 black white raw panel",
     # v2 is the 800x480 black/white raw panel; v1 was 640x384. "(B)"/"(C)"/colour panels are other models.
     "must": [r"7\.5", r"e-?paper|e-?ink|epd", r"\bv2\b|800\s*[x×]\s*480"],
     "must_not": [r"\((?:b|c|g|h)\)", r"\b(?:4|7|seven|four)[\s-]*colou?r\b", r"\bred\b", r"acep", r"photo\s*frame"]},
]

_NOT_A_BATTERY = re.compile(r"\b(?:cable|extension|adapter|charger|connector\s*(?:only|kit)|pigtail|switch\s*cable|lead)\b", re.I)
_DISPLAY = re.compile(r"display|panel|e-?paper|e-?ink|\bepd\b", re.I)
_ADAPTER = re.compile(r"adapter|despi|\bhat\b|driver\s*board", re.I)


def _rid(rule: str) -> str:
    return ge.rule_id(rule, RULES)


def _mk(rule: str, result: str, message: str, lines: list[ge.Line], **kw: Any) -> Check:
    return ge.make_check(rule, result, message, lines, rules_table=RULES, kb=kw.pop("kb", None) or list(RULES[rule]["kb_refs"]),
                         **kw)


def _applies(line: ge.Line, rule: str, test: Any) -> bool:
    if line.rules is not None:
        return rule in line.rules
    return bool(test(line))


def _offer_text(line: ge.Line) -> str:
    offer = line.raw.get("offer") or {}
    # description first, then title
    return " ".join(str(x) for x in (offer.get("description"), offer.get("title")) if x)


def _subject_text(line: ge.Line) -> str:
    return _offer_text(line) or " ".join(str(x) for x in (line.name, line.raw.get("spec"), line.raw.get("typical_spec")) if x)


def _is_battery(line: ge.Line) -> bool:
    return line.category == "battery"


def _is_display(line: ge.Line) -> bool:
    key = f"{line.row_id or ''} {line.name}"
    return bool(_DISPLAY.search(key)) and not _ADAPTER.search(key)


def _is_adapter(line: ge.Line) -> bool:
    return bool(_ADAPTER.search(f"{line.row_id or ''} {line.name}"))


# --------------------------------------------------------------------------- battery rules


R12_FILTER = {"category": "battery", "connector_family": "PH", "pitch_mm": 2.0, "pins": 2, "cells": 1,
              "exclude_text": ["reverse polarity"]}


def _battery_checks(line: ge.Line) -> list[Check]:
    out: list[Check] = []
    a = line.a
    text = _subject_text(line)
    flt = {"bom_line_id": line.id, **R12_FILTER}
    if line.raw.get("offer") and _NOT_A_BATTERY.search(text) and a.get("capacity_mah") is None and a.get("cells") is None:
        out.append(_mk("R12", "fail", "R12: not a battery (a cable or accessory listing).", [line],
                       fix_text="Pick a single-cell LiPo with a JST-PH 2.0 mm 2-pin plug.", fix_filter=flt))
        return out

    if _applies(line, "R12", _is_battery):
        fam, pitch, pins = a.get("connector_family"), a.get("pitch_mm"), a.get("pins")
        conn = a.get("connector")
        if conn is None or (conn == "JST" and fam is None):
            out.append(_mk("R12", "needs_human", "R12: connector family and pitch not stated in the listing text. "
                           "Needs JST-PH 2.0 mm, 2-pin.", [line]))
        elif fam != "PH" or pitch != 2.0:
            have = ge._connector_label(conn)
            out.append(_mk("R12", "fail", f"R12 FAIL: {have} ≠ JST-PH 2.0 mm.", [line],
                           fix_text="Pick a battery with a JST-PH 2.0 mm 2-pin plug.", fix_filter=flt))
        elif pins is not None and pins != 2:
            out.append(_mk("R12", "fail", f"R12 FAIL: {pins}-pin JST-PH ≠ 2-pin.", [line],
                           fix_text="Pick a battery with a 2-pin JST-PH 2.0 mm plug.", fix_filter=flt))
        elif pins is None:
            out.append(_mk("R12", "needs_human", "JST-PH 2.0 mm, but the pin count is not stated. Needs 2-pin.", [line]))
        else:
            out.append(_mk("R12", "pass", "JST-PH 2.0 mm, 2-pin, as the board needs.", [line]))

    if _applies(line, "R13", _is_battery):
        cells = a.get("cells")
        v = a.get("voltage_v")
        if isinstance(cells, int) and cells != 1:
            out.append(_mk("R13", "fail", f"R13 FAIL: {cells}S pack ({cells * ge.CELL_NOMINAL_V:.1f} V nominal, "
                           f"{cells * ge.CELL_FULL_V:.1f} V full) is above the board's 4.2 V.", [line],
                           fix_text="Pick a single-cell (1S, 3.7 V) battery.", fix_filter=flt))
        elif v is not None and float(v) > ge.CELL_FULL_V:
            out.append(_mk("R13", "fail", f"R13 FAIL: {ge._fmt(v)} V is above the board's 4.2 V.", [line],
                           fix_text="Pick a single-cell (1S, 3.7 V) battery.", fix_filter=flt))
        elif cells == 1:
            out.append(_mk("R13", "pass", "Single cell: 3.7 V nominal, 4.2 V full.", [line]))
        else:
            out.append(_mk("R13", "needs_human", "Cell count not stated (attribute cells). Needs a single cell.", [line]))

    if _applies(line, "R14", _is_battery):
        if a.get("reverse_polarity"):
            out.append(_mk("R14", "fail", "R14: the listing says reverse polarity. Rejected.", [line],
                           fix_text="Pick a battery whose listing does not say reverse polarity.", fix_filter=flt))
        else:
            out.append(_mk("R14", "warn", "Check polarity: JST-PH 2.0 polarity is not standardized. We did not verify it.",
                           [line], needs_ack=True))
    return out


# --------------------------------------------------------------------------- R15-R17


def match_panel(text: str) -> dict[str, Any] | None:
    """The Panel Support row a listing matches by exact model, or None."""
    for row in PANEL_SUPPORT:
        if all(re.search(p, text, re.I) for p in row["must"]) and not any(re.search(p, text, re.I) for p in row["must_not"]):
            return row
    return None


def _panel_checks(line: ge.Line) -> list[Check]:
    if not _applies(line, "R15", _is_display):
        return []
    text = _offer_text(line)
    rec = next(r for r in PANEL_SUPPORT if r["recommended"])
    flt = {"bom_line_id": line.id, "category": line.category or "board", "query": rec["search_query"], "model": rec["model"]}
    if not text:
        return [_mk("R15", "needs_human", "No panel listing yet: the panel must be a README Panel Support model "
                    f"(recommended: {rec['model']}).", [line])]
    row = match_panel(text)
    if row:
        return [_mk("R15", "pass", f"Matches the README Panel Support row L{row['readme_line']}: {row['model']}.", [line])]
    return [_mk("R15", "fail", "R15 FAIL: not a model in the README Panel Support list (size alone is not enough). "
                f"Swap to the recommended {rec['model']}.", [line],
                fix_text=f"Swap to the README's recommended panel: {rec['model']}.", fix_filter=flt)]


def _sensor_checks(line: ge.Line) -> list[Check]:
    if not _applies(line, "R16", lambda ln: ln.category == "sensor"):
        return []
    text = _subject_text(line)
    bme = re.search(r"\bbme\s*-?\s*280\b", text, re.I)
    bmp = re.search(r"\bbmp\s*-?\s*280\b", text, re.I)
    flt = {"bom_line_id": line.id, "category": "sensor", "query": "BME280 temperature humidity pressure sensor"}
    if bmp and not bme:
        return [_mk("R16", "fail", "R16 FAIL: BMP280 measures pressure and temperature, not humidity. Swap to a BME280.",
                    [line], fix_text="Swap to a BME280.", fix_filter=flt)]
    if bme and bmp:
        return [_mk("R16", "needs_human", "Listing names both BME280 and BMP280. Needs your check: humidity is required.",
                    [line])]
    if bme or re.search(r"humidity", text, re.I):
        return [_mk("R16", "pass", "Measures humidity (BME280).", [line])]
    return [_mk("R16", "needs_human", "Sensor does not say it measures humidity. Needs your check.", [line])]


def _adapter_checks(line: ge.Line) -> list[Check]:
    if not _applies(line, "R17", _is_adapter):
        return []
    text = _subject_text(line)
    if re.search(r"despi\s*-?\s*c02(?![0-9])", text, re.I):
        return [_mk("R17", "pass", "DESPI-C02 adapter, as the README recommends. Setup: check the RESE switch position "
                    "(README L140–L142).", [line])]
    if re.search(r"\bhat\b", text, re.I):
        return [_mk("R17", "warn", "Waveshare HAT instead of the DESPI-C02: the README does not recommend rev 2.2/2.3 HATs. "
                    "Setup note: the rev 2.3 HAT has an extra PWR pin (README L138).", [line], needs_ack=True,
                    fix_text="Prefer the DESPI-C02 adapter.",
                    fix_filter={"bom_line_id": line.id, "query": "DESPI-C02 e-paper adapter"})]
    return [_mk("R17", "needs_human", "Adapter model not recognized. The README recommends DESPI-C02. Needs your check.",
                [line])]


# --------------------------------------------------------------------------- pack interface


def check(plan: dict[str, Any], only: list[str] | None = None) -> list[Check]:
    """Run R12-R17 over a plan (shape: see generic_electrical)."""
    lines = ge.lines_of(plan)
    out: list[Check] = []
    for ln in lines:
        if _is_battery(ln) or (ln.rules and {"R12", "R13", "R14"} & set(ln.rules)):
            out.extend(_battery_checks(ln))
        out.extend(_panel_checks(ln))
        out.extend(_sensor_checks(ln))
        out.extend(_adapter_checks(ln))
    if only:
        keep = {ge._norm_rule(x) for x in only}
        out = [c for c in out if c.rule_id.split()[0] in keep]
    return out


def check_offer(line: dict[str, Any], offer: dict[str, Any]) -> list[Check]:
    """Check one candidate listing for this line (the listing's own text decides; description before title)."""
    raw = {k: v for k, v in line.items() if k not in ("attrs", "spec", "typical_spec", "offer")}
    return check({"lines": [{**raw, "offer": offer}]})


def fix(check: Check, plan: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Search filter for a failed check (R12/R13/R14 battery filter, R15 panel swap, R16 BME280, R17 DESPI-C02).

    `plan` is accepted for A's pack interface (rules/base.py) and not needed here.
    """
    return ge.fix(check)


def reject(line: dict[str, Any], offer: dict[str, Any], plan: dict[str, Any] | None = None) -> str | None:
    """A's pack interface (rules/base.py): why `offer` cannot be used for `line` (first FAIL), or None."""
    line = {k: v for k, v in ge._plain(line).items() if k != "chosen"}
    for chk in check_offer(line, ge._plain(offer)):
        if chk.result == "fail":
            return chk.message
    return None


def filter_batteries(line: dict[str, Any], offers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str]]]:
    """Auto-fix for R12/R13 (PLAN §13.3): (kept offers, [(rejected offer, reason)]).

    A listing is rejected only on a FAIL (wrong pitch, wrong pin count, not 1S, reverse polarity, not a battery),
    and every rejection keeps its reason so the battery's part panel can show it. Kept offers whose pin count is
    not stated stay in, after the full passes, with a needs-your-check result; all of them carry the R14 warning.
    """
    full: list[dict[str, Any]] = []
    unsure: list[dict[str, Any]] = []
    rejected: list[tuple[dict[str, Any], str]] = []
    for o in offers:
        checks = check_offer(line, o)
        bad = [c for c in checks if c.result == "fail"]
        if bad:
            rejected.append((o, bad[0].message))
        elif any(c.result == "needs_human" for c in checks):
            unsure.append(o)
        else:
            full.append(o)
    return full + unsure, rejected
