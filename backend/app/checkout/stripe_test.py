"""Tier 2: Stripe TEST MODE hold, per-store virtual cards, simulated authorizations (PLAN §12.3, §12.4). Owner: B.

Hard rules (PLAN §12.2): test keys only (config.assert_stripe_test_keys), assert livemode is false on
every object Stripe returns (config.assert_livemode_false), label everything TEST MODE, and never
expose these functions as agent tools: only a person clicking in the UI starts a test payment.
The app never sees a card number: card entry happens only inside Stripe's Payment Element.

The sequence (REST shapes from OP; plain HTTPS, no SDK):
1. POST /v1/payment_intents   amount, currency=usd, capture_method=manual, payment_method_types[]=card,
                              metadata[mandate_id], metadata[mandate_hash], metadata[run_id]      (pay_intent)
2. Browser: Payment Element + stripe.confirmPayment(redirect: if_required) with 4242 4242 4242 4242
   -> status requires_capture                                                                       -> pay.hold_placed
3. Per store: POST /v1/issuing/cards  cardholder, type=virtual, currency=usd, status=active,
              spending_controls[spending_limits][0][amount]=<store cents>, [interval]=per_authorization,
              metadata[mandate_hash], metadata[merchant]                                            -> pay.card_issued
              POST /v1/test_helpers/issuing/authorizations  card, amount, merchant_data[name]       -> pay.authorized | pay.declined
4. POST /v1/payment_intents/{id}/capture  amount_to_capture=<sum of approved>                       -> pay.captured
The payment mandate is created and hashed BEFORE the PaymentIntent, so Stripe and the audit trail point at
each other (its hash is in the PaymentIntent metadata). The PaymentIntent client_secret stays in memory: it is
never written to a record, an event, the cache or a log.
"""

from __future__ import annotations

from typing import Any, Protocol

from app import fixtures
from app.config import assert_livemode_false, assert_stripe_test_keys, get_settings
from app.integrations.base import MOCK_LABEL
from app.models import (
    Amount, PaymentAllocation, PaymentInstrument, PaymentMandate, PaymentSummary, PayIntentResponse, StoreTest,
    TestPayment, UserConsent,
)
from app.stores import http
from app.stores import registry as store_registry
from app.stores.base import canonical, env_secret, not_configured, now_iso, sha256_hex

STRIPE_API = "https://api.stripe.com"
STRIPE_TIMEOUT_S = 20.0
CONSENT_TEMPLATE = ("You authorise up to ${total}, split as shown. Each store can charge at most its own subtotal. "
                    "TEST MODE: no real money moves.")


class StripeTest(Protocol):
    async def create_hold(self, run_id: str, amount_cents: int, mandate_hash: str, **kw: Any) -> dict[str, Any]:
        """PaymentIntent with capture_method=manual. Returns {client_secret, payment_intent_id, livemode: False}."""
        ...

    async def fanout(self, run_id: str, payment_intent_id: str) -> list[dict[str, Any]]:
        """One Issuing virtual card per store, a simulated authorization each, then capture."""
        ...


def flatten_form(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Stripe's bracketed form encoding: {"metadata": {"a": 1}} -> {"metadata[a]": "1"}; lists of scalars repeat `key[]`."""
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten_form(v, f"{prefix}[{k}]" if prefix else str(k)))
    elif isinstance(obj, list):
        if all(not isinstance(v, (dict, list)) for v in obj):
            out[f"{prefix}[]"] = [str(v) for v in obj]
        else:
            for i, v in enumerate(obj):
                out.update(flatten_form(v, f"{prefix}[{i}]"))
    elif obj is not None:
        out[prefix] = ("true" if obj else "false") if isinstance(obj, bool) else str(obj)
    return out


class StripeRest:
    """Minimal Stripe REST client. Test keys only; every returned object must have livemode false."""

    def __init__(self, secret_key: str) -> None:
        if not secret_key:
            raise not_configured("§12.3 Tier 2", "STRIPE_SECRET_KEY (sk_test_…) is not set")
        assert_stripe_test_keys(secret_key, None)
        self._key = secret_key

    async def request(self, method: str, path: str, form: dict[str, Any] | None = None, *, idempotency_key: str | None = None) -> dict[str, Any]:
        if not path.startswith("/v1/"):
            raise ValueError("Stripe paths start with /v1/")
        headers = {"Authorization": f"Bearer {self._key}", "Stripe-Version": "2024-06-20"}
        if idempotency_key and method == "POST":
            headers["Idempotency-Key"] = idempotency_key
        _, body = await http.send(method, STRIPE_API + path, headers=headers,
                                  data=flatten_form(form) if form else None, timeout=STRIPE_TIMEOUT_S)
        if not isinstance(body, dict):
            raise http.StoreHTTPError(502, STRIPE_API + path, "Stripe returned no JSON object")
        assert_livemode_false(body)  # PLAN §12.2 rule 2: the backstop behind the key prefix check
        return body


# --------------------------------------------------------------------------- services (registry: "stripe")


class MockStripeTest:
    """Simulated Stripe for mock mode. Labelled simulated; nothing leaves the process."""

    def __init__(self) -> None:
        self._limits: dict[str, int] = {}
        self._status: dict[str, str] = {}

    async def create_hold(self, run_id: str, amount_cents: int, mandate_hash: str, **kw: Any) -> dict[str, Any]:
        data = fixtures.load("pay_intent_so101.json")
        assert_livemode_false(data)
        if kw.get("mandate_id"):  # a run-specific hold id; the fixture keeps its shape
            data["payment_intent_id"] = f"pi_mock_{sha256_hex(kw['mandate_id'])[:12]}"
        self._status[data["payment_intent_id"]] = "requires_capture"  # the mock skips the card form
        return data

    async def retrieve(self, payment_intent_id: str) -> dict[str, Any]:
        return {"id": payment_intent_id, "status": self._status.get(payment_intent_id, "requires_capture"), "livemode": False, **MOCK_LABEL}

    async def issue_card(self, store_id: str, limit_cents: int, mandate_hash: str, **kw: Any) -> dict[str, Any]:
        card_id = f"ic_mock_{store_id}"
        self._limits[card_id] = limit_cents
        return {"id": card_id, "last4": "0000", "livemode": False, **MOCK_LABEL}

    async def simulate_authorization(self, card_id: str, amount_cents: int, merchant_name: str, **kw: Any) -> dict[str, Any]:
        approved = amount_cents <= self._limits.get(card_id, 0)
        return {"id": f"iauth_mock_{card_id[8:]}", "approved": approved, "status": "pending" if approved else "closed",
                "amount": amount_cents, "livemode": False, **MOCK_LABEL}

    async def capture(self, payment_intent_id: str, amount_cents: int, **kw: Any) -> dict[str, Any]:
        self._status[payment_intent_id] = "succeeded"
        return {"id": payment_intent_id, "status": "succeeded", "amount_received": amount_cents, "livemode": False, **MOCK_LABEL}

    async def cancel(self, payment_intent_id: str, **kw: Any) -> dict[str, Any]:
        self._status[payment_intent_id] = "canceled"
        return {"id": payment_intent_id, "status": "canceled", "livemode": False, **MOCK_LABEL}

    async def fanout(self, run_id: str, payment_intent_id: str) -> list[dict[str, Any]]:
        allocations = fixtures.load("pay_intent_so101.json")["payment_mandate"]["allocations"]
        return [{**a, "status": "authorized", **MOCK_LABEL} for a in allocations]


class LiveStripeTest:
    """Stripe TEST MODE over REST. Constructing it checks the key prefixes; calls need STRIPE_SECRET_KEY."""

    def __init__(self) -> None:
        s = get_settings()
        assert_stripe_test_keys(s.stripe_secret_key, s.stripe_publishable_key)

    def configured(self) -> bool:
        return bool(get_settings().stripe_secret_key or env_secret("STRIPE_SECRET_KEY"))

    def _rest(self) -> StripeRest:
        return StripeRest(get_settings().stripe_secret_key or env_secret("STRIPE_SECRET_KEY"))

    async def create_hold(self, run_id: str, amount_cents: int, mandate_hash: str, *, mandate_id: str | None = None,
                          idempotency_key: str | None = None, **kw: Any) -> dict[str, Any]:
        if not isinstance(amount_cents, int) or amount_cents < 50:
            raise ValueError("a test hold needs at least 50 cents")
        pi = await self._rest().request("POST", "/v1/payment_intents", {
            "amount": amount_cents, "currency": "usd", "capture_method": "manual", "payment_method_types": ["card"],
            "description": "Build-to-Cart TEST MODE hold (no real money moves)",
            "metadata": {"mandate_id": mandate_id or "", "mandate_hash": mandate_hash, "run_id": run_id, "mode": "test"},
        }, idempotency_key=idempotency_key)
        return {"client_secret": pi["client_secret"], "payment_intent_id": pi["id"], "status": pi.get("status"),
                "amount": pi.get("amount"), "livemode": False}

    async def retrieve(self, payment_intent_id: str) -> dict[str, Any]:
        pi = await self._rest().request("GET", f"/v1/payment_intents/{payment_intent_id}")
        return {"id": pi["id"], "status": pi.get("status"), "amount": pi.get("amount"),
                "amount_capturable": pi.get("amount_capturable"), "livemode": False}

    async def issue_card(self, store_id: str, limit_cents: int, mandate_hash: str, *, idempotency_key: str | None = None, **kw: Any) -> dict[str, Any]:
        cardholder = env_secret("STRIPE_CARDHOLDER_ID")
        if not cardholder.startswith("ich_"):
            raise not_configured("§12.3 Tier 2 step 3", "STRIPE_CARDHOLDER_ID (ich_… from the test sandbox) is not set")
        card = await self._rest().request("POST", "/v1/issuing/cards", {
            "cardholder": cardholder, "type": "virtual", "currency": "usd", "status": "active",
            "spending_controls": {"spending_limits": [{"amount": limit_cents, "interval": "per_authorization"}]},
            "metadata": {"mandate_hash": mandate_hash, "merchant": store_id, "mode": "test"},
        }, idempotency_key=idempotency_key)
        return {"id": card["id"], "last4": card.get("last4"), "livemode": False}

    async def simulate_authorization(self, card_id: str, amount_cents: int, merchant_name: str, *,
                                     idempotency_key: str | None = None, **kw: Any) -> dict[str, Any]:
        auth = await self._rest().request("POST", "/v1/test_helpers/issuing/authorizations", {
            "card": card_id, "amount": amount_cents, "merchant_data": {"name": merchant_name[:22]},
        }, idempotency_key=idempotency_key)
        return {"id": auth["id"], "approved": bool(auth.get("approved")), "status": auth.get("status"),
                "amount": auth.get("amount"), "livemode": False}

    async def capture(self, payment_intent_id: str, amount_cents: int, *, idempotency_key: str | None = None, **kw: Any) -> dict[str, Any]:
        pi = await self._rest().request("POST", f"/v1/payment_intents/{payment_intent_id}/capture",
                                        {"amount_to_capture": amount_cents}, idempotency_key=idempotency_key)
        return {"id": pi["id"], "status": pi.get("status"), "amount_received": pi.get("amount_received"), "livemode": False}

    async def cancel(self, payment_intent_id: str, **kw: Any) -> dict[str, Any]:
        pi = await self._rest().request("POST", f"/v1/payment_intents/{payment_intent_id}/cancel")
        return {"id": pi["id"], "status": pi.get("status"), "livemode": False}

    async def fanout(self, run_id: str, payment_intent_id: str) -> list[dict[str, Any]]:
        paid = await pay_fanout(run_id, payment_intent_id, service=self)
        return [a.model_dump() for a in _session(run_id)["mandate"].allocations] if paid else []


# --------------------------------------------------------------------------- the Tier 2 flow (UI actions only)


def consent_text(total_usd: float) -> str:
    """The exact consent text the panel shows and the user ticks (PLAN §12.4)."""
    return CONSENT_TEMPLATE.format(total=f"{total_usd:,.2f}")


def _cents(usd: float) -> int:
    return int(round(usd * 100))


def mandate_hash(m: dict[str, Any]) -> str:
    """sha256 of the mandate's signed body: without mandate_hash, payment, signature and the fields the test payment
    fills in later (PLAN §12.4). D's `audit.mandate.payment_mandate_hash` is the one definition, so Verify recomputes it."""
    from app.audit import mandate as d_mandate

    return d_mandate.payment_mandate_hash({"type": "b2c.mandate.payment", **m})


def build_payment_mandate(run_id: str, cart: Any, closed_mandate_sha256: str, consent: str, at: str) -> PaymentMandate:
    """One allocation per store in the approved Universal Cart, whatever its action level."""
    allocations = []
    for g in cart.stores:
        if g.handoff is None:
            continue
        allocations.append(PaymentAllocation(store_id=g.store_id, action_level=g.handoff.kind, url_sha256=g.handoff.url_sha256,
                                             limit=_cents(g.subtotal_usd), status="queued"))
    total = sum(a.limit for a in allocations)
    mandate_id = "mnd_" + sha256_hex(f"{run_id}|{closed_mandate_sha256}|{at}")[:16]
    body = {"type": "b2c.mandate.payment", "version": "0.4", "mode": "test", "mandate_id": mandate_id,
            "closed_mandate_sha256": closed_mandate_sha256, "status": "open", "user_consent": {"at": at, "text_shown": consent},
            "total": {"amount": total, "currency": "usd"}, "allocations": [a.model_dump() for a in allocations], "simulated": True}
    return PaymentMandate(mandate_id=mandate_id, closed_mandate_sha256=closed_mandate_sha256, status="open",
                          user_consent=UserConsent(at=at, text_shown=consent), total=Amount(amount=total, currency="usd"),
                          allocations=allocations, mandate_hash=mandate_hash(body), signature=None)


def _session(run_id: str) -> dict[str, Any]:
    from app.checkout.cart import BOOK

    return BOOK.get(run_id).payment


def _service(service: Any) -> Any:
    if service is not None:
        return service
    from app import registry as services

    return services.get("stripe")


async def pay_intent(run_id: str, consent_shown: str, *, service: Any = None) -> PayIntentResponse:
    """POST /pay/intent: the payment mandate first, then the test PaymentIntent (manual capture)."""
    from app.checkout import cart as cart_mod
    from app.checkout.cart import BOOK, CartError, emit_event, emit_record

    settings = get_settings()
    if not settings.is_mock and settings.pay_tier < 2:
        raise CartError(409, "tier2_off", "The single test payment is off (PAY_TIER=1)")
    if settings.demo_mode == "replay":
        raise CartError(409, "replay", "Replay shows the recorded test-mode run; the Payment Element is not mounted")
    rec = BOOK.get(run_id)
    if rec.state == "draft":
        raise CartError(409, "approval_required", "Approve the cart before a test payment",
                        refusal=cart_mod.refusal("approval_required", "PLAN §12.4: a payment mandate needs a closed mandate", tool="pay_intent"))
    cart = cart_mod.build_cart(run_id)
    expected = consent_text(cart.total_usd)
    if (consent_shown or "").strip() != expected:
        raise CartError(422, "consent_mismatch", "The consent text must be exactly the one shown with the total")
    session = rec.payment
    if session.get("payment_intent_id") and session.get("status") == "open":
        return PayIntentResponse(client_secret=session["client_secret"], payment_intent_id=session["payment_intent_id"],
                                 payment_mandate=session["mandate"])
    at = now_iso()
    mandate = build_payment_mandate(run_id, cart, rec.closed_mandate_sha256 or "", expected, at)
    try:  # D signs it (ES256) and keeps it for the run's receipt; the hash is unchanged by signing
        from app.audit import mandate as d_mandate
        from app.models import Signature

        signed = d_mandate.sign_mandate(mandate.model_dump(mode="json", exclude_none=True), run_id=run_id)
        if signed.get("mandate_hash") == mandate.mandate_hash:
            mandate.signature = Signature.model_validate(signed["signature"])
    except Exception:
        pass  # unsigned: Verify will say so
    svc = _service(service)
    h = emit_record(run_id, "payment_mandate", mandate.model_dump())
    hold = await svc.create_hold(run_id, mandate.total.amount, mandate.mandate_hash, mandate_id=mandate.mandate_id,
                                 idempotency_key=f"b2c-{mandate.mandate_id}-hold")
    assert_livemode_false(hold)
    rec.payment = {"mandate": mandate, "payment_intent_id": hold["payment_intent_id"], "client_secret": hold["client_secret"],
                   "status": "open", "simulated": bool(hold.get("simulated"))}
    rec.test = {a.store_id: StoreTest(state="queued", limit_usd=a.limit / 100) for a in mandate.allocations}
    emit_record(run_id, "payment_hold", {"payment_intent": hold["payment_intent_id"], "amount": mandate.total.amount, "mode": "test",
                                         "status": "awaiting_card", "mandate_hash": mandate.mandate_hash})
    emit_event(run_id, "pay.hold_placed", f"Test payment started: ${mandate.total.amount / 100:,.2f} (waiting for the test card)",
               provider="stripe_test", simulated=True, record_hash=h, data={"mandate_hash": mandate.mandate_hash, "status": "awaiting_card"})
    return PayIntentResponse(client_secret=hold["client_secret"], payment_intent_id=hold["payment_intent_id"], payment_mandate=mandate)


async def pay_fanout(run_id: str, payment_intent_id: str, *, service: Any = None, over_limit_store: str | None = None) -> TestPayment:
    """POST /pay/fanout (run it as a background task; effects arrive as pay.* events).

    Hold confirmed -> one test Issuing card per store capped at its subtotal -> a simulated authorization each ->
    capture of the approved sum (declined stores are released). `over_limit_store` tries $1 over that store's
    cap, which Stripe declines: the optional 10-second demo (PLAN §12.3).
    """
    from app.checkout.cart import BOOK, CartError, emit_event, emit_record

    rec = BOOK.get(run_id)
    session = rec.payment
    if not session or session.get("payment_intent_id") != payment_intent_id:
        raise CartError(409, "unknown_payment_intent", "That test payment does not belong to this cart")
    if session.get("status") == "closed" and rec.test_payment is not None:
        return rec.test_payment
    svc = _service(service)
    pi = await svc.retrieve(payment_intent_id)
    assert_livemode_false(pi)
    if pi.get("status") != "requires_capture":
        raise CartError(409, "hold_not_placed", "Confirm the test card in the payment form first")
    mandate: PaymentMandate = session["mandate"]
    session["status"] = "executing"
    mandate.status = "executing"
    h = emit_record(run_id, "payment_hold", {"payment_intent": payment_intent_id, "amount": mandate.total.amount, "mode": "test",
                                             "status": "requires_capture", "mandate_hash": mandate.mandate_hash})
    emit_event(run_id, "pay.hold_placed", f"Test hold placed: ${mandate.total.amount / 100:,.2f} (TEST MODE)", severity="ok",
               provider="stripe_test", simulated=True, record_hash=h)
    captured = 0
    for alloc in mandate.allocations:
        name = store_registry.display_name(alloc.store_id)
        card = await svc.issue_card(alloc.store_id, alloc.limit, mandate.mandate_hash,
                                    idempotency_key=f"b2c-{mandate.mandate_id}-card-{alloc.store_id}")
        assert_livemode_false(card)
        alloc.instrument = PaymentInstrument(id=card["id"], last4=str(card.get("last4") or "????"))
        rec.test[alloc.store_id] = StoreTest(state="card_issued", card_last4=alloc.instrument.last4, limit_usd=alloc.limit / 100)
        h = emit_record(run_id, "issuing_card", {"store_id": alloc.store_id, "card": card["id"], "last4": alloc.instrument.last4,
                                                 "limit": alloc.limit, "interval": "per_authorization", "mode": "test"})
        emit_event(run_id, "pay.card_issued", f"Test card for {name}: •••• {alloc.instrument.last4}, limit ${alloc.limit / 100:,.2f}",
                   store_id=alloc.store_id, provider="stripe_test", simulated=True, record_hash=h)
        amount = alloc.limit + (100 if alloc.store_id == over_limit_store else 0)
        auth = await svc.simulate_authorization(card["id"], amount, name,
                                                idempotency_key=f"b2c-{mandate.mandate_id}-auth-{alloc.store_id}-{amount}")
        assert_livemode_false(auth)
        approved = bool(auth.get("approved"))
        alloc.authorization_id = auth.get("id")
        alloc.status = "authorized" if approved else "declined"
        rec.test[alloc.store_id] = StoreTest(state="authorized" if approved else "declined", card_last4=alloc.instrument.last4,
                                             limit_usd=alloc.limit / 100)
        h = emit_record(run_id, "issuing_authorization", {"store_id": alloc.store_id, "authorization": auth.get("id"), "amount": amount,
                                                          "approved": approved, "simulated": True, "mode": "test"})
        emit_event(run_id, "pay.authorized" if approved else "pay.declined",
                   f"{name}: ${amount / 100:,.2f} {'authorized' if approved else 'declined'} (simulated)",
                   severity="ok" if approved else "warn", store_id=alloc.store_id, provider="stripe_test", simulated=True, record_hash=h)
        if approved:
            captured += alloc.limit
    total = mandate.total.amount
    if captured > 0:
        res = await svc.capture(payment_intent_id, captured, idempotency_key=f"b2c-{mandate.mandate_id}-capture-{captured}")
    else:
        res = await svc.cancel(payment_intent_id)
    assert_livemode_false(res)
    released = total - captured
    mandate.payment = PaymentSummary(payment_intent=payment_intent_id, authorized=total, captured=captured, released=released)
    mandate.status = "closed"
    for alloc in mandate.allocations:
        if alloc.status == "authorized":
            rec.test[alloc.store_id] = StoreTest(state="settled", card_last4=alloc.instrument.last4 if alloc.instrument else None,
                                                 limit_usd=alloc.limit / 100)
    rec.test_payment = TestPayment(payment_intent=payment_intent_id, authorized_usd=total / 100, captured_usd=captured / 100,
                                   released_usd=released / 100, mandate_hash=mandate.mandate_hash)
    session["status"] = "closed"
    h = emit_record(run_id, "payment_capture", {"payment_intent": payment_intent_id, "captured": captured, "released": released,
                                                "mode": "test", "mandate_hash": mandate.mandate_hash})
    emit_event(run_id, "pay.captured", f"Test capture ${captured / 100:,.2f}; released ${released / 100:,.2f} (TEST MODE)",
               severity="ok", provider="stripe_test", simulated=True, record_hash=h,
               data={"captured_usd": captured / 100, "released_usd": released / 100, "mandate_hash": mandate.mandate_hash})
    return rec.test_payment


def payment_mandate(run_id: str) -> PaymentMandate | None:
    """The run's payment mandate, for D's receipt."""
    m = _session(run_id).get("mandate")
    return m if isinstance(m, PaymentMandate) else None
