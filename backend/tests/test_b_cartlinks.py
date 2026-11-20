"""Prefilled cart links (PLAN §3.16 rules 2 and 5, Appendix A.3): exact formats, downgrades, no tags or buyer data."""

from __future__ import annotations

import pytest
from b_support import b_env, set_mode  # noqa: F401

from app.stores import cartlinks
from app.stores.cartlinks import CartLinkError, CartLinkPending, LiveCartLinks, assert_clean, build_link


def test_amazon_format_is_exactly_appendix_a():
    url = cartlinks.amazon_url([("B0CTMM4LWK", 1), ("B087LY41PV", 2)])
    assert url == "https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=B0CTMM4LWK&Quantity.1=1&ASIN.2=B087LY41PV&Quantity.2=2"
    assert "tag" not in url.lower() and "associate" not in url.lower()


def test_digikey_fastadd_format_and_length_limit():
    url = cartlinks.digikey_url([("1738-DFR0654-ND", 1), ("1528-2652-ND", 3)])
    assert url == ("https://www.digikey.com/classic/ordering/fastadd.aspx?part1=1738-DFR0654-ND&qty1=1"
                   "&part2=1528-2652-ND&qty2=3&newcart=true")
    many = [(f"1738-DFR{n:04d}-ND", 1) for n in range(80)]
    assert cartlinks.digikey_url(many) is None  # > 1,700 characters (App. A.3)
    link = build_link("digikey", many, verified=True)
    assert link.url is None and link.action_level == "product_link" and "1,700" in link.downgrade_reason


def test_bestbuy_click_cart_is_one_unit_per_sku():
    assert cartlinks.bestbuy_url([("6505727", 1), ("6451330", 1)]) == "https://api.bestbuy.com/click/-/6505727,6451330/cart"
    assert cartlinks.bestbuy_url([("6505727", 2)]) is None
    link = build_link("bestbuy", [("6505727", 2)], verified=True)
    assert link.action_level == "product_link" and "one of each" in link.downgrade_reason


def test_walmart_affiliate_cart_format():
    assert cartlinks.walmart_url([("10450114", 1), ("123456789", 2)]) == \
        "https://affil.walmart.com/cart/addToCart?items=10450114|1,123456789|2"
    assert cartlinks.walmart_url([("10450114", 1)], pipe="%7C") == "https://affil.walmart.com/cart/addToCart?items=10450114%7C1"


@pytest.mark.parametrize("store_id,items", [
    ("amazon", [("B0", 1)]), ("amazon", [("b0ctmm4lwk", 1)]), ("amazon", [("B0CTMM4LWK", 0)]), ("amazon", []),
    ("bestbuy", [("65O5727", 1)]), ("walmart", [("abc", 1)]), ("digikey", [("x y z&tag=1", 1)]), ("amazon", [("B0CTMM4LWK", True)]),
])
def test_malformed_ids_or_quantities_never_build_a_link(store_id, items):
    assert cartlinks.FORMATS[store_id](items) is None
    link = build_link(store_id, items, verified=True)
    assert link.url is None and link.action_level == "product_link" and link.downgrade_reason


def test_unverified_formats_downgrade_to_product_links_with_the_reason():
    items = [("B0CTMM4LWK", 1)]
    pending = build_link("amazon", items, verified=None)
    assert pending.url is None and pending.action_level == "product_link" and "real browser" in pending.downgrade_reason
    assert pending.candidate_url and pending.candidate_url.startswith("https://www.amazon.com/")
    failed = build_link("amazon", items, verified=False)
    assert failed.url is None and "failed" in failed.downgrade_reason
    ok = build_link("amazon", items, verified=True)
    assert ok.url == ok.candidate_url and ok.action_level == "prefilled_cart" and ok.downgrade_reason is None


def test_stores_without_a_format_are_product_links():
    for store_id in ("adafruit", "seeed", "sparkfun", "ebay", "waveshare", "dfrobot", "wowrobo"):
        link = build_link(store_id, [("123", 1)], verified=True)
        assert link.url is None and link.action_level == "product_link"


def test_registry_flags_default_unverified(b_env, monkeypatch):
    from app.stores import registry as store_registry

    for sid in ("amazon", "digikey", "bestbuy", "walmart"):
        assert store_registry.cart_link_verified(sid) is None, "Appendix A marks no format as browser-verified"
    links = LiveCartLinks()
    assert links.link("amazon", [("B0CTMM4LWK", 1)]).action_level == "product_link"
    with pytest.raises(CartLinkPending, match=r"TODO\(B\) — PLAN App\. A\.3"):
        links.build("amazon", [("B0CTMM4LWK", 1)])
    monkeypatch.setenv("CART_LINKS_VERIFIED", "amazon, walmart")
    assert links.build("amazon", [("B0CTMM4LWK", 1)]).startswith("https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=")
    assert links.link("walmart", [("10450114", 1)]).action_level == "prefilled_cart"
    assert links.link("bestbuy", [("6505727", 1)]).action_level == "product_link"


@pytest.mark.parametrize("bad", [
    "https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=B0CTMM4LWK&Quantity.1=1&AssociateTag=x-20",
    "https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=B0CTMM4LWK&tag=x-20",
    "https://affil.walmart.com/cart/addToCart?items=1|1&email=a%40b.c",
    "https://api.bestbuy.com/click/-/6505727/cart?utm_source=x",
    "http://www.amazon.com/gp/aws/cart/add.html?ASIN.1=B0CTMM4LWK&Quantity.1=1",
])
def test_assert_clean_refuses_tags_tracking_and_buyer_data(bad):
    with pytest.raises(CartLinkError):
        assert_clean(bad)


def test_every_built_link_is_clean_and_is_a_never_request_host():
    """We build these strings for the user's browser; our own fetcher would refuse every one of them."""
    from app.stores.http import is_never_request

    for url in cartlinks.candidate_links().values():
        assert assert_clean(url) == url
        assert is_never_request(url)


def test_mock_links_reach_no_store():
    m = cartlinks.MockCartLinks()
    link = m.link("amazon", [("B0CTMM4LWK", 1)])
    assert link.url.startswith("https://mock.invalid/") and link.action_level == "prefilled_cart"
    assert m.link("adafruit", [("2652", 1)]).action_level == "product_link"
