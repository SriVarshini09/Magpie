"""The chat's actions. Each one calls an existing backend function through `ops` and appends message blocks.

Both agents use this one surface: the keyword router picks an action from the words, Claude picks one with a
tool call. No action approves, pays, signs or confirms an assumption: those stay with the person in the UI.
Every method returns a small dict (what happened, in facts) that the Claude agent sends back as the tool result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from app.chat import guardrail
from app.chat.ops import failure
from app.models import (
    BOMLine, CartEditRequest, ChatAction, ChatAssumption, ChatBlock, ChatCartStore, ChatCartSummary, ChatPartRow, ChatSession, Intake,
    RefusalRecord, RunState, UniversalCart,
)

__all__ = ["Session", "Turn", "find_line", "money", "TIER_LABEL"]

TIER_LABEL = {"cheapest": "cheapest", "fewest_checkouts": "fewest checkouts"}
MOCK_NOTE = "This is mock mode: the sample data doesn't change."
_NOTE = {"owned": "You have this", "not_found": "No acceptable offer found", "skipped": "Not needed for this build",
         "needs_human": "Needs your check", "warning": "Has a warning"}


def money(v: float | None) -> str:
    return "not quoted" if v is None else f"${v:,.2f}"


@dataclass
class Session:
    data: ChatSession
    refusals: list[RefusalRecord] = field(default_factory=list)


def _stems(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower().replace("_", " ")):
        if len(w) > 3 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


_STOP = _stems("the a an this that these those my your for of to it is why what which show me other others another different more "
               "use from at on in with and or i we have has own got already do does did not need want swap replace change remove drop "
               "make get buy part parts item items one some any all offer offers option options store stores please can you compare "
               "alternative alternatives choice chosen pick picked about tell there are was be been so just too also instead driver")


def find_line(state: RunState, phrase: str) -> BOMLine | None:
    """The BOM line a phrase names: a line id ("b3"), or the best word overlap with the line's name, category and spec."""
    m = re.search(r"\bb(\d{1,3})\b", phrase.lower())
    if m:
        hit = next((ln for ln in state.bom if ln.bom_line_id == f"b{m.group(1)}"), None)
        if hit is not None:
            return hit
    words = _stems(phrase) - _STOP
    if not words:
        return None
    best: tuple[float, BOMLine] | None = None
    for ln in state.bom:
        if ln.status == "removed":
            continue
        name = _stems(ln.raw_name)
        other = _stems(f"{ln.category or ''} {ln.spec or ''}")
        score = 2.0 * len(words & name) + 1.0 * len((words & other) - name)
        if score and ln.line_kind == "part":
            score += 0.25
        if score and (best is None or score > best[0]):
            best = (score, ln)
    return best[1] if best else None


class Turn:
    """One user message being answered: the blocks so far, and the actions that add to them."""

    def __init__(self, session: Session, ops: Any, *, text: str = "", link: str | None = None,
                 files: list[tuple[str, str | None, bytes]] | None = None) -> None:
        self.session, self.ops = session, ops
        self.text, self.link, self.files = text, link, files or []
        self.blocks: list[ChatBlock] = []
        self._state: RunState | None = None
        self.agent_used = "keyword"  # which implementation answered; the service sets it

    # ------------------------------------------------------------------ helpers

    @property
    def s(self) -> ChatSession:
        return self.session.data

    def say(self, text: str, tone: str | None = None, actions: list[ChatAction] | None = None) -> None:
        self.blocks.append(ChatBlock(kind="text", text=text, tone=tone, actions=actions or []))  # type: ignore[arg-type]

    def intake(self) -> Intake | None:
        return self.ops.get_intake(self.s.intake_id) if self.s.intake_id else None

    def state(self, fresh: bool = False) -> RunState | None:
        if not self.s.run_id:
            return None
        if self._state is None or fresh:
            try:
                self._state = self.ops.state(self.s.run_id)
            except HTTPException:
                self._state = None
        return self._state

    def _ready(self) -> RunState | None:
        """The run's state when it can be read or changed; otherwise says why not."""
        st = self.state(fresh=True)
        if st is None:
            if self.s.run_id:
                self.say("That run is no longer on the backend (it may have restarted). Start a new build to get a fresh cart.", "warn",
                         [ChatAction(kind="link", label="New build", href="/")])
            else:
                self.say("There's no cart yet. Sign the mandate first; the run starts as soon as you do.", "info")
                self.show_mandate()
            return None
        if st.status == "running":
            self.say("The run is still working. I'll post the parts as soon as it stops; changes wait until then.", "info")
            return None
        if st.status == "error":
            self.say("The run stopped with an error, so there's no cart to change. Start a new build to try again.", "warn",
                     [ChatAction(kind="link", label="Open 3D workspace", href=f"/run/{st.run_id}")])
            return None
        return st

    def _fail(self, exc: HTTPException, intake_override: Intake | None = None) -> dict[str, Any]:
        f = failure(exc)
        rec = None
        if f["refusal"]:
            try:
                rec = RefusalRecord.model_validate(f["refusal"])
            except Exception:
                rec = None
        if rec is not None:
            self.refused(rec, logged=True, intake_override=intake_override)
            return {"ok": False, "refused": rec.rule, "message": f["message"]}
        self.say(f["message"], "warn")
        return {"ok": False, "error": f["error"], "message": f["message"]}

    def refused(self, rec: RefusalRecord, *, logged: bool = False, intake_override: Intake | None = None) -> None:
        """A refusal block. `logged` means the backend function already wrote the refusal record."""
        self.session.refusals.append(rec)
        if not logged and self.s.run_id:
            try:
                self.ops.refuse(self.s.run_id, rec, guardrail.refusal_title(rec))
            except HTTPException:
                pass
        actions = []
        if self.s.run_id and rec.rule in ("approval_required", "action_allowed"):
            actions.append(ChatAction(kind="link", label="Review cart", href=f"/run/{self.s.run_id}/cart"))
        self.blocks.append(ChatBlock(kind="refusal", refusal=rec, text=guardrail.refusal_text(rec, has_cart=bool(self.s.run_id)), actions=actions))
        if rec.rule in guardrail.WIDENING_RULES and not any(b.kind == "mandate" for b in self.blocks):
            self.show_mandate(new=True, intake=intake_override)

    # ------------------------------------------------------------------ before the run

    async def start_request(self) -> dict[str, Any]:
        text = self.text.strip()
        if self.link and self.link not in text:
            text = f"{text} {self.link}".strip()
        try:
            it = await self.ops.intake(text or None, self.files)
        except HTTPException as exc:
            return self._fail(exc)
        self.s.intake_id, self.s.build_type = it.intake_id, it.build_type
        self._intake_blocks(it)
        return {"ok": True, "build_type": it.build_type, "confidence": it.confidence,
                "open_questions": [q.id for q in it.questions if not q.answer]}

    def _intake_blocks(self, it: Intake, lead: str | None = None) -> None:
        self.s.build_type = it.build_type
        self.blocks.append(ChatBlock(kind="build_type", intake=it, text=lead, simulated=it.simulated))
        if it.questions:
            self.blocks.append(ChatBlock(kind="questions", intake=it, simulated=it.simulated,
                                         actions=[ChatAction(kind="reply", label="Skip, use defaults", text="Use the defaults")]
                                         if any(not q.answer for q in it.questions) else []))
        self.show_mandate(intake=it)

    def show_mandate(self, new: bool = False, intake: Intake | None = None) -> dict[str, Any]:
        it = intake or self.intake()
        if it is None:
            self.say("Tell me what you want to build first: a sentence, a project link or a photo.", "info")
            return {"ok": False, "message": "no request yet"}
        open_q = any(not q.answer for q in it.questions)
        text = ("A new signed mandate starts a new run with these limits. Nothing changes until you sign." if new
                else "Sign the mandate to start the run." + (" Questions you leave open use their defaults." if open_q else ""))
        self.blocks.append(ChatBlock(kind="mandate", intake=it, text=text, simulated=it.simulated))
        return {"ok": True, "budget_usd": it.mandate_preset.budget_usd, "stores": it.mandate_preset.allowed_merchants}

    def _answers(self, values: dict[str, str], *, build_type: str | None = None, skip: bool | None = None, lead: str | None = None) -> dict[str, Any]:
        if not self.s.intake_id:
            self.say("Tell me what you want to build first: a sentence, a project link or a photo.", "info")
            return {"ok": False, "message": "no request yet"}
        try:
            it = self.ops.answers(self.s.intake_id, values, build_type, skip)
        except HTTPException as exc:
            return self._fail(exc)
        self._intake_blocks(it, lead)
        return {"ok": True, "ready": it.ready, "build_type": it.build_type, "answers": {q.id: q.answer for q in it.questions}}

    def answer_question(self, question_id: str, value: str) -> dict[str, Any]:
        return self._answers({question_id: value})

    def use_defaults(self) -> dict[str, Any]:
        return self._answers({}, skip=True)

    def set_build_type(self, build_type: str) -> dict[str, Any]:
        return self._answers({}, build_type=build_type, lead="Changed by you.")

    def set_request_budget(self, usd: float) -> dict[str, Any]:
        """Before signing: the budget the mandate form is prefilled with. Nothing is signed by this."""
        return self._answers({"budget": f"{usd:g}"}, lead=f"The mandate form now starts at {money(usd)}.")

    # ------------------------------------------------------------------ reading the run

    def part_rows(self, st: RunState) -> list[ChatPartRow]:
        rows = []
        for ln in st.bom:
            if ln.status == "removed":
                continue
            chosen = ln.chosen or []
            first = chosen[0] if chosen else None
            rows.append(ChatPartRow(
                bom_line_id=ln.bom_line_id, name=ln.raw_name, qty=ln.qty, status=ln.status, provenance=ln.provenance,
                store_id=first.store_id if first else None, store_name=first.store_name if first else None,
                action_level=first.action_level if first else None,
                line_usd=round(sum(c.price * c.packs for c in chosen), 2) if chosen else None,
                more_stores=max(0, (ln.stores_count or 0) - len({c.store_id for c in chosen})),
                note=(ln.owned_note if ln.status == "owned" and ln.owned_note else _NOTE.get(ln.status)) if not chosen else None,
                simulated=any(c.simulated for c in chosen) or st.simulated))
        return rows

    def _cart_summary(self, cart: UniversalCart, previous: float | None = None) -> ChatCartSummary:
        return ChatCartSummary(
            run_id=cart.run_id, state=cart.state, tier=cart.tier, total_usd=cart.total_usd, budget_usd=cart.budget_usd,
            previous_total_usd=previous if previous is not None and abs(previous - cart.total_usd) >= 0.005 else None,
            stores=[ChatCartStore(store_id=g.store_id, display_name=g.display_name, action_level=g.action_level, subtotal_usd=g.subtotal_usd,
                                  items=len(g.items)) for g in sorted(cart.stores, key=lambda g: g.order)],
            left_out=cart.left_out, open_assumptions=cart.open_assumptions, items_by_hand=cart.counts.items_by_hand, simulated=cart.simulated)

    def _links(self) -> list[ChatAction]:
        rid = self.s.run_id
        return [ChatAction(kind="link", label="Open 3D workspace", href=f"/run/{rid}"), ChatAction(kind="link", label="Review cart", href=f"/run/{rid}/cart")]

    def _cart_block(self, text: str | None = None, previous: float | None = None, actions: list[ChatAction] | None = None) -> UniversalCart | None:
        try:
            cart = self.ops.cart(self.s.run_id)
        except HTTPException as exc:
            self._fail(exc)
            return None
        self.blocks.append(ChatBlock(kind="cart", run_id=cart.run_id, cart=self._cart_summary(cart, previous), text=text,
                                     actions=actions if actions is not None else self._links(), simulated=cart.simulated))
        return cart

    def show_parts(self) -> dict[str, Any]:
        st = self._ready()
        if st is None:
            return {"ok": False}
        rows = self.part_rows(st)
        self.blocks.append(ChatBlock(kind="parts", run_id=st.run_id, parts=rows, simulated=st.simulated, actions=self._links()))
        return {"ok": True, "lines": [{"id": r.bom_line_id, "name": r.name, "store": r.store_name, "line_usd": r.line_usd, "status": r.status} for r in rows]}

    def show_cart(self) -> dict[str, Any]:
        if self._ready() is None:
            return {"ok": False}
        cart = self._cart_block()
        return {"ok": cart is not None, **({"total_usd": cart.total_usd, "stores": len(cart.stores), "open_assumptions": cart.open_assumptions} if cart else {})}

    def run_summary(self) -> None:
        """Posted once when a run stops: what was found, the parts, the cart and what is still open."""
        st = self.state(fresh=True)
        if st is None:
            return
        if st.status == "error":
            self.say("The run stopped with an error before a cart was ready. The timeline in the workspace says where.", "warn",
                     [ChatAction(kind="link", label="Open 3D workspace", href=f"/run/{st.run_id}")])
            return
        rows = self.part_rows(st)
        priced = [r for r in rows if r.line_usd is not None]
        plan = st.plans.get(st.active_tier)
        missing = [r.name for r in rows if r.status == "not_found"]
        text = f"I found offers for {len(priced)} of {len(rows)} lines"
        if plan:
            budget = st.mandate.constraints.budget_usd
            text += f" across {len(plan.stores)} store{'s' if len(plan.stores) != 1 else ''}: {money(plan.total_usd)}"
            text += (f", which is {money(plan.total_usd - budget)} over your {money(budget)} budget. It can't be approved until it fits."
                     if plan.total_usd > budget + 0.005 else f" of your {money(budget)} budget.")
        else:
            text += "."
        if missing:
            text += f" No acceptable offer for: {', '.join(missing)}."
        if st.refusals:
            text += f" {st.refusals} request{'s were' if st.refusals != 1 else ' was'} refused under your mandate."
        if st.simulated:
            text += " Store data here is simulated."
        self.say(text, "ok")
        self.blocks.append(ChatBlock(kind="parts", run_id=st.run_id, parts=rows, simulated=st.simulated))
        replies = [ChatAction(kind="reply", label="Make it cheaper", text="Make it cheaper"),
                   ChatAction(kind="reply", label="Fewest stores", text="Fewest stores")]
        if st.open_assumptions:
            replies.append(ChatAction(kind="reply", label="What's left to confirm?", text="What's left to confirm?"))
        self._cart_block(actions=self._links() + replies)

    def _panel(self, st: RunState, bom_line_id: str) -> Any:
        if not any(ln.bom_line_id == bom_line_id for ln in st.bom):
            self.say(f"There's no line {bom_line_id} in this parts list.", "warn")
            return None
        try:
            return self.ops.panel(st.run_id, bom_line_id)
        except HTTPException as exc:
            self._fail(exc)
            return None

    def compare_offers(self, bom_line_id: str) -> dict[str, Any]:
        st = self._ready()
        panel = self._panel(st, bom_line_id) if st else None
        if panel is None:
            return {"ok": False}
        count = {k: sum(o.status == k for o in panel.offers) for k in ("chosen", "alternative", "rejected", "refused")}
        if not panel.offers:
            text = f"No offers were found for {panel.name} in the stores your mandate allows."
        else:
            bits = [f"{count['chosen']} chosen", f"{count['alternative']} other acceptable"]
            if count["rejected"]:
                bits.append(f"{count['rejected']} rejected by a check")
            if count["refused"]:
                bits.append(f"{count['refused']} refused under your mandate")
            text = f"{len(panel.offers)} offer{'s' if len(panel.offers) != 1 else ''} for {panel.name}: {', '.join(bits)}."
        self.blocks.append(ChatBlock(kind="comparison", run_id=st.run_id, panel=panel, text=text, simulated=panel.simulated,
                                     actions=[ChatAction(kind="link", label="Open 3D workspace", href=f"/run/{st.run_id}")]))
        return {"ok": True, "name": panel.name, **count,
                "offers": [{"offer_id": o.offer_id, "store": o.store_name, "status": o.status, "line_usd": o.line_usd, "reason": o.reason} for o in panel.offers[:12]]}

    def explain_choice(self, bom_line_id: str) -> dict[str, Any]:
        st = self._ready()
        panel = self._panel(st, bom_line_id) if st else None
        if panel is None:
            return {"ok": False}
        text = panel.why.explanation
        if not any(o.status == "chosen" for o in panel.offers) and panel.status == "not_found":
            text = f"Nothing is chosen for {panel.name}: no acceptable offer was found in the stores your mandate allows. " + (text or "")
        self.blocks.append(ChatBlock(kind="why", run_id=st.run_id, panel=panel, text=text.strip(), simulated=panel.simulated,
                                     actions=[ChatAction(kind="reply", label="Show other offers", text=f"Show me other offers for {panel.name} ({bom_line_id})")]))
        return {"ok": True, "name": panel.name, "explanation": text, "reason_codes": panel.why.reason_codes}

    def show_open_assumptions(self) -> dict[str, Any]:
        st = self._ready()
        if st is None:
            return {"ok": False}
        rows = []
        for ln in st.bom:
            if ln.bom_line_id in st.open_assumptions and ln.provenance.type == "assumption":
                rows.append(ChatAssumption(bom_line_id=ln.bom_line_id, name=ln.raw_name, qty=ln.qty, spec=ln.spec,
                                           statement=ln.provenance.statement, basis=ln.provenance.basis))
        if not rows:
            self.say("Nothing is left to confirm. The cart can be approved from Review cart.", "ok", self._links())
            return {"ok": True, "open": []}
        self.blocks.append(ChatBlock(
            kind="assumptions", run_id=st.run_id, assumptions=rows, simulated=st.simulated,
            text=f"{len(rows)} assumption{'s' if len(rows) != 1 else ''} to confirm before the cart can be approved. "
                 "Confirming is yours to do: I can't confirm my own assumptions."))
        return {"ok": True, "open": [{"id": r.bom_line_id, "name": r.name, "statement": r.statement} for r in rows]}

    # ------------------------------------------------------------------ changing the plan (inside the signed mandate)

    def _total(self) -> float | None:
        try:
            return self.ops.cart(self.s.run_id).total_usd
        except HTTPException:
            return None

    def switch_tier(self, tier: str) -> dict[str, Any]:
        st = self._ready()
        if st is None:
            return {"ok": False}
        before = self._total()
        same = st.active_tier == tier
        try:
            self.ops.replan(st.run_id, tier, None)
        except HTTPException as exc:
            return self._fail(exc)
        after = self.state(fresh=True)
        plan = after.plans.get(tier) if after else None
        label = TIER_LABEL.get(tier, tier.replace("_", " "))
        if plan is None:
            self.say(f"There is no {label} plan for this run.", "warn")
            return {"ok": False}
        stores = f"{len(plan.stores)} store{'s' if len(plan.stores) != 1 else ''}"
        if same or before is None or abs(before - plan.total_usd) < 0.005:
            text = (f"The {label} plan is {'already active' if same else 'now active'}: {money(plan.total_usd)} across {stores}. "
                    + ("With the offers found it can't go lower." if tier == "cheapest" else "The total is the same as before."))
        else:
            text = f"Switched to the {label} plan: {money(plan.total_usd)} across {stores} (was {money(before)})."
        if self.ops.mock:
            text += " " + MOCK_NOTE
        self._cart_block(text, before)
        return {"ok": True, "tier": tier, "total_usd": plan.total_usd, "previous_total_usd": before, "stores": plan.stores}

    async def mark_owned(self, bom_line_id: str) -> dict[str, Any]:
        st = self._ready()
        if st is None:
            return {"ok": False}
        ln = next((x for x in st.bom if x.bom_line_id == bom_line_id), None)
        if ln is None:
            self.say(f"There's no line {bom_line_id} in this parts list.", "warn")
            return {"ok": False}
        if ln.status == "owned":
            self.say(f"{ln.raw_name} is already marked as owned and left out of the cart.", "info")
            return {"ok": True, "already": True}
        before = self._total()
        try:
            await self.ops.owned(st.run_id, bom_line_id, "You said in chat you have this")
        except HTTPException as exc:
            return self._fail(exc)
        text = f"Marked as owned: {ln.raw_name}. It's left out of the cart" + ("." if self.ops.mock else ", and noted so later runs know you have it.")
        if self.ops.mock:
            text += " " + MOCK_NOTE
        cart = self._cart_block(text, before)
        return {"ok": True, "name": ln.raw_name, "total_usd": cart.total_usd if cart else None, "previous_total_usd": before}

    async def edit_cart(self, op: str, bom_line_id: str, store_id: str | None = None, qty: int | None = None, offer_id: str | None = None) -> dict[str, Any]:
        st = self._ready()
        if st is None:
            return {"ok": False}
        ln = next((x for x in st.bom if x.bom_line_id == bom_line_id), None)
        if ln is None:
            self.say(f"There's no line {bom_line_id} in this parts list.", "warn")
            return {"ok": False}
        if op == "swap_offer" and not offer_id:
            panel = self._panel(st, bom_line_id)
            if panel is None:
                return {"ok": False}
            alts = sorted((o for o in panel.offers if o.status == "alternative" and (not store_id or o.store_id == store_id)), key=lambda o: o.line_usd)
            if not alts:
                self.say(f"There's no other acceptable offer for {ln.raw_name} to swap to. Here is everything that was found.", "info")
                self.blocks.append(ChatBlock(kind="comparison", run_id=st.run_id, panel=panel, simulated=panel.simulated))
                return {"ok": False, "message": "no alternative offer"}
            offer_id = alts[0].offer_id
        before = self._total()
        try:
            await self.ops.cart_edit(st.run_id, CartEditRequest(op=op, bom_line_id=bom_line_id, offer_id=offer_id, store_id=store_id, qty=qty))  # type: ignore[arg-type]
        except HTTPException as exc:
            return self._fail(exc)
        after = self.state(fresh=True)
        now = next((x for x in (after.bom if after else []) if x.bom_line_id == bom_line_id), None)
        where = ", ".join(sorted({c.store_name for c in (now.chosen or [])})) if now else ""
        verb = {"swap_offer": f"Swapped the offer for {ln.raw_name}", "move_store": f"Moved {ln.raw_name}", "remove": f"Removed {ln.raw_name} from the cart",
                "restore": f"Put {ln.raw_name} back", "set_qty": f"Set {ln.raw_name} to {qty}"}.get(op, f"Edited {ln.raw_name}")
        text = verb + (f": now from {where}." if where and op != "remove" else ".") + " The rest of the plan was re-checked around it."
        if self.ops.mock:
            text += " " + MOCK_NOTE
        cart = self._cart_block(text, before)
        return {"ok": True, "op": op, "name": ln.raw_name, "now_from": where, "total_usd": cart.total_usd if cart else None, "previous_total_usd": before}

    async def set_variant(self, question_id: str, value: str) -> dict[str, Any]:
        """Re-answer a chip question on a run and redo the steps that depend on it."""
        st = self._ready()
        if st is None:
            return {"ok": False}
        q = next((q for q in st.intake.questions if q.id == question_id), None)
        chip = next((c for c in (q.chips if q else []) if c.value == value), None)
        if chip is None:
            self.say("That isn't one of the choices for this build.", "warn")
            return {"ok": False, "message": "unknown choice"}
        try:
            await self.ops.variant(st.run_id, f"{question_id}_{value}")
        except HTTPException as exc:
            return self._fail(exc)
        if self.ops.mock:
            self.say(f"You picked {chip.label}. {MOCK_NOTE}", "info")
            return {"ok": True, "rerun": False}
        self.s.awaiting_summary = True
        self.blocks.append(ChatBlock(kind="progress", run_id=st.run_id, text=f"Re-running with {chip.label}. Parts, offers and checks are redone."))
        return {"ok": True, "rerun": True, "choice": chip.label}

    def set_budget_cap(self, usd: float) -> dict[str, Any]:
        """Plan under a lower cap. A cap above the signed budget is refused: that needs a new signed mandate."""
        st = self._ready()
        if st is None:
            return {"ok": False}
        if usd <= 0:
            self.say("A budget has to be more than zero.", "warn")
            return {"ok": False}
        before = self._total()
        wider = None
        it = self.intake()
        if it is not None:
            wider = it.model_copy(deep=True)
            wider.mandate_preset.budget_usd = usd
            wider.constraints.budget_usd = usd
        try:
            self.ops.replan(st.run_id, st.active_tier, usd)
        except HTTPException as exc:
            return self._fail(exc, intake_override=wider)
        after = self.state(fresh=True)
        plan = after.plans.get(after.active_tier) if after else None
        signed = st.mandate.constraints.budget_usd
        if plan is not None and (not plan.feasible or plan.over_budget_by):
            text = (f"Nothing fits under {money(usd)}: the {TIER_LABEL.get(plan.tier, plan.tier)} plan is {money(plan.total_usd)}"
                    + (f", {money(plan.over_budget_by)} over." if plan.over_budget_by else ".") + " Mark parts you already have, or remove some, to get under it.")
        else:
            text = f"Planned under a {money(usd)} cap (your signed budget is {money(signed)})."
        if self.ops.mock:
            text += " " + MOCK_NOTE
        self._cart_block(text, before)
        return {"ok": True, "cap_usd": usd, "total_usd": plan.total_usd if plan else None, "feasible": plan.feasible if plan else None}
