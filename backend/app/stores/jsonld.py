"""Brand-direct product pages (DFRobot, Waveshare) read as JSON-LD (PLAN §3.16, stretch 7). Owner: B.

Product link only; one request per product page, cached. Only the schema.org JSON-LD block is parsed
(`Product` with an `Offer`: price, priceCurrency, availability, sku, aggregateRating [checked Nov 19, OS K14,
K15]). The rest of the page is never read: page text is data, not instructions.
Pages with many variants (Waveshare ST3215) carry no JSON-LD offer and yield nothing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.models import Offer, PartQuery
from app.stores import http
from app.stores import registry as store_registry
from app.stores.base import RunCtx, make_offer_id, save_evidence, strip_html, to_float, to_int

HOSTS = frozenset({"www.dfrobot.com", "www.waveshare.com"})
STORE_BY_HOST = {"www.dfrobot.com": "dfrobot", "www.waveshare.com": "waveshare"}
_LD = re.compile(r"<script[^>]+type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)


def _walk(node: Any):
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk(node[key])


def products_in(html_text: str) -> list[dict[str, Any]]:
    """Every schema.org Product object in the page's JSON-LD blocks."""
    out = []
    for block in _LD.findall(html_text or ""):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _walk(data):
            t = node.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                out.append(node)
    return out


def _offer_fields(product: dict[str, Any]) -> tuple[float | None, str, str]:
    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    offers = offers or {}
    price = to_float(offers.get("price") if offers.get("price") is not None else offers.get("lowPrice"))
    currency = str(offers.get("priceCurrency") or "").upper()
    avail = str(offers.get("availability") or "")
    stock = "in_stock" if avail.endswith("InStock") else "out_of_stock" if avail.endswith(("OutOfStock", "SoldOut", "Discontinued")) else "unknown"
    return price, currency, stock


def offer_from_page(url: str, html_text: str, seen_at: str, evidence: tuple[str, str]) -> Offer | None:
    host = (re.match(r"https://([^/]+)", url) or [None, ""])[1]
    store_id = STORE_BY_HOST.get(host)
    if not store_id:
        return None
    for product in products_in(html_text):
        price, currency, stock = _offer_fields(product)
        if price is None or price <= 0 or currency != "USD":
            continue
        rating = product.get("aggregateRating") or {}
        sku = str(product.get("sku") or product.get("mpn") or "")
        level, reason = store_registry.effective_level(store_id, has_item_ids=True, qty=1)
        return Offer(
            offer_id=make_offer_id("jsonld", store_id, sku or url), store_id=store_id, store_name=store_registry.display_name(store_id),
            seller_name=None, title=str(product.get("name") or "")[:300], description=strip_html(str(product.get("description") or "")),
            url=url, price_usd=price, currency="USD", units_per_pack=1, stock=stock, condition="new",
            rating=to_float(rating.get("ratingValue")), reviews=to_int(rating.get("reviewCount") or rating.get("ratingCount")),
            ids={"sku": sku} if sku else {}, action_level=level, downgrade_reason=reason, source_api="jsonld",
            seen_at=seen_at, evidence_path=evidence[0], evidence_sha256=evidence[1])
    return None


async def read_product(url: str, run_id: str = "adhoc", *, bypass: bool = False) -> Offer | None:
    """One product page -> one Offer, or None. The URL is checked against the store allowlist first."""
    http.check_store_url(url, HOSTS)
    res = await http.fetch(url, adapter_hosts=HOSTS, tool="jsonld.page", bypass_cache=bypass, headers={"Accept": "text/html"})
    text = res.value if isinstance(res.value, str) else ""
    blocks = products_in(text)
    ev = save_evidence(run_id, {"source_api": "jsonld", "url": url, "seen_at": res.seen_at, "jsonld": blocks})
    return offer_from_page(url, text, res.seen_at, ev)


class JsonLdAdapter:
    """Refresh-only adapter for offers that came from a brand-direct page (no search: stretch 7)."""

    source_api = "jsonld"
    hosts = HOSTS

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        return []

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        fresh = await read_product(offer.url, ctx.run_id, bypass=True)
        if fresh is None:
            return None
        return offer.model_copy(update={"price_usd": fresh.price_usd, "stock": fresh.stock, "seen_at": fresh.seen_at,
                                        "evidence_path": fresh.evidence_path, "evidence_sha256": fresh.evidence_sha256})
