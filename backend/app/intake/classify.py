"""Intake classifier and build-type router (PLAN §3.17, M12). Owner: A.

One structured-output call made by the harness before the mandate exists. It is not an agent tool:
it has no tools, reaches no store and spends no money. When Claude is not available (no key, an API
error, a refusal) a keyword router answers instead and the intake says so (`source_api`).

Questions are data in the template, never invented by the model: the classifier only says which
question ids the text already answers.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from app import registry, runstate
from app.config import DATA_DIR
from app.intake import uploads
from app.intake.vision import normalize_parts
from app.models import (
    BuildTypeAlternative, Chip, DataSharing, Intake, IntakeConstraints, IntakeInputs, IntakeQuestion, MandatePreset,
)
from app.pipeline import template as templates
from app.stores.http import is_never_request

__all__ = ["classify", "route_keywords", "find_url", "IntakeError", "BUILD_LABELS", "mandate_preset", "REFUSAL_TEXT"]

REFUSAL_TEXT = "We can't read that site. Paste the parts list as text instead."
BUILD_LABELS = {"robot_arm": "Robot arm", "quadcopter": "Quadcopter", "rc_car": "RC car", "claw_gripper": "Claw gripper",
                "electronics_mcu": "Electronics project", "generic": "Generic build"}
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
# Generic trigger words per build type (PLAN §3.17 table). Project names are not listed here: they come
# from each template's own `title` and `summary` (data), which the router also matches.
KEYWORDS: list[tuple[str, str, float]] = [
    ("claw_gripper", r"\b(claw|gripper|grabber)\b", 0.85),
    ("robot_arm", r"\b(robot(ic)? arm|arm robot|manipulator|follower arm|leader arm)\b", 0.9),
    ("quadcopter", r"\b(drone|quad(copter)?|fpv|multirotor|uav)\b", 0.9),
    ("rc_car", r"\b(rc car|r/c car|rover|self[- ]driving car|robot car|buggy)\b", 0.88),
    ("electronics_mcu", r"\b(arduino|esp32|esp8266|microcontroller|breadboard|weather station|sensor project|e-?paper)\b", 0.85),
    ("robot_arm", r"\barm\d*\b", 0.6),
]
_STOP = {"the", "and", "for", "with", "from", "small", "build", "project", "template", "about", "used", "text", "search", "rebuilt", "mock",
         "fixture", "replaced", "when", "exists", "data", "templates", "json", "one", "its", "your", "under"}


def _template_words(build_type: str) -> set[str]:
    tpl = templates.load_template_sync(build_type).template
    if tpl.build_type != build_type:
        return set()
    words = set(re.findall(r"[a-z][a-z0-9-]{2,}", f"{tpl.title} {tpl.summary}".lower()))
    return words - _STOP


class IntakeError(Exception):
    """A 4xx for POST /api/intake. `refusal` is a RefusalRecord dict for a 409."""

    def __init__(self, status: int, error: str, message: str, refusal: dict[str, Any] | None = None) -> None:
        self.status, self.error, self.message, self.refusal = status, error, message, refusal
        super().__init__(message)


def find_url(text: str | None) -> str | None:
    m = _URL.search(text or "")
    return m.group(0).rstrip(".,;:!?") if m else None


def route_keywords(text: str | None, url: str | None = None) -> dict[str, Any]:
    """Deterministic build-type router. Used when Claude is unavailable, and as a sanity floor in tests."""
    hay = " ".join(x for x in (text, url) if x).lower().replace("_", " ")
    scores: dict[str, float] = {}
    for build_type, pattern, conf in KEYWORDS:
        if re.search(pattern, hay):
            scores[build_type] = max(scores.get(build_type, 0.0), conf)
    words = set(re.findall(r"[a-z][a-z0-9-]{2,}", hay))
    for build_type in BUILD_LABELS:
        if build_type != "generic" and build_type not in scores and len(words & _template_words(build_type)) >= 1:
            scores[build_type] = 0.65  # matched the template's own title or summary
    if not scores:
        return {"build_type": "generic", "confidence": 0.4, "alternatives": [], "summary": (text or "A build from your photo").strip()[:120],
                "budget_usd": None, "size_class": None, "answered_question_ids": [], "visible_parts": [], "source_api": "keyword_router"}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, conf = ranked[0]
    if len(ranked) > 1:
        conf = min(conf, 0.7)  # two types matched: let the user pick
    sig = templates.text_signals(text)
    summary = re.sub(_URL, "", text or "").strip(" ,.;") or f"{BUILD_LABELS[best]} from the project's README"
    return {"build_type": best, "confidence": conf, "alternatives": [{"build_type": b, "confidence": round(c * 0.6, 2)} for b, c in ranked[1:3]],
            "summary": summary[:120], "budget_usd": sig.get("budget_usd"), "size_class": None, "answered_question_ids": [],
            "visible_parts": [], "source_api": "keyword_router"}


def _default_merchants() -> list[str]:
    try:
        from app.stores import registry as store_registry

        return [s.store_id for s in store_registry.stores() if s.enabled]
    except Exception:
        return []


def with_simulated_store(merchants: list[str]) -> list[str]:
    """When the store adapters are mocks (pipeline mode: DEMO_MODE=live, IMPL_<STORE>=mock), the simulated store
    is offered in the mandate preset too. It is labelled simulated everywhere; with real adapters it is left out."""
    try:
        from app import registry
        from app.stores import registry as store_registry

        if registry.impl_mode("serpapi") != "mock" or registry.impl_mode("shopify_ucp") != "mock":
            return merchants
        extra = [s.store_id for s in store_registry.stores() if s.simulated and s.enabled and s.store_id not in merchants]
        return merchants + extra
    except Exception:
        return merchants


def mandate_preset(build_type: str, budget: float | None = None) -> MandatePreset:
    """`data/projects/<build_type>/preset.json` (D writes it) or a plain default. Nothing is shared but the country."""
    preset: dict[str, Any] = {}
    path = DATA_DIR / "projects" / build_type / "preset.json"
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw = raw.get("sample", raw) if isinstance(raw, dict) else {}  # D nests the landing sample under "sample"
            preset = raw.get("mandate_preset", raw) if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            preset = {}
    try:
        today = date.fromisoformat(runstate.now_iso()[:10])
    except ValueError:
        today = date.today()
    return MandatePreset(
        budget_usd=float(budget if budget is not None else preset.get("budget_usd", 150.0)),
        deadline=str(preset.get("deadline") or (today + timedelta(days=14)).isoformat()),
        ship_to_country=str(preset.get("ship_to_country", "US")),
        allowed_merchants=with_simulated_store(list(preset.get("allowed_merchants") or _default_merchants())),
        data_sharing=DataSharing.model_validate(preset.get("data_sharing") or {}),
    )


def _question_catalog() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for bt in BUILD_LABELS:
        tpl = templates.load_template_sync(bt).template
        if tpl.build_type == bt:
            out[bt] = [{"id": q.id, "text": q.text} for q in tpl.questions]
    return out


def build_type_question(build_type: str, alternatives: list[BuildTypeAlternative]) -> IntakeQuestion:
    opts = [build_type, *[a.build_type for a in alternatives if a.build_type != build_type]][:3]
    return IntakeQuestion(id="build_type", text=" or ".join(BUILD_LABELS[o] for o in opts) + "?",
                          chips=[Chip(value=o, label=BUILD_LABELS[o]) for o in opts], default=build_type)


def assemble(intake_id: str, raw: dict[str, Any], *, text: str | None, url: str | None, images: list[Any], set_by: str = "classifier",
             answers: dict[str, str] | None = None, known: set[str] | None = None) -> Intake:
    """Turn classification fields into the `Intake` contract: template, questions (0-3), mandate preset."""
    build_type = raw.get("build_type") if raw.get("build_type") in BUILD_LABELS else "generic"
    conf = max(0.0, min(1.0, float(raw.get("confidence") or 0.0)))
    lt = templates.load_template_sync(build_type)
    summary = str(raw.get("summary") or text or "").strip()[:160] or BUILD_LABELS[build_type]
    if lt.template.build_type != build_type:  # no usable template: route to generic and say so (P16 fallback)
        build_type = "generic"
        summary = f"{summary} (generic build: no template for this type yet)"
    alts = []
    for a in raw.get("alternatives") or []:
        if a.get("build_type") in BUILD_LABELS and a["build_type"] != build_type:
            alts.append(BuildTypeAlternative(build_type=a["build_type"], confidence=round(float(a.get("confidence") or 0), 2)))
    alts = sorted(alts, key=lambda a: -a.confidence)[:2]
    answers = dict(answers or {})
    answered = {q for q in raw.get("answered_question_ids") or [] if isinstance(q, str)}
    # a size the text names ("5 inch") picks that chip; a size question only counts as answered when its value is a chip
    size_q = next((q for q in lt.template.questions if q.id == "size_class"), None)
    size_chips = {c.value for c in size_q.chips} if size_q else set()
    raw_size = raw.get("size_class") if isinstance(raw.get("size_class"), str) else None
    if size_chips and raw_size not in size_chips:
        raw_size = None
    size = answers.get("size_class") or templates.answers_from_text(lt.template, text).get("size_class") or raw_size
    if size_chips and "size_class" in answered and size not in size_chips:
        answered.discard("size_class")
    limit = 3
    questions: list[IntakeQuestion] = []
    unsure = set_by == "classifier" and (conf < 0.6 or any(conf - a.confidence < 0.15 for a in alts)) and (alts or build_type == "generic")
    if unsure and alts and "build_type" not in answers:
        questions.append(build_type_question(build_type, alts))  # counts as one of the three
        limit = 2
    if images and not any(q.id == "own_photo_parts" for q in lt.template.questions) and raw.get("visible_parts"):
        questions.append(IntakeQuestion(id="own_photo_parts", text="Do you already own what's in the photo?",
                                        chips=[Chip(value="yes", label="Yes"), Chip(value="no", label="No")], default="yes"))
        limit -= 1
    tpl_questions = templates.questions_for(lt.template, text, answered=answered | ({"own_photo_parts"} if not images else set()), known=known, limit=10)
    if images:  # the photo question comes first: it decides which lines leave the cart
        tpl_questions.sort(key=lambda q: q.id != "own_photo_parts")
    questions += tpl_questions[:max(limit, 0)]
    questions = questions[:3]
    for q in questions:
        if q.id in answers:
            q.answer = answers[q.id]
    sig = templates.text_signals(text)
    budget = raw.get("budget_usd") if isinstance(raw.get("budget_usd"), (int, float)) else sig.get("budget_usd")
    if "budget" in answers:
        try:
            budget = float(answers["budget"])
        except ValueError:
            pass
    sizes = [(im.w, im.h) for im in images]
    parts = normalize_parts(raw.get("visible_parts"), sizes) if images else None
    return Intake(
        intake_id=intake_id, ready=all(q.answer for q in questions), summary=summary, build_type=build_type, confidence=round(conf, 2),  # type: ignore[arg-type]
        alternatives=alts, inputs=IntakeInputs(text=text, source_url=url, images=images),
        constraints=IntakeConstraints(budget_usd=float(budget) if budget is not None else None, size_class=size),
        questions=questions, visible_parts=parts, template_id=lt.template_id, mandate_preset=mandate_preset(build_type, budget),
        source_api=str(raw.get("source_api") or "claude"), simulated=bool(raw.get("simulated")) or lt.simulated)


async def classify(text: str | None, files: list[tuple[str, str | None, bytes]], run_id: str | None = None, *, llm: Any = None) -> Intake:
    """POST /api/intake. `files` is [(filename, content_type, bytes)]."""
    text = (text or "").strip() or None
    try:
        uploads.validate_uploads([(n, c, len(b)) for n, c, b in files])
    except uploads.UploadError as exc:
        raise IntakeError(422, exc.error, exc.message) from exc
    if not text and not files:
        raise IntakeError(422, "empty_request", "Type what you want to build, paste a link, or add a photo")
    for word in _URL.findall(text or ""):
        if is_never_request(word.rstrip(".,;:!?")):
            from app.agent.guard import refusal, store_of_host

            r = refusal("reference_host_not_allowed", "fetch allowlist (PLAN §3.16 rule 3)", tool="intake", field="text",
                        value=store_of_host(word), triggered_by="user_chat")
            raise IntakeError(409, "reference_host_not_allowed", REFUSAL_TEXT, r.model_dump())
    url = find_url(text)
    intake_id = runstate.new_id("in")
    images = []
    try:
        for name, ctype, body in files:
            images.append(uploads.save_upload(run_id or intake_id, body, ctype, name))
    except uploads.UploadError as exc:
        raise IntakeError(422, exc.error, exc.message) from exc
    raw: dict[str, Any] | None = None
    note = None
    llm = llm if llm is not None else registry.get("anthropic")
    try:
        jpegs = [uploads.read_upload(im.image_id) or b"" for im in images]
        try:
            raw = await llm.classify_intake(text, jpegs, questions=_question_catalog())
        except TypeError:  # the Protocol's two-argument form (MockLLM)
            raw = await llm.classify_intake(text, jpegs)
    except NotImplementedError:
        note = "no Claude key"
    except Exception as exc:  # refusal, API error, bad JSON: the router still answers
        note = type(exc).__name__
    if not isinstance(raw, dict) or raw.get("build_type") not in BUILD_LABELS:
        raw = route_keywords(text, url)
    elif "constraints" in raw:  # a full Intake dict (the mock): lift the fields we use
        raw = {**raw, "budget_usd": (raw.get("constraints") or {}).get("budget_usd"), "size_class": (raw.get("constraints") or {}).get("size_class"),
               "answered_question_ids": []}
    known: set[str] = set()
    intake = assemble(intake_id, raw, text=text, url=url, images=images, known=known)
    runstate.intakes[intake_id] = intake
    runstate.intake_meta[intake_id] = {"set_by": "classifier", "answered": sorted(set(raw.get("answered_question_ids") or [])), "defaulted": [],
                                       "raw": {k: raw.get(k) for k in ("build_type", "confidence", "alternatives", "summary", "source_api", "visible_parts")},
                                       "fallback": note, "changed_by_user": False, "answers": {}}
    return intake
