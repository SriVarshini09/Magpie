"""stores/http.py fetch (allowlist -> cache -> network) and app/cache.py record/replay (PLAN §3.11, §3.16 rule 3)."""

from __future__ import annotations

import asyncio
import json

import pytest
from b_support import b_env, install, json_response, set_mode  # noqa: F401

from app import cache
from app.stores import http
from app.stores.base import redact, save_evidence


def test_no_network_in_tests_without_a_mock_transport(b_env):
    with pytest.raises(http.LiveNetworkInTests):
        asyncio.run(http.send("GET", "https://serpapi.com/search.json"))


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/B0CTMM4LWK", "https://www.digikey.com/x", "https://www.ebay.com/itm/1", "https://www.walmart.com/ip/1",
    "https://www.bestbuy.com/site/x", "https://www.microcenter.com/x", "https://octopart.com/x", "https://www.robotshop.com/x",
    "https://api.bestbuy.com/click/-/6505727/cart", "https://affil.walmart.com/cart/addToCart?items=1|1",
])
def test_fetch_refuses_never_request_hosts_before_any_request(b_env, url):
    seen = install(lambda r: json_response({}))
    with pytest.raises(http.HostNotAllowed) as exc:
        asyncio.run(http.fetch(url, adapter_hosts=frozenset({"www.amazon.com", "serpapi.com"})))
    assert exc.value.refusal["rule"] == "host_not_allowed"
    assert seen == [], "a refused URL is never requested"


def test_fetch_caches_and_keeps_secrets_out_of_the_cache(b_env, monkeypatch):
    set_mode(monkeypatch, "live")
    seen = install(lambda r: json_response({"ok": True, "n": len(seen)}))
    res1 = asyncio.run(http.fetch("https://serpapi.com/search.json", adapter_hosts=frozenset({"serpapi.com"}),
                                  params={"q": "servo"}, secret_params={"api_key": "SECRET123"}, tool="t"))
    res2 = asyncio.run(http.fetch("https://serpapi.com/search.json", adapter_hosts=frozenset({"serpapi.com"}),
                                  params={"q": "servo"}, secret_params={"api_key": "SECRET123"}, tool="t"))
    assert len(seen) == 1 and seen[0].url.params["api_key"] == "SECRET123"
    assert not res1.cached and res2.cached and res2.value == res1.value and res2.seen_at == res1.seen_at
    files = list(cache.CACHE_DIR.glob("*.json"))
    assert len(files) == 1 and "SECRET123" not in files[0].read_text(encoding="utf-8")
    # bypass (the price refresh) skips the read and writes a fresh entry
    res3 = asyncio.run(http.fetch("https://serpapi.com/search.json", adapter_hosts=frozenset({"serpapi.com"}),
                                  params={"q": "servo"}, secret_params={"api_key": "SECRET123"}, tool="t", bypass_cache=True))
    assert len(seen) == 2 and not res3.cached


def test_errors_never_carry_the_query_string(b_env, monkeypatch):
    set_mode(monkeypatch, "live")
    install(lambda r: json_response({"error": "Invalid API key"}, status=401))
    with pytest.raises(http.StoreHTTPError) as exc:
        asyncio.run(http.fetch("https://serpapi.com/search.json", adapter_hosts=frozenset({"serpapi.com"}),
                               params={"q": "x"}, secret_params={"api_key": "SECRET123"}))
    assert exc.value.status == 401 and "SECRET123" not in str(exc.value) and "api_key" not in str(exc.value)


def test_redirects_are_not_followed(b_env, monkeypatch):
    import httpx

    set_mode(monkeypatch, "live")
    seen = install(lambda r: httpx.Response(302, headers={"location": "https://www.amazon.com/dp/B0"}))
    with pytest.raises(http.StoreHTTPError):
        asyncio.run(http.fetch("https://www.adafruit.com/api/products", adapter_hosts=frozenset({"www.adafruit.com"})))
    assert len(seen) == 1 and seen[0].url.host == "www.adafruit.com"


def test_record_then_replay_with_the_original_seen_at(b_env, monkeypatch):
    calls = []

    async def fetch_value():
        calls.append(1)
        return {"price": 17.0}

    set_mode(monkeypatch, "record")
    e1 = asyncio.run(cache.cached_entry("ucp.catalog.search", {"q": "psu"}, fetch_value))
    assert not e1.hit and calls == [1]
    assert [r["key"] for r in cache.recorded_keys()] == [e1.key]
    on_disk = json.loads((cache.CACHE_DIR / f"{e1.key}.json").read_text(encoding="utf-8"))
    assert on_disk["seen_at"] == e1.seen_at and on_disk["recorded_in"] == "record"

    cache.clear_memory()
    set_mode(monkeypatch, "replay")
    e2 = asyncio.run(cache.cached_entry("ucp.catalog.search", {"q": "psu"}, fetch_value))
    assert e2.hit and e2.value == {"price": 17.0} and e2.seen_at == e1.seen_at and calls == [1]
    e3 = asyncio.run(cache.cached_entry("ucp.catalog.search", {"q": "psu"}, fetch_value, bypass=True))
    assert e3.hit and calls == [1], "replay never touches the network, not even for a refresh"
    with pytest.raises(cache.ReplayMiss):
        asyncio.run(cache.cached_entry("ucp.catalog.search", {"q": "other"}, fetch_value))
    assert calls == [1]


def test_mock_mode_keeps_entries_in_memory_only(b_env):
    async def fetch_value():
        return 1

    asyncio.run(cache.cached("t", {"a": 1}, fetch_value))
    assert not cache.CACHE_DIR.exists() or not list(cache.CACHE_DIR.glob("*.json"))


def test_cache_key_is_canonical():
    assert cache.cache_key("t", {"b": 1, "a": [1, 2]}) == cache.cache_key("t", {"a": [1, 2], "b": 1})
    assert cache.cache_key("t", {"a": 1}) != cache.cache_key("u", {"a": 1})


def test_evidence_files_are_redacted_and_content_addressed(b_env):
    payload = {"params": {"q": "x", "api_key": "SECRET"}, "url": "https://serpapi.com/search.json?q=x&api_key=SECRET",
               "headers": {"Authorization": "Bearer abc.def"}, "note": "key sk_" + "test_abcdef123 was here"}
    path, digest = save_evidence("r_test", payload)
    text = (b_env / path).read_text(encoding="utf-8")
    assert path == f"evidence/r_test/{digest}.json" and "SECRET" not in text and "abc.def" not in text and "sk_test_abc" not in text
    assert save_evidence("r_test", payload) == (path, digest)
    assert redact({"immersive_product_page_token": "keep-me"}) == {"immersive_product_page_token": "keep-me"}
