"""Adafruit catalog JSON, no key (PLAN §3.16, Appendix A.4). Owner: B. Product links only.

    GET https://www.adafruit.com/api/products       (7.8 MB, 5,592 products [checked Nov 19])
    GET https://www.adafruit.com/api/product/<id>   (one product, for the price refresh)

The catalog is downloaded once a day (the cache key carries the date) and matched locally with rapidfuzz.
Fields: product_id, product_name, product_price, discount_pricing[{min_qty, discounted_price}], product_stock
("in stock", a count, "0" or a negative number), product_url, product_mpn, discontinue_status.
No rating, shipping or ETA: those stay null ("not quoted").
"""

from __future__ import annotations

import re
from typing import Any

from app.models import Offer, PartQuery
from app.stores import http
from app.stores import registry as store_registry
from app.stores.base import FixtureAdapter, RunCtx, make_offer_id, now, save_evidence, sha256_hex, canonical, to_float

CATALOG_URL = "https://www.adafruit.com/api/products"
PRODUCT_URL = "https://www.adafruit.com/api/product/{pid}"
MATCH_THRESHOLD = 62
MAX_OFFERS = 6


def stock_of(value: Any) -> str:
    s = str(value if value is not None else "").strip().lower()
    if s == "in stock":
        return "in_stock"
    try:
        return "in_stock" if int(float(s)) > 0 else "out_of_stock"
    except ValueError:
        return "unknown"


def tier_prices(product: dict[str, Any]) -> list[dict[str, Any]] | None:
    tiers = []
    for t in product.get("discount_pricing") or []:
        price = to_float(t.get("discounted_price"))
        min_qty = t.get("min_qty")
        if price is not None and isinstance(min_qty, (int, float)):
            tiers.append({"min_qty": int(min_qty), "price_usd": price, "label": t.get("show_qty")})
    return tiers or None


def _score(query: str, name: str) -> float:
    try:
        from rapidfuzz import fuzz

        return float(fuzz.token_set_ratio(query, name))
    except ImportError:  # rapidfuzz is a project dependency; difflib keeps a broken install usable
        import difflib

        return 100.0 * difflib.SequenceMatcher(None, query.lower(), name.lower()).ratio()


def match(query: str, products: list[dict[str, Any]], limit: int = MAX_OFFERS) -> list[tuple[float, dict[str, Any]]]:
    """Local fuzzy match: product name (and MPN, exactly). Discontinued products are skipped."""
    q = re.sub(r"\s+", " ", query).strip()
    if not q:
        return []
    q_tokens = {t for t in re.split(r"[^a-z0-9]+", q.lower()) if len(t) > 1}
    scored = []
    for p in products:
        if str(p.get("discontinue_status") or "").lower() == "discontinued":
            continue
        name = str(p.get("product_name") or "")
        mpn = str(p.get("product_mpn") or "").lower()
        if mpn and mpn in q_tokens:
            scored.append((100.0, p))
            continue
        score = _score(q, name)
        # token_set_ratio rewards a one-word overlap; require at least two shared tokens for long queries
        shared = q_tokens & {t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) > 1}
        if len(q_tokens) >= 3 and len(shared) < 2:
            continue
        if score >= MATCH_THRESHOLD:
            scored.append((score, p))
    scored.sort(key=lambda sp: -sp[0])
    return scored[:limit]


def _offer(p: dict[str, Any], seen_at: str, evidence: tuple[str, str]) -> Offer | None:
    price = to_float(p.get("product_price"))
    pid = str(p.get("product_id") or "")
    if price is None or price <= 0 or not pid.isdigit():
        return None
    level, reason = store_registry.effective_level("adafruit", has_item_ids=True, qty=1)
    ids = {"sku": pid}
    if p.get("product_mpn"):
        ids["mpn"] = str(p["product_mpn"])
    return Offer(
        offer_id=make_offer_id("adafruit", "adafruit", pid), store_id="adafruit", store_name="Adafruit", seller_name=None,
        title=str(p.get("product_name") or "")[:300], description=None, url=f"https://www.adafruit.com/product/{pid}",
        price_usd=price, currency="USD", units_per_pack=1, tier_prices=tier_prices(p), shipping_usd=None, eta_text=None,
        stock=stock_of(p.get("product_stock")), condition="new", rating=None, reviews=None, ids=ids, action_level=level,
        downgrade_reason=reason, source_api="adafruit", seen_at=seen_at, evidence_path=evidence[0], evidence_sha256=evidence[1],
    )


class MockAdafruit(FixtureAdapter):
    stands_for = ("adafruit",)


class LiveAdafruit:
    source_api = "adafruit"
    hosts = frozenset({"www.adafruit.com"})  # /api/ only

    def __init__(self) -> None:
        self._memo: tuple[str, list[dict[str, Any]], str, str] | None = None  # (day, products, seen_at, sha)

    def configured(self) -> bool:
        return True

    async def catalog(self) -> tuple[list[dict[str, Any]], str, str]:
        """(products, seen_at, catalog_sha256). Downloaded once a day into the cache (PLAN §3.11)."""
        day = now().date().isoformat()
        if self._memo and self._memo[0] == day:
            return self._memo[1], self._memo[2], self._memo[3]
        res = await http.fetch(CATALOG_URL, adapter_hosts=self.hosts, tool="adafruit.catalog", cache_tag={"day": day}, timeout=30.0)
        products = res.value if isinstance(res.value, list) else []
        digest = sha256_hex(canonical(products))
        self._memo = (day, products, res.seen_at, digest)
        return products, res.seen_at, digest

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        products, seen_at, digest = await self.catalog()
        out = []
        for score, p in match(q.query or q.spec or "", products):
            ev = save_evidence(ctx.run_id, {"source_api": "adafruit", "source": CATALOG_URL, "catalog_sha256": digest,
                                            "seen_at": seen_at, "match_score": round(score, 1), "product": p})
            o = _offer(p, seen_at, ev)
            if o:
                out.append(o)
        return out

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        """Re-read one product from /api/product/<id>, bypassing the cache."""
        pid = offer.ids.get("sku", "")
        if not pid.isdigit():
            return None
        res = await http.fetch(PRODUCT_URL.format(pid=pid), adapter_hosts=self.hosts, tool="adafruit.product", bypass_cache=True)
        p = res.value if isinstance(res.value, dict) else {}
        ev = save_evidence(ctx.run_id, {"source_api": "adafruit", "source": PRODUCT_URL.format(pid=pid), "seen_at": res.seen_at, "product": p})
        fresh = _offer(p, res.seen_at, ev)
        if fresh is None:
            return offer.model_copy(update={"stock": "unknown", "seen_at": res.seen_at})
        return offer.model_copy(update={"price_usd": fresh.price_usd, "stock": fresh.stock, "tier_prices": fresh.tier_prices,
                                        "seen_at": fresh.seen_at, "evidence_path": ev[0], "evidence_sha256": ev[1]})
