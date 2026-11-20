"""Tier 2 Stripe TEST MODE flow (PLAN §12.3, §12.4) against a fake Stripe served by httpx.MockTransport.

Covers: the payment mandate is hashed before the PaymentIntent, manual capture, one Issuing card per store
capped at its subtotal, simulated authorizations, capture of the approved sum (a declined store is released),
livemode asserted on every object, test keys only, and no client secret in any record or event.
"""

from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qs

import pytest
from b_support import SK_TEST, b_env, install, json_response, set_mode  # noqa: F401
from test_b_cart import BASE_LINES, RUN, bom, offers, plan, sign

from app.checkout import cart as cart_mod
from app.checkout import handoff, stripe_test
from app.checkout.cart import BOOK, CartContext, CartError
from app.config import StripeKeyError
from app.stores.base import now_iso


class FakeStripe:
    def __init__(self, livemode_on: str | None = None):
        self.pi: dict = {}
        self.limits: dict[str, int] = {}
        self.requests: list = []
        self.livemode_on = livemode_on

    def __call__(self, request):
        assert request.url.host == "api.stripe.com"
        assert request.headers["Authorization"] == f"Bearer {SK_TEST}"
        form = {k: v if len(v) > 1 else v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.requests.append((request.method, request.url.path, form, request.headers.get("Idempotency-Key")))
        path = request.url.path
        live = self.livemode_on is not None and self.livemode_on in path

        def ok(body):
            return json_response({**body, "livemode": live})

        if path == "/v1/payment_intents" and request.method == "POST":
            self.pi = {"id": "pi_test_1", "object": "payment_intent", "amount": int(form["amount"]), "status": "requires_payment_method",
                       "client_secret": "pi_test_1_secret_zzz", "metadata": {k[9:-1]: v for k, v in form.items() if k.startswith("metadata[")}}
            return ok(self.pi)
        if path == "/v1/payment_intents/pi_test_1" and request.method == "GET":
            return ok(self.pi)
        if path == "/v1/issuing/cards":
            card_id = f"ic_test_{len(self.limits) + 1}"
            self.limits[card_id] = int(form["spending_controls[spending_limits][0][amount]"])
            assert form["spending_controls[spending_limits][0][interval]"] == "per_authorization" and form["type"] == "virtual"
            return ok({"id": card_id, "object": "issuing.card", "last4": f"{len(self.limits):04d}"})
        if path == "/v1/test_helpers/issuing/authorizations":
            approved = int(form["amount"]) <= self.limits[form["card"]]
            return ok({"id": f"iauth_{form['card']}", "object": "issuing.authorization", "approved": approved,
                       "status": "pending" if approved else "closed", "amount": int(form["amount"])})
        if path == "/v1/payment_intents/pi_test_1/capture":
            self.pi.update(status="succeeded", amount_received=int(form["amount_to_capture"]))
            return ok(self.pi)
        if path == "/v1/payment_intents/pi_test_1/cancel":
            self.pi.update(status="canceled")
            return ok(self.pi)
        return json_response({"error": {"message": f"unexpected {path}"}}, status=400)


@pytest.fixture()
def approved_cart(b_env, monkeypatch):
    ctx = CartContext(run_id=RUN, plan=plan(BASE_LINES), offers=offers(now_iso()), bom=bom(), budget_usd=160.0)
    cart_mod.configure(context=lambda run_id: ctx)
    asyncio.run(handoff.approve(RUN, "p1", sign=sign))  # mock mode: mock carts and links
    yield ctx


@pytest.fixture()
def stripe_live(approved_cart, monkeypatch):
    from app import config

    monkeypatch.setenv("STRIPE_SECRET_KEY", SK_TEST)
    monkeypatch.setenv("PAY_TIER", "2")
    monkeypatch.setenv("STRIPE_CARDHOLDER_ID", "ich_test_123")
    set_mode(monkeypatch, "live")
    yield
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("PAY_TIER", "1")
    config.reload_settings()


def consent() -> str:
    return stripe_test.consent_text(cart_mod.build_cart(RUN).total_usd)


def test_full_test_mode_sequence_with_one_store_declined(stripe_live):
    fake = FakeStripe()
    install(fake)
    svc = stripe_test.LiveStripeTest()
    resp = asyncio.run(stripe_test.pay_intent(RUN, consent(), service=svc))
    assert resp.livemode is False and resp.simulated is True and resp.client_secret == "pi_test_1_secret_zzz"
    m = resp.payment_mandate
    assert m.mode == "test" and m.total.amount == 13241 and [a.limit for a in m.allocations] == [9094, 1700, 1199, 1248]
    assert m.mandate_hash == stripe_test.mandate_hash(m.model_dump()), "recomputable from the mandate as created"
    method, path, form, idem = fake.requests[0]
    assert (method, path) == ("POST", "/v1/payment_intents")
    assert form["capture_method"] == "manual" and form["currency"] == "usd" and form["payment_method_types[]"] == "card"
    assert form["metadata[mandate_hash]"] == m.mandate_hash and form["metadata[run_id]"] == RUN and idem
    # the same consent again does not create a second hold
    assert asyncio.run(stripe_test.pay_intent(RUN, consent(), service=svc)).payment_intent_id == "pi_test_1"
    assert sum(1 for r in fake.requests if r[1] == "/v1/payment_intents") == 1

    with pytest.raises(CartError, match="Confirm the test card"):
        asyncio.run(stripe_test.pay_fanout(RUN, "pi_test_1", service=svc))
    fake.pi["status"] = "requires_capture"  # what stripe.confirmPayment with 4242 4242 4242 4242 does in the browser
    paid = asyncio.run(stripe_test.pay_fanout(RUN, "pi_test_1", service=svc, over_limit_store="amazon"))
    assert (paid.captured_usd, paid.released_usd, paid.authorized_usd) == (119.93, 12.48, 132.41)
    capture = next(r for r in fake.requests if r[1].endswith("/capture"))
    assert capture[2]["amount_to_capture"] == "11993" and capture[3]
    cards = [r for r in fake.requests if r[1] == "/v1/issuing/cards"]
    assert [c[2]["metadata[merchant]"] for c in cards] == ["wowrobo", "geekworm", "armdojo", "amazon"]
    assert all(c[2]["cardholder"] == "ich_test_123" and c[2]["metadata[mandate_hash]"] == m.mandate_hash for c in cards)

    c = cart_mod.build_cart(RUN)
    states = {g.store_id: g.test.state for g in c.stores}
    assert states == {"wowrobo": "settled", "geekworm": "settled", "armdojo": "settled", "amazon": "declined"}
    assert all(g.test.simulated is True for g in c.stores) and c.test_payment.mandate_hash == m.mandate_hash
    rec = BOOK.get(RUN)
    kinds = [r["kind"] for r in rec.records]
    for k in ("payment_mandate", "payment_hold", "issuing_card", "issuing_authorization", "payment_capture"):
        assert k in kinds
    types = [e["type"] for e in rec.events]
    assert types.count("pay.card_issued") == 4 and types.count("pay.authorized") == 3 and types.count("pay.declined") == 1
    assert "pay.captured" in types and all(e.get("simulated") for e in rec.events if e["type"].startswith("pay."))
    assert "secret_zzz" not in json.dumps(rec.records) + json.dumps(rec.events), "the client secret never leaves memory"
    # fan-out is idempotent once closed
    assert asyncio.run(stripe_test.pay_fanout(RUN, "pi_test_1", service=svc)) == paid


def test_every_object_must_be_livemode_false(stripe_live):
    install(FakeStripe(livemode_on="/v1/issuing/cards"))
    svc = stripe_test.LiveStripeTest()
    asyncio.run(stripe_test.pay_intent(RUN, consent(), service=svc))
    BOOK.get(RUN).payment  # session exists
    fake_pi = {"status": "requires_capture"}
    svc_retrieve = svc.retrieve

    async def retrieve(pi):
        out = await svc_retrieve(pi)
        return {**out, **fake_pi}

    svc.retrieve = retrieve
    with pytest.raises(StripeKeyError):
        asyncio.run(stripe_test.pay_fanout(RUN, "pi_test_1", service=svc))
    assert BOOK.get(RUN).test_payment is None


def test_guards(approved_cart, monkeypatch):
    with pytest.raises(StripeKeyError):
        stripe_test.StripeRest("sk_" + "live_" + "x" * 24)
    with pytest.raises(NotImplementedError, match="STRIPE_SECRET_KEY"):
        stripe_test.StripeRest("")
    with pytest.raises(CartError) as exc:
        asyncio.run(stripe_test.pay_intent(RUN, "I agree"))
    assert exc.value.status == 422  # mock mode: the consent text must match exactly
    set_mode(monkeypatch, "live")
    with pytest.raises(CartError, match="PAY_TIER"):
        asyncio.run(stripe_test.pay_intent(RUN, consent()))
    set_mode(monkeypatch, "replay")
    monkeypatch.setenv("PAY_TIER", "2")
    from app import config

    config.reload_settings()
    with pytest.raises(CartError, match="recorded"):
        asyncio.run(stripe_test.pay_intent(RUN, consent()))
    monkeypatch.setenv("PAY_TIER", "1")
    config.reload_settings()


def test_draft_cart_cannot_pay(b_env):
    ctx = CartContext(run_id=RUN, plan=plan(BASE_LINES), offers=offers(now_iso()), bom=bom(), budget_usd=160.0)
    cart_mod.configure(context=lambda run_id: ctx)
    with pytest.raises(CartError) as exc:
        asyncio.run(stripe_test.pay_intent(RUN, stripe_test.consent_text(132.41)))
    assert exc.value.error == "approval_required"


def test_mock_service_runs_the_whole_flow_labelled_simulated(approved_cart):
    resp = asyncio.run(stripe_test.pay_intent(RUN, consent()))
    paid = asyncio.run(stripe_test.pay_fanout(RUN, resp.payment_intent_id))
    assert paid.captured_usd == 132.41 and paid.released_usd == 0 and paid.simulated is True
    assert {g.test.state for g in cart_mod.build_cart(RUN).stores} == {"settled"}


def test_form_encoding():
    assert stripe_test.flatten_form({"amount": 5, "payment_method_types": ["card"], "metadata": {"a": "b"},
                                     "spending_controls": {"spending_limits": [{"amount": 9, "interval": "per_authorization"}]}, "x": None}) == {
        "amount": "5", "payment_method_types[]": ["card"], "metadata[a]": "b",
        "spending_controls[spending_limits][0][amount]": "9", "spending_controls[spending_limits][0][interval]": "per_authorization"}


def test_payment_mandate_hash_excludes_payment_and_signature():
    base = {"type": "b2c.mandate.payment", "total": {"amount": 1}, "allocations": []}
    assert stripe_test.mandate_hash(base) == stripe_test.mandate_hash({**base, "payment": {"captured": 1}, "signature": {"jws": "x"},
                                                                       "mandate_hash": "sha256:old"})
    assert stripe_test.mandate_hash(base) != stripe_test.mandate_hash({**base, "total": {"amount": 2}})
