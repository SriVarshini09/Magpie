"""The chat start page: contract tests for the chat endpoints, the hero flows in PIPELINE MODE with no key
(keyword router + scripted agent on mock services), and the guard rules.

Nothing here reaches the network. The Claude agent is exercised with a fake client: no key, no call.
"""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from test_integration_e2e import SO101_URL, ok, pipeline, sse_events  # noqa: F401  (pipeline is a fixture)

from app.models import ChatSendResponse, ChatSession, ChatSessionSummary, RunSummary

DRONE = "a small camera drone under $200"


@pytest.fixture(autouse=True)
def _fresh_sessions():
    from app.chat import service

    service.SESSIONS.clear()
    service.AGENT_OVERRIDE = None
    yield
    service.SESSIONS.clear()
    service.AGENT_OVERRIDE = None


def new(c) -> str:
    s = ok(c.post("/api/chat/sessions"))
    ChatSession.model_validate(s)
    return s["session_id"]


def say(c, sid: str, text: str | None = None, **form) -> dict:
    data = {k: v for k, v in {"text": text, **form}.items() if v is not None}
    r = ok(c.post(f"/api/chat/sessions/{sid}/messages", data=data))
    ChatSendResponse.model_validate(r)
    assert r["messages"][0]["role"] == "user" and r["messages"][-1]["role"] == "agent"
    return r


def blocks(r: dict) -> list[dict]:
    return r["messages"][-1]["blocks"]


def kinds(r: dict) -> list[str]:
    return [b["kind"] for b in blocks(r)]


def block(r: dict, kind: str) -> dict:
    hit = next((b for b in blocks(r) if b["kind"] == kind), None)
    assert hit is not None, f"no {kind} block in {kinds(r)}: {[b.get('text') for b in blocks(r)]}"
    return hit


def sign(c, sid: str, intake: dict, **over) -> dict:
    r = ok(c.post(f"/api/chat/sessions/{sid}/mandate", json=intake["mandate_preset"] | over))
    ChatSendResponse.model_validate(r)
    return r


def all_text(r: dict) -> str:
    return " ".join(b.get("text") or "" for b in blocks(r))


def no_junk(r: dict) -> None:
    assert "undefined" not in all_text(r) and "NaN" not in all_text(r) and "None" not in all_text(r)


# ---------------------------------------------------------------------------- contract (mock mode)


def test_chat_endpoints_contract_in_mock_mode(client):
    c = client
    s = ok(c.post("/api/chat/sessions", json={"reference_search": False}))
    ChatSession.model_validate(s)
    assert s["agent"] == "keyword" and s["agent_label"] == "Keyword assistant (no AI key)" and s["reference_search"] is False
    sid = s["session_id"]
    assert ok(c.get("/api/chat/sessions")) == [], "an untouched session is not listed"
    assert c.get("/api/chat/sessions/c_nope").status_code == 404
    assert c.post("/api/chat/sessions/c_nope/messages", data={"text": "hi"}).status_code == 404
    assert c.post(f"/api/chat/sessions/{sid}/messages", data={"text": "   "}).status_code == 422
    assert c.post(f"/api/chat/sessions/{sid}/messages", data={"link": "ftp://x"}).status_code == 422
    assert c.post(f"/api/chat/sessions/{sid}/mandate", json={"budget_usd": 1, "deadline": "2026-12-04", "allowed_merchants": ["amazon"],
                                                              "data_sharing": {}}).status_code == 409, "nothing to sign yet"

    r = say(c, sid, DRONE)
    assert kinds(r) == ["build_type", "questions", "mandate"]
    it = block(r, "build_type")["intake"]
    assert it["build_type"] == "quadcopter" and block(r, "mandate")["intake"]["mandate_preset"]["budget_usd"] > 0
    listed = ok(c.get("/api/chat/sessions"))
    [ChatSessionSummary.model_validate(x) for x in listed]
    assert [x["title"] for x in listed] == [DRONE] and listed[0]["message_count"] == 2

    r = sign(c, sid, it)
    assert kinds(r)[:2] == ["text", "progress"] and {"parts", "cart"} <= set(kinds(r)), "the mock run is already finished: its summary follows"
    assert block(r, "cart")["simulated"] is True and block(r, "parts")["simulated"] is True and "mock mode" in all_text(r)
    rid = block(r, "progress")["run_id"]
    assert [a["href"] for a in block(r, "cart")["actions"] if a["kind"] == "link"] == [f"/run/{rid}", f"/run/{rid}/cart"]

    r = say(c, sid, "make it cheaper")
    assert "mock mode" in block(r, "cart")["text"], "mock edits say that the sample data does not change"
    r = say(c, sid, "approve it")
    assert block(r, "refusal")["refusal"]["rule"] == "approval_required"
    full = ok(c.get(f"/api/chat/sessions/{sid}"))
    ChatSession.model_validate(full)
    assert full["run_id"] == rid and full["status"] and len(full["messages"]) == 7 and full["simulated"] is True

    runs = ok(c.get("/api/runs"))
    [RunSummary.model_validate(x) for x in runs]
    assert {x["run_id"] for x in runs} >= {rid} and all(x["simulated"] for x in runs)


# ---------------------------------------------------------------------------- hero 1: the drone, by chat


def test_drone_by_chat_request_to_refused_approval(pipeline):
    c = pipeline
    sid = new(c)
    r = say(c, sid, DRONE)
    assert kinds(r) == ["build_type", "questions", "mandate"] and r["agent"] == "keyword"
    it = block(r, "build_type")["intake"]
    assert it["build_type"] == "quadcopter" and round(it["confidence"] * 100) == 70 and len(it["questions"]) == 3

    r = say(c, sid, "5 inch")  # a typed answer to a chip question
    it = block(r, "questions")["intake"]
    assert {q["id"]: q["answer"] for q in it["questions"]}["size_class"] == "5in"
    r = say(c, sid, "Have a soldering iron? No")  # a chip tap sends the question and the label
    it = block(r, "mandate")["intake"]
    assert {q["id"]: q["answer"] for q in it["questions"]} == {"size_class": "5in", "own_radio": None, "own_soldering_iron": "no"}

    r = sign(c, sid, it)
    assert "Mandate signed" in blocks(r)[0]["text"] and "can't check out or pay" in blocks(r)[0]["text"]
    rid = block(r, "progress")["run_id"]
    state = ok(c.get(f"/api/runs/{rid}"))
    assert state["status"] == "waiting_approval" and state["mandate"]["scope"]["reference_search"] is True
    parts = block(r, "parts")["parts"]
    assert len(parts) == len([ln for ln in state["bom"] if ln["status"] != "removed"])
    assert all(p["provenance"]["type"] for p in parts), "every line carries its provenance"
    priced = [p for p in parts if p["line_usd"] is not None]
    assert priced and all(p["store_name"] and p["action_level"] and p["simulated"] is True for p in priced)
    assert any(p["more_stores"] > 0 for p in parts), "the '+N stores' count comes from the offers found"
    cart = block(r, "cart")["cart"]
    assert cart["total_usd"] == ok(c.get(f"/api/runs/{rid}/cart"))["total_usd"] and cart["state"] == "draft" and cart["simulated"] is True
    assert cart["open_assumptions"] == state["open_assumptions"] and cart["stores"]
    types = {e["type"] for e in sse_events(c, rid)}
    assert {"bom.line", "offers.found", "plan.ready", "run.waiting_approval"} <= types, "the progress block reads the run's own SSE stream"
    no_junk(r)

    # refine: tier, owned, why, and the budget rule
    before = cart["total_usd"]
    r = say(c, sid, "make it cheaper")
    assert block(r, "cart")["cart"]["tier"] == "cheapest" and ok(c.get(f"/api/runs/{rid}"))["active_tier"] == "cheapest"
    r = say(c, sid, "fewest stores")
    assert block(r, "cart")["cart"]["tier"] == "fewest_checkouts" and ok(c.get(f"/api/runs/{rid}"))["active_tier"] == "fewest_checkouts"

    battery = next(ln for ln in state["bom"] if "battery" in ln["raw_name"].lower() and ln["status"] == "chosen")
    r = say(c, sid, "I already have a battery")
    after = ok(c.get(f"/api/runs/{rid}"))
    line = next(ln for ln in after["bom"] if ln["bom_line_id"] == battery["bom_line_id"])
    assert line["status"] == "owned" and battery["raw_name"] in blocks(r)[0]["text"]
    cart2 = block(r, "cart")["cart"]
    assert cart2["total_usd"] < before and cart2["previous_total_usd"] is not None
    assert any(x["bom_line_id"] == battery["bom_line_id"] and x["reason"] == "owned" for x in cart2["left_out"])
    assert any(e["type"] == "memory.written" or e["type"] == "owned.matched" for e in sse_events(c, rid)), "owned is remembered through the existing path"

    esc = next(ln for ln in state["bom"] if ln["raw_name"].lower().startswith("esc"))
    r = say(c, sid, "why this ESC?")
    why = block(r, "why")
    assert why["panel"]["bom_line_id"] == esc["bom_line_id"] and why["text"] and why["panel"]["why"]["explanation"] in why["text"]

    r = say(c, sid, "what's left to confirm?")
    assume = block(r, "assumptions")
    assert [a["bom_line_id"] for a in assume["assumptions"]] == after["open_assumptions"] and "can't confirm my own" in assume["text"]
    assert ok(c.get(f"/api/runs/{rid}"))["open_assumptions"] == after["open_assumptions"], "asking confirms nothing"

    # "approve it" approves nothing: refused, logged, and the cart is still a draft
    refusals_before = ok(c.get(f"/api/runs/{rid}"))["refusals"]
    r = say(c, sid, "approve it")
    ref = block(r, "refusal")
    assert ref["refusal"]["rule"] == "approval_required" and ref["refusal"]["triggered_by"] == "user_chat" and "Approve" in ref["text"]
    assert [a["href"] for a in ref["actions"]] == [f"/run/{rid}/cart"]
    st = ok(c.get(f"/api/runs/{rid}"))
    assert st["refusals"] == refusals_before + 1 and st["status"] == "waiting_approval"
    assert ok(c.get(f"/api/runs/{rid}/cart"))["state"] == "draft"
    receipt = ok(c.get(f"/api/runs/{rid}/receipt"))
    assert not any(rec["kind"] in ("approval", "mandate_closed") for rec in receipt["records"])
    assert any(rec["kind"] == "refusal" and "approval_required" in str(rec) for rec in receipt["records"]), "logged as a refusal record"

    # the person's own button still works: Confirm on the assumption card
    r = ok(c.post(f"/api/chat/sessions/{sid}/assumptions", json={"bom_line_id": after["open_assumptions"][0], "action": "confirm"}))
    assert "Confirmed by you" in r["messages"][-1]["blocks"][0]["text"] and ok(c.get(f"/api/runs/{rid}"))["open_assumptions"] == after["open_assumptions"][1:]


def test_drone_variant_and_budget_by_chat(pipeline):
    c = pipeline
    sid = new(c)
    it = block(say(c, sid, DRONE), "mandate")["intake"]
    r = sign(c, sid, it)
    rid = block(r, "progress")["run_id"]
    assert ok(c.get(f"/api/runs/{rid}"))["template"]["variant"] != "5in"

    r = say(c, sid, "make it 5-inch")  # re-answers the chip and re-runs
    assert kinds(r)[0] == "progress" and {"parts", "cart"} <= set(kinds(r)), "the re-run finished inline, so its summary follows"
    from app import runstate

    assert runstate.get(rid).answers["size_class"] == "5in"

    r = say(c, sid, "budget $250")  # above the signed $200: refused, and only a new signed mandate can raise it
    assert block(r, "refusal")["refusal"]["rule"] == "budget" and "new signed mandate" in block(r, "refusal")["text"]
    form = block(r, "mandate")
    assert form["intake"]["mandate_preset"]["budget_usd"] == 250 and "new run" in form["text"]
    assert ok(c.get(f"/api/runs/{rid}"))["mandate"]["constraints"]["budget_usd"] == 200, "chat did not widen the mandate"

    r = say(c, sid, "budget $150")  # tightening is inside the mandate
    assert "refusal" not in kinds(r) and block(r, "cart")["cart"]["budget_usd"] == 200

    # signing the form is the only way: a new run, under a new mandate
    r = ok(c.post(f"/api/chat/sessions/{sid}/mandate", json=form["intake"]["mandate_preset"]))
    rid2 = r["session"]["run_id"]
    assert rid2 != rid and ok(c.get(f"/api/runs/{rid2}"))["mandate"]["constraints"]["budget_usd"] == 250
    assert "new run under the new mandate" in r["messages"][-1]["blocks"][0]["text"]


# ---------------------------------------------------------------------------- hero 2: the SO-101 link, by chat


def test_so101_link_by_chat_quotes_and_comparison(pipeline):
    c = pipeline
    sid = new(c)
    r = say(c, sid, link=SO101_URL)
    assert r["messages"][0]["link"] == SO101_URL and block(r, "build_type")["intake"]["build_type"] == "robot_arm"
    assert ok(c.get("/api/chat/sessions"))[0]["title"] == "TheRobotStudio/SO-ARM100"
    r = say(c, sid, "12V")
    it = block(r, "mandate")["intake"]
    assert {q["id"]: q["answer"] for q in it["questions"]}["voltage_class"] == "12v"
    r = sign(c, sid, it)
    rid = block(r, "progress")["run_id"]
    parts = block(r, "parts")["parts"]
    quoted = [p for p in parts if p["provenance"]["type"] == "readme_quote"]
    assert len(quoted) >= 5 and all(p["provenance"]["quote"] for p in quoted), "parts quoted from the README"
    assert "refused under your mandate" in all_text(r)

    r = say(c, sid, "show me other servos")
    cmp_ = block(r, "comparison")
    servo = next(p for p in parts if "servo" in p["name"].lower())
    panel = cmp_["panel"]
    assert panel["bom_line_id"] == servo["bom_line_id"] and panel == ok(c.get(f"/api/runs/{rid}/parts/{servo['bom_line_id']}")), "the part panel's own data"
    statuses = {o["status"] for o in panel["offers"]}
    assert "chosen" in statuses and len(panel["offers"]) > 1
    assert all(o["reason"] for o in panel["offers"] if o["status"] in ("rejected", "refused")), "rejected and refused rows carry their reason"
    assert all(o["simulated"] and o["source_api"] == "mock" for o in panel["offers"]), "mock offers stay labelled"
    no_junk(r)

    # a cart edit through the existing edit + replan path
    alt = next((o for o in panel["offers"] if o["status"] == "alternative"), None)
    r = say(c, sid, "swap the servos")
    if alt is None:
        assert "no other acceptable offer" in all_text(r)
    else:
        assert "Swapped the offer" in block(r, "cart")["text"]
        events = sse_events(c, rid)
        assert any(e["type"] == "cart.edited" for e in events)
    r = say(c, sid, "use alibaba for the servos")  # a store outside the mandate
    assert block(r, "refusal")["refusal"]["rule"] == "merchant_allowed" and "mandate" in kinds(r)
    assert "alibaba.com" not in ok(c.get(f"/api/runs/{rid}"))["mandate"]["constraints"]["allowed_merchants"]


def test_move_store_by_chat_uses_the_cart_edit_path(pipeline):
    c = pipeline
    sid = new(c)
    it = block(say(c, sid, DRONE), "mandate")["intake"]
    r = sign(c, sid, it)
    rid = block(r, "progress")["run_id"]
    state = ok(c.get(f"/api/runs/{rid}"))
    motor = next(ln for ln in state["bom"] if "motor" in ln["raw_name"].lower())
    panel = ok(c.get(f"/api/runs/{rid}/parts/{motor['bom_line_id']}"))
    other = next((o["store_id"] for o in panel["offers"] if o["status"] == "alternative" and o["store_id"] != motor["chosen"][0]["store_id"]), None)
    target = other or "amazon"
    r = say(c, sid, f"use {target} for the motors")
    if other:
        now = next(ln for ln in ok(c.get(f"/api/runs/{rid}"))["bom"] if ln["bom_line_id"] == motor["bom_line_id"])
        assert {ch["store_id"] for ch in now["chosen"]} == {other} and "Moved" in block(r, "cart")["text"]
        assert any(e["type"] == "cart.edited" for e in sse_events(c, rid))
    else:
        assert "no acceptable offer" in all_text(r), "a store with nothing acceptable is said plainly, not faked"


# ---------------------------------------------------------------------------- photo


def test_photo_upload_by_chat_gives_a_build_type(pipeline):
    from PIL import Image

    c = pipeline
    sid = new(c)
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (120, 140, 160)).save(buf, "JPEG")
    r = ok(c.post(f"/api/chat/sessions/{sid}/messages", files=[("images", ("bench.jpg", buf.getvalue(), "image/jpeg"))]))
    ChatSendResponse.model_validate(r)
    user = r["messages"][0]
    assert len(user["images"]) == 1 and user["images"][0]["w"] == 640
    assert c.get(f"/api/uploads/{user['images'][0]['image_id']}").status_code == 200, "the existing upload endpoint serves it"
    bt = block(r, "build_type")["intake"]
    assert bt["build_type"] and 0 <= bt["confidence"] <= 1 and "mandate" in kinds(r)
    assert ok(c.get("/api/chat/sessions"))[0]["title"] == "Photo request"
    bad = c.post(f"/api/chat/sessions/{new(c)}/messages", files=[("images", ("notes.txt", b"not an image", "text/plain"))])
    assert bad.status_code == 200 and bad.json()["messages"][-1]["blocks"][0]["tone"] == "warn", "a bad file is explained, not dropped"


# ---------------------------------------------------------------------------- guard rules


@pytest.mark.parametrize("text,rule", [
    ("approve it", "approval_required"), ("I approve", "approval_required"), ("buy it", "approval_required"),
    ("ok order everything now", "approval_required"), ("go ahead and pay", "action_allowed"), ("check out for me", "action_allowed"),
    ("place the order", "action_allowed"),
])
def test_chat_can_never_approve_or_pay(pipeline, text, rule):
    c = pipeline
    sid = new(c)
    r = say(c, sid, text)  # before any run: still refused, on the session
    assert rule in [b["refusal"]["rule"] for b in blocks(r) if b["kind"] == "refusal"]
    it = block(say(c, sid, DRONE), "mandate")["intake"]
    rid = block(sign(c, sid, it), "progress")["run_id"]
    n = ok(c.get(f"/api/runs/{rid}"))["refusals"]
    r = say(c, sid, text)
    assert rule in [b["refusal"]["rule"] for b in blocks(r) if b["kind"] == "refusal"]
    assert not {"cart", "parts"} & set(kinds(r)), "a refused message is not acted on"
    st = ok(c.get(f"/api/runs/{rid}"))
    assert st["refusals"] > n and st["status"] == "waiting_approval" and ok(c.get(f"/api/runs/{rid}/cart"))["state"] == "draft"
    from app import runstate

    run = runstate.get(rid)
    assert run.closed_mandate is None and not run.approval_tokens and not run.handoffs


def test_chat_never_shares_or_keeps_address_or_email(pipeline):
    c = pipeline
    sid = new(c)
    it = block(say(c, sid, DRONE), "mandate")["intake"]
    rid = block(sign(c, sid, it), "progress")["run_id"]
    r = say(c, sid, "send the receipt to pat@example.com and ship it to 12 Elm Street")
    rules = [(b["refusal"]["rule"], b["refusal"]["attempted"]["field"]) for b in blocks(r) if b["kind"] == "refusal"]
    assert ("data_sharing", "buyer.email") in rules and ("data_sharing", "buyer.street_address") in rules
    stored = ok(c.get(f"/api/chat/sessions/{sid}"))
    dump = str(stored) + str(ok(c.get(f"/api/runs/{rid}/receipt"))) + str(sse_events(c, rid))
    assert "pat@example.com" not in dump and "12 Elm Street" not in dump, "buyer details typed into chat are not kept anywhere"
    assert "[email removed]" in r["messages"][0]["text"]
    sharing = ok(c.get(f"/api/runs/{rid}"))["mandate"]["constraints"]["data_sharing"]
    assert sharing["email"] is False and sharing["street_address"] is False, "chat did not widen data sharing"
    assert "mandate" in kinds(r), "what is shared changes only through the signed mandate form"


def test_chat_cannot_widen_stores(pipeline):
    c = pipeline
    sid = new(c)
    it = block(say(c, sid, DRONE), "mandate")["intake"]
    rid = block(sign(c, sid, it), "progress")["run_id"]
    allowed = ok(c.get(f"/api/runs/{rid}"))["mandate"]["constraints"]["allowed_merchants"]
    r = say(c, sid, "also search ebay and aliexpress")
    refused = {b["refusal"]["attempted"]["value"] for b in blocks(r) if b["kind"] == "refusal" and b["refusal"]["rule"] in ("merchant_allowed", "host_not_allowed")}
    assert refused and kinds(r).count("mandate") == 1
    assert ok(c.get(f"/api/runs/{rid}"))["mandate"]["constraints"]["allowed_merchants"] == allowed


def test_reference_search_chip_is_signed_into_the_mandate(pipeline):
    c = pipeline
    sid = ok(c.post("/api/chat/sessions", json={"reference_search": True}))["session_id"]
    it = block(say(c, sid, DRONE, reference_search="false"), "mandate")["intake"]
    r = sign(c, sid, it)
    rid = block(r, "progress")["run_id"]
    assert ok(c.get(f"/api/runs/{rid}"))["mandate"]["scope"]["reference_search"] is False and "no reference search" in blocks(r)[0]["text"]
    assert not any(e["type"] in ("reference.found", "reference.searched") for e in sse_events(c, rid))


def test_sync_posts_the_summary_once(pipeline):
    from app.chat import service

    c = pipeline
    sid = new(c)
    it = block(say(c, sid, DRONE), "mandate")["intake"]
    sign(c, sid, it)
    assert ok(c.post(f"/api/chat/sessions/{sid}/sync"))["messages"] == [], "the inline run was already summarised"
    service.SESSIONS[sid].data.awaiting_summary = True  # as when the run was still going at sign time
    r = ok(c.post(f"/api/chat/sessions/{sid}/sync"))
    assert {"parts", "cart"} <= {b["kind"] for b in r["messages"][-1]["blocks"]} and r["awaiting_summary"] is False
    assert ok(c.post(f"/api/chat/sessions/{sid}/sync"))["messages"] == []


# ---------------------------------------------------------------------------- the Claude agent (fake client, no network)


class FakeClient:
    """Stands in for AsyncAnthropic: `.beta.messages.create(**kwargs)` pops scripted responses."""

    def __init__(self, script: list) -> None:
        self.script, self.calls = list(script), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


def _resp(stop: str, *content):
    return SimpleNamespace(stop_reason=stop, content=list(content), usage=SimpleNamespace(input_tokens=1, output_tokens=1), model="claude-sonnet-5-5",
                           stop_details=SimpleNamespace(category="cyber", explanation=None) if stop == "refusal" else None)


def _use(name: str, **inp):
    return SimpleNamespace(type="tool_use", id=f"tu_{name}", name=name, input=inp)


def _text(t: str):
    return SimpleNamespace(type="text", text=t)


def _claude(script: list):
    from app.chat import service
    from app.chat.claude_agent import ClaudeAgent
    from app.integrations.anthropic_client import LiveLLM

    fake = FakeClient(script)
    service.AGENT_OVERRIDE = ClaudeAgent(LiveLLM(client=fake))
    return fake


def test_claude_agent_tools_are_strict_and_cannot_approve_or_pay():
    from app.chat.claude_agent import TOOLS

    names = {t["name"] for t in TOOLS}
    assert not {n for n in names if any(w in n for w in ("approve", "pay", "checkout", "sign", "confirm", "share"))}
    for t in TOOLS:
        schema = t["input_schema"]
        assert t["strict"] is True and schema["additionalProperties"] is False and sorted(schema["required"]) == sorted(schema["properties"])


def test_claude_agent_maps_tool_calls_to_the_same_blocks(pipeline):
    c = pipeline
    fake = _claude([
        _resp("tool_use", _use("read_request")),
        _resp("end_turn", _text("I read this as a quadcopter. Answer the questions, then sign the mandate.")),
        _resp("tool_use", _use("switch_tier", tier="fewest_checkouts"), _use("explain_choice", bom_line_id="b1")),
        _resp("end_turn", _text("Fewest checkouts is active.")),
        _resp("tool_use", _use("approve_cart")),  # a tool that does not exist: an error result, nothing happens
        _resp("end_turn", _text("I can't approve a cart. Use the Approve cart button.")),
        _resp("refusal"),
    ])
    sid = new(c)
    r = say(c, sid, DRONE)
    assert r["agent"] == "claude" and r["agent_label"].startswith("Claude (") and r["messages"][-1]["agent"] == "claude"
    assert kinds(r) == ["text", "build_type", "questions", "mandate"]
    first = fake.calls[0]
    assert first["model"] == "claude-sonnet-5-5" and "tool_choice" not in first and "temperature" not in first and "thinking" not in first
    assert first["fallbacks"] == "default" and first["betas"] == ["server-side-fallback-2026-07-01"]
    assert all(t["strict"] for t in first["tools"]) and first["messages"][-1]["role"] == "user" and "<state>" in first["messages"][-1]["content"]
    assert fake.calls[1]["messages"][-1]["content"][0]["type"] == "tool_result"

    rid = block(sign(c, sid, block(r, "mandate")["intake"]), "progress")["run_id"]
    r = say(c, sid, "fewer stores please, and why that frame?")
    assert kinds(r) == ["text", "cart", "why"] and ok(c.get(f"/api/runs/{rid}"))["active_tier"] == "fewest_checkouts"
    assert len(fake.calls[3]["messages"][-1]["content"]) == 2, "both tool results go back in one user message"

    r = say(c, sid, "do the thing")
    assert kinds(r) == ["text"] and fake.calls[5]["messages"][-1]["content"][0]["is_error"] is True
    assert ok(c.get(f"/api/runs/{rid}/cart"))["state"] == "draft"

    n = len(fake.calls)
    r = say(c, sid, "approve it")  # the guard runs in code first: Claude is never asked
    assert block(r, "refusal")["refusal"]["rule"] == "approval_required" and len(fake.calls) == n

    r = say(c, sid, "show the cart")  # Claude declines (stop_reason refusal): the keyword router answers this one
    assert r["messages"][-1]["agent"] == "keyword" and "cart" in kinds(r) and "keyword assistant answered" in all_text(r)
