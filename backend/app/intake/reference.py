"""Reference-design search: Keenable -> Exa via Airbyte -> Claude web search -> GitHub search (PLAN §3.18, P19).

Owner: B (providers and this chain; A's tool `find_reference_design` calls `find_reference_design` below).

Rules, enforced here in code:
- The query is checked BEFORE any provider is called: a never-request host (stores/http.py) or a store's
  domain in it is refused with `reference_host_not_allowed`. No provider is ever asked to search or fetch a
  store page (PLAN §3.16 rule 3): prices come only from SerpAPI and store APIs.
- Every result is checked BEFORE its text is read; results pointing at a never-request host or a store are
  dropped. Exa gets those domains as `exclude_domains` as well.
- At most REFERENCE_MAX_SEARCHES searches and REFERENCE_MAX_PAGES page reads per run; all calls are cached.
- A result only FINDS a page. The text we return is hashed on arrival (`doc_sha256` = sha256 of `text`, the
  exact string A's quote check runs against). Page text is data, never instructions.
- A provider with no key is skipped; one that fails is skipped; the next provider runs.
"""

from __future__ import annotations

import re
import typing
from typing import Any
from urllib.parse import urlsplit

from app import registry as services
from app.config import get_settings
from app.models import FetchedVia
from app.stores.base import NotConfigured, now_iso, registrable_domain, sha256_hex
from app.stores.http import NEVER_REQUEST, HostNotAllowed, host_of, is_never_request

PROVIDER_SERVICES = {"keenable": "keenable", "exa_airbyte": "exa_airbyte", "github_search": "github_search"}
MARKETPLACES = frozenset({"aliexpress.com", "aliexpress.us", "alibaba.com", "temu.com", "etsy.com", "newegg.com", "mouser.com",
                          "arrow.com", "lcsc.com", "newark.com", "farnell.com", "pololu.com"})
MIN_TEXT_CHARS = 200
_DOMAIN_TOKEN = re.compile(r"(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?=[/\s?#:]|$)", re.I)

_extra: dict[str, Any] = {}  # e.g. register_provider("claude_web_search", obj) by A
_budget: dict[str, dict[str, int]] = {}


def register_provider(provider_id: str, provider: Any) -> None:
    """Plug in a provider that is not a registry service (A: Claude web search, provider 3)."""
    _extra[provider_id] = provider


def reset_budget(run_id: str | None = None) -> None:
    if run_id is None:
        _budget.clear()
    else:
        _budget.pop(run_id, None)


def blocked_domains() -> set[str]:
    """Never-request hosts, every store in the registry and the marketplaces: never read through a provider."""
    from app.stores import registry as store_registry

    doms = {registrable_domain(d) for d in store_registry.all_store_domains() if "myshopify" not in d}
    return set(NEVER_REQUEST) | doms | set(MARKETPLACES) | {d for d in store_registry.all_store_domains() if "myshopify" in d}


def is_blocked_url(url: str) -> bool:
    host = host_of(url)
    if not host or is_never_request(url):
        return True
    blocked = blocked_domains()
    return host in blocked or registrable_domain(host) in blocked


def check_query(query: str) -> str:
    """Refuse a query that names a never-request host or a store before any provider sees it."""
    for m in _DOMAIN_TOKEN.finditer(query or ""):
        dom = m.group(1).lower()
        if is_blocked_url(dom):
            raise HostNotAllowed(dom, rule="reference_host_not_allowed",
                                 reason="a store or never-request host in a reference search (PLAN §3.16 rule 3)")
    return query


def safe_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop results that point at a never-request host or a store, before their text is read."""
    return [h for h in hits if isinstance(h.get("url"), str) and h["url"].startswith("https://") and not is_blocked_url(h["url"])]


def _provider(provider_id: str) -> Any | None:
    if provider_id in _extra:
        return _extra[provider_id]
    name = PROVIDER_SERVICES.get(provider_id)
    if name is None:
        return None
    impl = services.get(name)
    probe = getattr(impl, "configured", None)
    if callable(probe) and not probe():
        return None
    return impl


def _fetched_via_allowed(value: str) -> bool:
    return value in typing.get_args(FetchedVia)


def _budget_for(run_id: str) -> dict[str, int]:
    return _budget.setdefault(run_id, {"searches": 0, "pages": 0})


async def _read_text(hit: dict[str, Any], provider: Any, run_id: str) -> tuple[str | None, str | None, str | None]:
    """(text, fetched_via, licence) for a hit, reading at most one page. Store pages never get here."""
    s = get_settings()
    b = _budget_for(run_id)
    text, via = hit.get("text"), hit.get("fetched_via")
    if text and via and _fetched_via_allowed(via) and (len(text) >= MIN_TEXT_CHARS or hit.get("simulated")):
        return text, via, hit.get("licence")  # page text the provider returned, hashed on arrival by the caller
    if b["pages"] >= s.reference_max_pages:
        return None, None, None
    url = hit["url"]
    b["pages"] += 1
    try:
        if hit.get("found_via") == "github_search" or urlsplit(url).hostname == "github.com":
            doc = await services.get("airbyte_github").fetch_readme(url)
            return doc.text, doc.via, hit.get("licence")
        if hasattr(provider, "fetch_page") and getattr(provider, "provider_id", "") == "keenable":
            page = await provider.fetch_page(url)
            if page and page.get("text"):
                return page["text"], "keenable", hit.get("licence")
        from app.intake.http import fetch_page  # A's: allowlisted hosts only

        page = await fetch_page(url)
        return page.get("text"), "http", hit.get("licence")
    except (HostNotAllowed, NotImplementedError, NotConfigured):
        return None, None, None
    except Exception:  # noqa: BLE001 - an unreadable page is skipped, the next hit is tried
        return None, None, None


async def find_reference_designs(query: str, run_id: str, *, max_results: int = 3) -> dict[str, Any]:
    """All usable reference pages for one query, plus the attempt log A records as `reference_search`.

    Returns {"query", "results": [result...], "attempts": [{provider, status, hits, kept}]}.
    """
    check_query(query)
    s = get_settings()
    b = _budget_for(run_id)
    attempts: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for pid in s.reference_providers:
        if b["searches"] >= s.reference_max_searches:
            attempts.append({"provider": pid, "status": "skipped: REFERENCE_MAX_SEARCHES reached"})
            break
        provider = _provider(pid)
        if provider is None:
            attempts.append({"provider": pid, "status": "skipped: not configured"})
            continue
        b["searches"] += 1
        try:
            hits = await provider.search(query, max_results)
        except (NotConfigured, NotImplementedError):
            attempts.append({"provider": pid, "status": "skipped: not configured"})
            continue
        except HostNotAllowed as exc:
            attempts.append({"provider": pid, "status": f"refused: {exc.reason}"})
            continue
        except Exception as exc:  # noqa: BLE001 - a failing provider is a grey dot, the next one runs
            attempts.append({"provider": pid, "status": f"error: {type(exc).__name__}"})
            continue
        kept = safe_hits(hits or [])
        attempts.append({"provider": pid, "status": "ok", "hits": len(hits or []), "kept": len(kept)})
        for hit in kept:
            text, via, licence = await _read_text(hit, provider, run_id)
            min_len = 1 if hit.get("simulated") else MIN_TEXT_CHARS // 4
            if not text or len(text.strip()) < min_len or not via:
                continue
            results.append({
                "url": hit["url"], "title": hit.get("title") or hit["url"], "licence": licence, "text": text,
                "doc_sha256": sha256_hex(text), "found_via": hit.get("found_via") or pid, "fetched_via": via,
                "fetched_at": now_iso(), "provider": pid, "query": query,
                "source_api": hit.get("source_api") or pid, "simulated": bool(hit.get("simulated")),
            })
            if len(results) >= max_results:
                break
        if results:
            break
    return {"query": query, "results": results, "attempts": attempts}


async def find_reference_design(query: str, run_id: str) -> dict[str, Any] | None:
    """{url, title, licence?, doc_sha256, text, found_via, fetched_via, fetched_at, provider, attempts} or None.

    The one function A's `find_reference_design` tool calls. HostNotAllowed (rule reference_host_not_allowed)
    is raised for a query naming a store or a never-request host: record it as a refusal.
    """
    out = await find_reference_designs(query, run_id, max_results=1)
    if not out["results"]:
        return None
    return {**out["results"][0], "attempts": out["attempts"]}
