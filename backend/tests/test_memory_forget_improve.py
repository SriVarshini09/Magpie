"""Memory the user can see, teach and wipe (PLAN §3.15): GET /api/memory, POST /api/memory/forget, facts written
only from the user's decisions, one improve pass after approval, and preferences that never widen a mandate.

Nothing here reaches the network: mock mode uses the in-process `MockMemory`, and the live class is driven with a
fake `cognee` module object that records the exact calls.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.integrations import cognee_mem
from app.models import ForgetResponse, MemoryResponse, Offer
from tests.test_integration_e2e import acks, ok, pipeline, sse_events, start  # noqa: F401  (pipeline is a fixture)

DRONE = "a small camera drone under $200"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def fresh_memory():
    """A new MockMemory for the test (the registry keeps one instance per mode)."""
    from app import registry

    registry.reset()
    yield
    registry.reset()


# ---------------------------------------------------------------------------- mock mode: the two endpoints


def test_mock_memory_lists_seed_facts_then_forget_empties_it(client, fresh_memory):
    body = ok(client.get("/api/memory"))
    MemoryResponse.model_validate(body)
    assert body["mode"] == "mock" and body["simulated"] is True and body["provider"] == "cognee" and body["last_improve"] is None
    assert [f["text"] for f in body["facts"]] == cognee_mem.SEED_MEMORIES
    assert all(f["kind"] == "seed" and f["simulated"] is True for f in body["facts"])

    gone = ok(client.post("/api/memory/forget", json={"scope": "everything"}))
    ForgetResponse.model_validate(gone)
    assert gone["forgotten"] == len(cognee_mem.SEED_MEMORIES) and gone["simulated"] is True and "Mock memory" in gone["detail"]
    after = ok(client.get("/api/memory"))
    assert after["facts"] == [] and after["last_improve"] is None
    assert ok(client.post("/api/memory/forget"))["forgotten"] == 0  # no body: everything; nothing left


def test_mock_forget_preferences_keeps_owned_facts(client, fresh_memory):
    from app import registry

    mem = registry.get("cognee")
    run(mem.remember("chose Frame from Mock Hobby Store for a quadcopter", kind="preference", source="approved cart r_x", run_id="r_x"))
    gone = ok(client.post("/api/memory/forget", json={"scope": "preferences"}))
    left = [f["text"] for f in ok(client.get("/api/memory"))["facts"]]
    assert gone["forgotten"] == 2  # the fact above and the seeded "prefers US sellers" line
    assert left == [f for f in cognee_mem.SEED_MEMORIES if not f.startswith("prefers")]
    assert client.post("/api/memory/forget", json={"scope": "the lot"}).status_code == 422


def test_mock_approval_teaches_the_mock_memory(client, fresh_memory):
    cart = ok(client.get("/api/runs/r_mock_so101/cart"))
    ok(client.post("/api/runs/r_mock_so101/approve", json={"plan_id": cart["plan_id"], "acknowledged_warnings": []}))
    body = ok(client.get("/api/memory"))
    prefs = [f for f in body["facts"] if f["kind"] == "preference"]
    assert prefs and all(f["text"].startswith("chose ") and f["source"] == "approved cart r_mock_so101" and f["simulated"] for f in prefs)
    assert body["last_improve"]["run_id"] == "r_mock_so101" and body["last_improve"]["simulated"] is True
    assert body["last_improve"]["stages"][0] == {"stage": "feedback_weights", "status": "simulated",
                                                 "reason": body["last_improve"]["stages"][0]["reason"]}
    ok(client.post("/api/runs/r_mock_so101/approve", json={"plan_id": cart["plan_id"], "acknowledged_warnings": []}))  # again: nothing new
    assert len(ok(client.get("/api/memory"))["facts"]) == len(body["facts"])


# ---------------------------------------------------------------------------- buyer data


def test_buyer_data_is_refused_everywhere():
    mem = cognee_mem.MockMemory()
    for bad in ("chose Frame from a.person@example.com for a quadcopter", "you rejected the store at 12 Main Street",
                "chose Frame, call +1 415 555 0100"):
        with pytest.raises(ValueError):
            run(mem.remember(bad, kind="preference"))
        with pytest.raises(ValueError):
            run(mem.feedback(bad, session_id="s1"))
        with pytest.raises(ValueError):
            run(cognee_mem.LiveMemory(FakeCognee(), mode="off").remember(bad))
        with pytest.raises(ValueError):
            run(cognee_mem.LiveMemory(FakeCognee(), mode="cloud").feedback(bad, session_id="s1"))
    assert [f["text"] for f in run(mem.list_facts())] == cognee_mem.SEED_MEMORIES


def test_learn_drops_a_fact_that_looks_like_buyer_data(pipeline):
    from app import runstate
    from app.agent import memory as agent_memory

    _, _, rid = start(pipeline, DRONE)
    live_run = runstate.get(rid)
    wrote = run(agent_memory.learn(live_run, ["chose Frame from a.person@example.com for a quadcopter", "you rejected Frame for a quadcopter"],
                                   positive=False, source="test"))
    assert wrote == ["you rejected Frame for a quadcopter"]
    texts = [f["text"] for f in ok(pipeline.get("/api/memory"))["facts"]]
    assert "you rejected Frame for a quadcopter" in texts and not any("@" in t for t in texts)
    assert not any("@" in str(r) for r in live_run.records if r["kind"] == "memory_write")


# ---------------------------------------------------------------------------- pipeline mode: decisions -> memory -> the next run


def _approve(c, rid: str) -> dict:
    st = ok(c.get(f"/api/runs/{rid}"))
    for bid in st["open_assumptions"]:
        ok(c.post(f"/api/runs/{rid}/assumptions", json={"bom_line_id": bid, "action": "confirm"}))
    st = ok(c.get(f"/api/runs/{rid}"))
    cart = ok(c.get(f"/api/runs/{rid}/cart"))
    return ok(c.post(f"/api/runs/{rid}/approve", json={"plan_id": cart["plan_id"], "acknowledged_warnings": acks(st)}))


def test_approval_writes_preferences_and_runs_improve_and_the_next_run_says_so(pipeline):
    c = pipeline
    _, st, rid = start(c, DRONE)
    before = ok(c.get("/api/memory"))
    MemoryResponse.model_validate(before)
    assert before["mode"] == "mock" and before["simulated"] is True
    # the agent's own plan is not a preference: nothing is written until the user decides
    assert not [f for f in before["facts"] if f["kind"] == "preference"] and before["last_improve"] is None
    seed_pref = [e for e in sse_events(c, rid) if e["type"] == "agent.message" and e["title"].startswith("Memory:")]
    assert [e["title"] for e in seed_pref] == ["Memory: prefers US sellers; no Alibaba or AliExpress"]  # the seeded preference

    # a cart edit by the user: "you rejected ..."
    line = next(ln for ln in st["bom"] if ln.get("chosen"))
    ok(c.post(f"/api/runs/{rid}/cart/edit", json={"op": "remove", "bom_line_id": line["bom_line_id"]}))
    rejected = [f for f in ok(c.get("/api/memory"))["facts"] if f["text"].startswith("you rejected")]
    assert len(rejected) == 1 and line["raw_name"].split(",")[0] in rejected[0]["text"] and rejected[0]["kind"] == "preference"
    assert rejected[0]["run_id"] == rid and rejected[0]["source"].startswith("you rejected")
    assert ok(c.get("/api/memory"))["last_improve"] is None  # improve runs after approval only

    approved = _approve(c, rid)
    stores = {g["display_name"] for g in approved["cart"]["stores"]}
    body = ok(c.get("/api/memory"))
    MemoryResponse.model_validate(body)
    chose = [f for f in body["facts"] if f["text"].startswith("chose ")]
    assert chose and all(f["kind"] == "preference" and f["source"] == f"approved cart {rid}" and f["run_id"] == rid and f["simulated"] for f in chose)
    assert all(any(f" from {s} for a quadcopter" in f["text"] for s in stores) for f in chose)
    assert not any(line["raw_name"].split(",")[0] in f["text"] for f in chose)  # the removed line was not "chosen"
    imp = body["last_improve"]
    assert imp["run_id"] == rid and imp["feedback"] == [f["text"] for f in rejected + chose] and imp["simulated"] is True
    assert imp["stages"][0]["stage"] == "feedback_weights" and imp["stages"][0]["status"] == "simulated"

    events = sse_events(c, rid)
    assert sum(1 for e in events if e["type"] == "memory.written") == len(chose) + 1
    assert any(e["type"] == "agent.message" and e["title"].startswith("Memory improve pass: feedback_weights") for e in events)
    verify = ok(c.get(f"/api/runs/{rid}/verify"))
    assert verify["ok"] is True  # the memory_write records are part of the chain and it still verifies

    # the next run recalls what was chosen
    _, _, rid2 = start(c, DRONE)
    said = [e for e in sse_events(c, rid2) if e["type"] == "agent.message" and e["title"].startswith("Memory: last time you chose ")]
    assert said and all(e["data"]["role"] == "memory" and e["data"]["used"] is True and e["simulated"] is True for e in said)

    # and Forget everything wipes it, improve pass included
    gone = ok(c.post("/api/memory/forget", json={"scope": "everything"}))
    assert gone["forgotten"] == len(body["facts"])
    assert ok(c.get("/api/memory")) == {**body, "facts": [], "last_improve": None}
    _, _, rid3 = start(c, DRONE)
    assert not [e for e in sse_events(c, rid3) if e["title"].startswith("Memory:")]


def test_a_preference_never_lets_a_store_outside_the_mandate_through(pipeline):
    from app import registry, runstate
    from app.agent import memory as agent_memory

    c = pipeline
    _, st, rid = start(c, DRONE)
    live_run = runstate.get(rid)
    allowed = set(live_run.mandate.constraints.allowed_merchants)
    outside = next(o for o in live_run.offer_index.values() if o.store_id not in allowed)  # found, and refused by the mandate
    bid = live_run.offer_line[outside.offer_id]
    part = live_run.line(bid).raw_name.split(",")[0]
    ok(c.post("/api/memory/forget"))
    run(registry.get("cognee").remember(f"chose {part} from {outside.store_name} for a quadcopter", kind="preference", source="test"))

    _, st2, rid2 = start(c, DRONE)
    run2 = runstate.get(rid2)
    said = [e for e in sse_events(c, rid2) if e["title"].startswith("Memory: last time you chose")]
    assert len(said) == 1 and said[0]["data"]["used"] is False and "outside this mandate" in said[0]["detail"]
    assert run2.memory_prefs and agent_memory.preferred_stores(run2) == set()
    assert all(not v for v in run2.memory_tie_breaks.values())
    for plan in st2["plans"].values():
        assert all(pl["store_id"] in allowed for pl in plan["lines"]) and outside.store_id not in plan["stores"]
    assert st2["plans"] == st["plans"]  # the preference changed nothing
    bid2 = next(b for o, b in run2.offer_line.items() if run2.offer_index[o].store_id == outside.store_id)
    moved = c.post(f"/api/runs/{rid2}/cart/edit", json={"op": "move_store", "bom_line_id": bid2, "store_id": outside.store_id})
    assert moved.status_code == 409 and moved.json()["detail"]["error"] == "merchant_allowed"  # still refused


# ---------------------------------------------------------------------------- the tie-break, on its own


def _offer(oid: str, store: str, price: float) -> Offer:
    return Offer(offer_id=oid, store_id=store, store_name=store.title(), title=f"Widget at {store}", url=f"https://mock.invalid/{oid}",
                 price_usd=price, action_level="product_link", source_api="mock", seen_at="2026-11-20T10:00:00-08:00",
                 evidence_sha256="0" * 64, simulated=True)


def _fake_run(offers: list[Offer], allowed: list[str], prefs: list[str]):
    from app.runstate import Pins

    return SimpleNamespace(offers={"b1": offers}, rejected={}, offer_index={o.offer_id: o for o in offers}, edited_lines=set(), pins=Pins(),
                           memory_prefs=prefs, mandate=SimpleNamespace(constraints=SimpleNamespace(allowed_merchants=allowed)))


def _solve_with_memory(r, offers: list[Offer]):
    from app.agent import memory as agent_memory
    from app.pipeline import optimize

    def solve(require, ban):
        return optimize.optimize([optimize.PartNeed("b1", 1, offers)], tier="cheapest", budget=100, require=require, ban=ban, simulated=True)

    base = solve(set(), set())
    return base, agent_memory.tie_break(r, base, solve, r.pins, "cheapest")


def test_tie_break_prefers_a_remembered_store_only_on_a_tie_and_only_inside_the_mandate():
    same = [_offer("o1", "alpha", 10.0), _offer("o2", "beta", 10.0)]
    base, _ = _solve_with_memory(_fake_run(same, ["alpha", "beta"], []), same)
    loser = next(o for o in same if o.store_id != base.lines[0].store_id)  # whichever the optimizer does not pick by itself
    pref = [f"chose Widget from {loser.store_name} for a quadcopter"]

    r = _fake_run(same, ["alpha", "beta"], pref)
    _, plan = _solve_with_memory(r, same)
    assert plan.lines[0].store_id == loser.store_id and plan.total_usd == base.total_usd and r.memory_tie_breaks == {"cheapest": {"b1": loser.store_id}}

    r = _fake_run(same, [base.lines[0].store_id], pref)  # the remembered store is not in the mandate
    _, plan = _solve_with_memory(r, same)
    assert plan.lines[0].store_id == base.lines[0].store_id and r.memory_tie_breaks == {"cheapest": {}}

    dearer = [o if o.offer_id != loser.offer_id else _offer(o.offer_id, o.store_id, 10.5) for o in same]  # not a tie any more
    r = _fake_run(dearer, ["alpha", "beta"], pref)
    _, plan = _solve_with_memory(r, dearer)
    assert plan.lines[0].store_id == base.lines[0].store_id and plan.total_usd == 10.0

    r = _fake_run(same, ["alpha", "beta"], pref + [f"you rejected {loser.store_name} for Widget and chose {base.lines[0].store_id.title()} instead"])
    _, plan = _solve_with_memory(r, same)
    assert plan.lines[0].store_id == base.lines[0].store_id  # a later rejection cancels the preference


# ---------------------------------------------------------------------------- the live class against a fake cognee module


class QAEntry:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeCognee:
    """Stands in for the `cognee` module: records every call with its parameters. No network."""

    QAEntry = QAEntry

    def __init__(self, improve_error: Exception | None = None):
        self.calls: list[tuple] = []
        self.improve_error = improve_error

    async def serve(self, url=None, api_key=None):
        self.calls.append(("serve", url))

    async def remember(self, data, dataset_name="main_dataset", **kw):
        self.calls.append(("remember", data.__dict__ if isinstance(data, QAEntry) else data, dataset_name, kw))

    async def recall(self, query_text, datasets=None, top_k=15):
        self.calls.append(("recall", query_text, datasets, top_k))
        return [{"source": "graph", "text": "chose Frame from Mock Hobby Store for a quadcopter"}]

    async def improve(self, dataset="main_dataset", **kw):
        self.calls.append(("improve", dataset, kw))
        if self.improve_error:
            raise self.improve_error
        return SimpleNamespace(status="completed", stages=[
            SimpleNamespace(stage="feedback_weights", status="completed", reason=None, error=None, counts={"sessions": 1}),
            SimpleNamespace(stage="persist_session_qa", status="completed", reason=None, error=None, counts={}),
            SimpleNamespace(stage="distill_sessions", status="skipped", reason="no_llm_configured", error=None, counts={})])

    async def forget(self, **kw):
        self.calls.append(("forget", kw))
        return {"dataset_id": "00000000-0000-0000-0000-000000000000", "search_history_removed": True, "status": "success"}


def test_live_memory_calls_cognee_forget_and_improve_exactly(monkeypatch, tmp_path):
    monkeypatch.setenv("COGNEE_URL", "https://tenant.aws.cognee.invalid")
    monkeypatch.setenv("COGNEE_API_KEY", "test-key-not-real")
    fake = FakeCognee()
    ledger = tmp_path / "ledger.json"
    mem = cognee_mem.LiveMemory(fake, mode="cloud", ledger_path=ledger)
    fact = "chose Frame from Mock Hobby Store for a quadcopter"

    run(mem.remember(fact, "demo_user", kind="preference", source="approved cart r_1", run_id="r_1"))
    assert run(mem.feedback(fact, "demo_user", session_id="b2c_r_1", positive=True)) is True
    run(mem.feedback("you rejected Frame for a quadcopter", "demo_user", session_id="b2c_r_1", positive=False))
    out = run(mem.improve("demo_user", session_ids=["b2c_r_1"], run_id="r_1", feedback=[fact]))

    assert fake.calls[0] == ("serve", "https://tenant.aws.cognee.invalid") and sum(1 for c in fake.calls if c[0] == "serve") == 1
    assert fake.calls[1] == ("remember", fact, "demo_user", {})
    assert fake.calls[2] == ("remember", {"question": cognee_mem.FEEDBACK_QUESTION, "answer": fact, "feedback_text": fact, "feedback_score": 5},
                             "demo_user", {"session_id": "b2c_r_1"})
    assert fake.calls[3][1]["feedback_score"] == 1 and fake.calls[3][3] == {"session_id": "b2c_r_1"}
    assert fake.calls[4] == ("improve", "demo_user", {"session_ids": ["b2c_r_1"]})
    assert out["stages"] == [{"stage": "feedback_weights", "status": "completed", "reason": "sessions=1"},
                             {"stage": "persist_session_qa", "status": "completed", "reason": None},
                             {"stage": "distill_sessions", "status": "skipped", "reason": "no_llm_configured"}]
    assert out["run_id"] == "r_1" and out["feedback"] == [fact] and out["simulated"] is False and out["provider"] == "cognee"

    # the list is our ledger of what we wrote (kept across restarts), not a read of Cognee
    again = cognee_mem.LiveMemory(FakeCognee(), mode="cloud", ledger_path=ledger)
    facts = run(again.list_facts("demo_user"))
    assert [(f["text"], f["kind"], f["source"], f["run_id"], f["simulated"]) for f in facts] == [(fact, "preference", "approved cart r_1", "r_1", False)]
    assert again.last_improve("demo_user")["stages"][0]["stage"] == "feedback_weights"
    assert "test-key-not-real" not in ledger.read_text(encoding="utf-8")

    prefs = run(mem.preferences("demo_user", "quadcopter"))
    assert fake.calls[-1][0] == "recall" and fake.calls[-1][2] == ["demo_user"] and prefs[0]["memory_text"] == fact

    # preferences only: Cognee cannot forget one kind of fact, so nothing is deleted and it says so
    n_calls = len(fake.calls)
    kept = run(mem.forget("demo_user", "preferences"))
    assert kept["forgotten"] == 0 and "Nothing was forgotten" in kept["detail"] and len(fake.calls) == n_calls

    gone = run(mem.forget("demo_user", "everything"))
    ForgetResponse.model_validate(gone)
    assert fake.calls[-1] == ("forget", {"dataset": "demo_user"})
    assert gone["forgotten"] is None and gone["provider"] == "cognee" and gone["simulated"] is False
    assert run(mem.list_facts("demo_user")) == [] and mem.last_improve("demo_user") is None
    assert run(cognee_mem.LiveMemory(FakeCognee(), mode="cloud", ledger_path=ledger).list_facts("demo_user")) == []


def test_live_improve_failure_is_reported_as_a_stage_not_raised(monkeypatch):
    monkeypatch.setenv("COGNEE_URL", "https://tenant.aws.cognee.invalid")
    mem = cognee_mem.LiveMemory(FakeCognee(improve_error=RuntimeError("Remote improve failed (500)")), mode="cloud")
    out = run(mem.improve("demo_user", session_ids=["s"]))
    assert out["stages"] == [{"stage": "improve", "status": "errored", "reason": "RuntimeError: Remote improve failed (500)"}]
    assert mem.last_improve("demo_user") == out


def test_cognee_off_lists_and_forgets_only_that_users_rows(tmp_path):
    from app.integrations.s2 import LiveKnowledgeStore, OwnedPartsMemory, SqliteBackend

    st = LiveKnowledgeStore(SqliteBackend(tmp_path / "o.sqlite"), embedder=None, auto_seed=False)
    st.backend.apply_schema(8)
    fake = FakeCognee()
    mem = cognee_mem.LiveMemory(fake, mode="off", fallback=OwnedPartsMemory(st))
    try:
        run(mem.remember("owns two USB-C data cables", "demo_user", source="you said"))
        run(mem.remember("chose Frame from Mock Hobby Store for a quadcopter", "demo_user", kind="preference", source="approved cart r_1"))
        run(mem.remember("owns a soldering iron", "someone_else"))
        facts = run(mem.list_facts("demo_user"))
        assert [(f["text"], f["kind"], f["provider"]) for f in facts] == [
            ("owns two USB-C data cables", "owned", "owned_parts"), ("chose Frame from Mock Hobby Store for a quadcopter", "preference", "owned_parts")]
        assert [p["memory_text"] for p in run(mem.preferences("demo_user"))] == ["chose Frame from Mock Hobby Store for a quadcopter"]
        assert run(mem.feedback("chose Frame from Mock Hobby Store for a quadcopter", session_id="s")) is False
        imp = run(mem.improve("demo_user", session_ids=["s"]))
        assert imp["provider"] == "owned_parts" and imp["stages"][0]["status"] == "skipped"

        assert run(mem.forget("demo_user", "preferences"))["forgotten"] == 1
        assert [f["text"] for f in run(mem.list_facts("demo_user"))] == ["owns two USB-C data cables"]
        gone = run(mem.forget("demo_user", "everything"))
        assert gone["forgotten"] == 1 and gone["provider"] == "owned_parts"
        assert run(mem.list_facts("demo_user")) == [] and len(run(mem.list_facts("someone_else"))) == 1
        assert fake.calls == []  # Cognee is never touched when it is off
    finally:
        st.close()
