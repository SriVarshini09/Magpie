"""Sponsor clients with fakes: SIE, Cognee, Amplitude, Statsig (PLAN §3.15, §3.20). Owner: D. No network, no keys."""

from __future__ import annotations

import asyncio
import io

import pytest

from app import models as M
from app.integrations import amplitude, cognee_mem, sie, statsig_gate


def run(coro):
    return asyncio.run(coro)


def jpeg(w: int = 400, h: int = 300) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 200, 200)).save(buf, format="JPEG")
    return buf.getvalue()


# --------------------------------------------------------------------------- SIE


class FakeSIEClient:
    def __init__(self, fail_first: Exception | None = None):
        self.calls: list[tuple] = []
        self.fail_first = fail_first

    def _maybe_fail(self):
        if self.fail_first is not None:
            exc, self.fail_first = self.fail_first, None
            raise exc

    async def encode(self, model, items, is_query=None):
        self._maybe_fail()
        self.calls.append(("encode", model, items, is_query))

        class Arr(list):
            def tolist(self):
                return list(self)

        return [{"dense": Arr([float(len(i["text"])), 1.0])} for i in items]

    async def score(self, model, query, items):
        self.calls.append(("score", model, query, items))
        ranked = sorted(items, key=lambda i: -len(i["text"]))  # SDK returns entries sorted by relevance
        return {"scores": [{"item_id": i["id"], "score": len(i["text"]) / 100, "rank": r} for r, i in enumerate(ranked)]}

    async def extract(self, model, item, labels=None, options=None):
        self.calls.append(("extract", model, item, labels))
        if "images" in item:
            return {"objects": [{"label": "Servo Motor", "score": 0.81, "bbox": [10, 20, 100, 50]},
                                {"label": "breadboard", "score": 0.2, "bbox": [0, 0, 50, 50]},
                                {"label": "battery", "score": 0.9, "bbox": [390, 290, 50, 50]},
                                {"label": "led", "score": 0.7, "bbox": [5, 5, 0, 10]}]}
        return {"entities": [{"text": "12V", "label": "voltage", "score": 0.9, "start": 8, "end": 11}]}


def live_sie(client, **kw):
    return sie.LiveSIE(client, models={"encode": "emb-m", "score": "rr-m", "extract": "ner-m", "detect": "IDEA-Research/grounding-dino-base"}, **kw)


@pytest.fixture(autouse=True)
def clear_log():
    sie.CALL_LOG.clear()
    yield
    sie.CALL_LOG.clear()


def test_box_conversion_is_one_function_for_both_formats():
    assert sie.to_xyxy([10, 20, 100, 50], "xywh") == (10, 20, 110, 70)
    assert sie.to_xyxy([10, 20, 100, 50], "xyxy") == (10, 20, 100, 50)
    assert sie.to_xyxy([390, 290, 50, 50], "xywh", width=400, height=300) == (390, 290, 400, 300)
    assert sie.to_xyxy([5, 5, 0, 10], "xywh") is None and sie.to_xyxy([], "xywh") is None
    with pytest.raises(sie.SIEConfigError):
        sie.to_xyxy([1, 2, 3, 4], "cxcywh")


def test_box_format_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("SIE_BOX_FORMAT", "xyxy")
    assert sie.to_xyxy([10, 20, 100, 50]) == (10, 20, 100, 50)
    monkeypatch.setenv("SIE_BOX_FORMAT", "xywh")
    assert sie.to_xyxy([10, 20, 100, 50]) == (10, 20, 110, 70)


def test_detect_returns_photo_parts_in_xyxy_and_drops_low_scores():
    c = FakeSIEClient()
    parts = run(live_sie(c, box_format="xywh").detect(jpeg(), ["servo motor", "battery", "breadboard", "led"]))
    assert all(isinstance(p, M.PhotoPart) and p.detector == "sie:grounding-dino-base" for p in parts)
    by = {p.label: p for p in parts}
    assert set(by) == {"servo motor", "battery"}  # 0.2 dropped (< 0.35), zero-width box dropped
    assert by["servo motor"].box_xyxy_px == (10, 20, 110, 70)
    assert by["battery"].box_xyxy_px == (390, 290, 400, 300)  # clamped to the 400x300 image
    _, model, item, labels = c.calls[0]
    assert model == "IDEA-Research/grounding-dino-base" and item["images"][0]["format"] == "jpeg" and "battery" in labels


def test_encode_score_extract_shapes_and_call_log():
    c = FakeSIEClient()
    s = live_sie(c)
    vecs = run(s.encode(["ab", "abcd"], is_query=True))
    assert vecs == [[2.0, 1.0], [4.0, 1.0]] and c.calls[0][3] is True
    scores = run(s.score("12V supply", ["short", "a much longer title"]))
    assert scores == [0.05, 0.19]  # back in input order although the SDK sorts by relevance
    spans = run(s.extract("Servo - 12V, JST", ["voltage"]))
    assert spans[0]["label"] == "voltage" and spans[0]["text"] == "12V" and spans[0]["provider"] == "sie"
    table = {r["step"]: r for r in sie.call_table()}
    assert set(table) == {"encode", "score", "extract"} and table["encode"]["model"] == "emb-m" and table["encode"]["calls"] == 1
    assert sie.stats()["calls"] == 3


def test_provisioning_is_retried_once_with_retry_after(monkeypatch):
    class ProvisioningError(Exception):
        retry_after = 0.0

    c = FakeSIEClient(fail_first=ProvisioningError("503 PROVISIONING"))
    assert run(live_sie(c).encode(["x"])) == [[1.0, 1.0]]
    c2 = FakeSIEClient(fail_first=ValueError("bad request"))
    with pytest.raises(ValueError):
        run(live_sie(c2).encode(["x"]))
    assert any(not r["ok"] for r in sie.CALL_LOG)


def test_missing_model_or_key_fails_before_any_call(monkeypatch):
    for v in ("SIE_API_KEY", "SIE_BASE_URL", "SIE_EMBED_MODEL"):
        monkeypatch.delenv(v, raising=False)
    s = sie.LiveSIE()
    assert not s.configured()
    with pytest.raises(sie.SIEConfigError):
        run(s.encode(["x"]))
    assert s.model("detect") == "IDEA-Research/grounding-dino-base"


def test_a_vision_identify_parts_accepts_our_detect(monkeypatch):
    """A's intake/vision.py calls detect(image_jpeg, labels) and matches lower-case labels."""
    from app.intake import vision

    claude = [M.PhotoPart(label="servo motor", category="motor", box_xyxy_px=(12, 18, 105, 72), score=0.8, detector="claude_vision")]
    refined, detector = run(vision.identify_parts(claude, jpeg(), (400, 300), sie=live_sie(FakeSIEClient())))
    assert detector == "sie:grounding-dino-base" and refined[0].box_xyxy_px == (10, 20, 110, 70)


# --------------------------------------------------------------------------- Cognee


class FakeCognee:
    def __init__(self):
        self.calls: list[tuple] = []
        self.facts: list[str] = []

        class Config:
            def __init__(s):
                s.llm = s.emb = None

            def set_llm_config(s, d):
                s.llm = d

            def set_embedding_config(s, d):
                s.emb = d

        self.config = Config()

    async def serve(self, url=None, api_key=None):
        self.calls.append(("serve", url, api_key))

    async def remember(self, text, dataset_name="main_dataset"):
        self.calls.append(("remember", text, dataset_name))
        self.facts.append(text)

    async def recall(self, query_text, datasets=None, top_k=15):
        self.calls.append(("recall", query_text, datasets, top_k))
        word = query_text.split()[0].lower()
        return [{"source": "system", "text": "memory still warming up"}] + [
            {"source": "graph", "text": f} for f in self.facts if word in f.lower()]


def test_cognee_cloud_serves_then_remembers_and_recalls(monkeypatch):
    monkeypatch.setenv("COGNEE_URL", "https://tenant.aws.cognee.invalid")
    monkeypatch.setenv("COGNEE_API_KEY", "test-key-not-real")
    fake = FakeCognee()
    mem = cognee_mem.LiveMemory(fake, mode="cloud")
    run(mem.seed())
    hits = run(mem.recall("screwdriver set"))
    assert fake.calls[0] == ("serve", "https://tenant.aws.cognee.invalid", "test-key-not-real")
    assert sum(1 for c in fake.calls if c[0] == "serve") == 1
    assert ("remember", "owns a precision screwdriver set", "demo_user") in fake.calls
    assert hits == [{"memory_text": "owns a precision screwdriver set", "provider": "cognee", "simulated": False}]
    assert fake.calls[-1][2] == ["demo_user"]


def test_cognee_cloud_needs_a_url(monkeypatch):
    monkeypatch.delenv("COGNEE_URL", raising=False)
    with pytest.raises(cognee_mem.CogneeConfigError):
        run(cognee_mem.LiveMemory(FakeCognee(), mode="cloud").recall("x"))


def test_cognee_local_refuses_to_default_to_openai(monkeypatch):
    for n in cognee_mem.LOCAL_REQUIRED:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-sonnet-5")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    with pytest.raises(cognee_mem.CogneeConfigError) as err:
        run(cognee_mem.LiveMemory(FakeCognee(), mode="local").remember("owns a soldering iron"))
    assert "EMBEDDING_PROVIDER" in str(err.value) and "OpenAI" in str(err.value)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
    monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "384")
    fake = FakeCognee()
    run(cognee_mem.LiveMemory(fake, mode="local").remember("owns a soldering iron"))
    assert fake.config.llm["llm_provider"] == "anthropic" and fake.config.emb == {
        "embedding_provider": "fastembed", "embedding_model": "BAAI/bge-small-en-v1.5", "embedding_dimensions": 384}
    assert not any(c[0] == "serve" for c in fake.calls)


def test_cognee_off_uses_the_owned_parts_table(tmp_path):
    from app.integrations.s2 import LiveKnowledgeStore, OwnedPartsMemory, SqliteBackend

    st = LiveKnowledgeStore(SqliteBackend(tmp_path / "o.sqlite"), embedder=None, auto_seed=False)
    st.backend.apply_schema(8)
    mem = cognee_mem.LiveMemory(mode="off", fallback=OwnedPartsMemory(st))
    run(mem.remember("owns two USB-C data cables"))
    assert mem.provider == "owned_parts"
    assert run(mem.recall("USB-C Cable 2 pcs"))[0]["provider"] == "owned_parts"
    st.close()


def test_memory_refuses_buyer_data():
    for bad in ("my email is a.person@example.com", "call me at +1 415 555 0100", "ship to 12 Main Street"):
        with pytest.raises(ValueError):
            run(cognee_mem.LiveMemory(FakeCognee(), mode="off").remember(bad))
    with pytest.raises(ValueError):
        run(cognee_mem.MockMemory().remember("reach me at a@b.example"))


# --------------------------------------------------------------------------- Amplitude


class FakeAgent:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def track_tool_call(self, **kw):
        self.calls.append(("tool", kw))
        return "t1"

    def track_ai_message(self, **kw):
        self.calls.append(("ai", kw))
        return f"msg{len(self.calls)}"

    def track_user_message(self, **kw):
        self.calls.append(("user", kw))
        return "u1"

    def score(self, **kw):
        self.calls.append(("score", kw))

    def track_session_end(self, **kw):
        self.calls.append(("end", kw))


class FakeAI:
    def __init__(self):
        self.agent_obj = FakeAgent()
        self.shut = False

    def agent(self, agent_id):
        assert agent_id == "build-to-cart"
        return self.agent_obj

    def shutdown(self):
        self.shut = True


class FakeAmp:
    def __init__(self):
        self.events = []

    def track(self, ev):
        self.events.append(ev)


def test_amplitude_session_per_run_and_approval_score():
    ai, amp = FakeAI(), FakeAmp()
    a = amplitude.LiveAnalytics(ai, amp)
    a.track_tool_call("r_1", "search_offers", 812, "ok")
    a.track_tool_call("r_1", "create_carts", 3, "refused")
    a.track_ai_message("r_1", "claude-sonnet-5-5", 1200, 300, 950)
    a.score("r_1", "user-feedback", 1.0)
    calls = ai.agent_obj.calls
    assert all(kw["session_id"] == "r_1" and kw["user_id"] == "demo_user" for _, kw in calls)
    assert calls[0][1]["success"] is True and calls[1][1]["success"] is True and calls[1][1]["event_properties"]["outcome"] == "refused"
    assert calls[2][1]["content"] == "" and calls[2][1]["input_tokens"] == 1200
    score = calls[3][1]
    assert score["name"] == "user-feedback" and score["value"] == 1.0 and score["target_id"] == "msg3" and score["target_type"] == "message"
    a.shutdown()
    assert ai.shut and calls[-1][0] == "end"


def test_amplitude_properties_are_allow_listed_and_pii_free():
    ai, amp = FakeAI(), FakeAmp()
    a = amplitude.LiveAnalytics(ai, amp)
    a.track_event("r_1", "cart_approved", {"total_usd": 132.41, "stores": 4, "email": "a@b.example", "note": "free text",
                                           "tier": "cheapest", "store_id": "call +1 415 555 0100"})
    props = amp.events[0].event_properties
    assert props == {"run_id": "r_1", "total_usd": 132.41, "stores": 4, "tier": "cheapest"}
    a.track_user_message("r_1", "link")
    assert ai.agent_obj.calls[-1][1]["content"] == "[link]"


def test_amplitude_errors_never_reach_the_agent(monkeypatch):
    monkeypatch.delenv("AMPLITUDE_AI_API_KEY", raising=False)
    a = amplitude.LiveAnalytics()
    a.track_tool_call("r_1", "x", 1, "ok")
    a.score("r_1", "user-feedback", 0.0)
    assert a.errors == 2 and "AMPLITUDE_AI_API_KEY" in a.last_error
    a.shutdown()


# --------------------------------------------------------------------------- Statsig


class FakeStatsig:
    def __init__(self, on=True, fail=False):
        self.on, self.fail, self.events = on, fail, []

    def check_gate(self, user, name):
        if self.fail:
            raise RuntimeError("network down")
        return self.on

    def log_event(self, user, name, value=None, metadata=None):
        self.events.append((name, value, metadata))


def test_statsig_gate_and_events(monkeypatch):
    import statsig_python_core  # noqa: F401  (the SDK's StatsigUser is built locally, no network)

    g = statsig_gate.LiveGates(FakeStatsig(on=False))
    assert g.check_gate("strict_compat_rules") is False and g.last_source["strict_compat_rules"] == "statsig"
    g.log_event("cart_approved", value=1, metadata={"acknowledged": "R10", "email": "a@b.example"})
    assert g._s.events == [("cart_approved", 1, {"acknowledged": "R10"})]


def test_statsig_falls_back_to_the_strict_default():
    g = statsig_gate.LiveGates(FakeStatsig(fail=True))
    assert g.check_gate("strict_compat_rules") is True and g.last_source["strict_compat_rules"] == "default"
    assert g.check_gate("some_unknown_gate") is False


# --------------------------------------------------------------------------- registry


def test_live_classes_construct_without_network(live_mode):
    from app import registry

    for name in ("singlestore", "sie", "cognee", "amplitude", "statsig"):
        assert type(registry.get(name)).__name__.startswith("Live")
