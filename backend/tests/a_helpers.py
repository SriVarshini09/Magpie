"""Shared helpers for A's tests. Nothing here reaches the network: services are mocks or fakes."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.models import DataSharing, MandateActions, MandateConstraints, MandateInputs, MandateScope, Offer, OpenMandate, Signature

SO101_URL = "https://github.com/TheRobotStudio/SO-ARM100"
HERO_STORES = ["wowrobo", "armdojo", "geekworm", "amazon", "seeed", "adafruit", "sparkfun"]


def mandate(**over: Any) -> OpenMandate:
    scope = MandateScope(build_type=over.pop("build_type", "robot_arm"), build_type_set_by="classifier", goal="one follower arm", intake_sha256="0" * 64,
                         inputs=MandateInputs(source_url=over.pop("source_url", SO101_URL), image_sha256=over.pop("image_sha256", [])),
                         template_id="tpl_robot_arm", reference_search=over.pop("reference_search", True))
    cons = MandateConstraints(budget_usd=over.pop("budget_usd", 160), deadline="2026-12-04", allowed_merchants=over.pop("allowed_merchants", list(HERO_STORES)),
                              data_sharing=DataSharing(**over.pop("data_sharing", {})), actions=MandateActions(**over.pop("actions", {})))
    return OpenMandate(mandate_id="m_test", run_id="r_test", created_at="2026-11-20T13:00:00-08:00", expires_at="2026-11-20T19:00:00-08:00",
                       scope=scope, constraints=cons, signature=Signature(jws="test"))


def offer(offer_id: str, store: str, price: float, units: int = 1, level: str = "agent_cart", **kw: Any) -> Offer:
    return Offer(offer_id=offer_id, store_id=store, store_name=store.capitalize(), title=kw.pop("title", f"{offer_id} item"), url=f"https://mock.invalid/{store}/{offer_id}",
                 price_usd=price, units_per_pack=units, action_level=level, source_api="mock", seen_at="2026-11-20T13:04:10-08:00",  # type: ignore[arg-type]
                 evidence_sha256="e" * 64, stock=kw.pop("stock", "in_stock"), condition=kw.pop("condition", "new"), simulated=True, **kw)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def live_mock(monkeypatch, tmp_path):
    """DEMO_MODE=live with every external service on its Mock class: A's real pipeline, no network, no keys."""
    from app import config, registry, runstate
    from app.agent import ports, service
    from app.audit import chain, mandate as d_mandate
    from app.intake import uploads

    monkeypatch.setenv("DEMO_MODE", "live")
    for name in registry.SERVICES:
        monkeypatch.setenv(f"IMPL_{name.upper()}", "mock")
    # These runs model the event setup: a human has opened Amazon's cart link in a browser (PLAN §2.1, 1:15), so Amazon
    # offers are prefilled carts. Mock offers carry the level their hand-off really uses; without this they are product
    # links, everywhere (tests/test_qa_truthful_levels.py covers that case).
    monkeypatch.setenv("CART_LINKS_VERIFIED", "amazon")
    config.reload_settings()
    registry.reset()
    monkeypatch.setattr(runstate, "SNAPSHOT_DIR", None)
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(service, "RUN_INLINE", True)
    chain.configure(persist=False)
    try:
        from app.audit import evidence

        evidence.configure(tmp_path / "evidence")
    except Exception:
        pass
    d_mandate.use_key(d_mandate.fixture_key(), d_mandate.FIXTURE_KID)  # a public test key; nothing is written to runs/
    ports.FALLBACKS_USED.clear()
    yield
    d_mandate.use_key(None)
    chain.configure(persist=None)
    for name in registry.SERVICES:
        monkeypatch.setenv(f"IMPL_{name.upper()}", "")
    monkeypatch.setenv("DEMO_MODE", "mock")
    config.reload_settings()
    registry.reset()


def start_so101(client: Any, answers: dict[str, str] | None = None, budget: float = 160, stores: list[str] | None = None) -> str:
    """Intake -> answers -> run for the SO-ARM100 link. Returns the run id (the agent has finished: RUN_INLINE)."""
    it = client.post("/api/intake", data={"text": SO101_URL}).json()
    it = client.post(f"/api/intake/{it['intake_id']}/answers", json={"answers": answers or {"voltage_class": "12v"}, "skip_defaults": True}).json()
    preset = it["mandate_preset"] | {"budget_usd": budget, "allowed_merchants": stores or HERO_STORES}
    r = client.post("/api/runs", json={"intake_id": it["intake_id"], "mandate": preset})
    assert r.status_code == 200, r.text
    return r.json()["run_id"]
