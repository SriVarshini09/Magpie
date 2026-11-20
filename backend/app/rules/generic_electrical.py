"""Rule pack `generic_electrical`: runs on every build (PLAN §3.8, §13.1). Owner: D.

Rules G1-G11. The MVP four are G1, G3, G5, G7; the rest are P20. Every rule cites KB rows
(`kb://compat_rules_generic#g<n>` for the rule text, `kb://electrical_notes#<chunk>` for its sources).

Interface (PLAN §13.1: attrs(listing) -> dict, check(plan) -> Check[], fix(check) -> search filter):

    parse_attrs(text)          normalized attributes from one piece of listing or template text
    attrs(listing)             description first, then title; records where each value came from
    check(plan)                Check[] for a whole plan (BOM level or with chosen offers)
    check_offer(line, offer)   Check[] for one candidate listing against one BOM line (reject on "fail")
    fix(check)                 a search filter for the auto-fix, or None (G7 and other warn-only rules)

The attribute parsers live here; `rules/mcu_battery.py` reuses them (PLAN §13.5).

Plan input shape (tolerant; every key except `lines` is optional):

    plan = {
      "build_type": "quadcopter",
      "lines": [{
          "bom_line_id": "b7", "row_id": "battery", "name": "LiPo battery",      # or "raw_name"
          "category": "battery",                                                  # PLAN §3.19 categories
          "qty": 1,
          "attrs": {"cells": "4S", "connector": "XT30", "capacity_mah": "650-850", "max_current_a": None},
          "spec": "4S 650-850 mAh, XT30",                                         # or "typical_spec"
          "basis": "rule_of_thumb",                                               # reference | rule_of_thumb | ...
          "rules": ["G1", "G3", "G5"],                                            # optional: which rules read this line
          "offer": {"title": "...", "description": "..."},                       # optional: the chosen listing
      }],
      "edges": [{"from": "battery", "to": "esc", "label": "XT30", "rules": ["G5", "G6"]}],   # row_ids or bom_line_ids
    }

Effective attributes of a line = parse(offer.description) > parse(offer.title) > line.attrs > parse(spec).
If a line lists `rules`, a rule reads that line only when the rule id is listed; a line without `rules`
is matched by category. A missing attribute never passes: the result is `needs_human` naming the attribute.
A line whose `basis` is `rule_of_thumb` can only make a rule WARN, never FAIL. Rules marked
`human_check: "always"` never return a bare pass (best case: `needs_human`, "needs your check").
Every non-pass result that needs a person sets `needs_ack=True` (the Statsig gate `strict_compat_rules`
turns those into an acknowledge checkbox before Approve, PLAN §3.15).
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from app.models import Check

PACK_ID = "generic_electrical"

CELL_NOMINAL_V = 3.7
CELL_FULL_V = 4.2
SUPPLY_HEADROOM = 0.8  # G2: loads <= 80% of a supply's rating

_RULE_DOC = "kb://compat_rules_generic#"
_SRC = "kb://electrical_notes#"


def _refs(rule: str, *sources: str) -> list[str]:
    return [_RULE_DOC + rule.lower()] + [_SRC + s for s in sources]


RULES: dict[str, dict[str, Any]] = {
    "G1": {"name": "SUPPLY_VOLTAGE", "mvp": True, "human_check": "conditional",
           "kb_refs": _refs("G1", "arduino_uno_vin", "esp32_devkitc_power", "hcsr04_working", "am2302_dht22"),
           "summary": "The supply or battery voltage lies inside every powered part's stated input range. "
                      "Human check when the range comes only from a listing title."},
    "G2": {"name": "CURRENT_BUDGET", "mvp": False, "human_check": "conditional",
           "kb_refs": _refs("G2", "hcsr04_working", "donkeycar_battery_pack"),
           "summary": "Sum of known load currents <= 80% of the supply rating; for a battery <= capacity (Ah) x C. "
                      "Always a human check when any load current is unknown."},
    "G3": {"name": "CELL_COUNT", "mvp": True, "human_check": "never",
           "kb_refs": _refs("G3", "lipo_cell_voltage", "dfrobot_ph2_power", "px4_f450_esc"),
           "summary": "The battery's cell count lies inside the range the ESC, flight controller, driver or board states."},
    "G4": {"name": "LOGIC_LEVEL", "mvp": False, "human_check": "always",
           "kb_refs": _refs("G4", "espressif_esp32_input", "espressif_gpio_faq", "arduino_uno_ioref"),
           "summary": "A 5 V output must not drive a 3.3 V-only input without a level shifter or divider in the BOM."},
    "G5": {"name": "CONNECTOR_MATCH", "mvp": True, "human_check": "conditional",
           "kb_refs": _refs("G5", "jst_ph_pitch", "jst_xh_pitch", "jst_sh_pitch", "px4_x500_connectors", "waveshare_barrel"),
           "summary": "Mating connectors share family and pitch (JST-XH 2.5, PH 2.0, SH 1.0 mm; XT30 vs XT60; "
                      "barrel 5.5x2.1 vs 5.5x2.5)."},
    "G6": {"name": "CONNECTOR_CURRENT", "mvp": False, "human_check": "conditional",
           "kb_refs": _refs("G6", "holybro_connector_table", "amass_xt60_sheet", "xt30_rating", "jst_ratings"),
           "summary": "Expected continuous current <= the connector's rating (XT60 30 A, XT30 15 A [unverified], "
                      "JST-XH 3 A, PH 2 A, SH 1 A). Human check for XT30."},
    "G7": {"name": "KV_PROP_CELLS", "mvp": True, "human_check": "always",
           "kb_refs": _refs("G7", "oscarliang_motors_kv", "px4_x500_motor_kv", "holybro_x500_kv", "no_3inch_source"),
           "summary": "Motor KV suits the prop size and cell count (rule of thumb; WARN only, always a human check)."},
    "G8": {"name": "ESC_CURRENT", "mvp": False, "human_check": "conditional",
           "kb_refs": _refs("G8", "px4_x500_esc"),
           "summary": "ESC continuous current >= the motor's maximum current. Human check when the motor's maximum "
                      "current is not in the listing."},
    "G9": {"name": "DRIVER_CURRENT", "mvp": False, "human_check": "conditional",
           "kb_refs": _refs("G9", "st_l298", "toshiba_tb6612fng"),
           "summary": "Motor driver current per channel >= the motor's stall current; driver supply range includes "
                      "the battery. Human check when stall current is not listed."},
    "G10": {"name": "SERVO_SUPPLY", "mvp": False, "human_check": "conditional",
            "kb_refs": _refs("G10", "donkeycar_servo_rail", "sts3215_classes", "sg90_range"),
            "summary": "Servo supply inside the servo's range, on its own rail, not the controller's logic pin. "
                       "Human check for SG90-class numbers."},
    "G11": {"name": "PIN_CURRENT", "mvp": False, "human_check": "always",
            "kb_refs": _refs("G11", "arduino_pin_current"),
            "summary": "No motor, servo or relay coil is driven straight from a GPIO pin (use the driver in the BOM)."},
    "G12": {"name": "STACK_MOUNT", "mvp": False, "human_check": "conditional",
            "kb_refs": _refs("G12", "fpv_stack_mounting"),
            "summary": "Flight controller, ESC and VTX boards in one stack share its mounting pattern (20x20, 25.5x25.5 "
                       "or 30x30 mm). A listing for another pattern is rejected; one that states none is not judged."},
}

MVP_RULES = tuple(r for r, info in RULES.items() if info["mvp"])

# Connector ratings for G6 (A, continuous). XT30 is second-hand [unverified] -> always a human check.
CONNECTOR_RATING_A: dict[str, tuple[float, float | None, str]] = {
    "XT60": (30.0, 60.0, "holybro_connector_table"),
    "XT30": (15.0, 30.0, "xt30_rating"),
    "JST-XH": (3.0, None, "jst_ratings"),
    "JST-PH": (2.0, None, "jst_ratings"),
    "JST-SH": (1.0, None, "jst_ratings"),
}
UNVERIFIED_RATINGS = frozenset({"XT30"})

# G7 usual KV windows: (prop class in inches, cells) -> (low, high, source chunk). Rule of thumb.
KV_WINDOWS: dict[tuple[int, int], tuple[int, int, str]] = {
    (5, 4): (2300, 2800, "oscarliang_motors_kv"),
    (5, 6): (1600, 2100, "oscarliang_motors_kv"),
    (10, 4): (880, 920, "px4_x500_motor_kv"),  # PX4 page KV880 vs Holybro page KV920: both cited
}

# G9 driver chips: name pattern -> (amps per channel continuous, peak, max supply V, source chunk)
DRIVER_CHIPS: list[tuple[re.Pattern[str], float, float | None, float, str]] = [
    (re.compile(r"\bl298n?\b", re.I), 2.0, None, 46.0, "st_l298"),
    (re.compile(r"\btb6612(?:fng)?\b", re.I), 1.2, 3.2, 15.0, "toshiba_tb6612fng"),
]

# G10: SG90 4.8-6 V has no official sheet [unverified] -> human check.
SG90_RANGE = (4.8, 6.0)

POWERED_CATEGORIES = frozenset({"board", "esc_driver", "sensor", "camera", "radio"})
SUPPLY_CATEGORIES = frozenset({"battery", "power"})
LOAD_CATEGORIES = frozenset({"motor", "board", "sensor", "camera", "radio"})

# --------------------------------------------------------------------------- parsers

_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "×": "x", "″": '"', "”": '"',
                         "∼": "~", "～": "~"})
_NUM = r"(\d+(?:\.\d+)?)"
LIPO_NOMINALS = {1: 3.7, 2: 7.4, 3: 11.1, 4: 14.8, 5: 18.5, 6: 22.2}


def _blank(text: str, m: re.Match[str]) -> str:
    return text[: m.start()] + " " * (m.end() - m.start()) + text[m.end():]


def _sub_all(pattern: re.Pattern[str], text: str, fn: Any) -> str:
    """Call fn(match) for every match of pattern and blank the matched span."""
    while True:
        m = pattern.search(text)
        if not m:
            return text
        fn(m)
        text = _blank(text, m)


_CONN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 1.25 mm pitch first, so it can never be read as PH 2.0 ("JST 1.25", "Micro JST 1.25", "SH1.25", "PH1.25")
    (re.compile(r"(?:micro\s*)?jst\s*[-_ ]?\s*(?:type\s*)?(?:sh|ph|gh|zh)?\s*[-_ ]?\s*1\.25(?:\s*mm)?", re.I), "JST-1.25"),
    (re.compile(r"\b(?:micro\s*)?(?:sh|ph|gh|zh)\s*[-_ ]?\s*1\.25(?:\s*mm)?", re.I), "JST-1.25"),
    (re.compile(r"\b1\.25\s*mm\s*(?:pitch\s*)?(?:jst|connector|plug)", re.I), "JST-1.25"),
    (re.compile(r"\bpicoblade\b", re.I), "JST-1.25"),
    (re.compile(r"\bjst\s*[-_ ]?\s*(?:type\s*)?ph(?:\s*[-_ ]?\s*2(?:\.0)?(?![\d.])(?:\s*mm)?)?", re.I), "JST-PH"),
    (re.compile(r"\bph\s*[-_ ]?\s*2\.0(?:\s*mm)?", re.I), "JST-PH"),
    (re.compile(r"\bjst\s*[-_ ]?\s*(?:type\s*)?xh(?:\s*[-_ ]?\s*2\.54?(?:\s*mm)?)?", re.I), "JST-XH"),
    (re.compile(r"\bxh\s*[-_ ]?\s*2\.54?(?:\s*mm)?", re.I), "JST-XH"),
    (re.compile(r"\bjst\s*[-_ ]?\s*(?:type\s*)?sh(?:\s*[-_ ]?\s*1(?:\.0)?(?![\d.])(?:\s*mm)?)?", re.I), "JST-SH"),
    (re.compile(r"\bsh\s*[-_ ]?\s*1\.0(?:\s*mm)?", re.I), "JST-SH"),
    (re.compile(r"\bxt\s*[-_ ]?\s*(30|60|90)\s*(?:h|u|e)?(?![0-9a-z])", re.I), "XT"),
    (re.compile(r"(?<![\d.])5\.5\s*(?:mm)?\s*[x*/]\s*(2\.1|2\.5)\s*(?:mm)?", re.I), "BARREL"),  # also A's "barrel_5.5x2.1"
    (re.compile(r"\bjst\b", re.I), "JST"),
]

CONNECTOR_FAMILY: dict[str, tuple[str | None, float | None]] = {
    "JST-PH": ("PH", 2.0), "JST-XH": ("XH", 2.5), "JST-SH": ("SH", 1.0), "JST-1.25": (None, 1.25), "JST": (None, None),
}


def _connector_label(token: str) -> str:
    """Human-readable form used in messages: 'JST-PH 2.0 mm', 'JST 1.25 mm', 'XT60', 'barrel 5.5x2.1 mm'."""
    if token in CONNECTOR_FAMILY:
        fam, pitch = CONNECTOR_FAMILY[token]
        if token == "JST":
            return "JST (family not stated)"
        return f"JST-{fam} {pitch:.1f} mm" if fam else f"JST {pitch} mm"
    if token.startswith("BARREL-"):
        return f"barrel {token[7:]} mm"
    return token


def parse_connectors(text: str | None) -> tuple[list[str], str]:
    """Return (connector tokens in order of appearance, text with those spans blanked)."""
    if not text:
        return [], ""
    t = str(text).translate(_DASHES)
    found: list[tuple[int, str]] = []
    for pattern, kind in _CONN_PATTERNS:
        def take(m: re.Match[str], kind: str = kind) -> None:
            if kind == "XT":
                found.append((m.start(), f"XT{m.group(1)}"))
            elif kind == "BARREL":
                found.append((m.start(), f"BARREL-5.5x{m.group(1)}"))
            else:
                found.append((m.start(), kind))
        t = _sub_all(pattern, t, take)
    tokens: list[str] = []
    for _, tok in sorted(found):
        if tok not in tokens:
            tokens.append(tok)
    # a bare "JST" adds nothing when a specific JST family is also named
    if "JST" in tokens and any(x.startswith("JST-") for x in tokens):
        tokens.remove("JST")
    return tokens, t


_NEGATED = re.compile(r"not\s+work|won'?t\s+work|will\s+not|incompatible|not\s+compatible|does\s+not\s+fit|instead\s+of", re.I)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_attrs(text: str | None) -> dict[str, Any]:
    """Normalized attributes from one text (listing title, description, template spec).

    Keys (only those found are present): connector, connectors, connector_family, pitch_mm, barrel,
    pins, cells, cells_range, cells_from ("count" | "voltage"), voltage_v, voltages, voltage_range,
    mains_range, logic_v, logic_compat, five_v_tolerant, current_a, max_current_a, stall_current_a,
    capacity_mah, capacity_range, c_rating, kv, kv_range, size_in, prop_in, reverse_polarity,
    polarity_note, level_shifter.
    """
    out: dict[str, Any] = {}
    if not text:
        return out
    tokens, t = parse_connectors(text)
    if tokens:
        out["connectors"] = tokens
        out["connector"] = tokens[0]
        first_jst = next((x for x in tokens if x in CONNECTOR_FAMILY), None)
        if first_jst and first_jst != "JST":
            fam, pitch = CONNECTOR_FAMILY[first_jst]
            out["connector_family"] = fam
            out["pitch_mm"] = pitch
        barrel = next((x for x in tokens if x.startswith("BARREL-")), None)
        if barrel:
            out["barrel"] = barrel[7:]
    low = t

    if re.search(r"revers(?:e|ed)\s*polarity", low, re.I):
        out["reverse_polarity"] = True
    if re.search(r"check\s*(?:the\s*)?polarity|polarity\s*(?:is\s*)?not\s*standardi[sz]ed", low, re.I):
        out["polarity_note"] = True
    if re.search(r"level[\s-]*(?:shifter|converter|translator)|logic[\s-]*level[\s-]*(?:shifter|converter)", low, re.I):
        out["level_shifter"] = True

    # pins ("2-pin", "3 pin", "2P"); a count in a negative context ("will not work with ... 2-pin") is not this part's
    def pins(m: re.Match[str]) -> None:
        if _NEGATED.search(m.string[max(0, m.start() - 50): m.start()]):
            return
        out.setdefault("pins", int(m.group(1)))
    low = _sub_all(re.compile(r"\b(\d{1,2})\s*-?\s*pins?\b", re.I), low, pins)
    low = _sub_all(re.compile(r"(?<![sS\d.])(\d)\s*P\b"), low, pins)

    # logic levels
    if re.search(r"not\s*5\s*v\s*tolerant", low, re.I):
        out["five_v_tolerant"] = False
    elif re.search(r"\b5\s*v\s*tolerant", low, re.I):
        out["five_v_tolerant"] = True

    def compat(m: re.Match[str]) -> None:
        out["logic_compat"] = [3.3, 5.0]
    low = _sub_all(re.compile(r"\b3\.3\s*v?\s*/\s*5\s*v\b(?:\s*(?:compatible|tolerant|logic))?", re.I), low, compat)

    def logic(m: re.Match[str]) -> None:
        out.setdefault("logic_v", float(m.group(1)))
    low = _sub_all(re.compile(r"\b(3\.3|5(?:\.0)?)\s*v\s*(?:logic|i/o|io\b|gpio|signal)", re.I), low, logic)
    low = _sub_all(re.compile(r"\blogic(?:\s*level)?\s*(?:of|:|=)?\s*(3\.3|5(?:\.0)?)\s*v\b", re.I), low, logic)

    # cell counts
    def crange(m: re.Match[str]) -> None:
        out.setdefault("cells_range", [int(m.group(1)), int(m.group(2))])
    low = _sub_all(re.compile(r"\b(\d{1,2})\s*s?\s*(?:-|~|to)\s*(\d{1,2})\s*s\b", re.I), low, crange)

    def cells(m: re.Match[str]) -> None:
        if "cells" not in out:
            out["cells"] = int(m.group(1))
            out["cells_from"] = "count"
    low = _sub_all(re.compile(r"\b(\d{1,2})\s*s(?:\d+p)?\b", re.I), low, cells)
    low = _sub_all(re.compile(r"\b(\d{1,2})\s*-?\s*cells?\b", re.I), low, cells)

    # capacity
    def cap_range(m: re.Match[str]) -> None:
        out.setdefault("capacity_range", [int(_num(m.group(1))), int(_num(m.group(2)))])
    low = _sub_all(re.compile(r"\b(\d{2,6})\s*-\s*(\d{2,6})\s*m\s*a\s*h\b", re.I), low, cap_range)

    def cap(m: re.Match[str]) -> None:
        out.setdefault("capacity_mah", int(_num(m.group(1))))
    low = _sub_all(re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{2,6})\s*m\s*a\s*h\b", re.I), low, cap)

    # KV
    def kvr(m: re.Match[str]) -> None:
        out.setdefault("kv_range", [int(m.group(1)), int(m.group(2))])
    low = _sub_all(re.compile(r"\b(\d{3,5})\s*-\s*(\d{3,5})\s*kv\b", re.I), low, kvr)

    def kv(m: re.Match[str]) -> None:
        out.setdefault("kv", int(m.group(1) or m.group(2)))
    low = _sub_all(re.compile(r"\b(\d{2,5})\s*-?\s*kv\b|\bkv\s*-?\s*(\d{2,5})\b", re.I), low, kv)

    # props and sizes
    has_prop = re.search(r"\bprop(?:s|eller|ellers)?\b", low, re.I) is not None

    def prop_code(m: re.Match[str]) -> None:
        code = m.group(1) or m.group(2)
        lead = int(code[:2])
        inches = float(lead) if 10 <= lead <= 15 else int(code[0]) + int(code[1]) / 10
        out.setdefault("prop_in", inches)
    low = _sub_all(re.compile(r"\b(\d{4})\s*(?:props?|propellers?)\b|\bprop(?:s|ellers?)?\s*[:\-]?\s*(\d{4})\b", re.I),
                   low, prop_code)

    def size(m: re.Match[str]) -> None:
        out.setdefault("size_in", float(m.group(1)))
    low = _sub_all(re.compile(r"\b" + _NUM + r'\s*(?:-\s*)?(?:inch(?:es)?\b|in\b(?!\s*\d)|")', re.I), low, size)
    if has_prop and "prop_in" not in out and "size_in" in out:
        out["prop_in"] = out["size_in"]

    # C rating
    def crate(m: re.Match[str]) -> None:
        out.setdefault("c_rating", float(m.group(1)))
    low = _sub_all(re.compile(r"(?<![\d.°])\b(\d{1,3}(?:\.\d+)?)[cC](?![a-zA-Z0-9])"), low, crate)

    # voltage ranges, then single voltages
    def vrange(m: re.Match[str]) -> None:
        lo, hi = float(m.group(1)), float(m.group(2))
        if hi >= 90:
            out.setdefault("mains_range", [lo, hi])
        else:
            out.setdefault("voltage_range", [lo, hi])
    low = _sub_all(re.compile(r"(?<![\d.])" + _NUM + r"\s*(?:v(?:dc)?)?\s*(?:-|~|to)\s*" + _NUM + r"\s*v(?:dc|ac)?(?![a-z0-9])", re.I),
                   low, vrange)

    volts: list[float] = []

    def volt(m: re.Match[str]) -> None:
        v = float(m.group(1))
        if v >= 90:
            out.setdefault("mains_v", v)
        else:
            volts.append(v)
    low = _sub_all(re.compile(r"(?<![\d.])" + _NUM + r"\s*v(?:dc|ac)?(?![a-z0-9])", re.I), low, volt)
    if volts:
        out["voltages"] = volts
        out["voltage_v"] = volts[0]
        if "cells" not in out and "cells_range" not in out:
            for v in volts:
                n = next((n for n, nom in LIPO_NOMINALS.items() if abs(nom - v) < 0.051), None)
                if n:
                    out["cells"] = n
                    out["cells_from"] = "voltage"  # 14.8 V / 3.7 V: inferred, no explicit S count
                    break

    # currents (after voltages; "mAh" is already consumed)
    def amp(m: re.Match[str]) -> None:
        val = float(m.group(1)) / (1000 if m.group(2).lower() == "ma" else 1)
        before = low_now[max(0, m.start() - 14): m.start()].lower()
        after = low_now[m.end(): m.end() + 14].lower()
        if "stall" in before or "stall" in after:
            out.setdefault("stall_current_a", val)
        elif re.search(r"peak|burst|max", before + " " + after):
            out.setdefault("max_current_a", val)
        else:
            out.setdefault("current_a", val)
    pat_a = re.compile(r"(?<![\d.])" + _NUM + r"\s*(ma|a)(?![a-z])", re.I)
    while True:
        low_now = low
        m = pat_a.search(low)
        if not m:
            break
        amp(m)
        low = _blank(low, m)
    return out


def attrs(listing: dict[str, Any] | str | None) -> dict[str, Any]:
    """Attributes of one listing: description first, then title (PLAN §3.8, SD §4).

    Values found in the description win. `_from` maps each key to "description" | "title" | "text".
    A bare "JST" in the description does not override a specific JST family named in the title.
    """
    if listing is None:
        return {}
    if isinstance(listing, str):
        a = parse_attrs(listing)
        return {**a, "_from": {k: "text" for k in a}}
    ta = parse_attrs(listing.get("title"))
    da = parse_attrs(listing.get("description"))
    out: dict[str, Any] = {}
    src: dict[str, str] = {}
    for k, v in ta.items():
        out[k], src[k] = v, "title"
    vague_desc = da.get("connector") == "JST" and "connector_family" not in da
    for k, v in da.items():
        if vague_desc and k in ("connector", "connectors") and ta.get("connector_family"):
            continue
        out[k], src[k] = v, "description"
    out["_from"] = src
    return out


# --------------------------------------------------------------------------- line model


_NUMERIC_KEYS = {
    "voltage_v", "supply_v", "logic_v", "current_a", "max_current_a", "stall_current_a", "load_current_a",
    "expected_current_a", "capacity_mah", "c_rating", "pitch_mm", "prop_in", "size_in", "max_voltage_v", "pins",
}
_RANGE_KEYS = {"voltage_range", "cells_range", "kv_range", "capacity_range"}


def _first_number(s: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group(0)) if m else None


def _as_range(v: Any) -> list[float] | None:
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return [float(v[0]), float(v[1])]
    if isinstance(v, str):
        m = re.search(r"(\d+(?:\.\d+)?)\s*[a-zA-Z]*\s*(?:-|~|to)\s*(\d+(?:\.\d+)?)", v.translate(_DASHES))
        if m:
            return [float(m.group(1)), float(m.group(2))]
    return None


def _coerce_attrs(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize template / resolved attrs ("4S", "3500-4500", "XT-60", "5A") to the parser's keys."""
    out: dict[str, Any] = {}
    for k, v in (raw or {}).items():
        if v is None or v == "":
            continue  # null = unknown, never a guess
        if k == "cells":
            if isinstance(v, (int, float)):
                out["cells"], out["cells_from"] = int(v), "count"
            else:
                p = parse_attrs(str(v))
                for key in ("cells", "cells_range", "cells_from"):
                    if key in p:
                        out[key] = p[key]
                opts = [int(x) for x in re.findall(r"(\d{1,2})\s*s\b", str(v), re.I)]
                if len(opts) > 1 and "cells_range" not in p:
                    out["cells_options"] = opts
                    out.pop("cells", None)
        elif k == "kv":
            r = _as_range(v)
            if r:
                out["kv_range"] = [int(r[0]), int(r[1])]
            else:
                n = _first_number(str(v))
                if n is not None:
                    out["kv"] = int(n)
        elif k in _RANGE_KEYS:
            r = _as_range(v)
            if r:
                out[k] = [int(x) for x in r] if k in ("cells_range", "kv_range", "capacity_range") else r
        elif k in ("voltage", "input_voltage", "vin", "input_v"):
            p = parse_attrs(str(v) if not isinstance(v, (int, float)) else f"{v}V")
            for key in ("voltage_range", "voltage_v"):
                if key in p:
                    out[key] = p[key]
        elif k in ("connector", "connectors", "plug"):
            items = v if isinstance(v, list) else [v]
            toks: list[str] = []
            for item in items:
                tk, _ = parse_connectors(str(item))
                toks.extend(x for x in tk if x not in toks)
            if toks:
                out["connectors"] = toks
                out["connector"] = toks[0]
                jst = next((x for x in toks if x in CONNECTOR_FAMILY and x != "JST"), None)
                if jst:
                    out["connector_family"], out["pitch_mm"] = CONNECTOR_FAMILY[jst]
                barrel = next((x for x in toks if x.startswith("BARREL-")), None)
                if barrel:
                    out["barrel"] = barrel[7:]
            else:
                out[k] = v
        elif k == "barrel":
            tk, _ = parse_connectors(f"{v}")
            b = next((x for x in tk if x.startswith("BARREL-")), None)
            out["barrel"] = b[7:] if b else v
        elif k in _NUMERIC_KEYS:
            if isinstance(v, bool):
                out[k] = v
            elif isinstance(v, (int, float)):
                out[k] = v
            else:
                s = str(v)
                r = _as_range(s)
                if r and k in ("voltage_v", "capacity_mah"):
                    out["voltage_range" if k == "voltage_v" else "capacity_range"] = r if k == "voltage_v" else [int(x) for x in r]
                    continue
                n = _first_number(s)
                if n is not None:
                    if re.search(r"\d\s*ma\b", s, re.I) and k.endswith("current_a"):
                        n = n / 1000
                    out[k] = int(n) if k in ("capacity_mah", "pins") else n
        else:
            out[k] = v
    return out


@dataclass
class Line:
    """One BOM line as the rules see it."""

    id: str
    row_id: str | None
    name: str
    category: str | None
    qty: int
    a: dict[str, Any]
    src: dict[str, str]
    basis: str | None
    rules: list[str] | None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def keys(self) -> set[str]:
        return {k for k in (self.id, self.row_id) if k}

    @property
    def rot(self) -> bool:
        return self.basis == "rule_of_thumb"

    def text(self) -> str:
        offer = self.raw.get("offer") or {}
        return " ".join(str(x) for x in (self.name, self.raw.get("spec"), self.raw.get("typical_spec"),
                                          offer.get("title"), offer.get("description")) if x)


def _norm_rule(r: str) -> str:
    return str(r).strip().split()[0].upper()


def _plain(obj: Any) -> Any:
    return obj.model_dump(mode="json", by_alias=True) if hasattr(obj, "model_dump") else obj


def to_line(raw: dict[str, Any]) -> Line:
    """Build the rules' view of one BOM line (effective attrs with their source)."""
    raw = _plain(raw)
    if not raw.get("offer") and raw.get("chosen"):
        # A's plan shape (rules/base.py): `chosen` is a list of offers for this line; rules read the first one.
        first = _plain(raw["chosen"][0]) or {}
        raw = {**raw, "offer": {"title": first.get("title"), "description": first.get("description"),
                                "attrs": first.get("attrs") or {}, "spec_reads": first.get("spec_reads") or []}}
    eff: dict[str, Any] = {}
    src: dict[str, str] = {}

    def layer(values: dict[str, Any], name: str) -> None:
        for k, v in values.items():
            if k == "_from":
                continue
            eff[k], src[k] = v, name

    spec = raw.get("spec") or raw.get("typical_spec")
    layer(parse_attrs(spec), "spec")
    layer(_coerce_attrs(raw.get("attrs")), "attrs")
    offer = raw.get("offer") or {}
    layer(_coerce_attrs(offer.get("attrs")), "offer.attrs")  # already parsed by A's listing_attrs, if present
    layer(parse_attrs(offer.get("title")), "offer.title")
    d = parse_attrs(offer.get("description"))
    if d.get("connector") == "JST" and "connector_family" not in d and eff.get("connector_family"):
        d = {k: v for k, v in d.items() if k not in ("connector", "connectors")}
    layer(d, "offer.description")
    if offer.get("spec_reads"):  # what SIE extract (or the labelled mock reader) read wins over the patterns
        layer(_read_attrs(offer["spec_reads"]), "offer.spec_read")
    rules = raw.get("rules")
    qty = raw.get("qty")
    return Line(
        id=str(raw.get("bom_line_id") or raw.get("row_id") or raw.get("id") or "?"),
        row_id=raw.get("row_id"),
        name=str(raw.get("name") or raw.get("raw_name") or raw.get("row_id") or "part"),
        category=raw.get("category"),
        qty=int(qty) if isinstance(qty, (int, float)) and qty else 1,
        a=eff, src=src, basis=raw.get("basis"),
        rules=[_norm_rule(r) for r in rules] if isinstance(rules, list) else None,
        raw=raw,
    )


def _read_attrs(reads: Any) -> dict[str, Any]:
    """Spec reads as parser keys (rules/spec_reads.py). Never raises: with no usable read the patterns apply."""
    try:
        from app.rules import spec_reads  # lazy: spec_reads imports this module

        return spec_reads.rule_attrs(reads)
    except Exception:
        return {}


def _best_reads(reads: Any) -> dict[str, dict[str, Any]]:
    try:
        from app.rules import spec_reads

        return spec_reads.best(reads)
    except Exception:
        return {}


def _read_note(read: dict[str, Any] | None, fallback: str) -> str:
    """Who read the value a rule judged: 'SIE read “20x20” in the title', 'mock SIE read “20x20”', else the title."""
    if read:
        from app.rules import spec_reads

        return spec_reads.note(read) or fallback
    return fallback


def lines_of(plan: dict[str, Any]) -> list[Line]:
    plan = _plain(plan)
    return [to_line(ln) for ln in (plan.get("lines") or plan.get("bom") or [])]


def applies(line: Line, rule: str, categories: frozenset[str] | set[str] | None = None) -> bool:
    if line.rules is not None:
        return _norm_rule(rule) in line.rules
    return categories is not None and line.category in categories


def _is_servo(line: Line) -> bool:
    return bool(re.search(r"\bservo|sg90|mg996|sts3215", line.text(), re.I)) and line.category in ("motor", None)


def _is_dc_actuator(line: Line) -> bool:
    t = line.text()
    if re.search(r"relay|solenoid|coil|pump", t, re.I):
        return True
    return line.category == "motor" and not _is_servo(line) and not re.search(r"brushless|\bkv\b|\d{4}\s*kv", t, re.I) \
        and bool(re.search(r"\bdc\b|gear\s*motor|gearmotor|\btt\b|vibration", t, re.I))


# --------------------------------------------------------------------------- check helpers

_FILTERS: OrderedDict[str, dict[str, Any]] = OrderedDict()
_FILTER_CAP = 512


def _fkey(rule_id: str, bom_line_ids: list[str], message: str) -> str:
    return json.dumps([rule_id, list(bom_line_ids), message], ensure_ascii=False)


def rule_id(rule: str, rules: dict[str, dict[str, Any]] | None = None) -> str:
    info = (rules or RULES)[rule]
    return f"{rule} {info['name']}"


def make_check(rule: str, result: str, message: str, lines: list[Line], *, kb: list[str] | None = None,
               fix_text: str | None = None, fix_filter: dict[str, Any] | None = None, needs_ack: bool | None = None,
               rules_table: dict[str, dict[str, Any]] | None = None) -> Check:
    """One Check. A rule-of-thumb line can only make a rule WARN; non-pass human results need an ack."""
    table = rules_table or RULES
    downgraded = False
    if result == "fail" and any(ln.rot for ln in lines):
        result, downgraded = "warn", True
        message += " (from a rule-of-thumb row: warning only)"
    if needs_ack is None:
        needs_ack = result == "needs_human" or downgraded or (result == "warn" and table[rule]["human_check"] != "never")
    ids = []
    for ln in lines:
        if ln.id not in ids:
            ids.append(ln.id)
    rid = rule_id(rule, table)
    chk = Check(rule_id=rid, result=result, message=message, fix=fix_text, kb_refs=kb or list(table[rule]["kb_refs"]),
                bom_line_ids=ids, needs_ack=bool(needs_ack and result != "pass"))
    if fix_filter is not None and result in ("fail", "warn"):
        _FILTERS[_fkey(rid, ids, message)] = fix_filter
        while len(_FILTERS) > _FILTER_CAP:
            _FILTERS.popitem(last=False)
    return chk


def _kb(rule: str, *sources: str) -> list[str]:
    return _refs(rule, *sources)


def fix(check: Check, plan: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The search filter for a failed or warned check, or None when the rule has no auto-fix (G7, G2...).

    `plan` is accepted for A's pack interface (rules/base.py) and not needed here.
    """
    return _FILTERS.get(_fkey(check.rule_id, list(check.bom_line_ids), check.message))


def _fmt(v: float) -> str:
    return f"{v:g}"


def _battery_window(line: Line) -> tuple[float, float] | None:
    """Voltage window of a supply line: a battery spans nominal to full charge; a PSU is one value."""
    a = line.a
    if line.category == "battery":
        if isinstance(a.get("cells"), int):
            n = a["cells"]
            return n * CELL_NOMINAL_V, n * CELL_FULL_V
        if a.get("voltage_range"):
            lo, hi = a["voltage_range"]
            return float(lo), float(hi)
        if a.get("voltage_v") is not None:
            return float(a["voltage_v"]), float(a["voltage_v"])
        return None
    if a.get("voltage_v") is not None:
        return float(a["voltage_v"]), float(a["voltage_v"])
    if a.get("supply_v") is not None:
        return float(a["supply_v"]), float(a["supply_v"])
    return None


def _edges(plan: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for e in plan.get("edges") or []:
        frm = e.get("from", e.get("from_"))
        out.append({"from": frm, "to": e.get("to"), "label": e.get("label") or "",
                    "rules": [_norm_rule(r) for r in (e.get("rules") or e.get("rule_ids") or [])],
                    "current_a": e.get("current_a")})
    return out


def _by_key(lines: list[Line]) -> dict[str, Line]:
    m: dict[str, Line] = {}
    for ln in lines:
        for k in ln.keys:
            m.setdefault(k, ln)
    return m


def _supplies(lines: list[Line]) -> list[Line]:
    return [ln for ln in lines if ln.category in SUPPLY_CATEGORIES]


def _supply_for(part: Line, lines: list[Line], edges: list[dict[str, Any]]) -> tuple[Line | None, float | None, str]:
    """Which supply powers `part`: its own supply_v attr, an edge from a supply, or the only supply."""
    if part.a.get("supply_v") is not None:
        return None, float(part.a["supply_v"]), "stated rail"
    keys = _by_key(lines)
    for e in edges:
        if e["to"] in part.keys and e["from"] in keys and keys[e["from"]].category in SUPPLY_CATEGORIES:
            return keys[e["from"]], None, "edge"
        if e["from"] in part.keys and e["to"] in keys and keys[e["to"]].category in SUPPLY_CATEGORIES:
            return keys[e["to"]], None, "edge"
    sup = [s for s in _supplies(lines) if s is not part]
    if len(sup) == 1:
        return sup[0], None, "only supply"
    batteries = [s for s in sup if s.category == "battery"]
    if len(batteries) == 1:
        return batteries[0], None, "only battery"  # a PDB or power module passes the battery voltage on
    return None, None, "unknown" if sup else "none"


# --------------------------------------------------------------------------- G1 SUPPLY_VOLTAGE


def g1_supply_voltage(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    edges = _edges(plan)
    out: list[Check] = []
    for part in lines:
        if part.category in SUPPLY_CATEGORIES or part.category == "tool":
            continue
        if not (applies(part, "G1", POWERED_CATEGORIES) or (part.rules is None and part.a.get("voltage_range"))):
            continue
        sup, rail, how = _supply_for(part, lines, edges)
        if how == "none":
            continue  # nothing in the plan supplies power (USB-powered build): nothing to compare
        if sup is None and rail is None:
            out.append(make_check("G1", "needs_human", f"Which supply powers {part.name}? More than one supply and no "
                                  "connection says which.", [part]))
            continue
        window = (rail, rail) if rail is not None else _battery_window(sup)  # type: ignore[arg-type]
        involved = [part] + ([sup] if sup else [])
        if window is None:
            out.append(make_check("G1", "needs_human", f"Supply voltage of {sup.name} is unknown (attribute "  # type: ignore[union-attr]
                                  "voltage_v or cells). Needs your check.", involved))
            continue
        lo, hi = window
        sup_txt = f"{_fmt(lo)}–{_fmt(hi)} V" if lo != hi else f"{_fmt(lo)} V"
        rng = part.a.get("voltage_range")
        if rng:
            pmin, pmax = float(rng[0]), float(rng[1])
            title_only = part.src.get("voltage_range") == "offer.title"
            if hi > pmax or lo < pmin:
                out.append(make_check(
                    "G1", "fail", f"{sup.name if sup else 'The supply'} gives {sup_txt}; {part.name} takes "
                    f"{_fmt(pmin)}–{_fmt(pmax)} V.", involved,
                    fix_text=f"Pick a supply inside {_fmt(pmin)}–{_fmt(pmax)} V.",
                    fix_filter={"bom_line_id": sup.id if sup else None, "category": sup.category if sup else "power",
                                "voltage_min": pmin, "voltage_max": pmax}))
            elif title_only:
                out.append(make_check("G1", "needs_human", f"{sup_txt} is inside {_fmt(pmin)}–{_fmt(pmax)} V, but that "
                                      f"range comes only from the listing title of {part.name}. Needs your check.", involved))
            else:
                out.append(make_check("G1", "pass", f"{sup_txt} is inside {part.name}'s {_fmt(pmin)}–{_fmt(pmax)} V.", involved))
            continue
        rated = part.a.get("voltage_v")
        if rated is not None:
            if lo <= float(rated) <= hi:
                out.append(make_check("G1", "pass", f"{part.name} is rated {_fmt(rated)} V and gets {sup_txt}.", involved))
            else:
                out.append(make_check("G1", "needs_human", f"{part.name} is rated {_fmt(rated)} V and gets {sup_txt}; no "
                                      "input range is stated. Needs your check against the datasheet.", involved))
            continue
        out.append(make_check("G1", "needs_human", f"Input voltage range of {part.name} is unknown (attribute "
                              "voltage_range). Needs your check.", involved))
    return out


# --------------------------------------------------------------------------- G2 CURRENT_BUDGET


def _load_current(line: Line) -> float | None:
    for k in ("load_current_a", "max_current_a", "current_a"):
        if line.a.get(k) is not None:
            return float(line.a[k])
    return None


def g2_current_budget(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    supplies = [s for s in _supplies(lines) if applies(s, "G2", SUPPLY_CATEGORIES)]
    if not supplies:
        return []
    edges = _edges(plan)
    loads_all = [ln for ln in lines if ln.category in LOAD_CATEGORIES or ln.a.get("load_current_a") is not None]
    out: list[Check] = []
    for sup in supplies:
        connected = {e["to"] for e in edges if e["from"] in sup.keys} | {e["from"] for e in edges if e["to"] in sup.keys}
        if connected:
            loads = [ln for ln in loads_all if ln.keys & connected]
        elif len(_supplies(lines)) == 1:
            loads = loads_all
        else:
            out.append(make_check("G2", "needs_human", f"Which loads does {sup.name} feed? More than one supply and no "
                                  "connections.", [sup]))
            continue
        if not loads:
            continue
        a = sup.a
        if sup.category == "battery":
            if a.get("capacity_mah") is None or a.get("c_rating") is None:
                missing = "capacity_mah" if a.get("capacity_mah") is None else "c_rating"
                out.append(make_check("G2", "needs_human", f"{sup.name}: discharge limit unknown (attribute {missing}).",
                                      [sup] + loads))
                continue
            limit = float(a["capacity_mah"]) / 1000 * float(a["c_rating"])
            limit_txt = f"{_fmt(round(limit, 2))} A ({_fmt(a['capacity_mah'])} mAh x {_fmt(a['c_rating'])}C)"
        else:
            if a.get("current_a") is None:
                out.append(make_check("G2", "needs_human", f"{sup.name}: current rating unknown (attribute current_a).",
                                      [sup] + loads))
                continue
            limit = float(a["current_a"]) * SUPPLY_HEADROOM
            limit_txt = f"{_fmt(round(limit, 2))} A (80% of {_fmt(a['current_a'])} A)"
        known = 0.0
        unknown: list[str] = []
        for ln in loads:
            c = _load_current(ln)
            if c is None:
                unknown.append(ln.name)
            else:
                known += c * ln.qty
        known = round(known, 3)
        if known > limit:
            out.append(make_check("G2", "warn", f"Loads draw at least {_fmt(known)} A; the limit is {limit_txt}.",
                                  [sup] + loads, fix_text="Pick a supply with more current, or fewer loads.",
                                  fix_filter={"bom_line_id": sup.id, "category": sup.category,
                                              "current_min_a": round(known / SUPPLY_HEADROOM, 2) if sup.category != "battery" else None},
                                  needs_ack=True))
        elif unknown:
            out.append(make_check("G2", "needs_human", f"At least {_fmt(known)} A of {limit_txt}; current unknown for: "
                                  f"{', '.join(unknown)}. Needs your check.", [sup] + loads))
        else:
            out.append(make_check("G2", "pass", f"Loads draw {_fmt(known)} A; the limit is {limit_txt}.", [sup] + loads))
    return out


# --------------------------------------------------------------------------- G3 CELL_COUNT


def _cell_range_of(line: Line) -> tuple[int, int] | None:
    a = line.a
    if a.get("cells_range"):
        lo, hi = a["cells_range"]
        return int(lo), int(hi)
    if isinstance(a.get("cells"), int) and a.get("cells_from") != "voltage":
        return a["cells"], a["cells"]
    return None


def g3_cell_count(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    batteries = [ln for ln in lines if ln.category == "battery" and applies(ln, "G3", {"battery"})]
    parts = [ln for ln in lines if ln.category != "battery"
             and (applies(ln, "G3", set()) or (ln.rules is None and ln.a.get("cells_range")))]
    out: list[Check] = []
    for bat in batteries:
        cells = bat.a.get("cells")
        if not isinstance(cells, int):
            what = "fixed cell count (template gives options)" if bat.a.get("cells_options") or bat.a.get("cells_range") \
                else "cells"
            if parts:
                out.append(make_check("G3", "needs_human", f"{bat.name}: {what} unknown. Needs your check.", [bat] + parts))
            continue
        for part in parts:
            rng = _cell_range_of(part)
            if rng is None:
                out.append(make_check("G3", "needs_human", f"{part.name}: supported cell range unknown (attribute "
                                      "cells_range).", [bat, part]))
                continue
            lo, hi = rng
            rtxt = f"{lo}S" if lo == hi else f"{lo}–{hi}S"
            if lo <= cells <= hi:
                out.append(make_check("G3", "pass", f"{cells}S battery is inside {part.name}'s {rtxt} range.", [bat, part]))
            else:
                out.append(make_check("G3", "fail", f"{cells}S battery is outside {part.name}'s {rtxt} range.", [bat, part],
                                      fix_text=f"Pick a battery with {rtxt}.",
                                      fix_filter={"bom_line_id": bat.id, "category": "battery", "cells_min": lo, "cells_max": hi}))
    return out


# --------------------------------------------------------------------------- G4 LOGIC_LEVEL


def _logic_of(line: Line) -> tuple[float | None, bool]:
    """(logic voltage, tolerant of both 3.3 and 5 V)."""
    a = line.a
    if a.get("logic_compat"):
        return None, True
    if a.get("logic_v") is not None:
        return float(a["logic_v"]), bool(a.get("five_v_tolerant"))
    t = line.text().lower()
    if re.search(r"esp32|esp8266|rp2040|raspberry\s*pi|\bpi\s*5", t):
        return 3.3, False  # Espressif: "The voltage tolerance of GPIO is 3.6 V."; Pi GPIO is 3.3 V
    if re.search(r"arduino\s*uno|atmega328", t):
        return 5.0, False  # Arduino Uno: IOREF tied to 5 V
    return None, False


def g4_logic_level(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    involved = [ln for ln in lines if applies(ln, "G4", {"board", "sensor"})
                and ln.category not in SUPPLY_CATEGORIES | {"tool", "cable", "mechanical", "printed"}]
    if len(involved) < 2:
        return []
    shifter = [ln for ln in lines if ln.a.get("level_shifter") or re.search(r"level\s*shift|logic\s*level", ln.name, re.I)]
    three = [ln for ln in involved if _logic_of(ln) == (3.3, False)]
    five = [ln for ln in involved if _logic_of(ln)[0] == 5.0]
    unknown = [ln for ln in involved if _logic_of(ln) == (None, False)]
    out: list[Check] = []
    if three and five and not shifter:
        out.append(make_check(
            "G4", "warn", f"{', '.join(x.name for x in five)} is 5 V logic and {', '.join(x.name for x in three)} takes "
            "3.3 V only (GPIO tolerance 3.6 V). Proposed: add a logic level shifter (an assumption until you confirm).",
            three + five, fix_text="Add a logic level shifter line (assumption).",
            fix_filter={"add_line": {"name": "Logic level shifter", "category": "board", "provenance": "assumption",
                                     "statement": "A 5 V output drives a 3.3 V-only input; a level shifter is needed."}},
            needs_ack=True))
    elif unknown:
        out.append(make_check("G4", "needs_human", f"Logic level unknown for: {', '.join(x.name for x in unknown)} "
                              "(attribute logic_v). Needs your check.", involved))
    else:
        how = "a level shifter is in the BOM" if shifter and three and five else "no 5 V output meets a 3.3 V-only input"
        out.append(make_check("G4", "needs_human", f"Known boards agree: {how}. We know board families, not every "
                              "breakout. Needs your check.", involved))
    return out


# --------------------------------------------------------------------------- G5 CONNECTOR_MATCH


def _conn_key(token: str) -> tuple[str, Any]:
    if token in CONNECTOR_FAMILY:
        fam, pitch = CONNECTOR_FAMILY[token]
        return (fam or "JST?", pitch)
    if token.startswith("BARREL-"):
        return ("barrel", token[7:])
    return (token, None)


def _conns(line: Line) -> list[str]:
    a = line.a
    toks = list(a.get("connectors") or ([a["connector"]] if a.get("connector") else []))
    if a.get("barrel") and f"BARREL-{a['barrel']}" not in toks:
        toks.append(f"BARREL-{a['barrel']}")
    return toks


def _match_label(label_tokens: list[str], line: Line) -> tuple[str, str | None]:
    """('match'|'mismatch'|'unknown', the line's connector shown in messages)."""
    have = _conns(line)
    if not have:
        return "unknown", None
    want = {_conn_key(t) for t in label_tokens}
    have_keys = {_conn_key(t) for t in have}
    if want & have_keys:
        return "match", None
    if any(k[0] == "JST?" for k in have_keys) and any(k[0] in ("PH", "XH", "SH", "JST?") for k in want):
        return "unknown", have[0]
    same_kind = [t for t in have if (_conn_key(t)[0] == "barrel") == any(_conn_key(w)[0] == "barrel" for w in label_tokens)]
    return ("mismatch", same_kind[0]) if same_kind else ("unknown", have[0])


def g5_connector_match(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    edges = _edges(plan)
    keys = _by_key(lines)
    out: list[Check] = []
    edge_checked = False
    for e in edges:
        label_toks, _ = parse_connectors(e["label"])
        if not label_toks or (e["rules"] and "G5" not in e["rules"]):
            continue
        ends = [keys.get(e["from"]), keys.get(e["to"])]
        ends = [x for x in ends if x is not None]
        if len(ends) < 2:
            continue
        edge_checked = True
        label = " / ".join(_connector_label(t) for t in label_toks)
        bad = []
        unk = []
        for end in ends:
            state, theirs = _match_label(label_toks, end)
            if state == "mismatch":
                bad.append((end, theirs))
            elif state == "unknown":
                unk.append(end)
        if bad:
            end, theirs = bad[0]
            out.append(make_check("G5", "fail", f"G5: {_connector_label(theirs or '?')} ≠ {label} on {end.name}.", ends,
                                  fix_text=f"Pick {end.name} with {label}, or add an adapter line.",
                                  fix_filter={"bom_line_id": end.id, "category": end.category, "connector": label_toks[0]}))
        elif unk:
            out.append(make_check("G5", "needs_human", f"Connector of {', '.join(x.name for x in unk)} not in the listing "
                                  f"text (needs {label}; attribute connector). Needs your check.", ends))
        else:
            out.append(make_check("G5", "pass", f"{label} on both sides.", ends))
    if edge_checked:
        return out
    # No usable edges: a battery mates with the power module / PDB if there is one, else with the ESC or
    # board; a power module or PSU mates with the ESC or board.
    sups = [s for s in _supplies(lines) if applies(s, "G5", SUPPLY_CATEGORIES)]
    others = [ln for ln in lines if ln.category not in SUPPLY_CATEGORIES and applies(ln, "G5", {"esc_driver", "board"})]
    powers = [s for s in sups if s.category == "power"]
    pairs = [(b, t) for b in sups if b.category == "battery" for t in (powers or others)]
    pairs += [(p, t) for p in powers for t in others]
    for sup, part in pairs:
        theirs, mine = _conns(sup), _conns(part)
        if not theirs or not mine:
            missing = sup if not theirs else part
            out.append(make_check("G5", "needs_human", f"Connector of {missing.name} not in the listing text "
                                  "(attribute connector). Needs your check.", [sup, part]))
        elif {_conn_key(t) for t in theirs} & {_conn_key(t) for t in mine}:
            shared = next(t for t in theirs if _conn_key(t) in {_conn_key(x) for x in mine})
            out.append(make_check("G5", "pass", f"{_connector_label(shared)} on {sup.name} and {part.name}.", [sup, part]))
        else:
            out.append(make_check("G5", "fail", f"G5: {_connector_label(theirs[0])} ≠ {_connector_label(mine[0])} "
                                  f"({sup.name} vs {part.name}).", [sup, part],
                                  fix_text=f"Pick {sup.name} with {_connector_label(mine[0])}, or add an adapter line.",
                                  fix_filter={"bom_line_id": sup.id, "category": sup.category, "connector": mine[0]}))
    return out


# --------------------------------------------------------------------------- G6 CONNECTOR_CURRENT


def g6_connector_current(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    out: list[Check] = []
    edges = _edges(plan)
    keys = _by_key(lines)
    for sup in _supplies(lines):
        if not applies(sup, "G6", SUPPLY_CATEGORIES):
            continue
        rated = [t for t in _conns(sup) if t in CONNECTOR_RATING_A]
        if not rated:
            continue
        tok = rated[0]
        cont, burst, src = CONNECTOR_RATING_A[tok]
        kb = _kb("G6", src)
        unverified = tok in UNVERIFIED_RATINGS
        expected = sup.a.get("expected_current_a")
        unknown: list[str] = []
        no_load = False
        if expected is None:
            connected = {e["to"] for e in edges if e["from"] in sup.keys} | {e["from"] for e in edges if e["to"] in sup.keys}
            loads = [ln for ln in lines if (ln.category in LOAD_CATEGORIES or ln.a.get("load_current_a") is not None)
                     and (not connected or ln.keys & connected)]
            total = 0.0
            for ln in loads:
                c = _load_current(ln)
                if c is None:
                    unknown.append(ln.name)
                else:
                    total += c * ln.qty
            expected = round(total, 3)
            no_load = not loads  # nothing found that draws current through it: say so, never "0 A"
        rating_txt = f"{tok} is rated {_fmt(cont)} A continuous" + (f" ({_fmt(burst)} A burst)" if burst else "") + \
            (" [second-hand figure, unverified]" if unverified else "")
        if no_load:
            out.append(make_check("G6", "needs_human", f"No load current is known for {sup.name}'s {tok}; {rating_txt}. Needs your check.",
                                  [sup], kb=kb))
        elif float(expected) > cont:
            out.append(make_check("G6", "warn", f"At least {_fmt(expected)} A through {sup.name}'s {tok}; {rating_txt}.",
                                  [sup], kb=kb, needs_ack=True,
                                  fix_text="Pick a larger connector or split the load.",
                                  fix_filter={"bom_line_id": sup.id, "category": sup.category, "connector_current_min_a": expected}))
        elif unknown:
            out.append(make_check("G6", "needs_human", f"At least {_fmt(expected)} A through {tok}; {rating_txt}. Current "
                                  f"unknown for: {', '.join(unknown)}.", [sup], kb=kb))
        elif unverified:
            out.append(make_check("G6", "needs_human", f"{_fmt(expected)} A through {tok}; {rating_txt}. Needs your check.",
                                  [sup], kb=kb))
        else:
            out.append(make_check("G6", "pass", f"{_fmt(expected)} A through {tok}; {rating_txt}.", [sup], kb=kb))
    for e in edges:
        if e.get("current_a") is None:
            continue
        toks = [t for t in parse_connectors(e["label"])[0] if t in CONNECTOR_RATING_A]
        if not toks:
            continue
        cont, _, src = CONNECTOR_RATING_A[toks[0]]
        ends = [keys[k] for k in (e["from"], e["to"]) if k in keys]
        res = "warn" if float(e["current_a"]) > cont else ("needs_human" if toks[0] in UNVERIFIED_RATINGS else "pass")
        out.append(make_check("G6", res, f"{_fmt(e['current_a'])} A through {toks[0]} (rated {_fmt(cont)} A).", ends,
                              kb=_kb("G6", src)))
    return out


# --------------------------------------------------------------------------- G7 KV_PROP_CELLS


def _prop_size(lines: list[Line], motor: Line) -> float | None:
    for ln in lines:
        if re.search(r"\bprop", ln.name + " " + (ln.row_id or ""), re.I):
            for k in ("prop_in", "size_in"):
                if ln.a.get(k) is not None:
                    return float(ln.a[k])
    if motor.a.get("prop_in") is not None:
        return float(motor.a["prop_in"])
    for ln in lines:
        if ln.category == "mechanical" and re.search(r"frame", ln.name + " " + (ln.row_id or ""), re.I) \
                and ln.a.get("size_in") is not None:
            return float(ln.a["size_in"])
    return None


def _prop_class(inches: float) -> int | None:
    for cls, (lo, hi) in {3: (2.5, 3.5), 5: (4.5, 5.5), 10: (9.5, 10.5)}.items():
        if lo <= inches <= hi:
            return cls
    return None


_STATOR = re.compile(r"\b(\d{2})(\d{2})\b")  # "1404", "2207": stator width and height in mm
_MOUNT = re.compile(r"\b(\d{2}(?:\.\d)?)\s*[x×]\s*(\d{2}(?:\.\d)?)\s*(?:mm)?\b", re.I)
_MOUNT_CLASSES = (("20x20", 19.0, 21.0), ("25.5x25.5", 25.0, 26.5), ("30x30", 29.5, 31.0))


def _mount_class(text: str) -> str | None:
    """The stack mounting pattern named in a text: "20x20", "25.5x25.5" or "30x30" (30.5 holes count as 30x30)."""
    for m in _MOUNT.finditer(text):
        a, b = float(m.group(1)), float(m.group(2))
        if abs(a - b) > 0.6:
            continue  # "5x4.3" props or "60x40" boards are not a stack pattern
        for name, lo, hi in _MOUNT_CLASSES:
            if lo <= a <= hi:
                return name
    return None


def _listing_prop_class(got: dict[str, Any], title: str, category: str, stator: str | None = None) -> int | str | None:
    """The prop size class a listing is for: 3, 5 or 10 from a stated size, "5+" from a 20–24 mm motor stator
    (5-inch class or larger: an X500's 2216 motors swing 10-inch props), or None when the listing does not say.
    `stator` is a stator size read by SIE extract ("2207"); without one the title pattern is used."""
    for k in ("prop_in", "size_in"):
        if got.get(k) is not None:
            return _prop_class(float(got[k]))
    if category == "motor":
        m = _STATOR.search(stator or "") or _STATOR.search(title)
        if m:
            width = int(m.group(1))
            if 10 <= width <= 15:
                return 3
            if 20 <= width <= 24:
                return "5+"
    return None


def g7_kv_prop_cells(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    motors = [ln for ln in lines if ln.category == "motor" and not _is_servo(ln)
              and applies(ln, "G7", {"motor"}) and (ln.rules is not None or ln.a.get("kv") or ln.a.get("kv_range"))]
    out: list[Check] = []
    batteries = [ln for ln in lines if ln.category == "battery"]
    for motor in motors:
        kv = motor.a.get("kv")
        kvr = motor.a.get("kv_range")
        prop = _prop_size(lines, motor)
        cells = next((b.a["cells"] for b in batteries if isinstance(b.a.get("cells"), int)), None)
        involved = [motor] + batteries
        missing = [n for n, v in (("kv", kv or kvr), ("prop_in", prop), ("cells", cells)) if not v]
        if missing:
            out.append(make_check("G7", "needs_human", f"{motor.name}: {', '.join(missing)} unknown. Rule of thumb; "
                                  "needs your check.", involved))
            continue
        cls = _prop_class(float(prop))  # type: ignore[arg-type]
        window = KV_WINDOWS.get((cls, cells)) if cls else None  # type: ignore[arg-type]
        if window is None:
            why = "no source read for 3-inch props" if cls == 3 else f"no usual KV range on file for {_fmt(prop)}-inch props on {cells}S"  # type: ignore[arg-type]
            out.append(make_check("G7", "needs_human", f"{motor.name}: {why}. Rule of thumb; needs your check.", involved,
                                  kb=_kb("G7", "no_3inch_source")))
            continue
        lo, hi, src = window
        kb = _kb("G7", src) + ([_SRC + "holybro_x500_kv"] if cls == 10 else [])
        k_lo, k_hi = (kvr[0], kvr[1]) if kvr and not kv else (kv, kv)
        kv_txt = f"{k_lo} KV" if k_lo == k_hi else f"{k_lo}–{k_hi} KV"
        usual = f"{lo}–{hi} KV for {cls}-inch props on {cells}S"
        if k_lo >= lo and k_hi <= hi:
            out.append(make_check("G7", "needs_human", f"{kv_txt} is inside the usual {usual} (rule of thumb). Needs your "
                                  "check.", involved, kb=kb))
        else:
            out.append(make_check("G7", "warn", f"{kv_txt} is outside the usual {usual} (rule of thumb).", involved,
                                  kb=kb, needs_ack=True, fix_text=None))
    return out


# --------------------------------------------------------------------------- G8 ESC_CURRENT


def g8_esc_current(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    escs = [ln for ln in lines if ln.category == "esc_driver" and applies(ln, "G8", {"esc_driver"})
            and (ln.rules is not None or re.search(r"\besc\b", ln.text(), re.I))]
    motors = [ln for ln in lines if ln.category == "motor" and not _is_servo(ln) and not _is_dc_actuator(ln)
              and applies(ln, "G8", {"motor"})]
    out: list[Check] = []
    for esc in escs:
        for motor in motors:
            esc_a = esc.a.get("current_a")
            mot_a = motor.a.get("max_current_a")
            if esc_a is None:
                out.append(make_check("G8", "needs_human", f"{esc.name}: continuous current unknown (attribute current_a).",
                                      [esc, motor]))
            elif mot_a is None:
                out.append(make_check("G8", "needs_human", f"{motor.name}: maximum current not in the listing (attribute "
                                      f"max_current_a); {esc.name} gives {_fmt(esc_a)} A. Needs your check.", [esc, motor]))
            elif float(esc_a) >= float(mot_a):
                out.append(make_check("G8", "pass", f"{esc.name} {_fmt(esc_a)} A ≥ {motor.name} {_fmt(mot_a)} A max.",
                                      [esc, motor]))
            else:
                out.append(make_check("G8", "fail", f"{esc.name} {_fmt(esc_a)} A < {motor.name} {_fmt(mot_a)} A max.",
                                      [esc, motor], fix_text=f"Pick an ESC rated {_fmt(mot_a)} A or more.",
                                      fix_filter={"bom_line_id": esc.id, "category": "esc_driver", "current_min_a": float(mot_a)}))
    return out


# --------------------------------------------------------------------------- G9 DRIVER_CURRENT


def _driver_spec(line: Line) -> tuple[float | None, float | None, str | None]:
    """(amps per channel, max supply V, source chunk) from attrs first, then a known chip name."""
    amps = line.a.get("current_a")
    vmax = line.a.get("max_voltage_v") or (line.a.get("voltage_range") or [None, None])[1]
    for pat, a, _peak, v, src in DRIVER_CHIPS:
        if pat.search(line.text()):
            return (float(amps) if amps is not None else a), (float(vmax) if vmax is not None else v), src
    return (float(amps) if amps is not None else None), (float(vmax) if vmax is not None else None), None


def g9_driver_current(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    drivers = [ln for ln in lines if ln.category == "esc_driver" and applies(ln, "G9", {"esc_driver"})
               and not re.search(r"\besc\b|pca\s*9685", ln.text(), re.I)]
    motors = [ln for ln in lines if (_is_dc_actuator(ln) and ln.category == "motor") or
              (ln.category == "motor" and ln.rules is not None and "G9" in ln.rules and not _is_servo(ln))]
    out: list[Check] = []
    for drv in drivers:
        amps, vmax, src = _driver_spec(drv)
        kb = _kb("G9", src) if src else list(RULES["G9"]["kb_refs"])
        sup, rail, _ = _supply_for(drv, lines, _edges(plan))
        window = (rail, rail) if rail is not None else (_battery_window(sup) if sup else None)
        if window and vmax is not None and window[1] > vmax:
            out.append(make_check("G9", "fail", f"{drv.name} takes up to {_fmt(vmax)} V; the supply gives up to "
                                  f"{_fmt(window[1])} V.", [drv] + ([sup] if sup else []), kb=kb,
                                  fix_text=f"Pick a supply at or under {_fmt(vmax)} V, or another driver.",
                                  fix_filter={"bom_line_id": sup.id if sup else drv.id, "voltage_max": vmax}))
        for motor in motors:
            stall = motor.a.get("stall_current_a")
            if amps is None:
                out.append(make_check("G9", "needs_human", f"{drv.name}: current per channel unknown (attribute current_a).",
                                      [drv, motor], kb=kb))
            elif stall is None:
                out.append(make_check("G9", "needs_human", f"{motor.name}: stall current not listed (attribute "
                                      f"stall_current_a); {drv.name} gives {_fmt(amps)} A per channel. Needs your check.",
                                      [drv, motor], kb=kb))
            elif float(stall) <= amps:
                out.append(make_check("G9", "pass", f"{motor.name} stalls at {_fmt(stall)} A; {drv.name} gives "
                                      f"{_fmt(amps)} A per channel.", [drv, motor], kb=kb))
            else:
                out.append(make_check("G9", "fail", f"{motor.name} stalls at {_fmt(stall)} A; {drv.name} gives only "
                                      f"{_fmt(amps)} A per channel.", [drv, motor], kb=kb,
                                      fix_text=f"Pick a driver rated {_fmt(stall)} A per channel or more.",
                                      fix_filter={"bom_line_id": drv.id, "category": "esc_driver", "current_min_a": float(stall)}))
    return out


# --------------------------------------------------------------------------- G10 SERVO_SUPPLY

_LOGIC_PIN = re.compile(r"gpio|logic|\bpin\b|5v_pin|3v3|mcu|board|arduino|pi\b", re.I)


def g10_servo_supply(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    servos = [ln for ln in lines if _is_servo(ln) and applies(ln, "G10", {"motor"})]
    out: list[Check] = []
    edges = _edges(plan)
    keys = _by_key(lines)
    for servo in servos:
        powered_from = str(servo.a.get("powered_from") or "")
        from_board = bool(powered_from and _LOGIC_PIN.search(powered_from))
        for e in edges:
            if e["to"] in servo.keys and e["from"] in keys and keys[e["from"]].category == "board" \
                    and re.search(r"\b(?:5v|vcc|power|vin)\b", e["label"], re.I):
                from_board = True
        if from_board:
            out.append(make_check("G10", "warn", f"{servo.name} is powered from the controller's logic pin. Servos need "
                                  "their own rail. Proposed: a separate 5–6 V supply.", [servo], needs_ack=True,
                                  fix_text="Add a separate 5–6 V servo supply (assumption).",
                                  fix_filter={"add_line": {"name": "Separate 5–6 V servo supply", "category": "power",
                                                           "provenance": "assumption"}}))
            continue
        sg90 = bool(re.search(r"sg90", servo.text(), re.I))
        rng = servo.a.get("voltage_range")
        if not rng and sg90:
            rng = list(SG90_RANGE)
        sup, rail, how = _supply_for(servo, lines, edges)
        window = (rail, rail) if rail is not None else (_battery_window(sup) if sup else None)
        involved = [servo] + ([sup] if sup else [])
        if window is None:
            out.append(make_check("G10", "needs_human", f"Supply voltage for {servo.name} unknown. Needs your check.", involved))
            continue
        lo, hi = window
        if not rng:
            rated = servo.a.get("voltage_v")
            msg = f"{servo.name}: input range not stated (attribute voltage_range)" + \
                  (f"; rated {_fmt(rated)} V class, supply {_fmt(lo)}–{_fmt(hi)} V" if rated is not None else "") + \
                  ". Needs your check."
            out.append(make_check("G10", "needs_human", msg, involved))
            continue
        smin, smax = float(rng[0]), float(rng[1])
        inside = smin <= lo and hi <= smax
        if not inside:
            out.append(make_check("G10", "warn", f"Supply {_fmt(lo)}–{_fmt(hi)} V is outside {servo.name}'s "
                                  f"{_fmt(smin)}–{_fmt(smax)} V" + (" [SG90 numbers unverified]" if sg90 else "") + ".",
                                  involved, needs_ack=True, fix_text=f"Use a {_fmt(smin)}–{_fmt(smax)} V servo supply.",
                                  fix_filter={"bom_line_id": sup.id if sup else servo.id, "category": "power",
                                              "voltage_min": smin, "voltage_max": smax}))
        elif sg90 and not servo.a.get("voltage_range"):
            out.append(make_check("G10", "needs_human", f"Supply inside {_fmt(smin)}–{_fmt(smax)} V, but SG90-class "
                                  "numbers have no official sheet. Needs your check.", involved))
        else:
            out.append(make_check("G10", "pass", f"Supply {_fmt(lo)}–{_fmt(hi)} V is inside {servo.name}'s "
                                  f"{_fmt(smin)}–{_fmt(smax)} V, on its own rail.", involved))
    return out


# --------------------------------------------------------------------------- G11 PIN_CURRENT


def g11_pin_current(plan: dict[str, Any], lines: list[Line]) -> list[Check]:
    actuators = [ln for ln in lines if _is_dc_actuator(ln) and (ln.rules is None or "G11" in ln.rules)]
    if not actuators:
        return []
    drivers = [ln for ln in lines if ln not in actuators
               and (ln.category == "esc_driver" or re.search(r"driver|relay\s*module|transistor|mosfet", ln.name, re.I))]
    out: list[Check] = []
    for act in actuators:
        on_pin = bool(re.search(r"gpio|\bpin\b", str(act.a.get("powered_from") or act.a.get("driven_by") or ""), re.I))
        if on_pin or not drivers:
            what = f"{act.name} is driven straight from a GPIO pin" if on_pin else f"{act.name} has no driver in the BOM"
            out.append(make_check("G11", "warn", f"{what}; a GPIO pin gives about 20 mA [unverified]. Use a driver.",
                                  [act], needs_ack=True, fix_text="Add a motor driver or relay module (assumption).",
                                  fix_filter={"add_line": {"name": "Motor driver", "category": "esc_driver",
                                                           "provenance": "assumption"}}))
        else:
            out.append(make_check("G11", "needs_human", f"{act.name} has a driver in the BOM ({drivers[0].name}). Check "
                                  "the wiring: no coil straight on a GPIO pin (about 20 mA per pin [unverified]).",
                                  [act, drivers[0]]))
    return out


RULE_FUNCS = {
    "G1": g1_supply_voltage, "G2": g2_current_budget, "G3": g3_cell_count, "G4": g4_logic_level,
    "G5": g5_connector_match, "G6": g6_connector_current, "G7": g7_kv_prop_cells, "G8": g8_esc_current,
    "G9": g9_driver_current, "G10": g10_servo_supply, "G11": g11_pin_current,
}


def check(plan: dict[str, Any], only: list[str] | None = None) -> list[Check]:
    """Run G1-G11 (or `only`) over a plan. Never raises on odd input: a rule that cannot read the plan says so."""
    plan = _plain(plan)
    lines = lines_of(plan)
    out: list[Check] = []
    for rid, fn in RULE_FUNCS.items():
        if only and rid not in {_norm_rule(x) for x in only}:
            continue
        try:
            out.extend(fn(plan, lines))
        except Exception as exc:  # a rule bug must not hide the other rules' results
            out.append(Check(rule_id=rule_id(rid), result="needs_human", message=f"Rule could not run: {exc}. Needs your check.",
                             kb_refs=list(RULES[rid]["kb_refs"]), needs_ack=True))
    return out


# --------------------------------------------------------------------------- per-offer checks


def check_offer(line: dict[str, Any], offer: dict[str, Any]) -> list[Check]:
    """Check one candidate listing against one BOM line's requirements (template / resolved attrs).

    Reads the listing's description first, then its title. Returns only checks for attributes the line
    constrains; a "fail" means reject the listing (shown as a rejected row with the message as reason).
    """
    need = to_line({k: v for k, v in line.items() if k != "offer"})
    got = attrs(offer)
    reads = _best_reads(offer.get("spec_reads"))  # {attr: read}: specs SIE extract read from this listing
    read_attrs = _read_attrs(offer.get("spec_reads")) if reads else {}
    if "prop_in" in read_attrs:
        got.pop("size_in", None)
    got.update(read_attrs)  # a spec read wins over the title pattern for the same attribute
    cand = to_line({**{k: v for k, v in line.items() if k not in ("offer", "attrs", "spec", "typical_spec")},
                    "offer": offer})
    out: list[Check] = []
    title = str(offer.get("title") or "listing")[:60]

    def wants(rule: str, cats: set[str]) -> bool:
        return applies(need, rule, frozenset(cats))

    # G3: cells on batteries, cell range on ESC/FC/driver
    if wants("G3", {"battery", "esc_driver", "board"}):
        if need.category == "battery" and (isinstance(need.a.get("cells"), int) or need.a.get("cells_range")):
            want_lo, want_hi = (need.a["cells"], need.a["cells"]) if isinstance(need.a.get("cells"), int) else need.a["cells_range"]
            have = got.get("cells")
            if have is None:
                out.append(make_check("G3", "needs_human", f"Cell count not in the listing text ({title}).", [need]))
            elif not (want_lo <= have <= want_hi):
                want = f"{want_lo}S" if want_lo == want_hi else f"{want_lo}–{want_hi}S"
                out.append(make_check("G3", "fail", f"G3: {have}S ≠ {want}.", [need]))
            else:
                out.append(make_check("G3", "pass", f"{have}S as required.", [need]))
    # G5: connector family and pitch, barrel size
    need_conns = _conns(need)
    if need_conns and wants("G5", {"battery", "power", "esc_driver", "board"}):
        have_conns = _conns(cand)
        if not have_conns or (len(have_conns) == 1 and have_conns[0] == "JST" and any(t.startswith("JST") for t in need_conns)):
            out.append(make_check("G5", "needs_human", f"Connector not stated in the listing text ({title}); needs "
                                  f"{_connector_label(need_conns[0])}.", [need]))
        else:
            want_keys = {_conn_key(t) for t in need_conns}
            if want_keys & {_conn_key(t) for t in have_conns}:
                out.append(make_check("G5", "pass", f"{_connector_label(need_conns[0])} as required.", [need]))
            else:
                out.append(make_check("G5", "fail", f"G5: {_connector_label(have_conns[0])} ≠ {_connector_label(need_conns[0])}.",
                                      [need], fix_filter={"bom_line_id": need.id, "connector": need_conns[0]}))
    # G7 size class: a frame, propeller or motor listing for another prop size cannot be used. A 3-inch frame is
    # not a 5-inch frame, and a 1404 motor is not a 2207. Only the line's own prop_in (set by the template variant)
    # is compared; a listing that states no size is left to the plan-level G7 check.
    want_prop = need.a.get("prop_in")
    if want_prop is not None and need.category in ("mechanical", "motor"):
        try:
            want_cls = _prop_class(float(want_prop))
        except (TypeError, ValueError):
            want_cls = None
        have_cls = _listing_prop_class(got, str(offer.get("title") or ""), need.category, read_attrs.get("stator"))
        if want_cls is not None and have_cls is not None:
            ok = have_cls == want_cls or (have_cls == "5+" and want_cls in (5, 10))
            if not ok:
                have_txt = "5-inch or larger" if have_cls == "5+" else f"{have_cls}-inch"
                sized = got.get("prop_in") is not None or got.get("size_in") is not None
                by = _read_note(reads.get("prop_in") if sized else reads.get("stator") if need.category == "motor" else None, title)
                out.append(make_check("G7", "fail", f"G7: {have_txt} listing ≠ {want_cls}-inch build ({by}).", [need]))
            else:
                out.append(make_check("G7", "pass", f"Fits the {want_cls}-inch build.", [need]))
    # G12 stack mount: a 20x20 VTX does not bolt onto a 30x30 stack. Only lines whose template sets mount_mm are
    # judged, and only listings that state a pattern.
    want_mount = _mount_class(str(need.a.get("mount_mm") or ""))
    if want_mount is not None:
        have_mount = _mount_class(str(read_attrs.get("mount_mm") or ""))             or _mount_class(f"{offer.get('title') or ''} {offer.get('description') or ''}")
        if have_mount is not None:
            if have_mount != want_mount:
                by = _read_note(reads.get("mount_mm") if read_attrs.get("mount_mm") else None, title)
                out.append(make_check("G12", "fail", f"G12: {have_mount} mm stack ≠ {want_mount} mm stack ({by}).", [need],
                                      kb=_kb("G12", "fpv_stack_mounting")))
            else:
                out.append(make_check("G12", "pass", f"{want_mount} mm stack as required.", [need]))
    # G1 on supplies: required output voltage
    if need.category in SUPPLY_CATEGORIES and need.a.get("voltage_v") is not None and need.category == "power" \
            and wants("G1", {"power"}):
        have_v = got.get("voltage_v")
        if have_v is None:
            out.append(make_check("G1", "needs_human", f"Output voltage not in the listing text ({title}).", [need]))
        elif abs(float(have_v) - float(need.a["voltage_v"])) > 0.05:
            out.append(make_check("G1", "fail", f"G1: {_fmt(have_v)} V ≠ {_fmt(need.a['voltage_v'])} V.", [need]))
        else:
            out.append(make_check("G1", "pass", f"{_fmt(have_v)} V as required.", [need]))
    # G7 on motors: KV against the line's KV window (warn only)
    if need.category == "motor" and (need.a.get("kv_range") or need.a.get("kv")) and wants("G7", {"motor"}):
        have_kv = got.get("kv")
        lo, hi = need.a.get("kv_range") or (need.a["kv"], need.a["kv"])
        if have_kv is None:
            out.append(make_check("G7", "needs_human", f"KV not in the listing text ({title}).", [need]))
        elif not (lo <= have_kv <= hi):
            out.append(make_check("G7", "warn", f"G7: {have_kv} KV is outside {lo}–{hi} KV (rule of thumb).", [need],
                                  needs_ack=True))
        else:
            out.append(make_check("G7", "needs_human", f"{have_kv} KV is inside {lo}–{hi} KV (rule of thumb). Needs your "
                                  "check.", [need]))
    return out


def reject(line: dict[str, Any], offer: dict[str, Any], plan: dict[str, Any] | None = None) -> str | None:
    """A's pack interface (rules/base.py): why `offer` cannot be used for `line`, or None.

    Only a FAIL rejects a listing; warnings and needs_human results keep it (they show on the line instead).
    """
    line = _plain(line)
    line = {k: v for k, v in line.items() if k != "chosen"}
    for chk in check_offer(line, _plain(offer)):
        if chk.result == "fail":
            return chk.message
    return None
