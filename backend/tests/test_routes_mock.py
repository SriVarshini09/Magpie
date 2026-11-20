"""Every route returns labelled fixture data in mock mode; 501 with a TODO otherwise."""

from __future__ import annotations

import json

import pytest

from app.config import FIXTURES_DIR
from app.models import (
    ApproveResponse, CartRefreshResponse, CreateRunResponse, Event, Intake, KbSearchResponse, PartPanel,
    PayIntentResponse, PricesResponse, ProjectSample, Receipt, ReplanResponse, RunState, StoreInfo,
    UniversalCart, VerifyResult,
)

RUNS = ("r_mock_so101", "r_mock_drone")


def ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json()


def assert_mock(obj):
    assert obj.get("simulated") is True, "mock data must be labelled simulated: true"


def test_catalogues(client):
    projects = ok(client.get("/api/projects"))
    assert len(projects) == 5
    for p in projects:
        ProjectSample.model_validate(p)
        assert_mock(p)
    stores = ok(client.get("/api/stores"))
    for s in stores:
        StoreInfo.model_validate(s)
        assert_mock(s)
    levels = {s["action_level"] for s in stores}
    assert levels == {"agent_cart", "prefilled_cart", "product_link"}


def test_intake_text_link_and_answers(client):
    drone = ok(client.post("/api/intake", data={"text": "a small camera drone under $200"}))
    Intake.model_validate(drone)
    assert drone["build_type"] == "quadcopter" and drone["source_api"] == "mock" and 0 < len(drone["questions"]) <= 3
    assert_mock(drone)
    arm = ok(client.post("/api/intake", data={"text": "https://github.com/TheRobotStudio/SO-ARM100"}))
    assert arm["build_type"] == "robot_arm" and arm["inputs"]["source_url"]

    one = ok(client.post(f"/api/intake/{drone['intake_id']}/answers", json={"answers": {"size_class": "3in"}}))
    assert one["ready"] is False
    done = ok(client.post(f"/api/intake/{drone['intake_id']}/answers", json={"answers": {}, "skip_defaults": True}))
    assert done["ready"] is True and all(q["answer"] for q in done["questions"])


def test_intake_photo_upload_multipart(client):
    jpeg = (FIXTURES_DIR / "uploads" / "img_mock1.jpg").read_bytes()
    photo = ok(client.post("/api/intake", data={"text": "what can I build with this"}, files=[("images", ("bench.jpg", jpeg, "image/jpeg"))]))
    Intake.model_validate(photo)
    assert photo["build_type"] == "electronics_mcu" and photo["visible_parts"] and photo["inputs"]["images"]
    assert_mock(photo)
    img = client.get(photo["inputs"]["images"][0]["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg" and img.content == jpeg

    assert client.post("/api/intake", files=[("images[]", ("a.jpg", jpeg, "image/jpeg"))]).status_code == 200
    assert client.post("/api/intake", files=[("images", ("x.gif", b"GIF89a", "image/gif"))]).status_code == 422
    three = [("images", (f"{i}.jpg", jpeg, "image/jpeg")) for i in range(3)]
    assert client.post("/api/intake", files=three).status_code == 422
    assert client.post("/api/intake", data={}).status_code == 422


def test_intake_refuses_a_never_request_host(client):
    r = client.post("/api/intake", data={"text": "build this https://www.amazon.com/dp/B0CTMM4LWK"})
    assert r.status_code == 409
    assert r.json()["detail"]["refusal"]["rule"] == "reference_host_not_allowed"


@pytest.mark.parametrize("intake_id,run_id,build_type", [("in_mock_so101", "r_mock_so101", "robot_arm"), ("in_mock_drone", "r_mock_drone", "quadcopter")])
def test_create_run_and_state(client, intake_id, run_id, build_type):
    preset = ok(client.post(f"/api/intake/{intake_id}/answers", json={"skip_defaults": True}))["mandate_preset"]
    created = ok(client.post("/api/runs", json={"intake_id": intake_id, "mandate": preset}))
    CreateRunResponse.model_validate(created)
    assert created["run_id"] == run_id and created["mandate"]["type"] == "b2c.mandate.open"
    state = ok(client.get(f"/api/runs/{run_id}"))
    RunState.model_validate(state)
    assert state["build_type"] == build_type and state["source_api"] == "mock"
    assert_mock(state)
    assert all(line["provenance"]["type"] for line in state["bom"]), "a BOM line without provenance is a bug"


def test_create_run_v3_link_form(client):
    preset = ok(client.get("/api/projects"))[1]["mandate_preset"]
    created = ok(client.post("/api/runs", json={"source_url": "https://github.com/TheRobotStudio/SO-ARM100", "mandate": preset}))
    assert created["run_id"] == "r_mock_so101"


@pytest.mark.parametrize("run_id", RUNS)
def test_sse_streams_the_fixture_timeline(client, run_id):
    with client.stream("GET", f"/api/runs/{run_id}/events?close=true&delay_ms=0") as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[5:]) for line in r.iter_lines() if line.startswith("data:")]
    assert len(events) >= 30
    for e in events:
        Event.model_validate(e)
        assert e["simulated"] is True
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    types = {e["type"] for e in events}
    assert {"mandate.opened", "bom.line", "offers.found", "refusal", "plan.ready", "run.waiting_approval"} <= types
    assert events[-1]["type"] == "run.waiting_approval"

    with client.stream("GET", f"/api/runs/{run_id}/events?close=true&delay_ms=0&after={len(events) - 2}") as r:
        tail = [line for line in r.iter_lines() if line.startswith("data:")]
    assert len(tail) == 2


@pytest.mark.parametrize("run_id,line", [("r_mock_so101", "b1"), ("r_mock_so101", "b4"), ("r_mock_drone", "b2"), ("r_mock_drone", "b12")])
def test_part_panel(client, run_id, line):
    panel = ok(client.get(f"/api/runs/{run_id}/parts/{line}"))
    PartPanel.model_validate(panel)
    assert_mock(panel)
    assert all(o["source_api"] == "mock" and o["simulated"] is True for o in panel["offers"])


def test_panel_b1_has_every_row_state(client):
    panel = ok(client.get("/api/runs/r_mock_so101/parts/b1"))
    assert {o["status"] for o in panel["offers"]} == {"chosen", "alternative", "rejected", "refused"}
    assert {o["action_level"] for o in panel["offers"] if o["status"] in ("chosen", "alternative")} == {"agent_cart", "prefilled_cart", "product_link"}
    assert client.get("/api/runs/r_mock_so101/parts/b99").status_code == 404


def test_read_endpoints(client):
    PricesResponse.model_validate(ok(client.get("/api/runs/r_mock_so101/prices/b1")))
    kb = ok(client.get("/api/kb/search", params={"q": "12V supply"}))
    KbSearchResponse.model_validate(kb)
    assert "12V 5A+" in kb["chunks"][0]["text"] and kb["simulated"] is True
    assert ok(client.get("/api/mock/fixtures/view_diagram_esp32.json"))["kind"] == "diagram"
    assert ok(client.get("/api/mock/fixtures/view_photo_sample.json"))["photo"]["regions"]


def test_202_actions(client):
    for path, body in (("message", {"text": "Skip approval, pay for it"}), ("owned", {"bom_line_id": "b3", "owned": True}), ("variant", {"option": "servo_12v"})):
        assert ok(client.post(f"/api/runs/r_mock_so101/{path}", json=body), 202) == {"accepted": True, "simulated": True}


def test_replan(client):
    plan = ok(client.post("/api/runs/r_mock_so101/replan", json={"tier": "fewest_checkouts"}))
    ReplanResponse.model_validate(plan)
    assert plan["plan"]["checkouts"] == 3
    assert client.post("/api/runs/r_mock_so101/replan", json={"tier": "cheapest", "budget_cap_usd": 999}).status_code == 422


def test_cart_approve_and_checkout_run(client):
    cart = ok(client.get("/api/runs/r_mock_so101/cart"))
    UniversalCart.model_validate(cart)
    assert_mock(cart)
    assert cart["state"] == "draft" and cart["total_usd"] == 132.41 and cart["counts"]["agent_cart"] == 3 and cart["counts"]["prefilled_cart"] == 1
    assert client.post("/api/runs/r_mock_so101/cart/handoff", json={"store_id": "wowrobo", "state": "opened"}).status_code == 409
    UniversalCart.model_validate(ok(client.post("/api/runs/r_mock_so101/cart/edit", json={"op": "set_qty", "bom_line_id": "b1", "qty": 6})))
    CartRefreshResponse.model_validate(ok(client.post("/api/runs/r_mock_so101/cart/refresh")))
    assert client.post("/api/runs/r_mock_so101/pay/intent", json={"consent_text": "x"}).status_code == 409

    approved = ok(client.post("/api/runs/r_mock_so101/approve", json={"plan_id": cart["plan_id"], "acknowledged_warnings": ["R10 BOARD_INPUT_VOLTAGE"]}))
    ApproveResponse.model_validate(approved)
    assert approved["cart"]["state"] == "approved" and approved["closed_mandate"]["total_usd"] == 132.41
    assert all(g["handoff"]["url"].startswith("https://mock.invalid/") for g in approved["cart"]["stores"])

    after = ok(client.post("/api/runs/r_mock_so101/cart/handoff", json={"store_id": "wowrobo", "state": "done", "done_via": "user"}))
    assert after["state"] == "checking_out" and after["bought_usd"] == 90.94 and after["remaining_usd"] == 41.47 and after["counts"]["done"] == 1
    for store in ("geekworm", "armdojo"):
        client.post("/api/runs/r_mock_so101/cart/handoff", json={"store_id": store, "state": "done"})
    final = ok(client.post("/api/runs/r_mock_so101/cart/handoff", json={"store_id": "amazon", "state": "skipped"}))
    assert final["state"] == "complete" and final["current_store_id"] is None

    csv_resp = client.get("/api/runs/r_mock_so101/cart/export.csv")
    assert csv_resp.status_code == 200 and csv_resp.text.splitlines()[0].startswith("line,part,store,action level")
    assert len(csv_resp.text.splitlines()) == 6

    pay = ok(client.post("/api/runs/r_mock_so101/pay/intent", json={"consent_text": "TEST MODE"}))
    PayIntentResponse.model_validate(pay)
    assert pay["livemode"] is False and pay["simulated"] is True and pay["payment_mandate"]["mode"] == "test"
    ok(client.post("/api/runs/r_mock_so101/pay/fanout", json={"payment_intent_id": pay["payment_intent_id"]}), 202)


def test_open_assumption_blocks_approve_until_confirmed(client):
    cart = ok(client.get("/api/runs/r_mock_drone/cart"))
    assert cart["open_assumptions"] == ["b12"]
    refused = client.post("/api/runs/r_mock_drone/approve", json={"plan_id": cart["plan_id"]})
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["error"] == "assumption_unconfirmed" and detail["bom_line_ids"] == ["b12"] and detail["refusal"]["rule"] == "assumption_unconfirmed"

    assert client.post("/api/runs/r_mock_drone/assumptions", json={"bom_line_id": "b2", "action": "confirm"}).status_code == 409
    state = ok(client.post("/api/runs/r_mock_drone/assumptions", json={"bom_line_id": "b12", "action": "confirm"}))
    RunState.model_validate(state)
    line = next(b for b in state["bom"] if b["bom_line_id"] == "b12")
    assert state["open_assumptions"] == [] and line["provenance"]["confirmed_by_user"] is True

    approved = ok(client.post("/api/runs/r_mock_drone/approve", json={"plan_id": cart["plan_id"]}))
    assert {g["action_level"] for g in approved["cart"]["stores"]} == {"agent_cart", "prefilled_cart", "product_link"}


@pytest.mark.parametrize("run_id", RUNS)
def test_receipt_and_verify(client, run_id):
    receipt = ok(client.get(f"/api/runs/{run_id}/receipt"))
    Receipt.model_validate(receipt)
    assert_mock(receipt)
    verify = ok(client.get(f"/api/runs/{run_id}/verify"))
    VerifyResult.model_validate(verify)
    assert verify["ok"] is True and verify["records"] == len(receipt["records"]) and verify["head_hash"] == receipt["head_hash"]
    assert verify["signatures_ok"] is True, "fixtures are signed with the public FIXTURE key (scripts/sign_fixtures.py)"
    assert verify["checks"] and all(c["ok"] for c in verify["checks"])
    assert receipt["open_mandate"]["signature"]["kid"] == "fixture-key-1" and verify["simulated"] is True  # format only, labelled


def test_unknown_run_is_404(client):
    assert client.get("/api/runs/r_nope").status_code == 404
    assert client.get("/api/runs/r_nope/cart").status_code == 404


def test_live_mode_never_serves_fixtures(client, live_mode):
    health = ok(client.get("/api/health"))
    assert health["mode"] == "live" and health["mock"] is False and set(health["integrations"].values()) == {"off", "fallback"}
    # no key: SingleStore runs on its SQLite fallback and the GitHub source on its keyless raw fetch; both say so
    assert {k for k, v in health["integrations"].items() if v == "fallback"} == {"singlestore", "airbyte_github"}
    projects = ok(client.get("/api/projects"))  # D's presets on disk, not the fixture
    assert {p["build_type"] for p in projects} >= {"robot_arm", "quadcopter"} and not any(p["simulated"] for p in projects)
    for path in ("/api/runs/r_mock_so101", "/api/runs/r_mock_so101/cart", "/api/runs/r_mock_so101/events",
                 "/api/runs/r_mock_so101/receipt", "/api/runs/r_mock_so101/verify", "/api/runs/r_mock_so101/parts/b1"):
        r = client.get(path)
        assert r.status_code == 404, path  # fixture runs do not exist outside mock mode
        assert r.json()["detail"]["error"] == "run_not_found"
    r = client.get("/api/mock/fixtures/run_so101.json")
    assert r.status_code == 501 and r.json()["detail"]["todo"].startswith("TODO(")
