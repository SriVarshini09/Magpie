"""A receipt downloaded from the API (nulls added back by the response model) still verifies offline."""

import json
from pathlib import Path

import pytest

from app.audit import verify

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _mandates(r: dict) -> list[str]:
    return [k for k in ("open_mandate", "closed_mandate", "payment_mandate") if isinstance(r.get(k), dict)]


@pytest.mark.parametrize("name", ["receipt_drone.json", "receipt_so101.json"])
def test_nulls_added_by_the_api_do_not_break_signatures(name):
    r = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert verify.verify_receipt(r)["signatures_ok"]
    assert _mandates(r)
    for k in _mandates(r):
        r[k]["added_by_response_model"] = None  # what FastAPI's response_model does to optional fields
        nested = next((v for v in r[k].values() if isinstance(v, dict)), None)
        if nested is not None:
            nested["also_null"] = None  # and inside nested models
    d = verify.verify_receipt(r)
    assert d["ok"] and d["signatures_ok"], [c for c in d["checks"] if not c["ok"]]


def test_a_changed_value_still_fails():
    r = json.loads((FIXTURES / "receipt_drone.json").read_text(encoding="utf-8"))
    om = r["open_mandate"]
    key = next(k for k, v in om.items() if isinstance(v, str) and k != "signature")
    om[key] = om[key] + "x"
    assert not verify.verify_receipt(r)["signatures_ok"]
