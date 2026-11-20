"""Prefilled cart links as pure string building (PLAN §3.16 rules 2 and 5, Appendix A.3). Owner: B.

The backend NEVER requests these URLs: they are strings the user's browser opens.
A link carries item ids and quantities only: no affiliate tag, no tracking parameter, no buyer data
(tests/test_b_cartlinks.py).

Formats, exactly as Appendix A.3:
    Amazon    https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=<asin>&Quantity.1=<n>&ASIN.2=...
    Digi-Key  https://www.digikey.com/classic/ordering/fastadd.aspx?part1=<pn>&qty1=<n>&part2=...&newcart=true
    Best Buy  https://api.bestbuy.com/click/-/<sku1>,<sku2>/cart          (one unit per SKU)
    Walmart   https://affil.walmart.com/cart/addToCart?items=<id>|<qty>,<id2>|<qty2>   (try %7C if | fails)

A format is used only after a human opened it in a real browser (`cart_link_verified` in stores.json, or
CART_LINKS_VERIFIED in .env). Until then the store is shown as product links, with the reason.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urlsplit

from app.stores import registry as store_registry
from app.stores.registry import MAX_URL_CHARS

CartItems = list[tuple[str, int]]  # (store item id, quantity)

WALMART_PIPE = "|"  # Appendix A.3: "Try %7C if | fails" -> set to "%7C" after the C21 browser check if needed

_ID_PATTERNS: dict[str, re.Pattern[str]] = {
    "amazon": re.compile(r"^[A-Z0-9]{10}$"),
    "digikey": re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_/.#+]{1,63}$"),
    "bestbuy": re.compile(r"^\d{5,9}$"),
    "walmart": re.compile(r"^\d{4,15}$"),
}

# Words that must never appear in a cart link (affiliate tags, tracking, buyer data).
_FORBIDDEN = re.compile(
    r"(associatetag|[?&]tag=|affid|affiliate|utm_|[?&]ref=|email|phone|address|[?&]zip|postal|name=|@|%40)", re.I
)


class CartLinkError(ValueError):
    """A link that would carry something other than item ids and quantities."""


def assert_clean(url: str) -> str:
    """Raise if a link carries anything but ids and quantities (no tag, no buyer data)."""
    if _FORBIDDEN.search(url):
        raise CartLinkError("a cart link may carry item ids and quantities only")
    if urlsplit(url).scheme != "https":
        raise CartLinkError("cart links are https only")
    return url


def _valid(store_id: str, items: CartItems) -> bool:
    pat = _ID_PATTERNS[store_id]
    if not items:
        return False
    for item_id, qty in items:
        if not isinstance(item_id, str) or not pat.match(item_id):
            return False
        if not isinstance(qty, int) or isinstance(qty, bool) or not 1 <= qty <= 999:
            return False
    return True


def amazon_url(items: CartItems) -> str | None:
    if not _valid("amazon", items):
        return None
    q = "&".join(f"ASIN.{i}={asin}&Quantity.{i}={qty}" for i, (asin, qty) in enumerate(items, 1))
    return f"https://www.amazon.com/gp/aws/cart/add.html?{q}"


def digikey_url(items: CartItems) -> str | None:
    if not _valid("digikey", items):
        return None
    q = "&".join(f"part{i}={quote(pn, safe='-_.')}&qty{i}={qty}" for i, (pn, qty) in enumerate(items, 1))
    url = f"https://www.digikey.com/classic/ordering/fastadd.aspx?{q}&newcart=true"
    return url if len(url) <= MAX_URL_CHARS else None


def bestbuy_url(items: CartItems) -> str | None:
    """One unit per SKU: the format has no quantity field (OS K8)."""
    if not _valid("bestbuy", items) or any(qty != 1 for _, qty in items):
        return None
    return f"https://api.bestbuy.com/click/-/{','.join(sku for sku, _ in items)}/cart"


def walmart_url(items: CartItems, pipe: str | None = None) -> str | None:
    if not _valid("walmart", items):
        return None
    sep = pipe or WALMART_PIPE
    return "https://affil.walmart.com/cart/addToCart?items=" + ",".join(f"{wid}{sep}{qty}" for wid, qty in items)


FORMATS: dict[str, Callable[[CartItems], str | None]] = {
    "amazon": amazon_url,
    "digikey": digikey_url,
    "bestbuy": bestbuy_url,
    "walmart": walmart_url,
}
ID_KEYS = {"amazon": "asin", "digikey": "digikey_pn", "bestbuy": "bestbuy_sku", "walmart": "walmart_id"}


@dataclass(frozen=True)
class CartLink:
    """What the hand-off gets for one prefilled-cart store."""

    store_id: str
    url: str | None  # None: not usable as a prefilled cart; use product links
    action_level: str  # prefilled_cart | product_link
    downgrade_reason: str | None = None
    candidate_url: str | None = None  # the link a human opens for the 1:15 browser check (never requested by us)


def build_link(store_id: str, items: CartItems, *, verified: bool | None) -> CartLink:
    """Pure: the prefilled link for one store, or a product-link downgrade with the reason (rule 2)."""
    fmt = FORMATS.get(store_id)
    if fmt is None:
        return CartLink(store_id, None, "product_link", "No prefilled cart format exists for this store (Appendix A.3)")
    if not _valid(store_id, items):
        return CartLink(store_id, None, "product_link", store_registry.REASON_NO_ID)
    if store_id == "bestbuy" and any(qty != 1 for _, qty in items):
        return CartLink(store_id, None, "product_link", store_registry.REASON_QTY)
    url = fmt(items)
    if url is None:
        return CartLink(store_id, None, "product_link", store_registry.REASON_TOO_LONG)
    assert_clean(url)
    if verified is None:
        return CartLink(store_id, None, "product_link", store_registry.REASON_UNVERIFIED, candidate_url=url)
    if verified is False:
        return CartLink(store_id, None, "product_link", store_registry.REASON_FAILED, candidate_url=url)
    return CartLink(store_id, url, "prefilled_cart", None, candidate_url=url)


class CartLinkBuilder(Protocol):
    def build(self, store_id: str, items: CartItems) -> str | None:
        """The prefilled-cart URL, or None when the format cannot express the items or failed its check.

        Live: raises CartLinkPending while no human has opened that store's format in a browser yet.
        """
        ...

    def link(self, store_id: str, items: CartItems) -> CartLink:
        """Never raises: the URL or the product-link downgrade with its reason (used by the hand-offs)."""
        ...


class CartLinkPending(NotImplementedError):
    """The format exists but its 1:15 browser check (PLAN §2.1) has not happened: a human TODO."""


class MockCartLinks:
    """Links on the reserved .invalid TLD, so a click in mock mode reaches no store."""

    def build(self, store_id: str, items: CartItems) -> str | None:
        query = "&".join(f"item.{i}={item_id}&qty.{i}={qty}" for i, (item_id, qty) in enumerate(items, 1))
        return f"https://mock.invalid/{store_id}/cart/add?{query}"

    def link(self, store_id: str, items: CartItems) -> CartLink:
        if store_id not in FORMATS:
            return CartLink(store_id, None, "product_link", "No prefilled cart format exists for this store (Appendix A.3)")
        return CartLink(store_id, self.build(store_id, items), "prefilled_cart", None)


class LiveCartLinks:
    def configured(self) -> bool:
        return True

    def link(self, store_id: str, items: CartItems) -> CartLink:
        return build_link(store_id, items, verified=store_registry.cart_link_verified(store_id))

    def build(self, store_id: str, items: CartItems) -> str | None:
        if store_id in FORMATS and store_registry.cart_link_verified(store_id) is None:
            raise CartLinkPending(
                f"TODO(B) — PLAN App. A.3, §2.1 (1:15): a human opens the {store_id} cart link once in a real browser, "
                f"then sets cart_link_verified in data/stores.json (or CART_LINKS_VERIFIED={store_id} in .env)"
            )
        return self.link(store_id, items).url


def candidate_links(examples: dict[str, CartItems] | None = None) -> dict[str, str | None]:
    """The links a human opens for the browser check (scripts/record_hero.py --cart-links). Never requested by us."""
    examples = examples or {
        "amazon": [("B0CTMM4LWK", 1), ("B087LY41PV", 1)],
        "digikey": [("1738-DFR0654-ND", 1)],
        "bestbuy": [("6505727", 1), ("6451330", 1)],
        "walmart": [("10450114", 1)],
    }
    return {sid: FORMATS[sid](items) for sid, items in examples.items() if sid in FORMATS}
