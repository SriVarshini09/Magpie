"""Service registry: DEMO_MODE picks mock or live; IMPL_<SERVICE> overrides one service."""

from __future__ import annotations

import asyncio

import pytest

from app import registry
from app.models import KbSearchResponse, Offer, PartQuery
from app.stores.base import RunCtx, StoreAdapter


def test_mock_mode_gives_every_service_its_mock_class():
    for name, spec in registry.SERVICES.items():
        assert type(registry.get(name)).__name__ == spec.mock_cls
        assert spec.owner in "ABCD" and spec.plan.startswith(("§", "App"))


def test_live_classes_raise_todo_with_owner_and_plan_section(live_mode):
    assert set(registry.modes().values()) == {"live"}
    with pytest.raises(NotImplementedError, match=r"TODO\(B\) — PLAN §3\.16"):
        asyncio.run(registry.get("serpapi").search(PartQuery(bom_line_id="b1", query="x"), RunCtx(run_id="r")))
    # D implemented the live store: with no S2_URL it answers from the SQLite fallback (no network)
    assert isinstance(asyncio.run(registry.get("singlestore").hybrid_search("x")), KbSearchResponse)
    with pytest.raises(NotImplementedError, match=r"TODO\(A\) — PLAN §3\.17"):
        asyncio.run(registry.get("anthropic").classify_intake("x", []))
    with pytest.raises(NotImplementedError, match=r"TODO\(B\) — PLAN App\. A\.3"):
        registry.get("cartlinks").build("amazon", [("B0", 1)])


def test_per_service_override(monkeypatch, live_mode):
    monkeypatch.setenv("IMPL_SERPAPI", "mock")
    registry.reset()
    assert registry.impl_mode("serpapi") == "mock" and registry.impl_mode("adafruit") == "live"
    assert registry.any_mock() is True
    monkeypatch.setenv("IMPL_SERPAPI", "sometimes")
    with pytest.raises(Exception, match="IMPL_SERPAPI"):
        registry.impl_mode("serpapi")
    monkeypatch.setenv("IMPL_SERPAPI", "")


def test_mock_adapters_return_labelled_offers():
    ctx = RunCtx(run_id="r_mock_so101")
    total = 0
    for name in ("shopify_ucp", "serpapi", "adafruit", "magento", "digikey"):
        adapter = registry.get(name)
        assert isinstance(adapter, StoreAdapter) and adapter.hosts == frozenset()
        for line in ("b1", "b2", "b4", "b5"):
            for offer in asyncio.run(adapter.search(PartQuery(bom_line_id=line, query="x"), ctx)):
                assert isinstance(offer, Offer) and offer.source_api == "mock" and offer.simulated is True
                total += 1
    assert total >= 15


def test_mock_cart_links_reach_no_store_and_carry_no_buyer_data():
    url = registry.get("cartlinks").build("amazon", [("B0CTMM4LWK", 1), ("B092L925J4", 2)])
    assert url.startswith("https://mock.invalid/") and "tag=" not in url and "email" not in url


def test_other_mock_services_label_their_output():
    hits = asyncio.run(registry.get("keenable").search("small quadcopter"))
    assert hits[0]["source_api"] == "mock" and hits[0]["simulated"] is True
    doc = asyncio.run(registry.get("airbyte_github").fetch_readme("https://github.com/TheRobotStudio/SO-ARM100"))
    assert doc.simulated is True and "12V 5A+ power supply" in doc.text
    assert asyncio.run(registry.get("cognee").recall("screwdriver set"))[0]["simulated"] is True
