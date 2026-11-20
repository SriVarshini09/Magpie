"""Intake and build-type router (M12, P14): text, link and photo; chips from the template; the Claude call shape."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest
from a_helpers import SO101_URL, live_mock, run  # noqa: F401

from app import runstate
from app.intake import clarify, classify, vision
from app.intake.classify import IntakeError, route_keywords
from app.integrations import anthropic_client as ac


def jpeg(w=1600, h=1200, fmt="JPEG") -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 130, 140)).save(buf, format=fmt)
    return buf.getvalue()


class FakeClaude:
    """Stands in for AsyncAnthropic: records the request, returns a canned structured answer."""

    def __init__(self, answer: dict, stop_reason: str = "end_turn") -> None:
        self.answer, self.stop_reason, self.requests = answer, stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    async def create(self, **kw):
        self.requests.append(kw)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=json.dumps(self.answer))],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5), model=kw["model"],
                               stop_details=SimpleNamespace(category="cyber", explanation="x") if self.stop_reason == "refusal" else None)


ANSWER = {"build_type": "quadcopter", "confidence": 0.93, "alternatives": [{"build_type": "rc_car", "confidence": 0.03}],
          "summary": "A palm-size camera quadcopter, about $200", "budget_usd": 200, "size_class": None, "answered_question_ids": [], "visible_parts": []}


def test_keyword_router_covers_the_build_types():
    assert route_keywords("a small camera drone under $200")["build_type"] == "quadcopter"
    assert route_keywords("a small camera drone under $200")["budget_usd"] == 200.0
    assert route_keywords(None, SO101_URL)["build_type"] == "robot_arm"
    assert route_keywords("a robot claw for my desk")["build_type"] == "claw_gripper"
    assert route_keywords("self-driving RC car")["build_type"] == "rc_car"
    assert route_keywords("ESP32 weather station")["build_type"] == "electronics_mcu"
    generic = route_keywords("something to water my plants")
    assert generic["build_type"] == "generic" and generic["confidence"] < 0.6 and generic["budget_usd"] is None


def test_text_intake_uses_the_template_questions_and_reads_the_budget(live_mock):
    it = run(classify.classify("a small camera drone under $200", [], llm=ac.LiveLLM(client=FakeClaude(ANSWER))))
    assert it.build_type == "quadcopter" and it.template_id == "tpl_quadcopter" and it.source_api == "claude"
    assert it.constraints.budget_usd == 200 and it.mandate_preset.budget_usd == 200
    assert 0 < len(it.questions) <= 3 and not it.ready
    tpl_ids = [q.id for q in __import__("app.pipeline.template", fromlist=["x"]).load_template_sync("quadcopter").template.questions]
    assert [q.id for q in it.questions] == tpl_ids[:len(it.questions)]  # from the template, in its order; never invented
    assert it.mandate_preset.data_sharing.email is False and it.mandate_preset.data_sharing.street_address is False


def test_claude_request_shape_follows_the_api_rules(live_mock):
    fake = FakeClaude(ANSWER)
    run(classify.classify("a small camera drone under $200", [("p.jpg", "image/jpeg", jpeg())], llm=ac.LiveLLM(client=fake)))
    req = fake.requests[0]
    assert req["model"] == "claude-sonnet-5-5" and req["max_tokens"] == 16000
    assert req["betas"] == ["server-side-fallback-2026-07-01"] and req["fallbacks"] == "default"
    assert req["output_config"]["format"]["type"] == "json_schema" and req["output_config"]["format"]["schema"]["additionalProperties"] is False
    for banned in ("tool_choice", "temperature", "top_p", "top_k", "thinking"):
        assert banned not in req
    assert req["messages"][-1]["role"] == "user"  # no assistant prefill
    blocks = req["messages"][0]["content"]
    assert blocks[0]["type"] == "image" and blocks[0]["source"]["type"] == "base64" and blocks[0]["source"]["media_type"] == "image/jpeg"
    assert blocks[-1]["type"] == "text" and "1024 x 768" in blocks[-1]["text"]  # the image goes before the text, already resized


def test_refusal_or_no_key_falls_back_to_the_keyword_router(live_mock):
    refused = run(classify.classify("a small camera drone", [], llm=ac.LiveLLM(client=FakeClaude(ANSWER, stop_reason="refusal"))))
    assert refused.build_type == "quadcopter" and refused.source_api == "keyword_router"
    no_key = run(classify.classify("a small camera drone", [], llm=ac.LiveLLM()))  # no credentials under pytest
    assert no_key.source_api == "keyword_router"
    with pytest.raises(ac.LLMRefused):
        run(ac.LiveLLM(client=FakeClaude(ANSWER, stop_reason="refusal")).structured(model="claude-sonnet-5-5", system="s", messages=[], schema={}))


def test_link_is_detected_and_never_request_hosts_are_refused_with_409(live_mock):
    it = run(classify.classify(f"build this {SO101_URL} with 12V servos", []))
    assert it.inputs.source_url == SO101_URL and it.build_type == "robot_arm"
    with pytest.raises(IntakeError) as exc:
        run(classify.classify("https://www.amazon.com/dp/B0CTMM4LWK", []))
    assert exc.value.status == 409 and exc.value.refusal["rule"] == "reference_host_not_allowed"
    with pytest.raises(IntakeError) as exc:
        run(classify.classify("   ", []))
    assert exc.value.status == 422


def test_answers_change_label_and_defaults(live_mock):
    it = run(classify.classify("a small camera drone under $200", []))
    first = it.questions[0]
    it2 = clarify.apply_answers(it.intake_id, {first.id: first.chips[-1].value}, None, None)
    assert it2.questions[0].answer == first.chips[-1].value and not it2.ready
    it3 = clarify.apply_answers(it.intake_id, {}, None, True)
    assert it3.ready and all(q.answer for q in it3.questions)
    answers, defaulted = clarify.effective_answers(it.intake_id, it3)
    assert first.id not in defaulted and defaulted == {q.id for q in it3.questions[1:]}
    changed = clarify.apply_answers(it.intake_id, {}, "robot_arm", None)
    assert changed.build_type == "robot_arm" and changed.template_id == "tpl_robot_arm" and changed.confidence == 1.0
    assert runstate.intake_meta[it.intake_id]["set_by"] == "user" and runstate.intake_meta[it.intake_id]["changed_by_user"] is True
    with pytest.raises(IntakeError):
        clarify.apply_answers(it.intake_id, {changed.questions[0].id: "not-a-chip"}, None, None)


def test_low_confidence_asks_which_type_as_one_of_the_three(live_mock):
    low = {**ANSWER, "confidence": 0.5, "alternatives": [{"build_type": "rc_car", "confidence": 0.42}]}
    it = run(classify.classify("a small rover drone thing", [], llm=ac.LiveLLM(client=FakeClaude(low))))
    assert it.questions[0].id == "build_type" and [c.value for c in it.questions[0].chips] == ["quadcopter", "rc_car"] and len(it.questions) <= 3
    picked = clarify.apply_answers(it.intake_id, {"build_type": "quadcopter"}, None, None)
    assert picked.build_type == "quadcopter" and all(q.id != "build_type" or q.answer for q in picked.questions)


def test_a_type_without_a_template_routes_to_generic(live_mock, monkeypatch, tmp_path):
    from app.pipeline import template as templates

    monkeypatch.setattr(templates, "TEMPLATES_DIR", tmp_path)  # no template files: only the fixture-built ones and the generic build
    it = run(classify.classify("self-driving RC car", [], llm=ac.LiveLLM()))
    assert it.build_type == "generic" and it.template_id == "tpl_generic" and "generic build" in it.summary
    (tmp_path / "broken.json").write_text('{"build_type": "quadcopter", "template_id": "tpl_quadcopter"}', encoding="utf-8")
    bad = templates.load_template_sync("quadcopter")  # a file that fails validation is not loaded
    assert bad.template_id == "tpl_generic" and "failed validation" in bad.notice


def test_photo_upload_is_resized_stripped_hashed_and_boxes_are_kept_in_frame(live_mock):
    from app.intake import uploads

    parts = [{"label": "Arduino board", "category": "board", "image_index": 0, "box_xyxy_px": [96, 250, 430, 520], "score": 0.88},
             {"label": "breadboard", "category": "mechanical", "image_index": 0, "box_xyxy_px": [0.5, 0.25, 0.9, 0.6], "score": 0.9},  # fractions
             {"label": "wire", "category": "cable", "image_index": 0, "box_xyxy_px": [900, 700, 1400, 900], "score": 0.6},  # runs outside
             {"label": "ghost", "category": "sensor", "image_index": 0, "box_xyxy_px": [10, 10, 60, 60], "score": 0.2},  # under 0.35
             {"label": "led", "category": "mechanical", "image_index": 0, "box_xyxy_px": [5, 5, 5, 9], "score": 0.9}]  # empty
    fake = FakeClaude({**ANSWER, "build_type": "electronics_mcu", "summary": "A breadboard project", "budget_usd": None, "visible_parts": parts})
    it = run(classify.classify(None, [("bench.png", "image/png", jpeg(2048, 1536, "PNG"))], llm=ac.LiveLLM(client=fake)))
    img = it.inputs.images[0]
    assert (img.w, img.h) == (1024, 768) and len(img.sha256) == 64 and img.url == f"/api/uploads/{img.image_id}"
    stored = uploads.read_upload(img.image_id)
    from PIL import Image

    with Image.open(io.BytesIO(stored)) as im:
        assert im.format == "JPEG" and im.size == (1024, 768) and not im.getexif()
    got = {p.label: p for p in it.visible_parts}
    assert set(got) == {"arduino board", "breadboard", "wire"} and all(p.detector == "claude_vision" for p in got.values())
    assert got["breadboard"].box_xyxy_px == (512.0, 192.0, 921.6, 460.8) and got["wire"].box_xyxy_px == (900.0, 700.0, 1024.0, 768.0)
    assert any(q.id == "own_photo_parts" for q in it.questions)
    assert uploads.find_upload("../../etc/passwd") is None and uploads.find_upload("img_zzzz") is None


def test_upload_limits(live_mock):
    for files, error in (([("a.gif", "image/gif", b"GIF89a")], "unsupported_file"), ([("a.jpg", "image/jpeg", b"not an image")], "unsupported_file"),
                         ([("a.jpg", "image/jpeg", jpeg(64, 64))] * 3, "too_many_images"), ([("a.jpg", "image/jpeg", b"0" * (5 * 1024 * 1024 + 1))], "file_too_large")):
        with pytest.raises(IntakeError) as exc:
            run(classify.classify("x", files))
        assert exc.value.status == 422 and exc.value.error == error


def test_sie_boxes_refine_claudes_and_a_failing_sie_keeps_them():
    from app.models import PhotoPart

    base = [PhotoPart(label="servo", category="motor", box_xyxy_px=(100, 100, 300, 300), score=0.7, detector="claude_vision")]

    class Sie:
        async def detect(self, image, labels):
            assert labels == ["servo"]
            return [PhotoPart(label="servo", category="motor", box_xyxy_px=(110, 105, 310, 290), score=0.81, detector="sie:grounding-dino-base"),
                    PhotoPart(label="battery", category="battery", box_xyxy_px=(1, 1, 50, 50), score=0.9, detector="sie:grounding-dino-base")]

    class Down:
        async def detect(self, image, labels):
            raise NotImplementedError("TODO(D)")

    refined, detector = run(vision.identify_parts(base, b"jpeg", (1024, 768), sie=Sie()))
    assert detector == "sie:grounding-dino-base" and len(refined) == 1 and refined[0].box_xyxy_px == (110.0, 105.0, 310.0, 290.0)  # no new parts from detection
    kept, detector = run(vision.identify_parts(base, b"jpeg", (1024, 768), sie=Down()))
    assert detector == "claude_vision" and kept == base
