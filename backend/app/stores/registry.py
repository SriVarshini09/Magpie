"""Store registry: loads data/stores.json and hands out adapters (PLAN §3.16). Owner: B.

Which class backs an adapter (mock or live) is decided by app/registry.py (shared, coordinator-owned).

Action levels only go DOWN from the registry level (PLAN §3.16 rule 2): a prefilled-cart format that no
human has opened in a real browser, a missing item id, a quantity the format cannot express, or a link
over 1,700 characters all make the store a product link. The reason is shown on the badge tooltip.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from app import registry as services
from app.config import DATA_DIR
from app.models import StoreInfo
from app.stores.base import ACTION_RANK, registrable_domain

ADAPTER_SERVICES = ("shopify_ucp", "serpapi", "adafruit", "magento", "digikey")
MAX_URL_CHARS = 1700  # Digi-Key FastAdd; longer prefilled links downgrade to product links

REASON_UNVERIFIED = "This store's prefilled cart link has not yet been opened in a real browser by a human, so it is shown as product links"
REASON_FAILED = "Prefilled cart link failed its browser check: shown as product links"
REASON_NO_ID = "An item has no store id for the prefilled link"
REASON_NO_VARIANT = "An item has no Shopify variant id, so no agent cart can be built"
REASON_QTY = "This store's link adds one of each item; a quantity above 1 needs the product page"
REASON_TOO_LONG = "The prefilled link would be longer than 1,700 characters"


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    return json.loads((DATA_DIR / "stores.json").read_text(encoding="utf-8"))


def reload() -> None:
    load_registry.cache_clear()


def all_stores() -> list[dict[str, Any]]:
    return list(load_registry()["stores"])


def store(store_id: str) -> dict[str, Any] | None:
    return next((s for s in load_registry()["stores"] if s["store_id"] == store_id), None)


def sources() -> list[dict[str, Any]]:
    return list(load_registry().get("sources", []))


def _enabled(s: dict[str, Any]) -> bool:
    if s.get("enabled"):
        return True
    needs = s.get("enabled_if_env") or []
    return bool(needs) and all((os.getenv(n) or "").strip() for n in needs)


def cart_link_verified(store_id: str) -> bool | None:
    """True / False after a human's browser check, None while nobody has checked (PLAN §2.1, 1:15).

    `CART_LINKS_VERIFIED=amazon,bestbuy` in .env marks formats verified without editing stores.json.
    """
    env = {x.strip() for x in (os.getenv("CART_LINKS_VERIFIED") or "").split(",") if x.strip()}
    if store_id in env:
        return True
    s = store(store_id)
    return None if s is None else s.get("cart_link_verified")


def registry_level(store_id: str) -> str:
    """The level the registry promises before any downgrade. Unknown stores are product links."""
    s = store(store_id)
    return s["action_level"] if s else "product_link"


def display_name(store_id: str, fallback: str | None = None) -> str:
    s = store(store_id)
    return s["display_name"] if s else (fallback or store_id)


def domain(store_id: str, fallback_url: str | None = None) -> str:
    s = store(store_id)
    if s:
        return s["domain"]
    if fallback_url:
        return urlsplit(fallback_url).hostname or store_id
    return store_id


def stores() -> list[StoreInfo]:
    """GET /api/stores: the registry with each store's level AFTER the verification downgrade."""
    out = []
    for s in load_registry()["stores"]:
        level, reason = effective_level(s["store_id"], has_item_ids=True, qty=1)
        caveat = s.get("caveat")
        if reason and level != s["action_level"]:
            caveat = reason if not caveat else f"{caveat}. {reason}"
        out.append(StoreInfo(store_id=s["store_id"], display_name=s["display_name"], domain=s["domain"], action_level=level,
                             caveat=caveat, enabled=_enabled(s), simulated=bool(s.get("simulated"))))
    return out


def effective_level(store_id: str, *, has_item_ids: bool, qty: int, url_len: int = 0) -> tuple[str, str | None]:
    """Downgrades, never upgrades (PLAN §3.16 rule 2). Returns (action_level, downgrade_reason)."""
    level = registry_level(store_id)
    if level == "agent_cart":
        if not has_item_ids:
            return "product_link", REASON_NO_VARIANT
        return "agent_cart", None
    if level == "prefilled_cart":
        verified = cart_link_verified(store_id)
        if verified is None:
            return "product_link", REASON_UNVERIFIED
        if verified is False:
            return "product_link", REASON_FAILED
        if not has_item_ids:
            return "product_link", REASON_NO_ID
        s = store(store_id) or {}
        max_qty = s.get("max_qty_per_item")
        if max_qty and qty > max_qty:
            return "product_link", REASON_QTY
        if url_len > MAX_URL_CHARS:
            return "product_link", REASON_TOO_LONG
        return "prefilled_cart", None
    return "product_link", None


def lower(a: str, b: str) -> str:
    """The weaker of two action levels."""
    return a if ACTION_RANK[a] >= ACTION_RANK[b] else b


# --------------------------------------------------------------------------- lookups


def _host(url_or_host: str) -> str:
    s = url_or_host if "://" in url_or_host else "//" + url_or_host
    return (urlsplit(s).hostname or "").lower().strip(".")


def store_for_shopify_domain(domain_or_url: str) -> dict[str, Any] | None:
    """The registry store for a UCP seller domain (the myshopify domain or a public one)."""
    host = _host(domain_or_url)
    if not host:
        return None
    for s in load_registry()["stores"]:
        doms = [d.lower() for d in s.get("shopify_domains") or []]
        if s.get("search_source") == "shopify_ucp" and (host in doms or host == s["domain"].lower()):
            return s
    return None


def store_for_host(url_or_host: str) -> dict[str, Any] | None:
    """The registry store a product URL belongs to (www.amazon.com/dp/... -> amazon)."""
    host = _host(url_or_host)
    if not host:
        return None
    reg = registrable_domain(host)
    for s in load_registry()["stores"]:
        doms = {s["domain"].lower(), *[d.lower() for d in s.get("shopify_domains") or []]}
        if host in doms or reg in {registrable_domain(d) for d in doms if "myshopify" not in d}:
            return s
    return None


def store_for_merchant_name(name: str | None) -> dict[str, Any] | None:
    """Google Shopping's `source` ("Amazon.com", "Walmart - Seller") -> a registry store."""
    if not name:
        return None
    n = name.strip().lower()
    base = n.split(" - ")[0].strip()
    for s in load_registry()["stores"]:
        names = {x.lower() for x in s.get("merchant_names") or []} | {s["display_name"].lower()}
        if n in names or base in names:
            return s
    return None


def all_store_domains() -> set[str]:
    """Every domain the registry knows for a store: reference providers must never read these pages."""
    out: set[str] = set()
    for s in load_registry()["stores"]:
        if s.get("simulated"):
            continue
        out.add(s["domain"].lower())
        out.update(d.lower() for d in s.get("shopify_domains") or [])
    return out


# --------------------------------------------------------------------------- adapters


def adapters() -> dict[str, Any]:
    """Every enabled adapter, mock or live as the service registry decides."""
    return {name: services.get(name) for name in ADAPTER_SERVICES}


def adapter_for_source(source_api: str) -> Any | None:
    """The adapter that can refresh an offer with this source_api ("serpapi:amazon" -> serpapi)."""
    base = (source_api or "").split(":", 1)[0]
    if base in ADAPTER_SERVICES:
        return services.get(base)
    if base == "jsonld":
        from app.stores.jsonld import JsonLdAdapter

        return JsonLdAdapter()
    if base == "mock":
        from app.stores.mock import MockStore

        return MockStore()
    return None


def health() -> dict[str, str]:
    """Per-adapter state for /api/health: "mock", "ok" (configured), or "off" (no key / no CLI)."""
    out: dict[str, str] = {}
    for name in (*ADAPTER_SERVICES, "cartlinks"):
        if services.impl_mode(name) == "mock":
            out[name] = "mock"
            continue
        impl = services.get(name)
        probe = getattr(impl, "configured", None)
        try:
            out[name] = "ok" if (probe() if callable(probe) else True) else "off"
        except Exception:  # a probe must never break /api/health
            out[name] = "down"
    return out
