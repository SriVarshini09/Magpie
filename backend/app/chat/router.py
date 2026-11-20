"""The keyword assistant: a deterministic intent router, used when there is no Anthropic key.

It matches phrases; it does not understand free text, and the UI says so ("Keyword assistant (no AI key)").
Every intent ends in one of `Turn`'s actions, so what it shows always comes from the real backend functions.
"""

from __future__ import annotations

import re
from typing import Any

from app.chat.actions import Turn, find_line
from app.models import ChatAction, Intake, RunState

__all__ = ["KeywordAgent", "match_answers", "amount_in"]

BUILD_WORDS: list[tuple[str, str]] = [
    ("robot_arm", r"robot(ic)? arm|\barm\b"), ("quadcopter", r"quad(copter)?|drone|fpv"), ("rc_car", r"rc car|rover|car\b"),
    ("claw_gripper", r"claw|gripper"), ("electronics_mcu", r"electronics|microcontroller|arduino|esp32|circuit"),
    ("generic", r"generic|something else|none of these|other\b"),
]
_YES = {"yes", "y", "yep", "yeah", "sure"}
_NO = {"no", "n", "nope", "nah"}


def norm(text: str) -> str:
    t = text.lower()
    t = re.sub(r"(\d)\s*[- ]?\s*(?:inch(?:es)?|in\b|\")", r"\1in ", t)
    t = re.sub(r"(\d)\s*(?:volts?|v)\b", r"\1v", t)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.]+", " ", t)).strip()


def _candidates(chip_label: str, chip_value: str) -> list[str]:
    out = {norm(chip_label), norm(chip_value.replace("_", " "))}
    for part in re.split(r"[()]", chip_label):
        if part.strip():
            out.add(norm(part))
    out |= set(re.findall(r"\d+(?:\.\d+)?(?:in|v|mm)\b", norm(chip_label)))
    return sorted((c for c in out if len(c) >= 2 and c not in _YES | _NO), key=len, reverse=True)


def match_answers(intake: Intake, text: str, *, allow_yes_no: bool = True) -> dict[str, str]:
    """Chip answers found in a message: "What size? 5-inch", "size_class: 5in", "5 inch", or a bare yes / no."""
    low, n = text.strip().lower(), f" {norm(text)} "
    out: dict[str, str] = {}
    for q in intake.questions:
        rest = None
        if low.startswith(q.text.lower()):
            rest = low[len(q.text):]
        elif low.startswith(f"{q.id}:"):
            rest = low[len(q.id) + 1:]
        if rest is not None:
            r = norm(rest)
            hit = next((c for c in q.chips if r in (norm(c.label), norm(c.value))), None)
            if hit is not None:
                return {q.id: hit.value}
    for q in intake.questions:
        best: tuple[int, str] | None = None
        for chip in q.chips:
            for cand in _candidates(chip.label, chip.value):
                if f" {cand} " in n and (best is None or len(cand) > best[0]):
                    best = (len(cand), chip.value)
        if best is not None:
            out[q.id] = best[1]
    if not out and allow_yes_no and n.strip() in _YES | _NO:
        want = "yes" if n.strip() in _YES else "no"
        q = next((q for q in intake.questions if not q.answer and any(c.value == want for c in q.chips)), None)
        if q is not None:
            out[q.id] = want
    return out


def amount_in(text: str) -> float | None:
    m = (re.search(r"\$\s?(\d[\d,]*(?:\.\d+)?)", text) or re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:dollars|usd|bucks)\b", text, re.I)
         or re.search(r"(?i)\b(?:budget|cap|under|below|spend|max(?:imum)?)\D{0,12}(\d[\d,]*(?:\.\d+)?)", text))
    try:
        return float(m.group(1).replace(",", "")) if m else None
    except ValueError:
        return None


def _build_type(low: str) -> str | None:
    m = re.match(r"build type:\s*([a-z_]+)", low)
    if m:
        return m.group(1)
    if re.search(r"\b(it'?s|it is|its|change (it )?to|actually|i mean(t)?|read it as|treat it as)\b", low):
        return next((bt for bt, pat in BUILD_WORDS if re.search(pat, low)), None)
    return None


class KeywordAgent:
    kind = "keyword"
    label = "Keyword assistant (no AI key)"

    async def respond(self, turn: Turn) -> None:
        if turn.state() is None and turn.s.run_id is None:
            await self._before_run(turn)
        else:
            await self._on_run(turn)

    # ------------------------------------------------------------------ before a run exists

    async def _before_run(self, turn: Turn) -> None:
        text, low = turn.text.strip(), turn.text.strip().lower()
        it = turn.intake()
        if it is None or turn.link or turn.files:
            await turn.start_request()
            return
        bt = _build_type(low)
        if bt:
            turn.set_build_type(bt)
            return
        if re.search(r"\b(defaults?|skip)\b", low):
            turn.use_defaults()
            return
        answers = match_answers(it, text)
        if answers:
            turn._answers(answers)
            return
        usd = amount_in(text)
        if usd is not None and re.search(r"\b(budget|spend|cap|under|below|max)\b|\$", low) and len(low.split()) <= 8:
            turn.set_request_budget(usd)
            return
        if re.search(r"\b(sign|start|run it|go|begin|mandate|continue|next)\b", low):
            turn.say("Signing is yours to do: check the limits below and press Sign mandate and run.", "info")
            turn.show_mandate()
            return
        if len(low.split()) >= 3:
            await turn.start_request()  # a new description replaces the request
            return
        turn.say("I match phrases rather than free text. Answer a question above, change the build type, or sign the mandate to start the run.", "info")
        turn.show_mandate()

    # ------------------------------------------------------------------ on a run

    def _ask_which(self, turn: Turn, st: RunState, lead: str, template: str) -> None:
        lines = [ln for ln in st.bom if ln.status not in ("removed", "skipped")][:6]
        turn.say(lead, "info", [ChatAction(kind="reply", label=ln.raw_name[:24], text=template.format(name=ln.raw_name, id=ln.bom_line_id)) for ln in lines])

    def _store_in(self, turn: Turn, low: str) -> str | None:
        for sid, name in turn.ops.stores():
            names = {sid.lower(), name.lower(), re.sub(r"\s*\(.*?\)", "", name).strip().lower()}
            if any(n and re.search(rf"\b{re.escape(n)}\b", low) for n in names):
                return sid
        return None

    async def _on_run(self, turn: Turn) -> None:
        text, low = turn.text.strip(), turn.text.strip().lower()
        if turn.link or turn.files:
            turn.say("This conversation already has a run. Start a new build for another project, link or photo.", "info",
                     [ChatAction(kind="link", label="New build", href="/")])
            return
        st = turn._ready()
        if st is None:
            return
        line = find_line(st, text)
        swap = re.search(r"\b(swap|replace|switch out)\b|\b(a |another |use a )different\b", low)

        if re.search(r"\bwhy\b|\bexplain\b|how come|reason for", low):
            if line is None:
                self._ask_which(turn, st, "Which part do you want explained?", "Why this {name} ({id})?")
            else:
                turn.explain_choice(line.bom_line_id)
            return
        if not swap and re.search(r"\b(other|others|alternatives?|options?|compare|comparison|offers)\b", low):
            if line is None:
                self._ask_which(turn, st, "Which part should I compare offers for?", "Show me other offers for {name} ({id})")
            else:
                turn.compare_offers(line.bom_line_id)
            return
        if re.search(r"left to confirm|to confirm|assum|unconfirmed|what'?s (left|open)|still open|\bconfirm\b", low):
            turn.show_open_assumptions()
            return
        if re.search(r"\b(already (have|own|got)|i (have|own|got)|i'?ve got|we (have|own)|don'?t need to buy)\b", low):
            if line is None:
                self._ask_which(turn, st, "Which part do you already have?", "I already have the {name} ({id})")
            else:
                await turn.mark_owned(line.bom_line_id)
            return
        usd = amount_in(text)
        if usd is not None and re.search(r"\b(budget|spend|cap|under|below|max)\b", low):
            turn.set_budget_cap(usd)
            return
        if re.search(r"\b(cheap|cheaper|cheapest|lowest price|less expensive|save money|lower the (price|cost|total))\b", low):
            turn.switch_tier("cheapest")
            return
        if re.search(r"\b(fewest|fewer|less|one|single|minimum)\b.*\b(stores?|checkouts?|shops?|orders?)\b|\bconsolidate\b", low):
            turn.switch_tier("fewest_checkouts")
            return
        store = self._store_in(turn, low)
        if store is not None:
            if line is None:
                self._ask_which(turn, st, "Which part should come from that store?", f"Use {store} for the {{name}} ({{id}})")
            else:
                await turn.edit_cart("move_store", line.bom_line_id, store_id=store)
            return
        if swap:
            if line is None:
                self._ask_which(turn, st, "Which part should I swap?", "Swap the {name} ({id})")
            else:
                await turn.edit_cart("swap_offer", line.bom_line_id)
            return
        if line is not None and re.search(r"\b(restore|put back|add back|bring back)\b", low):
            await turn.edit_cart("restore", line.bom_line_id)
            return
        if line is not None and re.search(r"\b(remove|drop|delete|take out|leave out)\b|don'?t (need|want)", low):
            await turn.edit_cart("remove", line.bom_line_id)
            return
        qty = re.search(r"\b(\d{1,3})\b", low)
        if line is not None and qty and re.search(r"\b(need|qty|quantity|make that|pieces|units|want)\b", low) and not re.search(r"\d\s*(in|inch|v|mm)\b", low):
            await turn.edit_cart("set_qty", line.bom_line_id, qty=int(qty.group(1)))
            return
        variant = match_answers(st.intake, text, allow_yes_no=False)
        if variant:
            qid, value = next(iter(variant.items()))
            await turn.set_variant(qid, value)
            return
        if re.search(r"\b(cart|total|cost|how much|summary|price|stores?)\b", low):
            turn.show_cart()
            return
        if re.search(r"\b(parts?|list|bom|items?|lines?)\b", low):
            turn.show_parts()
            return
        self.help(turn, st)

    def help(self, turn: Turn, st: Any = None) -> None:
        turn.say("I'm the keyword assistant: I match phrases rather than understand free text. Things I can do on this cart:", "info", [
            ChatAction(kind="reply", label="Make it cheaper", text="Make it cheaper"),
            ChatAction(kind="reply", label="Fewest stores", text="Fewest stores"),
            ChatAction(kind="reply", label="Show the parts", text="Show the parts"),
            ChatAction(kind="reply", label="What's left to confirm?", text="What's left to confirm?"),
            ChatAction(kind="reply", label="Show the cart", text="Show the cart"),
        ])
