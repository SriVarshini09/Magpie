"""Domain pack `robot_arm`: rules R1–R11 for a bus-servo arm (PLAN §3.8). Owner: A.

Sources are KB rows (the SO-ARM100 README line 73 and the Waveshare Bus Servo Adapter wiki), cited by
`kb_ref` on every check. Roles are found by category: servos are `motor` lines, the controller is the
`board` line, the supply is the `power` line, USB leads are `cable` lines.

R10 has no auto-fix: the two sources disagree, so it is a WARN that needs a human, citing both.
"""

from __future__ import annotations

from typing import Any

from app.models import Check
from app.rules.base import missing, num

PACK_ID = "robot_arm"

KB_README_12V = "kb://so101_readme#L73"
KB_README_BOM = "kb://so101_readme#follower_bom"
KB_BOARD_JACK = "kb://waveshare_adapter#dc_jack"
KB_BOARD_INPUT = "kb://waveshare_adapter#input_voltage"
KB_BOARD_PROTOCOL = "kb://waveshare_adapter#protocol"

R1, R2, R3, R4 = "R1 PSU_VOLTAGE_MATCH", "R2 PSU_CURRENT_MIN", "R3 SERVO_VARIANT", "R4 SERVO_COUNT"
R5, R6, R7, R8 = "R5 BUS_PROTOCOL", "R6 BARREL_PLUG", "R7 NO_MIXED_VOLTAGE", "R8 USB_DATA"
R9, R10, R11 = "R9 PACK_COVERS_QTY", "R10 BOARD_INPUT_VOLTAGE", "R11 PLUG_AND_MAINS"

SUPPLY_FOR = {7.4: 5.0, 12.0: 12.0}  # servo voltage class -> supply voltage (README BOM; README line 73)
MIN_AMPS_12V = 5.0  # "12V 5A+ power supply" (README line 73)
FOLLOWER_VARIANTS = {7.4: {"C001"}, 12.0: {"C018", "C047"}}
LEADER_VARIANTS = {"C044", "C046"}
BARREL = "barrel_5.5x2.1"
OWNED = ("owned", "removed", "skipped")


def _by_cat(plan: dict[str, Any], category: str) -> list[dict[str, Any]]:
    return [ln for ln in plan["lines"] if ln.get("category") == category and ln.get("line_kind", "part") != "tool"]


def _servos(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [ln for ln in _by_cat(plan, "motor") if "servo" in (ln["name"] + " " + (ln.get("spec") or "")).lower()] or _by_cat(plan, "motor")


def _supply(plan: dict[str, Any]) -> dict[str, Any] | None:
    lines = [ln for ln in _by_cat(plan, "power") if "distribution" not in ln["name"].lower()]
    return lines[0] if lines else None


def _controller(plan: dict[str, Any]) -> dict[str, Any] | None:
    lines = _by_cat(plan, "board")
    return lines[0] if lines else None


def _text(offer: dict[str, Any]) -> str:
    return f"{offer.get('description') or ''} {offer.get('title') or ''}".lower()


def servo_class(plan: dict[str, Any]) -> float | None:
    """7.4 or 12.0: the voltage class the user picked (`voltage_class` chip or variant), else the BOM line's own."""
    ans = str(plan.get("answers", {}).get("voltage_class") or "").lower().replace("_", "")
    if ans.startswith("12") or ans.endswith("12v"):
        return 12.0
    if ans.startswith(("7", "74")) or "7v4" in ans or "7.4" in ans:
        return 7.4
    for ln in _servos(plan):
        v = num(ln.get("attrs", {}).get("voltage_v"))
        if v is not None:
            return 12.0 if v >= 11 else 7.4
    return None


def _supply_voltage(line: dict[str, Any]) -> tuple[float | None, str]:
    """(volts, where it came from): the chosen offer when there is one, else the BOM line's own spec."""
    for o in line.get("chosen") or []:
        v = num(o.get("attrs", {}).get("voltage_v"))
        if v is not None:
            return v, "offer"
    if line.get("chosen"):
        return None, "offer"
    return num(line.get("attrs", {}).get("voltage_v")), "bom"


def check(plan: dict[str, Any]) -> list[Check]:
    out: list[Check] = []
    servos, psu, board = _servos(plan), _supply(plan), _controller(plan)
    cls = servo_class(plan)
    servo_ids = [s["bom_line_id"] for s in servos]

    # R1: supply voltage matches the servo class
    if servos and psu and psu.get("status") not in OWNED:
        ids = [*servo_ids, psu["bom_line_id"]]
        if cls is None:
            out.append(missing(R1, "servo voltage", ids, "which servo voltage class this build uses", [KB_README_12V]))
        else:
            want = SUPPLY_FOR[cls]
            have, where = _supply_voltage(psu)
            if have is None:
                out.append(missing(R1, "voltage_v", ids, f"the supply must be {want:g} V for {cls:g} V servos", [KB_README_12V]))
            elif abs(have - want) > 0.6:
                src = "the README's supply" if where == "bom" else "the chosen supply"
                out.append(Check(rule_id=R1, result="fail", bom_line_ids=ids, kb_refs=[KB_README_12V],
                                 message=f"{cls:g}V servos need a {want:g}V supply, but {src} is {have:g}V.",
                                 fix=f"Swap the supply for a {want:g}V {'5A+ ' if want == 12 else ''}one (README line 73)"))
            else:
                out.append(Check(rule_id=R1, result="pass", bom_line_ids=ids, kb_refs=[KB_README_12V],
                                 message=f"{cls:g}V servos with a {have:g}V supply, as the README specifies."))

    # R2: a 12 V build needs 5 A or more
    if psu and cls == 12.0 and psu.get("chosen"):
        amps = max((num(o.get("attrs", {}).get("current_a")) or 0 for o in psu["chosen"]), default=0) or None
        if amps is None:
            out.append(missing(R2, "current_a", [psu["bom_line_id"]], f"the 12V build needs {MIN_AMPS_12V:g} A or more", [KB_README_12V]))
        elif amps < MIN_AMPS_12V:
            out.append(Check(rule_id=R2, result="fail", bom_line_ids=[psu["bom_line_id"]], kb_refs=[KB_README_12V],
                             message=f"{amps:g} A is under the 12V build's {MIN_AMPS_12V:g} A minimum.", fix="Search supplies rated 5 A or more"))
        else:
            out.append(Check(rule_id=R2, result="pass", bom_line_ids=[psu["bom_line_id"]], kb_refs=[KB_README_12V],
                             message=f"{amps:g} A meets the 12V build's {MIN_AMPS_12V:g} A minimum."))

    # R3: follower-arm servo variant; R7: one voltage class on the bus
    for s in servos:
        chosen = s.get("chosen") or []
        if not chosen:
            continue
        variants = {o.get("attrs", {}).get("variant") for o in chosen}
        if variants & LEADER_VARIANTS:
            bad = ", ".join(sorted(v for v in variants if v in LEADER_VARIANTS))
            out.append(Check(rule_id=R3, result="fail", bom_line_ids=[s["bom_line_id"]], kb_refs=[KB_README_BOM],
                             message=f"{bad} is a leader-arm gear ratio; the follower arm uses C001 (1/345).", fix="Replace with C001"))
        elif None in variants:
            out.append(missing(R3, "variant", [s["bom_line_id"]], "the listing does not state the servo variant code", [KB_README_BOM]))
        elif cls is not None and not variants <= FOLLOWER_VARIANTS[cls]:
            out.append(Check(rule_id=R3, result="fail", bom_line_ids=[s["bom_line_id"]], kb_refs=[KB_README_BOM],
                             message=f"Variant {', '.join(sorted(variants))} is not the {cls:g}V follower servo.",
                             fix=f"Replace with {' or '.join(sorted(FOLLOWER_VARIANTS[cls]))}"))
        else:
            out.append(Check(rule_id=R3, result="pass", bom_line_ids=[s["bom_line_id"]], kb_refs=[KB_README_BOM],
                             message=f"Servo variant {', '.join(sorted(variants))} matches the follower arm."))
    volts = {round(num(o.get("attrs", {}).get("voltage_v")) or -1, 1) for s in servos for o in s.get("chosen") or []} - {-1.0}
    if len({12.0 if v >= 11 else 7.4 for v in volts}) > 1:
        out.append(Check(rule_id=R7, result="fail", bom_line_ids=servo_ids, kb_refs=[KB_README_12V],
                         message="Servos on one bus must share a voltage class; the chosen listings mix 7.4V and 12V.",
                         fix="Align every servo to the chosen class"))

    # R4: servo count equals the servo meshes in the model
    for s in servos:
        want = plan.get("view_instances", {}).get(s["bom_line_id"])
        if want:
            if s["qty"] != want:
                out.append(Check(rule_id=R4, result="fail", bom_line_ids=[s["bom_line_id"]],
                                 message=f"{s['qty']} servos listed, but the model has {want} servo positions.", fix=f"Set quantity to {want}"))
            else:
                out.append(Check(rule_id=R4, result="pass", bom_line_ids=[s["bom_line_id"]],
                                 message=f"{want} servos match the {want} servo meshes in the URDF."))

    # R5: the controller is a serial bus servo adapter
    if board and board.get("chosen"):
        why = next((w for o in board["chosen"] if (w := _not_bus_adapter(o))), None)
        if why:
            out.append(Check(rule_id=R5, result="fail", bom_line_ids=[board["bom_line_id"]], kb_refs=[KB_BOARD_PROTOCOL], message=why,
                             fix="Use a serial bus servo adapter for ST/SC servos"))
        elif all("bus servo" in _text(o) or "serial bus" in _text(o) for o in board["chosen"]):
            out.append(Check(rule_id=R5, result="pass", bom_line_ids=[board["bom_line_id"]], kb_refs=[KB_BOARD_PROTOCOL],
                             message="The board is a serial bus servo adapter."))
        else:
            out.append(missing(R5, "protocol", [board["bom_line_id"]], "the listing does not say it is a serial bus servo adapter", [KB_BOARD_PROTOCOL]))

    # R6: 5.5 x 2.1 mm barrel plug; R11: US plug and 120 V input
    if psu and psu.get("chosen"):
        ids = [*([board["bom_line_id"]] if board else []), psu["bom_line_id"]]
        conns = [c for o in psu["chosen"] for c in o.get("attrs", {}).get("connectors", []) if str(c).startswith("barrel_")]
        if not conns:
            out.append(missing(R6, "connector", ids, "the plug must be 5.5x2.1 mm to fit the board's DC jack", [KB_BOARD_JACK]))
        elif BARREL not in conns:
            out.append(Check(rule_id=R6, result="fail", bom_line_ids=ids, kb_refs=[KB_BOARD_JACK],
                             message=f"The plug is {conns[0].removeprefix('barrel_')} mm; the board's jack is 5.5x2.1 mm.", fix="Filter supplies to a 5.5x2.1 mm plug"))
        else:
            out.append(Check(rule_id=R6, result="pass", bom_line_ids=ids, kb_refs=[KB_BOARD_JACK],
                             message="The supply has a 5.5x2.1 mm plug, matching the board's jack."))
        why = next((w for o in psu["chosen"] if (w := _mains_problem(o.get("attrs", {})))), None)
        plugs = {o.get("attrs", {}).get("plug") for o in psu["chosen"]}
        if why:
            out.append(Check(rule_id=R11, result="fail", bom_line_ids=[psu["bom_line_id"]], message=f"{why}.", fix="Filter to US-plug, 120V supplies"))
        elif plugs == {"US"}:
            out.append(Check(rule_id=R11, result="pass", bom_line_ids=[psu["bom_line_id"]], message="US plug; other regions' listings were rejected."))
        else:
            out.append(missing(R11, "plug", [psu["bom_line_id"]], "the listing does not say it has a US plug and 120V input"))

    # R8: USB cable carries data
    for c in _by_cat(plan, "cable"):
        if "usb" not in c["name"].lower() or c.get("status") in OWNED or not c.get("chosen"):
            continue
        if all("data" in _text(o) and "charge only" not in _text(o) and "charge-only" not in _text(o) for o in c["chosen"]):
            out.append(Check(rule_id=R8, result="pass", bom_line_ids=[c["bom_line_id"]], message="The listing states data transfer."))
        else:
            out.append(missing(R8, "data transfer", [c["bom_line_id"]], "a charge-only USB cable will not work"))

    # R9: pack units cover the quantity
    for ln in plan["lines"]:
        chosen = ln.get("chosen") or []
        if not chosen:
            continue
        units = sum(int(o.get("packs", 1)) * int(o.get("units_per_pack", 1)) for o in chosen)
        if units < ln["qty"]:
            out.append(Check(rule_id=R9, result="fail", bom_line_ids=[ln["bom_line_id"]],
                             message=f"The packs cover {units} of {ln['qty']} needed.", fix="Add single units"))
        elif len(chosen) > 1 or any(int(o.get("units_per_pack", 1)) > 1 for o in chosen):
            desc = " plus ".join(f"{o.get('packs', 1)} x {o.get('units_per_pack', 1)}-pack" if int(o.get("units_per_pack", 1)) > 1
                                 else f"{o.get('packs', 1)} single" for o in chosen)
            out.append(Check(rule_id=R9, result="pass", bom_line_ids=[ln["bom_line_id"]], message=f"{desc} covers {ln['qty']}."))

    # R10: the two trusted sources disagree. No auto-fix; a human decides.
    if board and psu and board.get("status") not in ("removed",):
        out.append(Check(rule_id=R10, result="warn", bom_line_ids=[board["bom_line_id"]], kb_refs=[KB_README_12V, KB_BOARD_INPUT], needs_ack=True,
                         message="Sources disagree: the README runs 7.4V servos from a 5V supply; the Waveshare wiki says the board takes "
                                 "9~12.6V (should match servo voltage). Needs your check."))
    return out


def _not_bus_adapter(offer: dict[str, Any]) -> str | None:
    t = _text(offer)
    if "driver hat" in t or " hat " in f" {t} " or "pca9685" in t or "pwm" in t:
        return "This is a PWM driver board (HAT), not a serial bus servo adapter"
    if "buck" in t or "dc-dc" in t:
        return "This is a DC-DC converter, not a servo adapter"
    return None


def _mains_problem(attrs: dict[str, Any]) -> str | None:
    plug, mains = attrs.get("plug"), attrs.get("mains_v")
    bits = []
    if plug and plug != "US":
        bits.append(f"{plug} plug")
    if mains and mains[0] > 130:
        bits.append(f"{mains[0]:g}V input")
    return ", ".join(bits) or None


def fix(check: Check, plan: dict[str, Any]) -> dict[str, Any] | None:
    """A search filter that repairs a FAIL. R10 has none on purpose."""
    cls = servo_class(plan)
    psu = _supply(plan)
    no = check.rule_id.split()[0]
    if no in ("R1", "R2", "R6", "R11") and psu and cls is not None:
        want = SUPPLY_FOR[cls]
        amps = MIN_AMPS_12V if want == 12 else None
        spec = f"{want:g}V {f'{amps:g}A+ ' if amps else ''}power supply, 5.5x2.1 mm plug, US plug"
        return {"bom_line_id": psu["bom_line_id"], "action": "respec", "spec": spec,
                "query": f"{want:g}V {f'{amps:g}A ' if amps else ''}power supply 5.5x2.1mm",
                "attrs": {"voltage_v": want, **({"min_current_a": amps} if amps else {}), "connector": BARREL, "plug": "US"},
                "kb_refs": [KB_README_12V], "summary": f"swapped in a {want:g}V {f'{amps:g}A+ ' if amps else ''}supply"}
    if no == "R4":
        line = check.bom_line_ids[0] if check.bom_line_ids else None
        want = plan.get("view_instances", {}).get(line or "")
        return {"bom_line_id": line, "action": "set_qty", "qty": want, "summary": f"set quantity to {want}"} if want else None
    if no in ("R3", "R7") and cls is not None:
        line = check.bom_line_ids[0] if check.bom_line_ids else None
        return {"bom_line_id": line, "action": "refilter", "attrs": {"variant_in": sorted(FOLLOWER_VARIANTS[cls]), "voltage_v": cls},
                "summary": f"kept only {cls:g}V follower servos"}
    if no == "R5":
        return {"bom_line_id": check.bom_line_ids[0] if check.bom_line_ids else None, "action": "refilter", "summary": "rejected boards that are not bus servo adapters"}
    return None


def respec(line: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any] | None:
    """The spec a chip answer implies for a line, with its source. Called before the checks.

    - 12V picked: the servo line becomes the 12V 30 kg version (README line 73).
    - The README's supply row states no voltage; its BOM is the 5V build ("instead of a 5V one", line 73).
    """
    cls = servo_class(plan)
    cat, attrs = line.get("category"), line.get("attrs", {})
    text = (line["name"] + " " + (line.get("spec") or "")).lower()
    if cat == "motor" and "servo" in text and cls == 12.0 and (num(attrs.get("voltage_v")) or 0) < 11:
        return {"spec": "Feetech STS3215 12V 30kg (C018)", "attrs": {"voltage_v": 12.0, "variant": "C018"},
                "query": "STS3215 12V 30kg servo C018", "kb_refs": [KB_README_12V], "by": "you",
                "summary": "switched from 7.4V C001 to the 12V 30kg version"}
    if cat == "power" and "distribution" not in text and num(attrs.get("voltage_v")) is None and not line.get("chosen"):
        return {"spec": "5V power supply, 5.5x2.1 mm plug (the README's BOM is the 5V build)", "attrs": {"voltage_v": 5.0, "connector": BARREL},
                "query": "5V power supply 5.5x2.1mm", "kb_refs": [KB_README_12V], "by": "source",
                "summary": "the README's supply is the 5V one"}
    if cat == "board" and "bus servo" not in text and not line.get("chosen"):
        return {"spec": "Waveshare Bus Servo Adapter (A), serial bus servo driver for ST/SC servos", "attrs": {},
                "query": "Waveshare bus servo adapter serial bus servo driver board", "kb_refs": [KB_BOARD_PROTOCOL], "by": "source",
                "summary": "the README links the Waveshare serial bus servo driver board"}
    return None


def reject(line: dict[str, Any], offer: dict[str, Any], plan: dict[str, Any]) -> str | None:
    """Why an offer cannot be used for a line (PLAN §3.6 rank filters). None means it may be ranked."""
    a = offer.get("attrs", {})
    cat, name = line.get("category"), line.get("name", "").lower()
    cls = servo_class(plan)
    if cat == "motor" and "servo" in (name + " " + (line.get("spec") or "").lower()):
        variant, volt = a.get("variant"), num(a.get("voltage_v"))
        if variant in LEADER_VARIANTS:
            return f"variant_mismatch: {variant} is a leader-arm servo (R3)"
        if cls is not None:
            ocls = None if volt is None else (12.0 if volt >= 11 else 7.4)
            if (variant and variant not in FOLLOWER_VARIANTS[cls]) or (ocls is not None and ocls != cls):
                have = " ".join(x for x in (f"{ocls:g}V" if ocls else "", variant or "") if x)
                return f"variant_mismatch: {have}, need {cls:g}V {'/'.join(sorted(FOLLOWER_VARIANTS[cls]))}"
    if cat == "board":
        why = _not_bus_adapter(offer)
        if why:
            return f"R5: {why[0].lower()}{why[1:]}"
    if cat == "power" and "distribution" not in name:
        why = _mains_problem(a)
        if why:
            return f"R11: {why}"
        if cls is not None:
            want, volt, amps = SUPPLY_FOR[cls], num(a.get("voltage_v")), num(a.get("current_a"))
            if volt is not None and abs(volt - want) > 0.6:
                return f"R1: {volt:g} V supply, need {want:g} V"
            if want == 12 and amps is not None and amps < MIN_AMPS_12V:
                return f"R2: {amps:g} A < {MIN_AMPS_12V:g} A"
        barrels = [c for c in a.get("connectors", []) if str(c).startswith("barrel_")]
        if barrels and BARREL not in barrels:
            return f"R6: {barrels[0].removeprefix('barrel_')} mm plug, need 5.5x2.1 mm"
    return None
