"""Digi-Key Product Information API v4 (PLAN §3.16, Appendix A.4, P11). Owner: B.

Only api.digikey.com, and only with the developer key. The Digi-Key WEBSITE is on the never-request list:
the FastAdd cart link (stores/cartlinks.py) is a string the user's browser opens.

    POST https://api.digikey.com/v1/oauth2/token                 client_credentials (DIGIKEY_CLIENT_ID / _SECRET)
    POST https://api.digikey.com/products/v4/search/keyword      {"Keywords": "...", "Limit": 10}
    GET  https://api.digikey.com/products/v4/search/{pn}/productdetails
    headers: Authorization: Bearer <token>, X-DIGIKEY-Client-Id, X-DIGIKEY-Locale-Site: US,
             X-DIGIKEY-Locale-Language: en, X-DIGIKEY-Locale-Currency: USD
Paths and the v4 response shape (Products[].ProductVariations[].DigiKeyProductNumber / StandardPricing)
are [unverified, confirm in C23]. Register a PRODUCTION app: sandbox apps only reach sandbox endpoints.
The token is kept in memory only: never in the cache, an evidence file or a log.
"""

from __future__ import annotations

import time
from typing import Any

from app.models import Offer, PartQuery
from app.stores import http
from app.stores import registry as store_registry
from app.stores.base import (
    AdapterError,
    FixtureAdapter,
    RunCtx,
    env_secret,
    make_offer_id,
    not_configured,
    save_evidence,
    to_float,
    to_int,
)

TOKEN_URL = "https://api.digikey.com/v1/oauth2/token"
SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"
DETAILS_URL = "https://api.digikey.com/products/v4/search/{pn}/productdetails"
LOCALE = {"X-DIGIKEY-Locale-Site": "US", "X-DIGIKEY-Locale-Language": "en", "X-DIGIKEY-Locale-Currency": "USD"}
SKIP_PACKAGING = ("tape & reel", "digi-reel")  # reels have large minimums or a reeling fee


def _price_at(pricing: list[dict[str, Any]], qty: int) -> float | None:
    best = None
    for p in sorted(pricing or [], key=lambda x: to_int(x.get("BreakQuantity")) or 0):
        if (to_int(p.get("BreakQuantity")) or 1) <= max(qty, 1):
            best = to_float(p.get("UnitPrice"))
    if best is None and pricing:
        best = to_float(sorted(pricing, key=lambda x: to_int(x.get("BreakQuantity")) or 0)[0].get("UnitPrice"))
    return best


def _offers(products: list[dict[str, Any]], qty: int, seen_at: str, evidence: tuple[str, str]) -> list[Offer]:
    out = []
    for p in products:
        desc = p.get("Description") or {}
        title_bits = [str((p.get("Manufacturer") or {}).get("Name") or ""), str(p.get("ManufacturerProductNumber") or ""),
                      str(desc.get("ProductDescription") or "")]
        title = " ".join(b for b in title_bits if b).strip()
        avail = to_int(p.get("QuantityAvailable"))
        for v in p.get("ProductVariations") or []:
            pn = str(v.get("DigiKeyProductNumber") or "")
            pack = str((v.get("PackageType") or {}).get("Name") or "")
            if not pn or any(s in pack.lower() for s in SKIP_PACKAGING):
                continue
            pricing = v.get("StandardPricing") or []
            price = _price_at(pricing, qty)
            if price is None or price <= 0:
                continue
            tiers = [{"min_qty": to_int(t.get("BreakQuantity")), "price_usd": to_float(t.get("UnitPrice"))} for t in pricing]
            level, reason = store_registry.effective_level("digikey", has_item_ids=True, qty=qty)
            out.append(Offer(
                offer_id=make_offer_id("digikey", "digikey", pn), store_id="digikey", store_name="Digi-Key", seller_name=None,
                title=f"{title} ({pack})" if pack else title, description=str(desc.get("DetailedDescription") or "")[:2000] or None,
                url=str(p.get("ProductUrl") or ""), price_usd=price, currency="USD", units_per_pack=1, tier_prices=tiers or None,
                stock="in_stock" if (avail or 0) > 0 else "out_of_stock" if avail == 0 else "unknown", condition="new",
                ids={"digikey_pn": pn, "mpn": str(p.get("ManufacturerProductNumber") or "")}, action_level=level,
                downgrade_reason=reason, source_api="digikey", seen_at=seen_at, evidence_path=evidence[0], evidence_sha256=evidence[1]))
    return out


class MockDigiKey(FixtureAdapter):
    stands_for = ("digikey",)


class LiveDigiKey:
    source_api = "digikey"
    hosts = frozenset({"api.digikey.com"})

    def __init__(self) -> None:
        self._token: tuple[str, float] | None = None  # (access token, expires at); memory only

    def configured(self) -> bool:
        return bool(env_secret("DIGIKEY_CLIENT_ID") and env_secret("DIGIKEY_CLIENT_SECRET"))

    def _creds(self) -> tuple[str, str]:
        cid, secret = env_secret("DIGIKEY_CLIENT_ID"), env_secret("DIGIKEY_CLIENT_SECRET")
        if not (cid and secret):
            raise not_configured("§3.16, App. A.4 (P11)", "DIGIKEY_CLIENT_ID and DIGIKEY_CLIENT_SECRET are not set (a production app)")
        return cid, secret

    async def _bearer(self) -> str:
        if self._token and self._token[1] > time.time() + 30:
            return self._token[0]
        cid, secret = self._creds()
        res = await http.fetch(TOKEN_URL, adapter_hosts=self.hosts, method="POST", use_cache=False,
                               data={"client_id": cid, "client_secret": secret, "grant_type": "client_credentials"})
        body = res.value if isinstance(res.value, dict) else {}
        token = body.get("access_token")
        if not token:
            raise AdapterError("Digi-Key token request returned no access_token")
        self._token = (str(token), time.time() + float(body.get("expires_in") or 600))
        return self._token[0]

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._bearer()}", "X-DIGIKEY-Client-Id": self._creds()[0]}

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        term = (q.query or q.spec or "").strip()[:200]
        if not term:
            return []
        body = {"Keywords": term, "Limit": 10, "Offset": 0}
        res = await http.fetch(SEARCH_URL, adapter_hosts=self.hosts, method="POST", json_body=body, headers=dict(LOCALE),
                               secret_headers=await self._headers(), tool="digikey.keyword", bypass_cache=ctx.bypass_cache)
        ev = save_evidence(ctx.run_id, {"source_api": "digikey", "request": body, "seen_at": res.seen_at, "response": res.value})
        products = (res.value or {}).get("Products") if isinstance(res.value, dict) else None
        return _offers(products or [], q.qty, res.seen_at, ev)

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        pn = offer.ids.get("digikey_pn", "")
        if not pn:
            return None
        from urllib.parse import quote

        url = DETAILS_URL.format(pn=quote(pn, safe=""))
        res = await http.fetch(url, adapter_hosts=self.hosts, headers=dict(LOCALE), secret_headers=await self._headers(),
                               tool="digikey.details", bypass_cache=True)
        ev = save_evidence(ctx.run_id, {"source_api": "digikey", "details": pn, "seen_at": res.seen_at, "response": res.value})
        product = (res.value or {}).get("Product") if isinstance(res.value, dict) else None
        fresh = next((o for o in _offers([product] if product else [], 1, res.seen_at, ev) if o.ids.get("digikey_pn") == pn), None)
        if fresh is None:
            return offer.model_copy(update={"stock": "unknown", "seen_at": res.seen_at})
        return offer.model_copy(update={"price_usd": fresh.price_usd, "stock": fresh.stock, "tier_prices": fresh.tier_prices,
                                        "seen_at": fresh.seen_at, "evidence_path": ev[0], "evidence_sha256": ev[1]})
