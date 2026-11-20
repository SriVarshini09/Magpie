"""Seeed and SparkFun through Magento GraphQL, no key (PLAN §3.16, Appendix A.4). Owner: B. Product links only.

    GET https://<host>/graphql?query={products(search:"…",pageSize:N){items{name sku stock_status url_key
        price_range{minimum_price{final_price{value currency}}}}}}
Anonymous GET returns name, SKU, stock_status, final_price and url_key [checked Nov 19, OS K13]; field nesting
[confirm at build]. Deep link: https://<host>/<url_key>.html. Magento guest carts made through GraphQL live on
our server and cannot be handed to the user's browser, so these stores are product links only.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.models import Offer, PartQuery
from app.stores import http
from app.stores import registry as store_registry
from app.stores.base import AdapterError, FixtureAdapter, RunCtx, make_offer_id, save_evidence, to_float

STORES = {"seeed": "www.seeedstudio.com", "sparkfun": "www.sparkfun.com"}
PAGE_SIZE = 8
_FIELDS = "items{name sku stock_status url_key price_range{minimum_price{final_price{value currency}}}}"
_SAFE = re.compile(r"[^A-Za-z0-9 .,_/+#\-]")


def gql_string(text: str, limit: int = 120) -> str:
    """A GraphQL string literal for a search term (listing-derived text is reduced to safe characters)."""
    return json.dumps(re.sub(r"\s+", " ", _SAFE.sub(" ", text or "")).strip()[:limit])


def search_query(term: str, page_size: int = PAGE_SIZE) -> str:
    return "{products(search:%s,pageSize:%d){%s}}" % (gql_string(term), page_size, _FIELDS)


def sku_query(sku: str) -> str:
    return "{products(filter:{sku:{eq:%s}}){%s}}" % (gql_string(sku, 64), _FIELDS)


def _items(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise AdapterError("Magento GraphQL answered with something that is not JSON")
    if body.get("errors") and not (body.get("data") or {}).get("products"):
        raise AdapterError(f"Magento GraphQL error: {str(body['errors'][0].get('message', ''))[:120]}")
    return ((body.get("data") or {}).get("products") or {}).get("items") or []


def _offers(store_id: str, host: str, items: list[dict[str, Any]], seen_at: str, evidence: tuple[str, str]) -> list[Offer]:
    out = []
    for it in items:
        final = (((it.get("price_range") or {}).get("minimum_price") or {}).get("final_price") or {})
        price, currency = to_float(final.get("value")), str(final.get("currency") or "").upper()
        sku, url_key = str(it.get("sku") or ""), str(it.get("url_key") or "")
        if price is None or price <= 0 or currency != "USD" or not sku or not re.fullmatch(r"[A-Za-z0-9._-]+", url_key):
            continue
        status = str(it.get("stock_status") or "").upper()
        level, reason = store_registry.effective_level(store_id, has_item_ids=True, qty=1)
        out.append(Offer(
            offer_id=make_offer_id("magento", store_id, sku), store_id=store_id, store_name=store_registry.display_name(store_id),
            seller_name=None, title=str(it.get("name") or "")[:300], url=f"https://{host}/{url_key}.html", price_usd=price,
            currency="USD", units_per_pack=1, stock="in_stock" if status == "IN_STOCK" else "out_of_stock" if status == "OUT_OF_STOCK" else "unknown",
            condition="new", ids={"sku": sku, "url_key": url_key, "magento_host": host}, action_level=level, downgrade_reason=reason,
            source_api="magento", seen_at=seen_at, evidence_path=evidence[0], evidence_sha256=evidence[1]))
    return out


class MockMagento(FixtureAdapter):
    stands_for = ("magento",)


class LiveMagento:
    source_api = "magento"
    hosts = frozenset({"www.seeedstudio.com", "www.sparkfun.com"})  # /graphql only

    def configured(self) -> bool:
        return True

    async def _query(self, store_id: str, gql: str, ctx: RunCtx, *, bypass: bool = False) -> list[Offer]:
        host = STORES[store_id]
        res = await http.fetch(f"https://{host}/graphql", adapter_hosts=self.hosts, params={"query": gql},
                               headers={"Accept": "application/json"}, tool=f"magento.{store_id}",
                               bypass_cache=bypass or ctx.bypass_cache)
        ev = save_evidence(ctx.run_id, {"source_api": "magento", "store_id": store_id, "query": gql, "seen_at": res.seen_at, "response": res.value})
        return _offers(store_id, host, _items(res.value), res.seen_at, ev)

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        """Both stores; one failing store never fails the other."""
        term = q.query or q.spec or ""
        if not term.strip():
            return []
        out: list[Offer] = []
        errors = []
        for store_id in STORES:
            try:
                out += await self._query(store_id, search_query(term), ctx)
            except (AdapterError, http.StoreHTTPError) as exc:
                errors.append(f"{store_id}: {exc}")
        if errors and not out and len(errors) == len(STORES):
            raise AdapterError("; ".join(errors)[:300])
        return out

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        """Re-query one SKU, bypassing the cache."""
        sku = offer.ids.get("sku", "")
        if offer.store_id not in STORES or not sku:
            return None
        fresh = await self._query(offer.store_id, sku_query(sku), ctx, bypass=True)
        match = next((o for o in fresh if o.ids.get("sku") == sku), None)
        if match is None:
            return offer.model_copy(update={"stock": "unknown"})
        return offer.model_copy(update={"price_usd": match.price_usd, "stock": match.stock, "seen_at": match.seen_at,
                                        "evidence_path": match.evidence_path, "evidence_sha256": match.evidence_sha256})
