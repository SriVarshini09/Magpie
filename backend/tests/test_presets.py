"""Project presets (PLAN §13.1): data/projects/<build_type>/preset.json.

Shape: {"sample": ProjectSample, "template_id", "default_answers", "seed_memories", "kb_docs", "notes", ...}.
`sample` validates directly as `app.models.ProjectSample`, so GET /api/projects can serve it as is.
"""

from __future__ import annotations

import json
import re

import pytest

from app.config import DATA_DIR
from app.models import ProjectSample

PRESETS = ["robot_arm", "quadcopter", "electronics_mcu"]
BUYER_KEYS = {"email", "phone", "phone_number", "name", "first_name", "last_name", "address", "street", "street_address",
              "postal_code", "zip", "card", "card_number", "password"}


def load(bt: str) -> dict:
    return json.loads((DATA_DIR / "projects" / bt / "preset.json").read_text(encoding="utf-8"))


def store_ids() -> set[str]:
    data = json.loads((DATA_DIR / "stores.json").read_text(encoding="utf-8"))
    stores = data["stores"] if isinstance(data, dict) else data
    return {s["store_id"] for s in stores}


def walk_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{path}.{k}", k, v
            yield from walk_keys(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_keys(v, f"{path}[{i}]")


@pytest.mark.parametrize("bt", PRESETS)
def test_preset_sample_validates_and_is_not_mock(bt):
    p = load(bt)
    sample = ProjectSample.model_validate(p["sample"])
    assert sample.build_type == bt
    assert sample.simulated is False and "simulated" not in p["sample"]  # config, not mock data
    assert sample.example_text or sample.source_url


@pytest.mark.parametrize("bt", PRESETS)
def test_preset_template_exists_and_answers_are_chips(bt):
    p = load(bt)
    assert p["template_id"] == f"tpl_{bt}"
    tpl = json.loads((DATA_DIR / "kb" / "templates" / f"{bt}.json").read_text(encoding="utf-8"))
    assert tpl["template_id"] == p["template_id"]
    chips = {q["id"]: {c["value"] for c in q["chips"]} for q in tpl["questions"]}
    for answers in (p["default_answers"], p.get("stage_answers", {})):
        for qid, value in answers.items():
            assert qid in chips and value in chips[qid], (bt, qid, value)
    assert p["template_id"] in p["kb_docs"]
    assert all(re.fullmatch(r"[a-z0-9_]+", d) for d in p["kb_docs"])


@pytest.mark.parametrize("bt", PRESETS)
def test_preset_merchants_are_registered_stores(bt):
    merchants = load(bt)["sample"]["mandate_preset"]["allowed_merchants"]
    assert merchants and len(merchants) == len(set(merchants))
    assert set(merchants) <= store_ids(), set(merchants) - store_ids()
    assert "mock_store" not in merchants  # fixture-only id


@pytest.mark.parametrize("bt", PRESETS)
def test_preset_holds_no_buyer_data_and_shares_country_only(bt):
    p = load(bt)
    for path, key, _ in walk_keys(p):
        if ".data_sharing." in path + ".":
            continue  # data_sharing holds the consent flags, which are booleans
        assert key not in BUYER_KEYS, path
    sharing = p["sample"]["mandate_preset"]["data_sharing"]
    assert sharing["country"] is True and not any(v for k, v in sharing.items() if k != "country")
    assert all(isinstance(m, str) and m for m in p["seed_memories"])


def test_preset_links_and_budgets_match_the_plan():
    arm, drone, mcu = (load(b)["sample"] for b in PRESETS)
    assert arm["source_url"] == "https://github.com/TheRobotStudio/SO-ARM100" and arm["mandate_preset"]["budget_usd"] == 160
    assert drone["example_text"] == "a small camera drone under $200" and drone["mandate_preset"]["budget_usd"] == 200
    assert mcu["source_url"] == "https://github.com/lmarzen/esp32-weather-epd" and mcu["mandate_preset"]["budget_usd"] == 130
    assert load("electronics_mcu")["source_commit"] == "c78ad15e7933684fb5af19168f6e2da003e08b84"
    assert load("robot_arm")["stage_answers"]["voltage_class"] == "12v"  # the 12V fix on stage (M4)
