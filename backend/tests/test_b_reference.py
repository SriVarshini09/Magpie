"""Reference-design search chain (PLAN §3.18, P19): the never-request list is checked before every provider
call, store pages are never read through a provider, results are dropped before their text is read, the
per-run budget holds, and each provider parses its (unverified, configurable) response shape."""

from __future__ import annotations

import asyncio

import pytest
from b_support import b_env, install, json_response, set_mode  # noqa: F401

from app.intake import reference
from app.stores.http import HostNotAllowed

PAGE = "A 5-inch FPV build: 2306 2450KV motors on 4S, 35A ESC, 5x4.3x3 props. " * 6


class Spy:
    def __init__(self, provider_id, hits):
        self.provider_id, self.hits, self.calls = provider_id, hits, []

    async def search(self, query, max_results=3):
        self.calls.append(query)
        return self.hits


@pytest.fixture()
def chain(b_env, monkeypatch):
    monkeypatch.setenv("REFERENCE_PROVIDERS", "spy1,spy2")
    from app import config

    config.reload_settings()
    yield
    monkeypatch.delenv("REFERENCE_PROVIDERS")
    config.reload_settings()


@pytest.mark.parametrize("query", [
    "STS3215 servo amazon.com/dp/B0CTMM4LWK", "https://www.digikey.com/en/products/detail/x", "ebay.co.uk servo",
    "walmart.com power supply", "12V PSU from www.adafruit.com", "servo on seeedstudio.com", "alibaba.com servo",
    "robotshop-us.myshopify.com servo",
])
def test_store_or_never_request_host_in_the_query_is_refused_before_any_provider(chain, query):
    spy = Spy("spy1", [])
    reference.register_provider("spy1", spy)
    with pytest.raises(HostNotAllowed) as exc:
        asyncio.run(reference.find_reference_design(query, "r1"))
    assert exc.value.refusal["rule"] == "reference_host_not_allowed"
    assert spy.calls == [], "the check runs before the provider is called"


def test_results_pointing_at_stores_are_dropped_before_their_text_is_read(chain):
    spy = Spy("spy1", [
        {"url": "https://www.amazon.com/dp/B0", "title": "listing", "text": PAGE, "fetched_via": "keenable", "found_via": "keenable"},
        {"url": "https://www.adafruit.com/product/352", "title": "store page", "text": PAGE, "fetched_via": "keenable", "found_via": "keenable"},
        {"url": "https://shop.wowrobo.com/products/x", "title": "store page", "text": PAGE, "fetched_via": "keenable", "found_via": "keenable"},
        {"url": "https://docs.px4.io/main/en/frames_multicopter/holybro_x500V2_pixhawk5x", "title": "PX4 X500", "text": PAGE,
         "fetched_via": "keenable", "found_via": "keenable", "licence": "CC-BY-4.0"},
    ])
    reference.register_provider("spy1", spy)
    out = asyncio.run(reference.find_reference_design("5 inch quadcopter build", "r1"))
    assert out["url"].startswith("https://docs.px4.io/") and out["found_via"] == "keenable" and out["fetched_via"] == "keenable"
    assert out["licence"] == "CC-BY-4.0" and out["doc_sha256"] == reference.sha256_hex(out["text"])
    assert out["attempts"][0] == {"provider": "spy1", "status": "ok", "hits": 4, "kept": 1}


def test_failed_or_empty_providers_fall_through_and_the_budget_holds(chain, monkeypatch):
    class Boom:
        provider_id = "spy1"

        async def search(self, q, n=3):
            raise RuntimeError("down")

    spy2 = Spy("spy2", [{"url": "https://docs.holybro.com/x", "title": "Holybro", "text": PAGE, "fetched_via": "http", "found_via": "github_search"}])
    reference.register_provider("spy1", Boom())
    reference.register_provider("spy2", spy2)
    out = asyncio.run(reference.find_reference_design("quad", "r2"))
    assert out["provider"] == "spy2" and out["attempts"][0]["status"] == "error: RuntimeError"
    monkeypatch.setenv("REFERENCE_MAX_SEARCHES", "3")
    from app import config

    config.reload_settings()
    for _ in range(2):
        asyncio.run(reference.find_reference_design("quad", "r3"))
    # each call spends one search per provider tried (spy1 errors, then spy2): 3 searches are gone after two calls
    third = asyncio.run(reference.find_reference_designs("quad", "r3"))
    assert any("REFERENCE_MAX_SEARCHES" in a["status"] for a in third["attempts"]) and third["results"] == []
    monkeypatch.delenv("REFERENCE_MAX_SEARCHES")
    config.reload_settings()


def test_mock_providers_answer_in_mock_mode(b_env):
    out = asyncio.run(reference.find_reference_design("small camera quadcopter", "r_mock"))
    assert out["simulated"] is True and out["source_api"] == "mock" and out["url"].startswith("https://mock.invalid/")


def test_providers_without_a_key_are_skipped(b_env, monkeypatch):
    set_mode(monkeypatch, "live")
    monkeypatch.setenv("REFERENCE_PROVIDERS", "keenable,exa_airbyte")
    from app import config

    config.reload_settings()
    out = asyncio.run(reference.find_reference_designs("quad", "r4"))
    assert [a["status"] for a in out["attempts"]] == ["skipped: not configured", "skipped: not configured"] and out["results"] == []
    monkeypatch.delenv("REFERENCE_PROVIDERS")
    config.reload_settings()


def test_keenable_parses_results_and_never_leaks_its_key(b_env, monkeypatch):
    from app.integrations.keenable import LiveKeenable

    set_mode(monkeypatch, "live")
    monkeypatch.setenv("KEENABLE_API_KEY", "KEENKEY")

    def handler(request):
        assert request.url.host == "api.keenable.ai" and request.headers["Authorization"] == "Bearer KEENKEY"
        return json_response({"results": [{"url": "https://docs.px4.io/a", "title": "PX4", "markdown": PAGE},
                                          {"url": "https://blog.example/b", "title": "Blog", "snippet": "short"},
                                          {"url": "http://insecure.example/c", "title": "no"}]})

    seen = install(handler)
    hits = asyncio.run(LiveKeenable().search("quad build", 3))
    assert [h["url"] for h in hits] == ["https://docs.px4.io/a", "https://blog.example/b"]
    assert hits[0]["text"] == PAGE and hits[0]["fetched_via"] == "keenable" and hits[1]["text"] is None
    asyncio.run(LiveKeenable().search("quad build", 3))
    assert len(seen) == 1, "cached"
    for f in (b_env / "cache").glob("*.json"):
        assert "KEENKEY" not in f.read_text(encoding="utf-8")


def test_github_search_is_a_pointer_and_the_readme_comes_from_airbyte_github(b_env, monkeypatch):
    from app import registry
    from app.integrations.github_search import LiveGitHubSearch
    from app.models import SourceDoc

    set_mode(monkeypatch, "live")
    monkeypatch.setenv("REFERENCE_PROVIDERS", "github_search")
    from app import config

    config.reload_settings()

    def handler(request):
        assert request.url.host == "api.github.com" and request.url.path == "/search/repositories"
        assert request.url.params["q"] == "donkey car" and "Authorization" not in request.headers
        return json_response({"items": [{"html_url": "https://github.com/autorope/donkeycar", "full_name": "autorope/donkeycar",
                                         "description": "Open source hardware and software", "license": {"spdx_id": "MIT"}}]})

    install(handler)

    class FakeGitHub:
        async def fetch_readme(self, url):
            assert url == "https://github.com/autorope/donkeycar"
            return SourceDoc(id="s1", url=url, path="README.md", commit_sha="abc", text=PAGE, sha256="x", fetched_at="t", via="airbyte.github")

    registry._instances[("airbyte_github", "live")] = FakeGitHub()
    hits = asyncio.run(LiveGitHubSearch().search('donkey car "&|', 3))
    assert hits[0]["text"] is None and hits[0]["licence"] == "MIT" and hits[0]["found_via"] == "github_search"
    out = asyncio.run(reference.find_reference_design("donkey car", "r5"))
    assert out["fetched_via"] == "airbyte.github" and out["found_via"] == "github_search" and out["text"] == PAGE
    monkeypatch.delenv("REFERENCE_PROVIDERS")
    config.reload_settings()


def test_exa_excludes_stores_and_never_request_domains(b_env, monkeypatch):
    from app.integrations.airbyte_exa import LiveExa

    set_mode(monkeypatch, "live")
    monkeypatch.setenv("EXA_API_KEY", "EXAKEY")
    seen = {}

    class Conn:
        async def execute(self, entity, action, params):
            seen.update(entity=entity, action=action, params=params)

            class R:
                data = [{"url": "https://docs.arduino.cc/x", "title": "Uno", "text": PAGE},
                        {"url": "https://www.amazon.com/dp/B0", "title": "listing", "text": PAGE}]
            return R()

        async def close(self):
            seen["closed"] = True

    hits = asyncio.run(LiveExa(connector_factory=lambda key: Conn()).search("arduino weather station", 3))
    assert (seen["entity"], seen["action"]) == ("search_results", "list") and seen["closed"]
    excl = set(seen["params"]["exclude_domains"])
    assert {"amazon.com", "digikey.com", "ebay.com", "walmart.com", "adafruit.com", "seeedstudio.com", "aliexpress.com"} <= excl
    assert seen["params"]["contents"]["text"]["maxCharacters"] > 0
    assert hits[0]["fetched_via"] == "exa_airbyte"
    # the chain still drops the store result even if Exa returned one
    assert [h["url"] for h in reference.safe_hits(hits)] == ["https://docs.arduino.cc/x"]


def test_exa_text_is_not_used_until_the_contract_allows_it(b_env, monkeypatch):
    """FetchedVia has no "exa_airbyte" yet (contract change requested): Exa hits are re-read over http instead."""
    import typing

    from app.models import FetchedVia

    assert reference._fetched_via_allowed("keenable") and reference._fetched_via_allowed("http")
    assert reference._fetched_via_allowed("exa_airbyte") == ("exa_airbyte" in typing.get_args(FetchedVia))
