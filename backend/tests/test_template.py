"""Build-type templates (PLAN §3.19, Appendix B). A template that fails here is not loaded and its
build type routes to `generic` (PLAN §2.1, P16 fallback).

Conventions checked here (and relied on by the template loader):
- base `parts` describe the default variant; `variants[].overrides` is `{row_id: {field: value}}` plus an
  optional `_view: {"scale": float}`;
- `qty: 0` means "row not used in this variant"; `qty: null` means "unknown" (generic rows);
- a view part is drawn only when its row is in the BOM and the row's `mesh` (after overrides) is not null.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from app.config import DATA_DIR, FIXTURES_DIR, REPO_ROOT
from app.models import Template, TemplatePart

TEMPLATES_DIR = DATA_DIR / "kb" / "templates"
SOURCES_MD = DATA_DIR / "kb" / "template_sources.md"
BUILD_TYPES = ["robot_arm", "quadcopter", "rc_car", "claw_gripper", "electronics_mcu", "generic"]
RULE_IDS = {f"G{i}" for i in range(1, 12)} | {f"R{i}" for i in range(1, 18)}
RULE_PACKS = {"generic_electrical", "robot_arm", "mcu_battery"}
# PLAN §3.8: the attribute names the generic rule pack reads; `variant` is the servo variant code (R3).
ATTR_NAMES = {
    "voltage_v", "voltage_range", "current_a", "max_current_a", "cells", "cells_range", "capacity_mah",
    "c_rating", "logic_v", "connector", "pitch_mm", "kv", "prop_in", "variant", "mount_mm",
}
OVERRIDE_FIELDS = set(TemplatePart.model_fields) - {"row_id", "category"}
# Conditions the intake may test before asking a question; anything else in skip_if is a typo.
SKIP_TOKENS = {
    "text_mentions_size", "text_mentions_voltage", "text_mentions_board", "text_mentions_servo",
    "text_mentions_power", "link_names_board", "link_names_power", "memory_answers", "photo_present", "no_photo",
}
# PLAN Appendix C mesh names per procedural model, and the SO-101 URDF meshes.
APPENDIX_C_MESHES = {
    "quadcopter": {"frame", "motor", "esc", "fc", "receiver", "vtx", "camera", "props", "battery", "pdb", "gps"},
    "rc_car": {"chassis", "printed", "usb_battery", "sbc", "servo_driver", "camera", "jumpers", "motor"},
    "claw": {"wrist", "servo", "jaw_fixed", "jaw_moving", "screws", "controller", "psu", "clamp"},
}
FRONTEND_MODEL_FILES = {"quadcopter": "quadcopter.ts", "rc_car": "rcCar.ts", "claw": "claw.ts"}
URDF = REPO_ROOT / "frontend" / "public" / "so101" / "so101_new_calib.urdf"
SO_README = (FIXTURES_DIR / "sources" / "SO-ARM100_README.md").read_text(encoding="utf-8")
SO_URL = "https://github.com/TheRobotStudio/SO-ARM100"


def load(build_type: str) -> dict:
    return json.loads((TEMPLATES_DIR / f"{build_type}.json").read_text(encoding="utf-8"))


def variant_parts(raw: dict, variant: dict | None) -> list[dict]:
    """The rows as one variant sees them (base rows with that variant's overrides applied)."""
    parts = copy.deepcopy(raw["parts"])
    if variant is None:
        return parts
    for row in parts:
        over = variant["overrides"].get(row["row_id"], {})
        for field, value in over.items():
            if field == "attrs" and value is not None:
                row["attrs"] = {**row.get("attrs", {}), **value}
            else:
                row[field] = value
    return parts


def all_views(raw: dict) -> list[tuple[str, list[dict]]]:
    return [("base", variant_parts(raw, None))] + [(v["id"], variant_parts(raw, v)) for v in raw["variants"]]


def sources_chunks() -> dict[str, dict[str, list[str]]]:
    """chunk_id -> {meta key: [values]} from template_sources.md (the KB markdown format)."""
    chunks: dict[str, dict[str, list[str]]] = {}
    current = None
    for line in SOURCES_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## chunk: ([a-z0-9_]+)\s*$", line)
        if m:
            current = chunks.setdefault(m.group(1), {})
            continue
        m = re.match(r"^- ([a-z_]+): (.*)$", line)
        if current is not None and m:
            current.setdefault(m.group(1), []).append(m.group(2).strip())
    return chunks


def test_every_build_type_has_exactly_one_template_file():
    assert sorted(p.stem for p in TEMPLATES_DIR.glob("*.json")) == sorted(BUILD_TYPES)


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_template_validates_and_names_match(bt):
    raw = load(bt)
    tpl = Template.model_validate(raw)
    assert tpl.build_type == bt and tpl.template_id == f"tpl_{bt}"
    assert tpl.version and tpl.title and len(tpl.summary) > 60
    assert "generic_electrical" in tpl.rule_packs and set(tpl.rule_packs) <= RULE_PACKS


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_row_ids_unique_and_rule_ids_exist(bt):
    raw = load(bt)
    ids = [p["row_id"] for p in raw["parts"]]
    assert len(ids) == len(set(ids)), ids
    assert all(re.fullmatch(r"[a-z0-9_]+", i) for i in ids)
    for _, parts in all_views(raw):
        for p in parts:
            assert set(p.get("rules", [])) <= RULE_IDS, (p["row_id"], p["rules"])
    for e in raw["edges"]:
        assert set(e["rules"]) <= RULE_IDS


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_view_parts_and_edges_point_at_rows(bt):
    raw = load(bt)
    ids = {p["row_id"] for p in raw["parts"]}
    meshes_by_row: dict[str, set[str]] = {}
    for vp in raw["view"]["parts"]:
        assert vp["row_id"] in ids, vp
        meshes_by_row.setdefault(vp["row_id"], set()).add(vp["mesh"])
    for e in raw["edges"]:
        assert e["from"] in ids and e["to"] in ids and e["from"] != e["to"], e
    # every row mesh, in every variant, is a mesh the view draws for that row
    for name, parts in all_views(raw):
        for p in parts:
            if p.get("mesh"):
                assert p["mesh"] in meshes_by_row.get(p["row_id"], set()), (bt, name, p["row_id"], p["mesh"])


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_provenance_basis_rules(bt):
    """reference rows cite a URL (and, in the base rows, a short exact quote); rule-of-thumb rows say so."""
    raw = load(bt)
    for name, parts in all_views(raw):
        for p in parts:
            src = p.get("source") or {}
            spec = p.get("typical_spec") or ""
            if p["basis"] == "reference":
                assert src.get("url"), (bt, name, p["row_id"])
                if name == "base":
                    assert src.get("quote"), (bt, p["row_id"], "base reference rows need a quote")
                elif not src.get("quote"):
                    assert "not quoted" in spec, (bt, name, p["row_id"], "say 'cited, not quoted'")
            if p["basis"] == "rule_of_thumb":
                assert "rule of thumb" in spec.lower(), (bt, name, p["row_id"])
            if src.get("quote"):
                assert len(src["quote"].split()) < 15, (bt, p["row_id"], "quotes stay short")
            if p["basis"] == "assumption":
                assert not src, (bt, p["row_id"], "an assumption has no source")


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_every_source_url_is_a_reference_with_a_licence(bt):
    raw = load(bt)
    refs = {r["url"]: r for r in raw["references"]}
    for r in refs.values():
        assert r.get("licence"), r["url"]
    for name, parts in all_views(raw):
        for p in parts:
            url = (p.get("source") or {}).get("url")
            if url and url.startswith("http"):
                assert url in refs, (bt, name, p["row_id"], url)


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_attrs_use_rule_attribute_names(bt):
    raw = load(bt)
    for _, parts in all_views(raw):
        for p in parts:
            assert set(p.get("attrs", {})) <= ATTR_NAMES, (bt, p["row_id"], set(p["attrs"]) - ATTR_NAMES)
            for v in p.get("attrs", {}).values():
                assert v is None or isinstance(v, str), (bt, p["row_id"], v)


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_questions_chips_and_defaults(bt):
    raw = load(bt)
    qids = [q["id"] for q in raw["questions"]]
    assert len(qids) == len(set(qids))
    for q in raw["questions"]:
        values = [c["value"] for c in q["chips"]]
        assert len(values) >= 2 and len(values) == len(set(values))
        assert q["default"] in values, q["id"]
        assert set(q.get("skip_if", [])) <= SKIP_TOKENS, q["skip_if"]
    # at most three chip questions apply to any one request (PLAN §3.17), with or without a photo
    text_mode = [q for q in raw["questions"] if "no_photo" not in q.get("skip_if", [])]
    photo_mode = [q for q in raw["questions"] if "photo_present" not in q.get("skip_if", [])]
    assert len(text_mode) <= 3 and len(photo_mode) <= 3, (bt, len(text_mode), len(photo_mode))
    for p in raw["parts"]:
        if p.get("own_question"):
            assert p["own_question"] in qids, (bt, p["row_id"])


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_variants_are_keyed_by_questions_and_rows(bt):
    raw = load(bt)
    qids = {q["id"]: {c["value"] for c in q["chips"]} for q in raw["questions"]}
    ids = {p["row_id"] for p in raw["parts"]}
    vids = [v["id"] for v in raw["variants"]]
    assert len(vids) == len(set(vids))
    for v in raw["variants"]:
        for key, value in v["when"].items():
            if key == "source_url":
                assert value.startswith("https://")
            else:
                assert key in qids and value in qids[key], (bt, v["id"], key, value)
        for row_id, over in v["overrides"].items():
            if row_id == "_view":
                assert set(over) <= {"scale"}
                continue
            assert row_id in ids, (bt, v["id"], row_id)
            assert set(over) <= OVERRIDE_FIELDS, (bt, v["id"], row_id, set(over) - OVERRIDE_FIELDS)
        for p in variant_parts(raw, v):
            TemplatePart.model_validate(p)  # an override never produces an invalid row
    # the chips' defaults select exactly one variant, when there are variants keyed by questions
    defaults = {q["id"]: q["default"] for q in raw["questions"]}
    keyed = [v for v in raw["variants"] if "source_url" not in v["when"]]
    if keyed:
        picked = [v["id"] for v in keyed if all(defaults.get(k) == val for k, val in v["when"].items())]
        assert len(picked) == 1, (bt, picked)


@pytest.mark.parametrize("bt", BUILD_TYPES)
def test_quantities_are_known_or_null(bt):
    raw = load(bt)
    for _, parts in all_views(raw):
        for p in parts:
            assert p["qty"] is None or p["qty"] >= 0
            if bt == "generic":
                assert p["qty"] is None and p["basis"] == "assumption" and not p.get("typical_spec")
    if bt != "generic":
        assert all(p["qty"] is not None for p in raw["parts"])


def test_quadcopter_default_is_3in_4s_and_matches_the_drone_fixture():
    raw = load("quadcopter")
    defaults = {q["id"]: q["default"] for q in raw["questions"]}
    picked = [v["id"] for v in raw["variants"] if all(defaults.get(k) == val for k, val in v["when"].items())]
    assert picked == ["3in_4s"]
    assert next(v for v in raw["variants"] if v["id"] == "3in_4s")["overrides"]["_view"] == {"scale": 0.65}
    # rows in use in the default variant, in order, are the drone fixture's b1..b12 kb refs
    run = json.loads((FIXTURES_DIR / "run_drone.json").read_text(encoding="utf-8"))
    fixture_rows = [b["provenance"]["kb_ref"].split("#")[1] for b in run["bom"] if b["provenance"].get("kb_ref")]
    used = [p["row_id"] for p in raw["parts"] if p["qty"]]
    assert [r for r in used if r in fixture_rows] == fixture_rows
    # every 3-inch row is a rule of thumb: no source was read for those numbers (PLAN Appendix B.2)
    assert all(p["basis"] == "rule_of_thumb" for p in raw["parts"])
    motor = next(p for p in raw["parts"] if p["row_id"] == "motor")
    assert motor["attrs"]["kv"] == "3500-4500" and motor["attrs"]["cells"] == "4S" and motor["qty"] == 4


def test_quadcopter_x500_cites_both_kv_sources():
    raw = load("quadcopter")
    x500 = next(v for v in raw["variants"] if v["id"] == "x500")
    spec = x500["overrides"]["motor"]["typical_spec"]
    assert "KV880" in spec and "KV920" in spec and "disagree" in spec
    urls = {r["url"] for r in raw["references"]}
    assert any("docs.px4.io" in u for u in urls) and any("docs.holybro.com" in u for u in urls)


def test_robot_arm_and_claw_quotes_are_exact_substrings_of_the_so101_readme():
    for bt in ("robot_arm", "claw_gripper"):
        raw = load(bt)
        for _, parts in all_views(raw):
            for p in parts:
                src = p.get("source") or {}
                if src.get("url") == SO_URL and src.get("quote"):
                    assert src["quote"] in SO_README, (bt, p["row_id"], src["quote"])


def test_robot_arm_matches_the_readme_follower_arm():
    raw = load("robot_arm")
    rows = {p["row_id"]: p for p in raw["parts"]}
    assert rows["servo"]["qty"] == 6 and rows["servo"]["attrs"]["voltage_v"] == "7.4"
    twelve = next(v for v in raw["variants"] if v["id"] == "12v")["overrides"]
    assert twelve["psu"]["attrs"]["voltage_v"] == "12" and twelve["psu"]["source"]["quote"] == "12V 5A+ power supply"
    assert rows["psu"]["attrs"]["current_a"] is None  # amps are not stated for the 5V build: unknown, never a guess


def test_rc_car_never_guesses_the_chassis_battery():
    rows = {p["row_id"]: p for p in load("rc_car")["parts"]}
    assert rows["chassis"]["attrs"] == {"voltage_v": None, "cells": None}


def test_claw_screw_counts_are_assumptions():
    rows = {p["row_id"]: p for p in load("claw_gripper")["parts"]}
    assert rows["screws"]["basis"] == "assumption"


def test_electronics_esp32_epaper_variant_matches_plan_13_2():
    raw = load("electronics_mcu")
    v = next(v for v in raw["variants"] if v["id"] == "esp32_epaper")
    assert v["when"] == {"source_url": "https://github.com/lmarzen/esp32-weather-epd"}
    quotes = {row: o["source"]["quote"] for row, o in v["overrides"].items() if isinstance(o, dict) and o.get("source")}
    assert quotes["mcu"] == "FireBeetle 2 ESP32-E" and quotes["battery"] == "3.7V LiPo w/ JST-PH2.0 connector"
    assert quotes["adapter"] == "DESPI-C02" and quotes["sensor"] == "BME280"
    battery = v["overrides"]["battery"]["attrs"]
    assert battery["connector"] == "JST-PH" and battery["pitch_mm"] == "2.0" and battery["cells"] == "1S"
    assert "mcu_battery" in raw["rule_packs"]
    # the breadboard-photo detection labels from Appendix B.5 are in the searchable summary
    for label in ("arduino board", "esp32 board", "breadboard", "jumper wires", "sensor module", "lcd display"):
        assert label in raw["summary"]


def _frontend_meshes(model: str) -> set[str]:
    path = REPO_ROOT / "frontend" / "src" / "models" / FRONTEND_MODEL_FILES[model]
    if not path.is_file():
        return set()
    # only mesh fields inside the PartDef array, not the comment line that lists the names
    code = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("//"))
    return set(re.findall(r"""mesh:\s*["']([A-Za-z0-9_]+)["']""", code))


@pytest.mark.parametrize("bt", ["quadcopter", "rc_car", "claw_gripper", "robot_arm"])
def test_mesh_names_match_the_3d_models(bt):
    raw = load(bt)
    meshes = {vp["mesh"] for vp in raw["view"]["parts"]}
    model = raw["view"]["model"]
    if raw["view"]["kind"] == "urdf":
        urdf = set(re.findall(r'filename="assets/([A-Za-z0-9_]+)\.stl"', URDF.read_text(encoding="utf-8")))
        assert meshes and meshes <= urdf, meshes - urdf
        return
    assert meshes <= APPENDIX_C_MESHES[model], meshes - APPENDIX_C_MESHES[model]
    frontend = _frontend_meshes(model)
    if frontend:  # C's parts array exists: the template may only name meshes it draws
        assert meshes <= frontend, (model, meshes - frontend)


def test_template_sources_md_has_a_chunk_for_every_reference():
    chunks = sources_chunks()
    by_url = {meta["source"][0]: cid for cid, meta in chunks.items() if meta.get("source")}
    for bt in BUILD_TYPES:
        for ref in load(bt)["references"]:
            assert ref["url"] in by_url, (bt, ref["url"])
            meta = chunks[by_url[ref["url"]]]
            assert meta.get("licence"), ref["url"]
    head = SOURCES_MD.read_text(encoding="utf-8").split("---")[1]
    assert "doc_id: template_sources" in head and "kind: reference" in head


def test_every_template_quote_appears_in_template_sources_md():
    chunks = sources_chunks()
    by_url = {meta["source"][0]: meta for meta in chunks.values() if meta.get("source")}
    for bt in BUILD_TYPES:
        raw = load(bt)
        for _, parts in all_views(raw):
            for p in parts:
                src = p.get("source") or {}
                if src.get("quote"):
                    listed = [q.strip('"') for q in by_url[src["url"]].get("quote", [])]
                    assert any(src["quote"] == q for q in listed), (bt, p["row_id"], src["quote"])


def test_files_are_utf8_lf():
    for path in [*TEMPLATES_DIR.glob("*.json"), SOURCES_MD]:
        data = path.read_bytes()
        assert b"\r\n" not in data, path
        data.decode("utf-8")
