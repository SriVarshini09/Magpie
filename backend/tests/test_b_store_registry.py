"""Store registry (PLAN §3.16): levels only go down, lookups, the /api/stores view, health."""

from __future__ import annotations

from b_support import b_env, set_mode  # noqa: F401

from app.stores import registry as store_registry
from app.stores.registry import effective_level


def test_every_store_has_the_fields_the_code_reads():
    for s in store_registry.all_stores():
        assert s["action_level"] in ("agent_cart", "prefilled_cart", "product_link")
        assert s["store_id"] and s["display_name"] and s["domain"]
        if s["search_source"] == "shopify_ucp" and s["store_id"] not in ("thepihut", "pimoroni"):
            assert s["business_url"].startswith("https://") and s["shopify_domains"]
        if s["action_level"] == "prefilled_cart":
            assert s["cart_link_format"] and s["item_id_key"]


def test_downgrades_never_upgrades(b_env, monkeypatch):
    assert effective_level("wowrobo", has_item_ids=True, qty=1) == ("agent_cart", None)
    level, why = effective_level("wowrobo", has_item_ids=False, qty=1)
    assert level == "product_link" and "variant" in why
    # prefilled formats stay product links until a human opened them in a browser
    level, why = effective_level("amazon", has_item_ids=True, qty=2)
    assert level == "product_link" and "real browser" in why
    monkeypatch.setenv("CART_LINKS_VERIFIED", "amazon,bestbuy,digikey")
    assert effective_level("amazon", has_item_ids=True, qty=2) == ("prefilled_cart", None)
    assert effective_level("amazon", has_item_ids=False, qty=1)[0] == "product_link"
    assert effective_level("bestbuy", has_item_ids=True, qty=2)[0] == "product_link"  # one unit per SKU
    assert effective_level("bestbuy", has_item_ids=True, qty=1)[0] == "prefilled_cart"
    assert effective_level("digikey", has_item_ids=True, qty=1, url_len=1701)[0] == "product_link"
    # product-link stores and unknown stores never go up
    assert effective_level("adafruit", has_item_ids=True, qty=1) == ("product_link", None)
    assert effective_level("some-shop.com", has_item_ids=True, qty=1) == ("product_link", None)


def test_walmart_is_a_product_link_until_its_browser_check(b_env, monkeypatch):
    assert store_registry.registry_level("walmart") == "prefilled_cart"
    assert effective_level("walmart", has_item_ids=True, qty=1)[0] == "product_link"
    info = {s.store_id: s for s in store_registry.stores()}
    assert info["walmart"].action_level == "product_link" and "browser" in info["walmart"].caveat
    assert info["wowrobo"].action_level == "agent_cart"
    assert info["mock_store"].simulated is True
    assert info["digikey"].enabled is False
    monkeypatch.setenv("DIGIKEY_CLIENT_ID", "id")
    monkeypatch.setenv("DIGIKEY_CLIENT_SECRET", "secret")
    assert {s.store_id: s for s in store_registry.stores()}["digikey"].enabled is True


def test_lookups():
    assert store_registry.store_for_shopify_domain("f0c6d4-21.myshopify.com")["store_id"] == "wowrobo"
    assert store_registry.store_for_shopify_domain("https://shop.wowrobo.com")["store_id"] == "wowrobo"
    assert store_registry.store_for_shopify_domain("robotshop-us.myshopify.com")["store_id"] == "robotshop"
    assert store_registry.store_for_shopify_domain("unknown-x.myshopify.com") is None
    assert store_registry.store_for_host("https://www.amazon.com/dp/B0CTMM4LWK")["store_id"] == "amazon"
    assert store_registry.store_for_host("https://www.adafruit.com/product/2652")["store_id"] == "adafruit"
    assert store_registry.store_for_host("https://notamazon.com/x") is None
    assert store_registry.store_for_merchant_name("Amazon.com - Seller")["store_id"] == "amazon"
    assert store_registry.store_for_merchant_name("Walmart - ACME Seller")["store_id"] == "walmart"
    assert store_registry.store_for_merchant_name("Best Buy")["store_id"] == "bestbuy"
    assert store_registry.store_for_merchant_name("Some Shop") is None
    assert "amazon.com" in store_registry.all_store_domains() and "mock.invalid" not in store_registry.all_store_domains()


def test_adapter_for_source():
    from app.stores.jsonld import JsonLdAdapter
    from app.stores.mock import MockStore

    assert store_registry.adapter_for_source("serpapi:amazon") is not None
    assert isinstance(store_registry.adapter_for_source("jsonld"), JsonLdAdapter)
    assert isinstance(store_registry.adapter_for_source("mock"), MockStore)
    assert store_registry.adapter_for_source("alibaba") is None


def test_health_reports_mock_ok_or_off(b_env, monkeypatch):
    assert set(store_registry.health().values()) == {"mock"}
    set_mode(monkeypatch, "live")
    monkeypatch.setenv("UCP_BIN", "definitely-not-a-ucp-binary")
    monkeypatch.setenv("UCP_NPX_FALLBACK", "0")
    h = store_registry.health()
    assert h["serpapi"] == "off" and h["digikey"] == "off" and h["shopify_ucp"] == "off"
    assert h["adafruit"] == "ok" and h["magento"] == "ok" and h["cartlinks"] == "ok"
    monkeypatch.setenv("SERPAPI_KEY", "fake-key-for-test")
    assert store_registry.health()["serpapi"] == "ok"
