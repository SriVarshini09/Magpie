"""Shared helpers for B's tests (stores, checkout, providers). Not a test module.

Every B test runs with: the cache and evidence folders in a temp dir, no chain/evidence writes from D's
stubs, no network (a MockTransport or nothing: stores/http.py refuses the network under pytest), and the
cart book cleared. `set_mode` switches DEMO_MODE for one test and puts it back.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from app.models import Offer

SK_TEST = "sk_" + "test_" + "x" * 24  # fake values, built at runtime so no key-shaped literal sits in the repo
PK_TEST = "pk_" + "test_" + "x" * 24


@pytest.fixture()
def b_env(monkeypatch, tmp_path):
    from app import cache, config, registry
    from app.audit import chain, evidence
    from app.checkout import cart
    from app.intake import reference
    from app.stores import base, http
    from app.stores import registry as store_registry

    def _stub(*a: Any, **k: Any) -> Any:
        raise NotImplementedError("stubbed in B's tests")

    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(base, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(evidence, "write_evidence", _stub)
    monkeypatch.setattr(chain, "append", _stub)
    cache.clear_memory()
    cart.BOOK.clear()
    saved_hooks = dict(cart.HOOKS.__dict__)
    reference.reset_budget()
    store_registry.reload()
    yield tmp_path
    http.set_transport(None)
    cache.clear_memory()
    cart.BOOK.clear()
    cart.HOOKS.__dict__.update(saved_hooks)
    reference._extra.clear()
    monkeypatch.setenv("DEMO_MODE", "mock")
    config.reload_settings()
    registry.reset()
    store_registry.reload()


def set_mode(monkeypatch, mode: str) -> None:
    from app import config, registry

    monkeypatch.setenv("DEMO_MODE", mode)
    config.reload_settings()
    registry.reset()


def install(handler: Callable[[Any], Any]) -> list[Any]:
    """Install an httpx.MockTransport; returns the list of requests it saw."""
    import httpx

    from app.stores import http

    seen: list[Any] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http.set_transport(httpx.MockTransport(wrapped))
    return seen


def json_response(body: Any, status: int = 200) -> Any:
    import httpx

    return httpx.Response(status, content=json.dumps(body).encode(), headers={"content-type": "application/json"})


def offer(offer_id: str, store_id: str, price: float, *, level: str = "agent_cart", units: int = 1, ids: dict[str, str] | None = None,
          source_api: str = "shopify_ucp", seen_at: str = "2026-11-20T13:04:10-08:00", stock: str = "in_stock",
          refused: str | None = None, url: str | None = None, simulated: bool = False, title: str | None = None) -> Offer:
    return Offer(offer_id=offer_id, store_id=store_id, store_name=store_id.title(), title=title or f"{store_id} item {offer_id}",
                 url=url or f"https://{store_id}.example/p/{offer_id}", price_usd=price, units_per_pack=units, stock=stock,
                 condition="new", ids=ids or {}, action_level=level, source_api=source_api, seen_at=seen_at,
                 evidence_sha256="e" * 64, refused=refused, simulated=simulated)
