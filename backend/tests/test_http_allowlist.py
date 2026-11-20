"""Fetch allowlist and never-request list (PLAN §3.16 rule 3)."""

from __future__ import annotations

import pytest

from app.stores.http import NEVER_REQUEST, HostNotAllowed, check_store_url, host_of, is_never_request

REQUIRED_NEVER = {"amazon.com", "digikey.com", "ebay.com", "walmart.com", "microcenter.com", "octopart.com", "robotshop.com", "bestbuy.com"}


def test_never_request_list_is_complete():
    assert REQUIRED_NEVER <= NEVER_REQUEST


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/B0CTMM4LWK", "https://amazon.com/gp/aws/cart/add.html?ASIN.1=B0", "https://smile.amazon.com/x",
    "https://www.amazon.fr/dp/B07BNF842T/", "https://www.amazon.co.jp/dp/B0C3H9L6KZ", "https://AMAZON.COM./x",
    "https://www.digikey.com/classic/ordering/fastadd.aspx?part1=1738-DFR0654-ND", "https://digikey.com/",
    "https://www.ebay.com/itm/1", "https://www.ebay.co.uk/itm/1", "https://www.walmart.com/ip/1", "https://affil.walmart.com/cart/addToCart?items=1",
    "https://www.microcenter.com/product/1", "https://octopart.com/search?q=bme280", "https://www.robotshop.com/products/x",
    "https://api.bestbuy.com/click/-/123/cart", "https://www.bestbuy.com/site/x", "https://user:pw@www.amazon.com:443/x",
    "www.amazon.com", "not a url at all ://",
])
def test_never_request_hosts_are_refused(url):
    assert is_never_request(url)
    with pytest.raises(HostNotAllowed) as exc:
        check_store_url(url)
    assert exc.value.refusal["rule"] == "host_not_allowed"


@pytest.mark.parametrize("url", [
    "https://serpapi.com/search.json?engine=google_shopping&q=x", "https://api.digikey.com/v1/oauth2/token",
    "https://www.adafruit.com/api/products", "https://www.seeedstudio.com/graphql?query=x", "https://www.sparkfun.com/graphql?query=x",
])
def test_allowlisted_store_requests_pass(url):
    assert not is_never_request(url)
    assert check_store_url(url) == url


@pytest.mark.parametrize("url,why", [
    ("http://serpapi.com/search.json", "https only"),
    ("https://www.adafruit.com/product/352", "path"),
    ("https://www.seeedstudio.com/SO-ARM100-Low-Cost-AI-Arm-Kit.html", "path"),
    ("https://example.com/", "allowlist"),
    ("https://robotshop-us.myshopify.com/products/x", "allowlist"),  # reached only through the ucp CLI
    ("https://serpapi.com.evil.example/search.json", "allowlist"),
    ("https://notamazon.com/", "allowlist"),
])
def test_everything_else_is_refused(url, why):
    with pytest.raises(HostNotAllowed, match=why):
        check_store_url(url)


def test_lookalike_hosts_are_not_confused_with_the_list():
    assert not is_never_request("https://notamazon.com/")
    assert not is_never_request("https://robotshop-us.myshopify.com/")
    assert not is_never_request("https://api.digikey.com/products/v4/search/keyword")
    assert is_never_request("https://api.digikey.com.evil.walmart.com/")


def test_an_adapter_may_only_reach_its_own_hosts():
    from app.stores.adafruit import LiveAdafruit
    from app.stores.serpapi import LiveSerpApi

    assert check_store_url("https://serpapi.com/search.json", LiveSerpApi.hosts)
    with pytest.raises(HostNotAllowed, match="adapter"):
        check_store_url("https://serpapi.com/search.json", LiveAdafruit.hosts)


def test_host_of():
    assert host_of("https://WWW.Amazon.com:443/x") == "www.amazon.com"
    assert host_of("api.digikey.com") == "api.digikey.com"


async def _fetch(url):
    from app.stores.http import fetch

    return await fetch(url, adapter_hosts=frozenset({"www.amazon.com"}))


def test_fetch_checks_the_host_before_anything_else():
    import asyncio

    with pytest.raises(HostNotAllowed):
        asyncio.run(_fetch("https://www.amazon.com/dp/B0"))
