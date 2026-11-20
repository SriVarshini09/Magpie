"""Rule-pack interface and the attribute parser every pack shares (PLAN §3.8, §13.1). Owner: A.

A pack is a module in `app/rules/` with:

    PACK_ID: str
    def check(plan: dict) -> list[Check]            required. `plan` is `PlanContext.to_dict()` (shape below)
    def fix(check: Check, plan: dict) -> dict|None  optional. A search filter that would repair a FAIL
    def reject(line: dict, offer: dict, plan: dict) -> str|None   optional. Why an offer cannot be used for a line

    plan = {
      "build_type": str, "answers": {question_id: value}, "ship_to_country": "US",
      "lines": [{
          "bom_line_id", "name", "category", "qty", "line_kind", "status", "row_id", "rules": [rule ids],
          "spec": str|None, "attrs": {...parse_attrs keys...},            # the BOM line itself
          "chosen": [{"offer_id", "store_id", "title", "description", "packs", "units_per_pack", "attrs": {...}}],
      }],
      "edges": [{"from": bom_line_id, "to": bom_line_id, "label": str, "rules": [rule ids]}],
      "view_instances": {bom_line_id: mesh instance count},
    }

Evaluation is deterministic Python over attributes parsed from the listing DESCRIPTION FIRST, THEN THE TITLE.
A missing attribute never passes: the result is `needs_human` with the attribute named.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from app.models import Check

__all__ = ["parse_attrs", "listing_attrs", "PlanContext", "LineCtx", "load_pack", "missing", "num", "in_range", "rule_no"]

_NUM = r"(\d+(?:\.\d+)?)"
_MAINS = re.compile(rf"(?i)\b(?:ac\s*)?{_NUM}\s*(?:-|~|to)\s*{_NUM}\s*v(?:ac)?\b|\b(1[012]0|2[2-4]0)\s*v(?:ac)?\b(?:\s*(?:input|mains|ac))?")
_VOLT_RANGE = re.compile(rf"(?i){_NUM}\s*(?:-|~|–|to)\s*{_NUM}\s*v(?:dc)?\b")
_VOLT = re.compile(rf"(?i)(?<![\w.]){_NUM}\s*v(?:dc|olts?)?\b(?!\w)")
_AMP = re.compile(rf"(?i)(?<![\w.]){_NUM}\s*(m?a)(?:mps?)?\b(?!h)")
_MAH = re.compile(rf"(?i)(?<![\w.]){_NUM}\s*mah\b")
_CELLS_RANGE = re.compile(r"(?i)\b(\d{1,2})\s*(?:-|~|–|to)\s*(\d{1,2})\s*s\b(?!\w)")
_CELLS = re.compile(r"(?i)\b(\d{1,2})\s*(?:s\b(?:\d*p)?|[- ]?cells?\b)")
_KV_RANGE = re.compile(r"(?i)\b(\d{3,5})\s*(?:-|~|–|to)\s*(\d{3,5})\s*kv\b")
_KV = re.compile(r"(?i)\b(?:kv\s*(\d{3,5})|(\d{3,5})\s*kv)\b")
_C_RATING = re.compile(r"(?i)\b(\d{1,3})\s*c\b(?!\d)")
_PROP = re.compile(r"(?i)\b(\d{1,2}(?:\.\d)?)\s*(?:-|\s)?(?:inch|in\b|\")")
_BARREL = re.compile(r"(?i)\b(?:dc\s*)?(5\.5)\s*(?:mm)?\s*(?:x|×|\*|/)\s*(2\.[15])\s*(?:mm)?|\bdc\s?55(21|25)\b")
_XT = re.compile(r"(?i)\bxt[- ]?(30|60|90)[a-z]?\b")
_JST = re.compile(r"(?i)\bjst[- ]?(xh|ph|sh|gh|zh|rcy)\b|\b(ph|xh|sh)\s?(2\.0|2\.5|2\.54|1\.0|1\.25)\b")
_PITCH = re.compile(rf"(?i)\b{_NUM}\s*mm\s*pitch\b|\bpitch\s*{_NUM}\s*mm\b")
_PLUG = re.compile(r"(?i)\b(us|usa|american|uk|british|eu|european|au|australian|jp|japan)[- ]?(?:standard\s+)?(?:plug|adapter plug|type)\b")
_VARIANT = re.compile(r"\b(C\d{3})\b")
_GEAR = re.compile(r"\b1/(\d{2,3})\b")
_LOGIC = re.compile(r"(?i)\b(3\.3|5)\s*v\s*(?:logic|i/?o|gpio|ttl)\b|\b(?:logic|i/?o|gpio|ttl)\s*(?:level\s*)?(3\.3|5)\s*v\b")
JST_PITCH = {"XH": 2.5, "PH": 2.0, "SH": 1.0, "GH": 1.25, "ZH": 1.5}
PLUGS = {"us": "US", "usa": "US", "american": "US", "uk": "UK", "british": "UK", "eu": "EU", "european": "EU", "au": "AU",
         "australian": "AU", "jp": "JP", "japan": "JP"}


def num(value: Any) -> float | None:
    """A number from 12, "12", "12V", "5 A". None when there is no number (never a guess)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(_NUM, str(value))
    return float(m.group(1)) if m else None


def in_range(value: float, rng: Any) -> bool | None:
    """True/False when `rng` is [lo, hi] or "lo-hi"; None when it is not a range."""
    if isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(x, (int, float)) for x in rng):
        return rng[0] <= value <= rng[1]
    if isinstance(rng, str):
        m = re.match(rf"^\s*{_NUM}\s*(?:-|~|–|to)\s*{_NUM}", rng)
        if m:
            return float(m.group(1)) <= value <= float(m.group(2))
    return None


def parse_attrs(text: str) -> dict[str, Any]:
    """Normalize the electrical attributes a listing or a spec line states.

    Keys (only those found): voltage_v, voltage_range [lo, hi], mains_v [lo, hi], current_a, capacity_mah, cells,
    cells_range [lo, hi], c_rating, kv, kv_range [lo, hi], prop_in, connector ("XT60", "XT30", "JST-XH",
    "barrel_5.5x2.1", …), connectors [all found], pitch_mm, plug ("US", "UK", …), logic_v, variant ("C001"), gear.

    "4S", "4 cell", "14.8V" all give cells = 4; "2300KV", "2300 kv" give kv = 2300; "XT-60", "XT60H" give "XT60".
    Mains voltages (100-240V, 120V, 220V input) go to `mains_v`, never to `voltage_v`.
    """
    out: dict[str, Any] = {}
    t = text or ""
    work = t
    mains: list[float] = []
    for m in _MAINS.finditer(t):
        if m.group(1) and m.group(2):
            lo, hi = float(m.group(1)), float(m.group(2))
            if hi >= 100:
                mains += [lo, hi]
                work = work.replace(m.group(0), " ")
        elif m.group(3):
            mains.append(float(m.group(3)))
            work = work.replace(m.group(0), " ")
    if mains:
        out["mains_v"] = [min(mains), max(mains)]
    m = _VOLT_RANGE.search(work)
    if m:
        out["voltage_range"] = [float(m.group(1)), float(m.group(2))]
        work = work.replace(m.group(0), " ")
    volts = [float(v) for v in _VOLT.findall(work)]
    if volts:
        out["voltage_v"] = volts[0]
        if len(set(volts)) > 1:
            out["voltages"] = sorted(set(volts))
    amps = [float(v) / (1000 if unit.lower() == "ma" else 1) for v, unit in _AMP.findall(work)]
    if amps:
        out["current_a"] = max(amps)
    m = _MAH.search(t)
    if m:
        out["capacity_mah"] = float(m.group(1))
    m = _CELLS_RANGE.search(t)
    if m:
        out["cells_range"] = [int(m.group(1)), int(m.group(2))]
    else:
        m = _CELLS.search(t)
        if m and 1 <= int(m.group(1)) <= 14:
            out["cells"] = int(m.group(1))
    if "cells" not in out and "cells_range" not in out and "voltage_v" in out and re.search(r"(?i)\b(lipo|li-?po|li-?ion|battery)\b", t):
        cells = out["voltage_v"] / 3.7
        if abs(cells - round(cells)) < 0.06 and 1 <= round(cells) <= 14:
            out["cells"] = int(round(cells))  # 14.8 V -> 4S, 11.1 V -> 3S
    m = _KV_RANGE.search(t)
    if m:
        out["kv_range"] = [int(m.group(1)), int(m.group(2))]
    else:
        m = _KV.search(t)
        if m:
            out["kv"] = int(m.group(1) or m.group(2))
    m = _C_RATING.search(t)
    if m and "capacity_mah" in out:
        out["c_rating"] = int(m.group(1))
    m = _PROP.search(t)
    if m:
        out["prop_in"] = float(m.group(1))
    connectors: list[str] = []
    for m in _BARREL.finditer(t):
        inner = m.group(2) or ("2.1" if m.group(3) == "21" else "2.5")
        connectors.append(f"barrel_5.5x{inner}")
    connectors += [f"XT{m.group(1)}" for m in _XT.finditer(t)]
    for m in _JST.finditer(t):
        connectors.append(f"JST-{(m.group(1) or m.group(2)).upper()}")
    if re.search(r"(?i)\busb[- ]?c\b|\btype[- ]?c\b", t):
        connectors.append("USB-C")
    if connectors:
        uniq = list(dict.fromkeys(connectors))
        out["connector"], out["connectors"] = uniq[0], uniq
        fam = uniq[0].removeprefix("JST-")
        if fam in JST_PITCH:
            out["pitch_mm"] = JST_PITCH[fam]
    m = _PITCH.search(t)
    if m:
        out["pitch_mm"] = float(m.group(1) or m.group(2))
    m = _PLUG.search(t)
    if m:
        out["plug"] = PLUGS[m.group(1).lower()]
    m = _LOGIC.search(t)
    if m:
        out["logic_v"] = float(m.group(1) or m.group(2))
    m = _VARIANT.search(t)
    if m:
        out["variant"] = m.group(1)
    m = _GEAR.search(t)
    if m:
        out["gear"] = f"1/{m.group(1)}"
    return out


def listing_attrs(title: str | None, description: str | None = None) -> dict[str, Any]:
    """Attributes of a store listing: description first, then the title fills what the description lacks."""
    desc = parse_attrs(description or "")
    for k, v in parse_attrs(title or "").items():
        desc.setdefault(k, v)
    return desc


def rule_no(rule_id: str) -> str:
    """'R1 PSU_VOLTAGE_MATCH' -> 'R1'."""
    return rule_id.split()[0] if rule_id else ""


def missing(rule_id: str, attribute: str, lines: list[str], what: str, kb_refs: list[str] | None = None) -> Check:
    """The result every rule returns for a missing value: `needs_human`, naming the attribute."""
    return Check(rule_id=rule_id, result="needs_human", message=f"Needs your check: {what} ({attribute} not stated)",
                 kb_refs=kb_refs or [], bom_line_ids=lines)


@dataclass
class LineCtx:
    bom_line_id: str
    name: str
    category: str | None = None
    qty: int = 1
    line_kind: str = "part"
    status: str = "extracted"
    row_id: str | None = None
    rules: list[str] = field(default_factory=list)
    spec: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)
    chosen: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class PlanContext:
    build_type: str
    lines: list[LineCtx]
    answers: dict[str, str] = field(default_factory=dict)
    edges: list[dict[str, Any]] = field(default_factory=list)
    view_instances: dict[str, int] = field(default_factory=dict)
    ship_to_country: str = "US"

    def to_dict(self) -> dict[str, Any]:
        return {"build_type": self.build_type, "answers": dict(self.answers), "ship_to_country": self.ship_to_country,
                "lines": [ln.to_dict() for ln in self.lines], "edges": list(self.edges), "view_instances": dict(self.view_instances)}


def load_pack(name: str) -> ModuleType | None:
    """The pack module `app.rules.<name>`, or None when it does not exist."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name == "base":
        return None
    try:
        return importlib.import_module(f"app.rules.{name}")
    except ImportError:
        return None
