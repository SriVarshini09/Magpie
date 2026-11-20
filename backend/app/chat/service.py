"""Chat sessions for the start page: in memory, linked to an intake and a run.

Order of a message: redact buyer details -> the guard (`guardrail.precheck`, in code, both agents) -> the
agent (keyword router, or Claude with tools when a key is set) -> the run summary if a run just stopped.
Signing a mandate and resolving an assumption are separate endpoints: they are the person's own UI actions.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from app.chat import guardrail
from app.chat.actions import Session, Turn, money
from app.chat.ops import LiveOps, MockOps, draft_mandate
from app.chat.router import KeywordAgent
from app.config import get_settings
from app.models import (
    AssumptionRequest, ChatBlock, ChatMessage, ChatSendResponse, ChatSession, ChatSessionSummary, DataSharing, MandatePreset, RunSummary,
)
from app.runstate import new_id, now_iso

__all__ = ["create_session", "list_sessions", "get_session", "send", "sign_mandate", "sync", "resolve_assumption", "list_runs", "SESSIONS"]

SESSIONS: dict[str, Session] = {}
AGENT_OVERRIDE: Any = None  # tests set an agent here
_URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
MAX_TEXT = 4000


def _err(status: int, error: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": error, "message": message, "bom_line_ids": []})


def ops() -> Any:
    if get_settings().is_mock:
        from app import main

        return MockOps(main.mock)
    return LiveOps()


def pick_agent() -> Any:
    """Claude when a key is set and the service is live; otherwise the keyword router."""
    if AGENT_OVERRIDE is not None:
        return AGENT_OVERRIDE
    if not get_settings().is_mock:
        try:
            from app import registry
            from app.integrations import anthropic_client

            llm = registry.get("anthropic")
            if hasattr(llm, "_create") and anthropic_client.has_credentials():
                from app.chat.claude_agent import ClaudeAgent

                return ClaudeAgent(llm)
        except Exception:
            pass
    return KeywordAgent()


def _session(session_id: str) -> Session:
    s = SESSIONS.get(session_id)
    if s is None:
        raise _err(404, "session_not_found", f"No chat session {session_id}. Sessions live in memory; the backend may have restarted.")
    return s


def _refresh(s: Session, o: Any) -> None:
    d = s.data
    agent = pick_agent()
    d.agent, d.agent_label = agent.kind, agent.label
    d.message_count = len(d.messages)
    if d.run_id:
        try:
            st = o.state(d.run_id)
            d.status, d.build_type, d.simulated = st.status, st.build_type, st.simulated
        except HTTPException:
            d.status = None


def _summary(s: Session) -> ChatSessionSummary:
    return ChatSessionSummary(**{k: getattr(s.data, k) for k in ChatSessionSummary.model_fields})


def _response(s: Session, new: list[ChatMessage], o: Any) -> ChatSendResponse:
    s.data.updated_at = now_iso() if new else s.data.updated_at
    _refresh(s, o)
    return ChatSendResponse(session=_summary(s), messages=new, awaiting_summary=s.data.awaiting_summary, agent=s.data.agent, agent_label=s.data.agent_label)


def _agent_message(blocks: list[ChatBlock], kind: str) -> ChatMessage:
    return ChatMessage(message_id=new_id("cm"), role="agent", ts=now_iso(), blocks=blocks, agent=kind)  # type: ignore[arg-type]


def create_session(reference_search: bool = True) -> ChatSession:
    now = now_iso()
    s = Session(ChatSession(session_id=new_id("c"), title="New build", created_at=now, updated_at=now, reference_search=reference_search))
    SESSIONS[s.data.session_id] = s
    _refresh(s, ops())
    return s.data


def list_sessions() -> list[ChatSessionSummary]:
    o = ops()
    out = []
    for s in SESSIONS.values():
        if not s.data.messages:
            continue  # an untouched "New build" is not a conversation yet
        _refresh(s, o)
        out.append(_summary(s))
    return sorted(out, key=lambda x: x.updated_at, reverse=True)


def get_session(session_id: str) -> ChatSession:
    s = _session(session_id)
    _refresh(s, ops())
    return s.data


def list_runs() -> list[RunSummary]:
    return ops().runs()


def _title(text: str, link: str | None, photos: int) -> str:
    plain = _URL.sub("", text).strip(" ,.;:")
    if plain:
        return plain[:60] + ("…" if len(plain) > 60 else "")
    if link:
        m = re.search(r"github\.com/([^/\s]+/[^/\s#?]+)", link)
        return (m.group(1) if m else re.sub(r"^https?://(www\.)?", "", link))[:60]
    return "Photo request" if photos else "New build"


def _guard_mandate(turn: Turn) -> Any:
    st = turn.state()
    if st is not None:
        return st.mandate
    it = turn.intake()
    if it is not None:
        return draft_mandate(it.mandate_preset, it.build_type)
    try:
        from app.intake import classify

        return draft_mandate(classify.mandate_preset("generic"))
    except Exception:
        return draft_mandate(MandatePreset(budget_usd=1, deadline="1970-01-01", allowed_merchants=[], data_sharing=DataSharing()))


async def send(session_id: str, text: str | None, link: str | None, files: list[tuple[str, str | None, bytes]],
               reference_search: bool | None = None) -> ChatSendResponse:
    s, o = _session(session_id), ops()
    raw = (text or "").strip()[:MAX_TEXT]
    link = (link or "").strip() or None
    if link and not re.match(r"https?://", link, re.I):
        raise _err(422, "bad_link", "A link has to start with http:// or https://")
    if not raw and not link and not files:
        raise _err(422, "empty_message", "Type a message, paste a link, or add a photo")
    if reference_search is not None:
        s.data.reference_search = reference_search
    clean, redacted = guardrail.redact(raw)
    if link is None:
        m = _URL.search(clean)
        link = m.group(0).rstrip(".,;:!?") if m else None
    if not s.data.messages:
        s.data.title = _title(clean, link, len(files))
    user = ChatMessage(message_id=new_id("cm"), role="user", ts=now_iso(), text=clean or None, link=link)
    s.data.messages.append(user)

    agent = pick_agent()
    turn = Turn(s, o, text=clean, link=link, files=files)
    turn.agent_used = agent.kind
    if s.data.run_id and clean:
        try:
            o.note_user_message(s.data.run_id, clean)
        except HTTPException:
            pass
    known = None
    try:
        known = o.store_words(s.data.run_id)
    except Exception:
        known = None
    refusals = guardrail.precheck(_guard_mandate(turn), raw, known_stores=known)
    if refusals:
        for r in refusals:  # refused in code: the agent never sees this message
            turn.refused(r)
        if redacted:
            turn.say("The personal details in that message were left out of this conversation's record.", "info")
    else:
        try:
            await agent.respond(turn)
        except HTTPException as exc:
            turn._fail(exc)
        if not turn.blocks:
            turn.say("I couldn't act on that. Try one of the suggestions, or rephrase it.", "warn")
    intake = turn.intake()
    if files and intake is not None and intake.inputs.images:
        user.images = list(intake.inputs.images)
    _finish(turn)
    reply = _agent_message(turn.blocks, turn.agent_used)
    s.data.messages.append(reply)
    return _response(s, [user, reply], o)


def _finish(turn: Turn) -> None:
    """If a run this session is waiting on has stopped, post its summary (once)."""
    d = turn.s
    if not d.awaiting_summary or not d.run_id:
        return
    st = turn.state(fresh=True)
    if st is None:
        d.awaiting_summary = False
        return
    if st.status != "running":
        d.awaiting_summary = False
        turn.run_summary()


async def sign_mandate(session_id: str, preset: MandatePreset) -> ChatSendResponse:
    """The Sign button in the chat. A person's action: neither agent has a tool or an intent that reaches it."""
    s, o = _session(session_id), ops()
    if not s.data.intake_id:
        raise _err(409, "no_request", "Describe what you want to build before signing a mandate")
    again = s.data.run_id is not None
    run_id = await o.create_run(s.data.intake_id, preset, s.data.reference_search)
    s.data.run_id = run_id
    turn = Turn(s, o)
    st = turn.state(fresh=True)
    sig = st.mandate.signature if st else None
    signed = bool(sig and sig.alg != "none" and sig.jws not in ("", "unsigned"))
    n = len(preset.allowed_merchants)
    head = "Sample mandate (mock mode)" if o.mock else ("Mandate signed" if signed else "Mandate recorded (signing is not connected)")
    text = (f"{head}: {money(preset.budget_usd)} budget, {n} store{'s' if n != 1 else ''}"
            + ("" if s.data.reference_search else ", no reference search")
            + (". This is a new run under the new mandate; the earlier run is unchanged." if again else ".")
            + " I can search and build carts inside these limits. I can't check out or pay.")
    turn.say(text, "ok")
    turn.blocks.append(ChatBlock(kind="progress", run_id=run_id, simulated=bool(st and st.simulated)))
    s.data.awaiting_summary = True
    _finish(turn)
    reply = _agent_message(turn.blocks, pick_agent().kind)
    s.data.messages.append(reply)
    return _response(s, [reply], o)


async def sync(session_id: str) -> ChatSendResponse:
    """Called by the page when the run's event stream says it stopped: posts the summary if one is due."""
    s, o = _session(session_id), ops()
    turn = Turn(s, o)
    _finish(turn)
    if not turn.blocks:
        return _response(s, [], o)
    reply = _agent_message(turn.blocks, pick_agent().kind)
    s.data.messages.append(reply)
    return _response(s, [reply], o)


async def resolve_assumption(session_id: str, body: AssumptionRequest) -> ChatSendResponse:
    """Confirm / Edit / Remove on an assumption card. The person's own action (the agent cannot confirm its assumptions)."""
    s, o = _session(session_id), ops()
    if not s.data.run_id:
        raise _err(409, "no_run", "There is no run in this conversation yet")
    turn = Turn(s, o)
    before = turn.state(fresh=True)
    name = next((ln.raw_name for ln in (before.bom if before else []) if ln.bom_line_id == body.bom_line_id), body.bom_line_id)
    await o.assumption(s.data.run_id, body)
    verb = {"confirm": "Confirmed by you", "edit": "Edited and confirmed by you", "remove": "Removed by you"}[body.action]
    turn.say(f"{verb}: {name}." + (" " + "This is mock mode: only the sample's flag changes." if o.mock else ""), "ok")
    after = turn.state(fresh=True)
    if after is not None and after.open_assumptions:
        turn.show_open_assumptions()
    elif after is not None:
        turn._cart_block("Nothing is left to confirm. The cart can be approved from Review cart.")
    reply = _agent_message(turn.blocks, pick_agent().kind)
    s.data.messages.append(reply)
    return _response(s, [reply], o)
