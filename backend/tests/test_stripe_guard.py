"""Stripe test-key guard (PLAN §3.3, §12.2): no live key is ever accepted; livemode must be false."""

from __future__ import annotations

import pytest

from app import config
from app.config import StripeKeyError, assert_livemode_false, assert_stripe_test_keys

# Built at runtime so no key-shaped literal sits in the repo. These are fake values.
SK_TEST, PK_TEST = "sk_" + "test_" + "x" * 24, "pk_" + "test_" + "x" * 24
SK_LIVE, PK_LIVE, RK_LIVE = "sk_" + "live_" + "x" * 24, "pk_" + "live_" + "x" * 24, "rk_" + "live_" + "x" * 24


def test_test_keys_and_empty_keys_pass():
    assert_stripe_test_keys(SK_TEST, PK_TEST)
    assert_stripe_test_keys("", "")
    assert_stripe_test_keys(None, None)


@pytest.mark.parametrize("sk,pk", [
    (SK_LIVE, PK_TEST), (SK_TEST, PK_LIVE), (RK_LIVE, ""), ("rk_test_" + "x" * 24, ""), ("sk_TEST_abc", ""),
    (" " + SK_TEST, ""), ("whatever", ""), ("", "pk_whatever"), (PK_TEST, SK_TEST),
])
def test_anything_else_is_refused(sk, pk):
    with pytest.raises(StripeKeyError) as exc:
        assert_stripe_test_keys(sk, pk)
    assert "x" * 24 not in str(exc.value), "the key must never appear in the error"


def test_settings_refuse_to_load_with_a_live_key(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", SK_LIVE)
    with pytest.raises(StripeKeyError):
        config.reload_settings()
    monkeypatch.setenv("STRIPE_SECRET_KEY", SK_TEST)
    monkeypatch.setenv("VITE_STRIPE_PUBLISHABLE_KEY", PK_LIVE)
    with pytest.raises(StripeKeyError):
        config.reload_settings()
    monkeypatch.setenv("VITE_STRIPE_PUBLISHABLE_KEY", PK_TEST)
    assert config.reload_settings().stripe_secret_key == SK_TEST
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("VITE_STRIPE_PUBLISHABLE_KEY", "")
    config.reload_settings()


def test_livemode_must_be_false():
    assert_livemode_false({"id": "pi_1", "livemode": False})

    class Obj:
        livemode = False

    assert_livemode_false(Obj())
    for bad in ({"livemode": True}, {"id": "pi_1"}, {"livemode": None}, {"livemode": "false"}, {"livemode": 0}, object()):
        with pytest.raises(StripeKeyError):
            assert_livemode_false(bad)


def test_live_stripe_service_checks_keys_on_construction(monkeypatch):
    from app import registry
    from app.checkout.stripe_test import LiveStripeTest

    monkeypatch.setenv("IMPL_STRIPE", "live")
    registry.reset()
    assert isinstance(registry.get("stripe"), LiveStripeTest)
    monkeypatch.setenv("IMPL_STRIPE", "")
    registry.reset()


def test_mock_stripe_is_labelled_test_and_simulated():
    import asyncio

    from app import registry

    hold = asyncio.run(registry.get("stripe").create_hold("r_mock_so101", 13241, "sha256:x"))
    assert hold["livemode"] is False and hold["simulated"] is True and hold["payment_mandate"]["mode"] == "test"
