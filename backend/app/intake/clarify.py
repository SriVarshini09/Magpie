"""Clarifying chips: at most three questions from the template; every one has a default (PLAN §3.17).

Owner: A. `POST /api/intake/{id}/answers`: a tap per chip. Changing the label re-picks the template and
its questions. The user's choice always wins and is logged as `changed_by_user`. A defaulted answer is
remembered as defaulted, so a part it changes becomes an assumption (`pipeline/template.py`).
"""

from __future__ import annotations

from typing import Any

from app import runstate
from app.intake.classify import BUILD_LABELS, IntakeError, assemble
from app.models import Intake

__all__ = ["apply_answers", "effective_answers"]


def apply_answers(intake_id: str, answers: dict[str, str] | None, build_type: str | None = None, skip_defaults: bool | None = None) -> Intake:
    intake = runstate.intakes.get(intake_id)
    if intake is None:
        raise IntakeError(404, "intake_not_found", f"No intake {intake_id}")
    meta = runstate.intake_meta.setdefault(intake_id, {"set_by": "classifier", "answered": [], "defaulted": [], "raw": {}, "answers": {}, "changed_by_user": False})
    answers = dict(answers or {})
    stored: dict[str, str] = meta.setdefault("answers", {})
    new_type = build_type or answers.get("build_type")
    if new_type is not None and new_type not in BUILD_LABELS:
        raise IntakeError(422, "unknown_build_type", f"Unknown build type {new_type}")
    for qid, value in answers.items():
        q = next((q for q in intake.questions if q.id == qid), None)
        if q is not None and value not in {c.value for c in q.chips}:
            raise IntakeError(422, "unknown_answer", f"{value!r} is not one of the choices for {qid}")
        stored[qid] = value
        if qid in meta["defaulted"]:
            meta["defaulted"].remove(qid)  # a tap replaces a default
    if new_type is not None and (new_type != intake.build_type or "build_type" in answers):
        stored["build_type"] = new_type
        if new_type != intake.build_type:
            meta["set_by"], meta["changed_by_user"] = "user", True
        raw: dict[str, Any] = {**meta.get("raw", {}), "build_type": new_type, "confidence": 1.0 if meta["set_by"] == "user" else intake.confidence,
                               "alternatives": [], "summary": intake.summary, "answered_question_ids": meta.get("answered", []),
                               "budget_usd": intake.constraints.budget_usd, "size_class": intake.constraints.size_class,
                               "visible_parts": [p.model_dump() for p in intake.visible_parts or []], "simulated": False}
        intake = assemble(intake_id, raw, text=intake.inputs.text, url=intake.inputs.source_url, images=intake.inputs.images,
                          set_by=meta["set_by"], answers=stored)
    for q in intake.questions:
        if q.id in stored:
            q.answer = stored[q.id]
        elif skip_defaults and not q.answer:
            q.answer = q.default
            stored[q.id] = q.default
            if q.id not in meta["defaulted"]:
                meta["defaulted"].append(q.id)
    if "budget" in stored:
        try:
            intake.constraints.budget_usd = float(stored["budget"])
            intake.mandate_preset.budget_usd = float(stored["budget"])
        except ValueError:
            pass
    if "size_class" in stored:
        intake.constraints.size_class = stored["size_class"]
    intake.ready = all(q.answer for q in intake.questions)
    runstate.intakes[intake_id] = intake
    return intake


def effective_answers(intake_id: str, intake: Intake) -> tuple[dict[str, str], set[str]]:
    """(answers including defaults, ids that were defaulted) for a run that starts from this intake."""
    meta = runstate.intake_meta.get(intake_id, {})
    answers = dict(meta.get("answers", {}))
    defaulted = set(meta.get("defaulted", []))
    for q in intake.questions:
        if q.answer is not None:
            answers.setdefault(q.id, q.answer)
        elif q.id not in answers:
            answers[q.id] = q.default
            defaulted.add(q.id)
    if intake.constraints.size_class and "size_class" not in answers:  # the text named the size, so no chip was shown for it
        answers["size_class"] = intake.constraints.size_class
    return answers, defaulted
