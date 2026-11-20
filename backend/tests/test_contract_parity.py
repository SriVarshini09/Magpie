"""frontend/src/lib/types.ts mirrors app/models.py field for field (it is generated from it)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "scripts"))

import gen_types  # noqa: E402

from app import models as M  # noqa: E402

pytestmark = pytest.mark.skipif(not gen_types.OUT.parent.parent.parent.exists(), reason="frontend/ not present")


def test_types_ts_is_up_to_date():
    assert gen_types.OUT.exists(), "run: uv run python scripts/gen_types.py"
    on_disk = gen_types.OUT.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert on_disk == gen_types.render(), "types.ts is out of date. Run: cd backend && uv run python scripts/gen_types.py"


def test_every_model_field_is_in_types_ts():
    text = gen_types.OUT.read_text(encoding="utf-8")
    for cls in gen_types.model_classes():
        block = re.search(rf"export type {cls.__name__} = \{{(.*?)\n\}};", text, re.S)
        assert block, f"{cls.__name__} missing from types.ts"
        keys = set(re.findall(r"^\s+(\w+)\??:", block.group(1), re.M))
        expected = {f.alias or name for name, f in cls.model_fields.items()}
        assert keys == expected, f"{cls.__name__}: {keys ^ expected}"
    for name in M.TS_ALIASES:
        assert f"export type {name} =" in text


def test_required_contract_types_exist():
    required = {"BOMLine", "Offer", "DecisionRecord", "OpenMandate", "ClosedMandate", "PaymentMandate", "CartPlan", "UniversalCart",
                "StoreGroup", "CartHandoff", "PartPanel", "Intake", "IntakeRequest", "IntakeAnswersRequest", "ViewData", "DiagramData",
                "KitToken", "PhotoView", "Event", "RunState", "Template", "Receipt", "Health"}
    assert required <= {c.__name__ for c in gen_types.model_classes()}
    assert set(M.ProvenanceType.__args__) == {"readme_quote", "reference_project", "template_row", "photo_region", "assumption"}
    assert set(M.ActionLevel.__args__) == {"agent_cart", "prefilled_cart", "product_link"}
