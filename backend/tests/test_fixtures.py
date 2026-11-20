"""Fixtures match the contract, are labelled mock, and keep the claims the demo makes."""

from __future__ import annotations

import json
import re

import pytest

from app import fixtures
from app.audit.chain import recompute, sha256_hex
from app.config import DATA_DIR, FIXTURES_DIR
from app import models as M

SHAPES = {
    r"run_.*\.json": M.RunState, r"cart_(so101|drone)(_approved)?\.json": M.UniversalCart, r"panel_.*\.json": M.PartPanel,
    r"intake_.*\.json": M.Intake, r"receipt_.*\.json": M.Receipt, r"verify_.*\.json": M.VerifyResult,
    r"closed_mandate_.*\.json": M.ClosedMandate, r"view_.*\.json": M.ViewData, r"kb_search\.json": M.KbSearchResponse,
    r"prices_.*\.json": M.PricesResponse, r"pay_intent_.*\.json": M.PayIntentResponse, r"cart_refresh\.json": M.CartRefreshResponse,
}
LISTS = {r"projects\.json": M.ProjectSample, r"stores\.json": M.StoreInfo, r"events_.*\.jsonl": M.Event}
README = (FIXTURES_DIR / "sources" / "SO-ARM100_README.md").read_bytes()


def shape_of(name, table):
    return next((model for pattern, model in table.items() if re.fullmatch(pattern, name)), None)


@pytest.mark.parametrize("name", fixtures.names())
def test_fixture_matches_its_model_and_is_labelled_mock(name):
    data = fixtures.load(name)
    if name.startswith("offers_"):
        items = [{k: v for k, v in o.items() if k != "bom_line_id"} for o in data]
        model = M.Offer
    elif (model := shape_of(name, LISTS)) is not None:
        items = data
    else:
        model = shape_of(name, SHAPES)
        assert model is not None, f"no model registered for fixture {name}"
        items = [data]
    assert items
    for item in items:
        model.model_validate(item)
        assert item.get("simulated") is True, f"{name}: mock data must carry simulated: true"
        if "source_api" in model.model_fields and model is not M.Event:
            assert item.get("source_api") == "mock", f"{name}: mock data must carry source_api: mock"


def test_every_offer_anywhere_is_labelled_mock():
    text = "".join((FIXTURES_DIR / n).read_text(encoding="utf-8") for n in fixtures.names())
    apis = set(re.findall(r'"source_api": "([^"]+)"', text))
    assert apis == {"mock"}, apis
    for o in json.loads((DATA_DIR / "mock_store.json").read_text(encoding="utf-8")):
        assert o["source_api"] == "mock" and o["simulated"] is True and "mock.invalid" in o["url"]


def test_no_fixture_url_points_at_a_real_store_except_source_links():
    text = "".join((FIXTURES_DIR / n).read_text(encoding="utf-8") for n in fixtures.names())
    hosts = set(re.findall(r'https://([^/"\s]+)', text))
    assert hosts <= {"mock.invalid", "github.com", "docs.px4.io"}, hosts


def walk_provenance(obj):
    if isinstance(obj, dict):
        if obj.get("type") in M.ProvenanceType.__args__:
            yield obj
        for v in obj.values():
            yield from walk_provenance(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_provenance(v)


def test_readme_quotes_are_exact_substrings_of_the_bundled_readme():
    text = README.decode("utf-8")
    run = fixtures.load("run_so101.json")
    assert run["source"]["sha256"] == sha256_hex(README)
    quotes = [p for p in walk_provenance(run) if p["type"] == "readme_quote"]
    assert len(quotes) == 7
    for p in quotes:
        start, end = p["span"]
        assert text[start:end] == p["quote"], p["quote"]
        assert text.count("\n", 0, start) + 1 == p["line_from"]
        assert p["doc_sha256"] == sha256_hex(README) and p["commit_sha"] == run["source"]["commit_sha"]
    assert "you will also have to buy a 12V 5A+ power supply instead of a 5V one" in text.split("\n")[72]


def test_so101_run_matches_the_plan():
    run = fixtures.load("run_so101.json")
    assert [b["bom_line_id"] for b in run["bom"]] == [f"b{i}" for i in range(1, 8)]
    assert run["provenance_counts"]["readme_quote"] == 7
    servo = {m["mesh"]: m["instances"] for m in run["view"]["parts"] if m["bom_line_id"] == "b1"}
    assert sum(servo.values()) == 6
    assert len([m for m in run["view"]["parts"] if m["bom_line_id"] == "b7"]) == 11
    cart = fixtures.load("cart_so101.json")
    assert {g["store_id"]: g["subtotal_usd"] for g in cart["stores"]} == {"wowrobo": 90.94, "geekworm": 17.0, "armdojo": 11.99, "amazon": 12.48}
    assert cart["total_usd"] == 132.41 <= cart["budget_usd"] == 160
    urdf = (FIXTURES_DIR.parents[1] / "frontend" / "public" / "so101" / "so101_new_calib.urdf")
    if urdf.exists():
        meshes = set(re.findall(r'filename="assets/([^"]+)\.stl"', urdf.read_text(encoding="utf-8")))
        assert meshes == {m["mesh"] for m in run["view"]["parts"]}
        assert all((urdf.parent / "assets" / f"{m}.stl").is_file() for m in meshes)


def test_drone_run_matches_the_plan():
    run = fixtures.load("run_drone.json")
    assert len(run["bom"]) >= 10 and run["view"]["kind"] == "procedural" and run["view"]["model"] == "quadcopter"
    types = [b["provenance"]["type"] for b in run["bom"]]
    assert types.count("assumption") == 1 and types.count("template_row") == len(types) - 1
    assert any(b["provenance"].get("basis") == "rule_of_thumb" for b in run["bom"])
    assert run["open_assumptions"] == ["b12"] and run["provenance_counts"] == {"readme_quote": 0, "reference_project": 0, "template_row": 11, "photo_region": 0, "assumption": 1}
    assert all(p["kb_ref"].startswith("kb://tpl_quadcopter#") for p in walk_provenance(run["bom"]) if p["type"] == "template_row")
    assert any(c["rule_id"].startswith("G7") and c["result"] == "warn" for c in run["checks"])
    cart = fixtures.load("cart_drone.json")
    assert cart["total_usd"] <= cart["budget_usd"] and cart["open_assumptions"] == ["b12"]


@pytest.mark.parametrize("key", ["so101", "drone"])
def test_sample_chain_recomputes(key):
    receipt = fixtures.load(f"receipt_{key}.json")
    ok, broken_at, head = recompute(receipt["records"])
    assert ok and broken_at is None and head == receipt["head_hash"]
    tampered = json.loads(json.dumps(receipt["records"]))
    tampered[2]["ts"] = "2026-11-20T00:00:00-08:00"
    ok, broken_at, _ = recompute(tampered)
    assert not ok and broken_at == 3


def test_closed_mandate_binds_plan_and_handoffs():
    closed = fixtures.load("closed_mandate_so101.json")
    cart = fixtures.load("cart_so101_approved.json")
    assert closed["total_usd"] == 132.41 and len(closed["handoffs"]) == 4
    for h, g in zip(closed["handoffs"], cart["stores"]):
        assert h["url_sha256"] == sha256_hex(h["url"]) == g["handoff"]["url_sha256"]
    assert {h["action_level"] for h in closed["handoffs"]} == {"agent_cart", "prefilled_cart"}


def test_photo_sample_boxes_are_inside_the_image():
    view = fixtures.load("view_photo_sample.json")
    photo = view["photo"]
    assert sha256_hex((FIXTURES_DIR / "uploads" / "img_mock1.jpg").read_bytes()) == photo["sha256"]
    for r in photo["regions"]:
        x1, y1, x2, y2 = r["box_xyxy_px"]
        assert 0 <= x1 < x2 <= photo["w"] and 0 <= y1 < y2 <= photo["h"] and r["score"] >= 0.35


def test_esp32_diagram_edges_join_existing_nodes():
    view = fixtures.load("view_diagram_esp32.json")
    ids = {n["id"] for n in view["diagram"]["nodes"]}
    assert len(ids) == 5 and all(e["from"] in ids and e["to"] in ids and e["rule_ids"] for e in view["edges"])
