"""SerpAPI: shopping prices from five engines (PLAN §3.16, §3.11). Owner: B.

Prices only: reference-design search never uses SerpAPI (PLAN §3.18). Cache-first, a call counter, and a
hard stop at 45 uncached calls in any rolling hour (the free plan allows 50 an hour for the whole team)
and SERPAPI_MAX_SEARCHES a day. The counter is kept in runs/serpapi_usage.json so a restart does not
reset it. The API key never appears in a log, an event, a cache file or an evidence file.

    GET https://serpapi.com/search.json?engine=<e>&...&api_key=...
Engines and fields (OS §2.1, from SerpAPI's docs; parameter names [confirm in C22]):
    google_shopping           q, gl=us, hl=en   -> shopping_results[]: title, source, extracted_price, rating, reviews,
                                                   delivery, product_link, immersive_product_page_token
    google_immersive_product  page_token        -> product_results.stores[]: name, link, extracted_price, shipping,
                                                   extracted_total, rating, reviews, details_and_offers
    amazon                    k, amazon_domain  -> organic_results[]: asin, title, link, extracted_price, rating, reviews
    walmart                   query             -> organic_results[]: us_item_id, primary_offer.offer_price, out_of_stock
    ebay                      _nkw, ebay_domain -> organic_results[]: link, product_id, price, shipping, condition

Default engines per BOM line: google_shopping + amazon (PLAN §3.11 budget). SERPAPI_ENGINES adds walmart and
ebay. The Immersive lookup runs only for the offers A decides to buy (`immersive`), never for every line.
Marketplace links are rebuilt in canonical form (amazon.com/dp/<asin>, walmart.com/ip/<id>, ebay.com/itm/<id>),
so no tracking or affiliate parameter is ever carried through. We never request those URLs.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config import BACKEND_DIR, get_settings
from app.models import Offer, PartQuery
from app.stores import http
from app.stores import registry as store_registry
from app.stores.cartlinks import ID_KEYS
from app.stores.base import (
    AdapterError,
    FixtureAdapter,
    RefreshSkipped,
    RunCtx,
    env_secret,
    make_offer_id,
    not_configured,
    now,
    parse_pack_units,
    parse_ts,
    registrable_domain,
    save_evidence,
    slug,
    to_float,
    to_int,
)

ENGINES = ("google_shopping", "amazon", "google_immersive_product", "walmart", "ebay")
DEFAULT_ENGINES = ("google_shopping", "amazon")
ENDPOINT = "https://serpapi.com/search.json"
PER_HOUR_LIMIT = int(os.getenv("SERPAPI_MAX_PER_HOUR") or 45)
REFRESH_MIN_AGE_MIN = 30  # SerpAPI offers are refreshed only when older than this (PLAN §12.3)
MAX_RESULTS_PER_ENGINE = 12
USAGE_FILE = BACKEND_DIR / "runs" / "serpapi_usage.json"

_TRACKING = re.compile(r"^(utm_.*|srsltid|gclid|gbraid|wbraid|tag|ref|ref_|psc|th|linkcode|camp|creative|affid|affiliate.*|clickid|irgwc|sourceid|veh|wmlspartner|mkcid|mkrid|campid|customid|toolid|mkevt)$", re.I)


class QuotaExceeded(RuntimeError):
    """The SerpAPI guard refused an uncached call (45 an hour, SERPAPI_MAX_SEARCHES a day)."""


class QuotaGuard:
    """Counts uncached SerpAPI calls. Shared by every adapter instance in the process, persisted to disk."""

    def __init__(self, path: Path | None = USAGE_FILE, per_hour: int | None = None, per_day: int | None = None) -> None:
        self.path = path
        self.per_hour = per_hour if per_hour is not None else PER_HOUR_LIMIT
        self._per_day = per_day
        self._lock = threading.Lock()
        self._stamps: list[float] = []
        self._load()

    @property
    def per_day(self) -> int:
        return self._per_day if self._per_day is not None else get_settings().serpapi_max_searches

    def _load(self) -> None:
        if self.path and self.path.is_file():
            try:
                self._stamps = [float(x) for x in json.loads(self.path.read_text(encoding="utf-8")).get("calls", [])]
            except (OSError, ValueError, TypeError):
                self._stamps = []

    def _save(self) -> None:
        if not self.path or (self.path == USAGE_FILE and os.getenv("PYTEST_CURRENT_TEST")):
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"calls": self._stamps[-500:]}), encoding="utf-8")
        except OSError:
            pass  # the in-memory count still guards this process

    def _window(self, seconds: float) -> int:
        cutoff = time.time() - seconds
        return sum(1 for t in self._stamps if t >= cutoff)

    def used_last_hour(self) -> int:
        return self._window(3600)

    def used_today(self) -> int:
        start = now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return sum(1 for t in self._stamps if t >= start)

    def remaining(self) -> int:
        return max(0, min(self.per_hour - self.used_last_hour(), self.per_day - self.used_today()))

    def check(self) -> None:
        with self._lock:
            if self.used_last_hour() >= self.per_hour:
                raise QuotaExceeded(f"SerpAPI guard: {self.per_hour} uncached searches in the last hour (free plan: 50/hour)")
            if self.used_today() >= self.per_day:
                raise QuotaExceeded(f"SerpAPI guard: SERPAPI_MAX_SEARCHES={self.per_day} reached for today")

    def record(self) -> None:
        with self._lock:
            self._stamps.append(time.time())
            self._save()


QUOTA = QuotaGuard()


def usage() -> dict[str, int]:
    """For /api/health (`serpapi_used`) and scripts/record_hero.py."""
    return {"used_today": QUOTA.used_today(), "used_last_hour": QUOTA.used_last_hour(),
            "limit_hour": QUOTA.per_hour, "limit_day": QUOTA.per_day, "remaining": QUOTA.remaining()}


# --------------------------------------------------------------------------- link and id helpers


def clean_link(url: str | None) -> str | None:
    """Drop tracking and affiliate parameters from a store link; canonical form for the marketplaces."""
    if not url or not url.startswith(("https://", "http://")):
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if asin := asin_from(url):
        if "amazon." in host:
            return f"https://www.amazon.com/dp/{asin}"
    if (wid := walmart_id_from(url)) and "walmart." in host:
        return f"https://www.walmart.com/ip/{wid}"
    if (eid := ebay_id_from(url)) and "ebay." in host:
        return f"https://www.ebay.com/itm/{eid}"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if not _TRACKING.match(k)]
    return urlunsplit(("https", parts.netloc, parts.path, urlencode(query), ""))


def asin_from(url: str | None) -> str | None:
    m = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)", url or "")
    return m.group(1) if m else None


def walmart_id_from(url: str | None) -> str | None:
    m = re.search(r"/ip/(?:[^/?]+/)?(\d{4,15})(?:[/?]|$)", url or "")
    return m.group(1) if m else None


def ebay_id_from(url: str | None) -> str | None:
    m = re.search(r"/itm/(?:[^/?]+/)?(\d{9,15})(?:[/?]|$)", url or "")
    return m.group(1) if m else None


def bestbuy_sku_from(url: str | None) -> str | None:
    """Best Buy SKU from a product URL: /site/<slug>/<sku>.p or ?skuId=<sku> [unverified, PLAN §3.16]."""
    m = re.search(r"/(\d{6,8})\.p(?:[?/]|$)", url or "") or re.search(r"[?&]skuId=(\d{6,8})", url or "")
    return m.group(1) if m else None


def _shipping(text: Any) -> float | None:
    """A shipping figure only when the source states one ("Free delivery" -> 0, "$5.99 shipping" -> 5.99)."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    if isinstance(text, list):
        text = " ".join(str(x) for x in text)
    s = str(text or "").lower()
    if not s:
        return None
    if "free" in s and ("ship" in s or "deliver" in s):
        return 0.0
    m = re.search(r"\$\s?(\d+(?:\.\d{1,2})?)\s*(?:shipping|delivery)", s)
    return float(m.group(1)) if m else None


def _eta(text: Any) -> str | None:
    if isinstance(text, list):
        text = "; ".join(str(x) for x in text)
    s = str(text or "").strip()
    return s[:120] if s and re.search(r"\b(by|arrives|get it|days?|tomorrow|mon|tue|wed|thu|fri|sat|sun)\b", s, re.I) else None


def _stock_from_text(text: Any) -> str:
    s = (" ".join(text) if isinstance(text, list) else str(text or "")).lower()
    if "out of stock" in s or "sold out" in s:
        return "out_of_stock"
    if "in stock" in s:
        return "in_stock"
    return "unknown"


def _store_for(name: str | None, link: str | None) -> tuple[str, str]:
    s = (store_registry.store_for_host(link) if link else None) or store_registry.store_for_merchant_name(name)
    if s:
        return s["store_id"], s["display_name"]
    host = urlsplit(link).hostname if link else None
    if host and "google." not in host:
        return registrable_domain(host), name or host
    return slug(name or "unknown-store"), name or "Unknown store"


# --------------------------------------------------------------------------- adapters


class MockSerpApi(FixtureAdapter):
    stands_for = ("serpapi",)
    calls_used = 0  # uncached calls today; reported by /api/health


class LiveSerpApi:
    source_api = "serpapi"
    hosts = frozenset({"serpapi.com"})

    def __init__(self, engines: tuple[str, ...] | None = None, quota: QuotaGuard | None = None) -> None:
        env = tuple(e.strip() for e in (os.getenv("SERPAPI_ENGINES") or "").split(",") if e.strip())
        self.engines = tuple(e for e in (engines or env or DEFAULT_ENGINES) if e in ENGINES and e != "google_immersive_product")
        self.quota = quota or QUOTA

    @property
    def calls_used(self) -> int:
        return self.quota.used_today()

    def configured(self) -> bool:
        return bool(env_secret("SERPAPI_KEY"))

    def _key(self) -> str:
        key = env_secret("SERPAPI_KEY")
        if not key:
            raise not_configured("§3.16, §3.11", "SERPAPI_KEY is not set: a human adds it to .env (PLAN §1.1)")
        return key

    async def _call(self, engine: str, params: dict[str, Any], ctx: RunCtx, *, bypass: bool = False) -> http.Fetched:
        key = self._key()
        full = {"engine": engine, **params}
        res = await http.fetch(ENDPOINT, adapter_hosts=self.hosts, params=full, secret_params={"api_key": key},
                               tool=f"serpapi.{engine}", bypass_cache=bypass or ctx.bypass_cache, before_network=self.quota.check)
        if not res.cached:
            self.quota.record()
        if isinstance(res.value, dict) and res.value.get("error") and not any(
                res.value.get(k) for k in ("shopping_results", "organic_results", "product_results")):
            msg = str(res.value["error"])
            if "hasn't returned any results" in msg or "no results" in msg.lower():
                return http.Fetched({}, res.seen_at, res.cached)
            raise AdapterError(f"SerpAPI {engine}: {msg[:160]}")
        return res

    def _evidence(self, ctx: RunCtx, engine: str, params: dict[str, Any], res: http.Fetched) -> tuple[str, str]:
        return save_evidence(ctx.run_id, {"source_api": f"serpapi:{engine}", "params": params, "seen_at": res.seen_at,
                                          "cached": res.cached, "response": res.value})

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        """google_shopping + amazon by default; one failing engine never fails the others."""
        self._key()
        query = re.sub(r"\s+", " ", (q.query or q.spec or "")).strip()[:200]
        if not query:
            return []
        offers: list[Offer] = []
        errors: list[str] = []
        for engine in self.engines:
            try:
                offers += await getattr(self, f"_{engine}")(query, ctx)
            except QuotaExceeded:
                raise
            except (AdapterError, http.StoreHTTPError, http.HostNotAllowed) as exc:
                errors.append(f"{engine}: {exc}")
        if errors and not offers:
            raise AdapterError("; ".join(errors)[:400])
        return offers

    # ---- engines

    async def _google_shopping(self, query: str, ctx: RunCtx, *, bypass: bool = False) -> list[Offer]:
        params = {"q": query, "gl": "us", "hl": "en", "location": "United States"}
        res = await self._call("google_shopping", params, ctx, bypass=bypass)
        ev = self._evidence(ctx, "google_shopping", params, res)
        out = []
        rows = (res.value or {}).get("shopping_results") or []
        for r in rows[:MAX_RESULTS_PER_ENGINE]:
            price = to_float(r.get("extracted_price"))
            if price is None or price <= 0:
                continue
            link = r.get("product_link") or r.get("link")
            store_id, store_name = _store_for(r.get("source"), None)
            ids: dict[str, str] = {"serp_q": query, "serp_engine": "google_shopping"}
            if r.get("immersive_product_page_token"):
                ids["immersive_token"] = str(r["immersive_product_page_token"])
            if r.get("product_id"):
                ids["google_product_id"] = str(r["product_id"])
            cond = str(r.get("second_hand_condition") or "").lower()
            level, reason = store_registry.effective_level(store_id, has_item_ids=False, qty=1)
            title = str(r.get("title") or "")
            out.append(Offer(
                offer_id=make_offer_id("serpapi:google_shopping", store_id, ids.get("google_product_id") or f"{title}|{r.get('source')}"),
                store_id=store_id, store_name=store_name, seller_name=None, title=title[:300], url=link or "",
                price_usd=price, units_per_pack=parse_pack_units(title), shipping_usd=_shipping(r.get("delivery")),
                eta_text=_eta(r.get("delivery")), stock="unknown", condition="used" if cond else "unknown",
                rating=to_float(r.get("rating")), reviews=to_int(r.get("reviews")), ids=ids, action_level=level,
                downgrade_reason=reason, source_api="serpapi:google_shopping", seen_at=res.seen_at,
                evidence_path=ev[0], evidence_sha256=ev[1]))
        return out

    async def _amazon(self, query: str, ctx: RunCtx, *, bypass: bool = False) -> list[Offer]:
        params = {"k": query, "amazon_domain": "amazon.com", "language": "en_US"}
        res = await self._call("amazon", params, ctx, bypass=bypass)
        ev = self._evidence(ctx, "amazon", params, res)
        out = []
        for r in ((res.value or {}).get("organic_results") or [])[:MAX_RESULTS_PER_ENGINE]:
            asin = str(r.get("asin") or "") or asin_from(r.get("link"))
            price = to_float(r.get("extracted_price"))
            if not asin or not re.fullmatch(r"[A-Z0-9]{10}", asin) or price is None or price <= 0 or r.get("sponsored"):
                continue
            title = str(r.get("title") or "")
            level, reason = store_registry.effective_level("amazon", has_item_ids=True, qty=1)
            out.append(Offer(
                offer_id=make_offer_id("serpapi:amazon", "amazon", asin), store_id="amazon", store_name="Amazon",
                seller_name=None, title=title[:300], url=f"https://www.amazon.com/dp/{asin}", price_usd=price,
                units_per_pack=parse_pack_units(title), shipping_usd=_shipping(r.get("delivery")), eta_text=_eta(r.get("delivery")),
                stock="unknown", condition="new", rating=to_float(r.get("rating")), reviews=to_int(r.get("reviews")),
                ids={"asin": asin, "serp_q": query, "serp_engine": "amazon"}, action_level=level, downgrade_reason=reason,
                source_api="serpapi:amazon", seen_at=res.seen_at, evidence_path=ev[0], evidence_sha256=ev[1]))
        return out

    async def _walmart(self, query: str, ctx: RunCtx, *, bypass: bool = False) -> list[Offer]:
        params = {"query": query}
        res = await self._call("walmart", params, ctx, bypass=bypass)
        ev = self._evidence(ctx, "walmart", params, res)
        out = []
        for r in ((res.value or {}).get("organic_results") or [])[:MAX_RESULTS_PER_ENGINE]:
            wid = str(r.get("us_item_id") or "") or walmart_id_from(r.get("product_page_url"))
            offer = r.get("primary_offer") or {}
            price = to_float(offer.get("offer_price"))
            if not wid or not wid.isdigit() or price is None or price <= 0:
                continue
            title = str(r.get("title") or "")
            level, reason = store_registry.effective_level("walmart", has_item_ids=True, qty=1)
            oos = r.get("out_of_stock")
            out.append(Offer(
                offer_id=make_offer_id("serpapi:walmart", "walmart", wid), store_id="walmart", store_name="Walmart",
                seller_name=r.get("seller_name"), title=title[:300], url=f"https://www.walmart.com/ip/{wid}", price_usd=price,
                units_per_pack=parse_pack_units(title), shipping_usd=0.0 if r.get("free_shipping") else None,
                eta_text="2-day shipping" if r.get("two_day_shipping") else None,
                stock="out_of_stock" if oos is True else "in_stock" if oos is False else "unknown", condition="new",
                rating=to_float(r.get("rating")), reviews=to_int(r.get("reviews")),
                ids={"walmart_id": wid, "serp_q": query, "serp_engine": "walmart"}, action_level=level, downgrade_reason=reason,
                source_api="serpapi:walmart", seen_at=res.seen_at, evidence_path=ev[0], evidence_sha256=ev[1]))
        return out

    async def _ebay(self, query: str, ctx: RunCtx, *, bypass: bool = False) -> list[Offer]:
        params = {"_nkw": query, "ebay_domain": "ebay.com", "LH_BIN": "1", "LH_ItemCondition": "1000"}
        res = await self._call("ebay", params, ctx, bypass=bypass)
        ev = self._evidence(ctx, "ebay", params, res)
        out = []
        for r in ((res.value or {}).get("organic_results") or [])[:MAX_RESULTS_PER_ENGINE]:
            item = str(r.get("product_id") or "") or ebay_id_from(r.get("link"))
            price_obj = r.get("price") or {}
            price = to_float(price_obj.get("extracted")) if isinstance(price_obj, dict) else to_float(price_obj)
            if price is None and isinstance(price_obj, dict) and isinstance(price_obj.get("from"), dict):
                price = to_float(price_obj["from"].get("extracted"))
            fmt = str(r.get("buying_format") or "").lower()
            if not item or not item.isdigit() or price is None or price <= 0 or "auction" in fmt or r.get("bids"):
                continue  # auctions have no fixed price (PLAN §3.16 rule 6)
            cond = str(r.get("condition") or "").lower()
            title = str(r.get("title") or "")
            level, reason = store_registry.effective_level("ebay", has_item_ids=True, qty=1)
            seller = r.get("seller") or {}
            out.append(Offer(
                offer_id=make_offer_id("serpapi:ebay", "ebay", item), store_id="ebay", store_name="eBay",
                seller_name=seller.get("username") if isinstance(seller, dict) else None, title=title[:300],
                url=f"https://www.ebay.com/itm/{item}", price_usd=price, units_per_pack=parse_pack_units(title),
                shipping_usd=_shipping(r.get("shipping")), stock="unknown",
                condition="new" if cond.startswith(("brand new", "new")) and "other" not in cond else "used" if cond else "unknown",
                rating=None, reviews=None, ids={"ebay_item": item, "serp_q": query, "serp_engine": "ebay"},
                action_level=level, downgrade_reason=reason, source_api="serpapi:ebay", seen_at=res.seen_at,
                evidence_path=ev[0], evidence_sha256=ev[1]))
        return out

    async def immersive(self, offer_or_token: Offer | str, ctx: RunCtx, *, bypass: bool = False) -> list[Offer]:
        """Every store's offer for one Google Shopping product (the part panel's "every store" table).

        Run it only for the top-ranked result of a line that will be bought (PLAN §3.16): one search each.
        """
        self._key()
        token = offer_or_token.ids.get("immersive_token") if isinstance(offer_or_token, Offer) else offer_or_token
        if not token:
            return []
        title_hint = offer_or_token.title if isinstance(offer_or_token, Offer) else ""
        params = {"page_token": token}
        res = await self._call("google_immersive_product", params, ctx, bypass=bypass)
        ev = self._evidence(ctx, "google_immersive_product", params, res)
        pr = (res.value or {}).get("product_results") or {}
        title = str(pr.get("title") or title_hint or "")
        out = []
        for st in (pr.get("stores") or [])[:20]:
            price = to_float(st.get("extracted_price"))
            link = clean_link(st.get("link"))
            if price is None or price <= 0 or not link:
                continue
            store_id, store_name = _store_for(st.get("name"), link)
            ids: dict[str, str] = {"immersive_token": str(token), "serp_engine": "google_immersive_product"}
            if a := asin_from(link):
                ids["asin"] = a
            if w := walmart_id_from(link):
                ids["walmart_id"] = w
            if e := ebay_id_from(link):
                ids["ebay_item"] = e
            if b := bestbuy_sku_from(link):
                ids["bestbuy_sku"] = b
            has_ids = bool(ids.get(ID_KEYS.get(store_id, ""), ""))
            level, reason = store_registry.effective_level(store_id, has_item_ids=has_ids, qty=1)
            ship = to_float(st.get("extracted_shipping")) if st.get("extracted_shipping") is not None else _shipping(st.get("shipping"))
            out.append(Offer(
                offer_id=make_offer_id("serpapi:google_immersive_product", store_id, link), store_id=store_id, store_name=store_name,
                seller_name=None, title=(str(st.get("title") or title))[:300], url=link, price_usd=price,
                units_per_pack=parse_pack_units(title), shipping_usd=ship, eta_text=_eta(st.get("delivery")),
                stock=_stock_from_text(st.get("details_and_offers")), condition="unknown",
                rating=to_float(st.get("rating")), reviews=to_int(st.get("reviews")), ids=ids, action_level=level,
                downgrade_reason=reason, source_api="serpapi:google_immersive_product", seen_at=res.seen_at,
                evidence_path=ev[0], evidence_sha256=ev[1]))
        return out

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        """Only when older than 30 minutes and the quota allows; otherwise the age stays visible (PLAN §12.3)."""
        seen = parse_ts(offer.seen_at)
        if seen is not None and (now() - seen).total_seconds() < REFRESH_MIN_AGE_MIN * 60:
            raise RefreshSkipped(f"SerpAPI price is under {REFRESH_MIN_AGE_MIN} minutes old")
        if self.quota.remaining() < 1:
            raise RefreshSkipped("SerpAPI quota")
        engine = offer.ids.get("serp_engine") or offer.source_api.split(":", 1)[-1]
        query = offer.ids.get("serp_q", "")
        if engine == "google_immersive_product":
            fresh = await self.immersive(offer.ids.get("immersive_token", ""), ctx, bypass=True)
        elif engine in ("google_shopping", "amazon", "walmart", "ebay") and query:
            fresh = await getattr(self, f"_{engine}")(query, ctx, bypass=True)
        else:
            return None
        match = next((o for o in fresh if o.offer_id == offer.offer_id), None)
        if match is None:
            return offer.model_copy(update={"stock": "unknown", "seen_at": fresh[0].seen_at if fresh else offer.seen_at})
        return offer.model_copy(update={"price_usd": match.price_usd, "stock": match.stock, "seen_at": match.seen_at,
                                        "shipping_usd": match.shipping_usd, "evidence_path": match.evidence_path,
                                        "evidence_sha256": match.evidence_sha256})
