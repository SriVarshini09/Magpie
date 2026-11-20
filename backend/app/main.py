"""FastAPI app: every endpoint of PLAN §4.2, plus SSE and the photo upload.

SCAFFOLD STATE: in mock mode (DEMO_MODE=mock, the default) each route answers from fixtures
through app/mock_backend.py. In any other mode a route returns 501 with the owner's TODO until
that owner replaces its body. Route owners (PLAN §4.2) are in each route's `live(...)` call.

Shared file. A owns it during the build (PLAN §4.1); B and D ask A for the edits to their routes,
or hand A a router to include.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from app import fixtures, registry
from app.config import FIXTURES_DIR, get_settings
from app.mock_backend import MockBackend, api_error
from app.models import (
    Accepted, ApproveRequest, ApproveResponse, AssumptionRequest, CartEditRequest, CartItemAddedRequest, CartRefreshResponse,
    ChatCreateRequest, ChatSendResponse, ChatSession, ChatSessionSummary, MandatePreset, RunSummary,
    CreateRunRequest, CreateRunResponse, DataStats, HandoffUpdateRequest, Health, Intake, IntakeAnswersRequest,
    KbSearchResponse, MessageRequest, OwnedRequest, PartPanel, PayFanoutRequest, PayIntentRequest,
    PayIntentResponse, PricesResponse, ProjectSample, Receipt, ReplanRequest, ReplanResponse, RunState,
    StoreInfo, UniversalCart, VariantRequest, VerifyResult,
)
from app.models import ForgetRequest, ForgetResponse, MemoryResponse

mock = MockBackend()
_background: set[asyncio.Task[Any]] = set()  # keeps fire-and-forget tasks alive until they finish


def is_mock() -> bool:
    return get_settings().is_mock


def svc() -> Any:
    """A's live handlers (app/agent/service.py). Imported lazily so mock mode never needs them."""
    from app.agent import service

    service.install_hooks()
    return service


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()  # raises on a bad DEMO_MODE or a non-test Stripe key: the backend refuses to start
    if not get_settings().is_mock:
        try:  # B's reference provider 3 (Claude web search); the reference search skips it when no key is set
            from app.intake import claude_search

            claude_search.register()
        except Exception:
            pass
    yield
    for name in ("amplitude", "statsig"):  # D's clients: flush what is queued; a stub or a mock is fine here
        try:
            registry.get(name).shutdown()
        except Exception:
            pass


app = FastAPI(title="Build-to-Cart API", version="0.0.1", lifespan=lifespan)


@app.exception_handler(NotImplementedError)
async def not_implemented(_: Request, exc: NotImplementedError) -> Response:
    """A route whose owner's module is still a stub answers 501 with that owner's TODO."""
    from fastapi.responses import JSONResponse

    text = str(exc)
    return JSONResponse(status_code=501, content={"detail": {"error": "not_implemented", "message": "This endpoint has no live implementation yet.",
                                                             "todo": text if text.startswith("TODO(") else f"TODO: {text[:200]}"}})


try:  # B's cart errors are HTTP-shaped: {"detail": ApiError}
    from fastapi.responses import JSONResponse as _JSON

    from app.checkout.cart import CartError as _CartError

    @app.exception_handler(_CartError)
    async def cart_error(_: Request, exc: Any) -> Response:
        return _JSON(status_code=exc.status, content={"detail": exc.detail()})
except (ImportError, AttributeError):  # B's module is still a stub
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-B2C-Mode", "X-B2C-Mock"],
)


@app.middleware("http")
async def label_mode(request: Request, call_next: Any) -> Response:
    """Every response says which mode produced it, so the UI can show the "Mock data" badge."""
    response = await call_next(request)
    response.headers["X-B2C-Mode"] = get_settings().demo_mode
    response.headers["X-B2C-Mock"] = "true" if registry.any_mock() else "false"
    return response


def live(owner: str, plan: str) -> MockBackend:
    """Return the mock backend in mock mode; otherwise 501 with the owner's TODO.

    Builders: replace the route body with the real implementation and keep the mock branch.
    """
    if get_settings().is_mock:
        return mock
    raise api_error(501, "not_implemented", "This endpoint has no live implementation yet.", todo=f"TODO({owner}) — PLAN {plan}")


# ----------------------------------------------------------------------------- health, catalogues


@app.get("/health", response_model=Health)
@app.get("/api/health", response_model=Health)
async def health() -> dict[str, Any]:
    """Per-integration and per-store state. `ok` means configured; `off` means no key or still a stub."""
    s = get_settings()
    integrations, store_states = svc().health_states()
    used = 0
    try:  # B's counter (stores/serpapi.py), when it exists
        used = int(getattr(registry.get("serpapi"), "used", 0) or 0)
    except Exception:
        used = 0
    return {"mode": s.demo_mode, "mock": registry.any_mock(), "pay_tier": s.pay_tier, "serpapi_used": used,
            "integrations": integrations, "stores": store_states, "impl": registry.modes()}


@app.get("/api/projects", response_model=list[ProjectSample])
async def projects() -> Any:
    if is_mock():
        return fixtures.load("projects.json")
    return svc().projects()


@app.get("/api/stores", response_model=list[StoreInfo])
async def stores() -> Any:
    if is_mock():
        return fixtures.load("stores.json")
    from app.stores import registry as store_registry  # B

    return store_registry.stores()


# ----------------------------------------------------------------------------- intake


@app.post("/api/intake", response_model=Intake)
async def post_intake(
    text: str | None = Form(default=None),
    run_id: str | None = Form(default=None),
    images: list[UploadFile] = File(default=[]),
    images_bracket: list[UploadFile] = File(default=[], alias="images[]"),
) -> Any:
    """Multipart: `text?`, `images` (or `images[]`), `run_id?`. 422 for a bad file, 409 for a never-request host."""
    files = [*images, *images_bracket]
    bodies = [(f.filename or "upload", f.content_type, await f.read()) for f in files]
    if is_mock():
        return mock.intake(text, [(n, c, len(b)) for n, c, b in bodies])
    return await svc().intake(text, bodies, run_id)


@app.post("/api/intake/{intake_id}/answers", response_model=Intake)
async def post_answers(intake_id: str, body: IntakeAnswersRequest) -> Any:
    if is_mock():
        return mock.answers(intake_id, body.answers, body.build_type, body.skip_defaults)
    return svc().answers(intake_id, body.answers, body.build_type, body.skip_defaults)


@app.get("/api/uploads/{image_id}")
async def get_upload(image_id: str) -> Response:
    """The resized image, same origin, no cache headers."""
    if not image_id.replace("_", "").isalnum():
        raise api_error(404, "image_not_found", "No such image")
    if is_mock():
        path = FIXTURES_DIR / "uploads" / f"{image_id}.jpg"
    else:
        from app.intake import uploads

        path = uploads.find_upload(image_id)
    if path is None or not path.is_file():
        raise api_error(404, "image_not_found", "No such image")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ----------------------------------------------------------------------------- runs


@app.post("/api/runs", response_model=CreateRunResponse)
async def create_run(body: CreateRunRequest) -> Any:
    if is_mock():
        return mock.create_run(body.intake_id, body.source_url)
    return await svc().create_run(body)


@app.get("/api/runs/{run_id}", response_model=RunState)
async def get_run(run_id: str) -> Any:
    if is_mock():
        return mock.run(run_id)
    return svc().get_run(run_id)


@app.get("/api/runs/{run_id}/events")
async def run_events(
    run_id: str,
    request: Request,
    after: int = Query(default=0, description="Send only events with seq greater than this"),
    delay_ms: int | None = Query(default=None, ge=0, le=5000, description="Mock: pause between events"),
    close: bool = Query(default=False, description="Mock: end the stream after the last fixture event"),
    last_event_id: str | None = Header(default=None),
) -> EventSourceResponse:
    """SSE: one `message` per `Event`, JSON in `data`, `id` = seq. Mock mode replays the fixture timeline."""
    start = max(after, int(last_event_id) if last_event_id and last_event_id.isdigit() else 0)
    if not is_mock():
        run = svc().run_or_404(run_id)

        async def live_stream() -> AsyncIterator[dict[str, str]]:
            """Events as the tool wrapper emits them. `close` ends the stream once the run stops moving."""
            sent = start
            while True:
                for ev in list(run.events[sent:]):
                    sent = ev.seq
                    yield {"id": str(ev.seq), "data": json.dumps(ev.model_dump(mode="json", exclude_none=True), ensure_ascii=False)}
                if close and run.status != "running":
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.2)

        return EventSourceResponse(live_stream(), headers={"X-B2C-Mode": get_settings().demo_mode})
    events = mock.events(run_id)
    delay = (get_settings().mock_sse_delay_ms if delay_ms is None else delay_ms) / 1000

    async def stream() -> AsyncIterator[dict[str, str]]:
        for ev in events:
            if ev["seq"] <= start:
                continue
            if delay:
                await asyncio.sleep(delay)
            yield {"id": str(ev["seq"]), "data": json.dumps(ev, ensure_ascii=False)}
        while not close and not await request.is_disconnected():
            await asyncio.sleep(1)  # stay open like a live run; sse-starlette sends the keep-alive pings

    return EventSourceResponse(stream(), headers={"X-B2C-Mode": get_settings().demo_mode})


@app.post("/api/runs/{run_id}/assumptions", response_model=RunState)
async def post_assumption(run_id: str, body: AssumptionRequest) -> Any:
    """A UI action. The agent cannot confirm its own assumptions (PLAN §3.6)."""
    if is_mock():
        return mock.assumption(run_id, body.bom_line_id, body.action, body.spec, body.qty)
    return await svc().assumption(run_id, body)


@app.get("/api/runs/{run_id}/parts/{bom_line_id}", response_model=PartPanel)
async def get_part_panel(run_id: str, bom_line_id: str) -> Any:
    if is_mock():
        return mock.panel(run_id, bom_line_id)
    return svc().get_panel(run_id, bom_line_id)


@app.get("/api/runs/{run_id}/prices/{bom_line_id}", response_model=PricesResponse)
async def get_prices(run_id: str, bom_line_id: str) -> Any:
    if is_mock():
        mock.line(run_id, bom_line_id)
        return await registry.get("singlestore").prices(run_id, bom_line_id)
    svc().line_or_404(svc().run_or_404(run_id), bom_line_id)
    from app.audit import api as d_api  # D

    return await d_api.prices_body(run_id, bom_line_id)


@app.get("/api/kb/search", response_model=KbSearchResponse)
async def kb_search(q: str = Query(min_length=1)) -> Any:
    if is_mock():
        return await registry.get("singlestore").hybrid_search(q)
    from app.audit import api as d_api  # D

    return await d_api.kb_search_body(q)


@app.get("/api/data/stats", response_model=DataStats)
async def data_stats() -> Any:
    """The Data drawer: row counts per table, KB rows by kind, the last query, the SIE call table (owner D)."""
    from app.audit import api as d_api  # D; the mock store answers in mock mode

    body = d_api.data_stats_body()
    lq = body.get("last_query")
    return {**{k: v for k, v in body.items() if k in DataStats.model_fields},
            "last_query": {k: lq[k] for k in ("sql", "took_ms", "at")} if lq else None}


@app.post("/api/runs/{run_id}/message", response_model=Accepted, status_code=202)
async def post_message(run_id: str, body: MessageRequest) -> Any:
    """Chat and the attack presets. Chat approves nothing (PLAN §3.6)."""
    if is_mock():
        mock.run(run_id)
        return {"accepted": True, "simulated": True}
    await svc().message(run_id, body.text)
    return {"accepted": True, "simulated": False}


@app.post("/api/runs/{run_id}/owned", response_model=Accepted, status_code=202)
async def post_owned(run_id: str, body: OwnedRequest) -> Any:
    if is_mock():
        mock.line(run_id, body.bom_line_id)
        return {"accepted": True, "simulated": True}
    await svc().owned(run_id, body.bom_line_id, body.owned, body.note)
    return {"accepted": True, "simulated": False}


@app.post("/api/runs/{run_id}/variant", response_model=Accepted, status_code=202)
async def post_variant(run_id: str, body: VariantRequest) -> Any:
    if is_mock():
        mock.run(run_id)
        return {"accepted": True, "simulated": True}
    await svc().variant(run_id, body.option)
    return {"accepted": True, "simulated": False}


@app.post("/api/runs/{run_id}/replan", response_model=ReplanResponse)
async def post_replan(run_id: str, body: ReplanRequest) -> Any:
    """A UI action: it can only tighten the plan inside the signed mandate. 422 if the cap exceeds it."""
    if is_mock():
        return mock.replan(run_id, body.tier, body.budget_cap_usd)
    return svc().replan(run_id, body.tier, body.budget_cap_usd)


# ----------------------------------------------------------------------------- chat (the start page)
# Sessions live in memory. Chat can refine a cart through the existing functions; it can never approve, pay or
# widen a mandate (app/chat/guardrail.py). Signing and assumption buttons are the person's own actions.


def chat() -> Any:
    from app.chat import service as chat_service

    return chat_service


@app.get("/api/runs", response_model=list[RunSummary])
async def list_runs() -> Any:
    """Runs this backend knows (in memory), newest first: the Library, Carts and Receipts lists."""
    return chat().list_runs()


@app.post("/api/chat/sessions", response_model=ChatSession)
async def chat_create(body: ChatCreateRequest | None = None) -> Any:
    return chat().create_session(body.reference_search if body else True)


@app.get("/api/chat/sessions", response_model=list[ChatSessionSummary])
async def chat_list() -> Any:
    return chat().list_sessions()


@app.get("/api/chat/sessions/{session_id}", response_model=ChatSession)
async def chat_get(session_id: str) -> Any:
    return chat().get_session(session_id)


@app.post("/api/chat/sessions/{session_id}/messages", response_model=ChatSendResponse)
async def chat_send(
    session_id: str,
    text: str | None = Form(default=None),
    link: str | None = Form(default=None),
    reference_search: bool | None = Form(default=None),
    images: list[UploadFile] = File(default=[]),
    images_bracket: list[UploadFile] = File(default=[], alias="images[]"),
) -> Any:
    """Multipart: `text?`, `link?`, `images` (the intake's upload rules), `reference_search?`. Returns the new messages."""
    files = [*images, *images_bracket]
    bodies = [(f.filename or "upload", f.content_type, await f.read()) for f in files]
    return await chat().send(session_id, text, link, bodies, reference_search)


@app.post("/api/chat/sessions/{session_id}/mandate", response_model=ChatSendResponse)
async def chat_sign(session_id: str, body: MandatePreset) -> Any:
    """The Sign button: signs the open mandate and starts the run. A UI action, never an agent tool."""
    return await chat().sign_mandate(session_id, body)


@app.post("/api/chat/sessions/{session_id}/sync", response_model=ChatSendResponse)
async def chat_sync(session_id: str) -> Any:
    """Posts the run summary once the run this session waits on has stopped. Safe to call again."""
    return await chat().sync(session_id)


@app.post("/api/chat/sessions/{session_id}/assumptions", response_model=ChatSendResponse)
async def chat_assumption(session_id: str, body: AssumptionRequest) -> Any:
    """Confirm / Edit / Remove on an assumption card: the person's action, as on POST /api/runs/{id}/assumptions."""
    return await chat().resolve_assumption(session_id, body)


# ----------------------------------------------------------------------------- Universal Cart


@app.get("/api/runs/{run_id}/cart", response_model=UniversalCart)
async def get_cart(run_id: str) -> Any:
    if is_mock():
        return mock.cart(run_id)
    svc().run_or_404(run_id)
    from app.checkout import cart as b_cart  # B: get_cart(run_id) -> UniversalCart (falls back to build_cart)

    return getattr(b_cart, "get_cart", b_cart.build_cart)(run_id)


@app.post("/api/runs/{run_id}/cart/edit", response_model=UniversalCart)
async def post_cart_edit(run_id: str, body: CartEditRequest) -> Any:
    """Mock mode accepts the edit and returns the cart unchanged."""
    if is_mock():
        return mock.cart_edit(run_id)
    return await svc().cart_edit(run_id, body)


@app.post("/api/runs/{run_id}/cart/refresh", response_model=CartRefreshResponse)
async def post_cart_refresh(run_id: str) -> Any:
    if is_mock():
        mock.cart(run_id)
        return fixtures.load("cart_refresh.json")
    svc().run_or_404(run_id)
    from app.checkout import refresh as b_refresh  # B: refresh_prices(run_id) -> CartRefreshResponse

    return await b_refresh.refresh_prices(run_id)


@app.post("/api/runs/{run_id}/approve", response_model=ApproveResponse)
async def post_approve(run_id: str, body: ApproveRequest) -> Any:
    """409 while any assumption is unconfirmed, or when prices are stale (PLAN §3.18, §12.3)."""
    if is_mock():
        was_draft = mock.cart(run_id)["state"] == "draft"
        out = mock.approve(run_id, body.plan_id)
        if was_draft:  # the approved fixture cart becomes preference facts in the mock memory (labelled simulated)
            from app.agent import memory as agent_memory

            await agent_memory.on_mock_approved(run_id, mock.run(run_id), out["cart"])
        return out
    return await svc().approve(run_id, body)


@app.post("/api/runs/{run_id}/cart/handoff", response_model=UniversalCart)
async def post_handoff(run_id: str, body: HandoffUpdateRequest) -> Any:
    if is_mock():
        return mock.handoff(run_id, body.store_id, body.state, body.done_via, body.order_id)
    svc().run_or_404(run_id)
    from app.checkout import handoff as b_handoff  # B: update_handoff(run_id, store_id, state[, done_via, order_id]) -> UniversalCart

    cart = b_handoff.update_handoff(run_id, body.store_id, body.state, done_via=body.done_via, order_id=body.order_id)
    return svc().after_cart_change(run_id, cart)


@app.post("/api/runs/{run_id}/cart/reopen", response_model=UniversalCart)
async def post_cart_reopen(run_id: str) -> Any:
    """The "Edit cart" button on an approved cart: open Shopify carts are cancelled, the cart is a draft again
    and needs a new approval. The closed mandate already signed stays in the chain; it is never edited."""
    if is_mock():
        return mock.reopen(run_id)
    return await svc().cart_reopen(run_id)


@app.post("/api/runs/{run_id}/cart/item-added", response_model=UniversalCart)
async def post_cart_item_added(run_id: str, body: CartItemAddedRequest) -> Any:
    """The per-item "added" tick on a product-link store. Kept with the cart and recorded in the chain."""
    if is_mock():
        return mock.item_added(run_id, body.offer_id, body.added)
    svc().run_or_404(run_id)
    from app.checkout import cart as b_cart  # B

    if not any(i.offer_id == body.offer_id for g in b_cart.get_cart(run_id).stores for i in g.items):
        raise api_error(404, "item_not_found", f"No cart item {body.offer_id}")
    return svc().after_cart_change(run_id, b_cart.set_item_added(run_id, body.offer_id, body.added))


@app.get("/api/runs/{run_id}/cart/export.csv")
async def get_cart_csv(run_id: str) -> PlainTextResponse:
    if is_mock():
        text = mock.export_csv(run_id)
    else:
        svc().run_or_404(run_id)
        from app.checkout import export as b_export  # B: export_csv(run_id) -> str, part names from the BOM

        text = b_export.export_csv(run_id)
    return PlainTextResponse(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{run_id}-cart.csv"'})


# ----------------------------------------------------------------------------- Tier 2 (Stripe TEST MODE)
# Not agent tools. Only a person clicking in the UI can start a test payment (PLAN §3.1).


@app.post("/api/runs/{run_id}/pay/intent", response_model=PayIntentResponse)
async def post_pay_intent(run_id: str, body: PayIntentRequest) -> Any:
    if is_mock():
        cart = mock.cart(run_id)
        if cart["state"] == "draft":
            raise api_error(409, "approval_required", "Approve the cart before a test payment")
        return await registry.get("stripe").create_hold(run_id, round(cart["total_usd"] * 100), "sha256:mock")
    run = svc().run_or_404(run_id)
    if run.closed_mandate is None:
        raise api_error(409, "approval_required", "Approve the cart before a test payment")
    from app.checkout import stripe_test as b_stripe  # B. TEST MODE only; a human UI action, never an agent tool

    return await b_stripe.pay_intent(run_id, body.consent_text)  # the payment mandate first, then the test hold


@app.post("/api/runs/{run_id}/pay/fanout", response_model=Accepted, status_code=202)
async def post_pay_fanout(run_id: str, body: PayFanoutRequest) -> Any:
    if is_mock():
        mock.cart(run_id)
        return {"accepted": True, "simulated": True}
    run = svc().run_or_404(run_id)
    from app.checkout import cart as b_cart
    from app.checkout import stripe_test as b_stripe  # B: pay_fanout emits pay.* events as it goes

    session = b_cart.BOOK.get(run_id).payment
    if not session or session.get("payment_intent_id") != body.payment_intent_id:
        raise api_error(409, "unknown_payment_intent", "That test payment does not belong to this cart")

    async def fanout() -> None:
        try:
            await b_stripe.pay_fanout(run_id, body.payment_intent_id, over_limit_store=body.over_limit_store)
        except Exception as exc:  # a background task has no response to carry the error: say it on the timeline
            message = getattr(exc, "message", None) or str(exc)
            run.emit("pay.declined", f"Test payment stopped: {str(message)[:160]}", "fail", provider="stripe_test", simulated=True)

    _background.add(task := asyncio.create_task(fanout()))
    task.add_done_callback(_background.discard)
    return {"accepted": True, "simulated": True}


# ----------------------------------------------------------------------------- receipt


@app.get("/api/runs/{run_id}/receipt", response_model=Receipt)
async def get_receipt(run_id: str) -> Any:
    if is_mock():
        return mock.receipt(run_id)
    from app.audit import api as d_api  # D

    return d_api.receipt_body(run_id, **svc().receipt_overrides(run_id))


@app.get("/api/runs/{run_id}/verify", response_model=VerifyResult)
async def get_verify(run_id: str) -> Any:
    """Mock: the sample chain and its signatures are real, made with the public FIXTURE key (format only)."""
    if is_mock():
        return mock.verify(run_id)
    from app.audit import api as d_api  # D

    return d_api.verify_body(run_id, **svc().receipt_overrides(run_id))


# ----------------------------------------------------------------------------- memory (Cognee, PLAN §3.15)
# What the agent remembers about this user, the last improve pass, and the button that wipes it. The registry
# hands back the in-process mock in mock mode (no network) and the Cognee / owned-parts client otherwise.


@app.get("/api/memory", response_model=MemoryResponse)
async def get_memory() -> Any:
    from app.integrations import cognee_mem

    try:
        return await cognee_mem.memory_body()
    except Exception as exc:
        raise api_error(502, "memory_unavailable", f"Memory could not be read: {type(exc).__name__}") from exc


@app.post("/api/memory/forget", response_model=ForgetResponse)
async def post_memory_forget(body: ForgetRequest | None = None) -> Any:
    """A UI action (the Forget button), never an agent tool."""
    from app.integrations import cognee_mem

    try:
        return await cognee_mem.forget_body(body.scope if body else "everything")
    except Exception as exc:
        raise api_error(502, "memory_unavailable", f"Memory could not be cleared: {type(exc).__name__}: {str(exc)[:160]}") from exc


# ----------------------------------------------------------------------------- mock-only helper (not in PLAN §4.2)


@app.get("/api/mock/fixtures")
async def list_fixtures() -> list[str]:
    live("C", "n/a: mock-only helper")
    return fixtures.names()


@app.get("/api/mock/fixtures/{name}")
async def get_fixture(name: str) -> Any:
    """Any fixture by file name, e.g. view_diagram_esp32.json or view_photo_sample.json. Mock mode only."""
    live("C", "n/a: mock-only helper")
    if name not in fixtures.names():
        raise HTTPException(status_code=404, detail={"error": "fixture_not_found", "message": name})
    return fixtures.load(name)
