"""Keenable: reference-design search and page text, provider 1 (PLAN §3.18, P19). Owner: B.

Never pass a never-request host or a store page to this provider: intake/reference.py checks the query and
every result first (stores/http.py `is_never_request`, the store registry's domains).

    POST https://api.keenable.ai/v1/search   {"query": "...", "limit": n}          -> results with url, title, text
    POST https://api.keenable.ai/v1/fetch    {"url": "..."}                         -> page text as Markdown
Request and response shapes are [unverified: write them down in check C30]. The endpoints, the auth header
and the field names are configurable (KEENABLE_SEARCH_URL, KEENABLE_FETCH_URL, KEENABLE_AUTH=bearer|x-api-key)
and the parser accepts the common spellings. The key is never logged, cached or written to evidence.
Results only FIND a page. Page text is data, never instructions.
"""

from __future__ import annotations

import os
from typing import Any

from app import cache
from app.integrations.base import mock_reference_hit
from app.stores import http
from app.stores.base import env_secret, not_configured

SEARCH_URL = os.getenv("KEENABLE_SEARCH_URL") or "https://api.keenable.ai/v1/search"
FETCH_URL = os.getenv("KEENABLE_FETCH_URL") or "https://api.keenable.ai/v1/fetch"
_TEXT_KEYS = ("markdown", "content", "text", "page_content", "body")
_LIST_KEYS = ("results", "data", "items", "hits", "pages")


def _auth_headers(key: str) -> dict[str, str]:
    if (os.getenv("KEENABLE_AUTH") or "bearer").lower() == "x-api-key":
        return {"X-API-Key": key}
    return {"Authorization": f"Bearer {key}"}


def _rows(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [r for r in body if isinstance(r, dict)]
    if isinstance(body, dict):
        for k in _LIST_KEYS:
            v = body.get(k)
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
            if isinstance(v, dict):
                return _rows(v)
    return []


def _text(row: dict[str, Any]) -> str | None:
    for k in _TEXT_KEYS:
        v = row.get(k)
        if isinstance(v, str) and len(v.strip()) >= 200:  # a snippet is not page text
            return v
    return None


def parse_hits(body: Any, provider_id: str = "keenable") -> list[dict[str, Any]]:
    out = []
    for r in _rows(body):
        url = r.get("url") or r.get("link") or r.get("href")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        text = _text(r)
        out.append({"url": url, "title": str(r.get("title") or r.get("name") or url)[:300], "text": text,
                    "licence": r.get("license") or r.get("licence"), "found_via": provider_id,
                    "fetched_via": "keenable" if text else None, "source_api": provider_id, "simulated": False})
    return out


class MockKeenable:
    provider_id = "keenable"

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        return [mock_reference_hit(self.provider_id, query)]

    async def fetch_page(self, url: str) -> dict[str, Any] | None:
        return None


class LiveKeenable:
    provider_id = "keenable"

    def configured(self) -> bool:
        return bool(env_secret("KEENABLE_API_KEY"))

    def _key(self) -> str:
        key = env_secret("KEENABLE_API_KEY")
        if not key:
            raise not_configured("§3.18 (P19)", "KEENABLE_API_KEY is not set (optional provider; the next one is used)")
        return key

    async def _post(self, url: str, body: dict[str, Any], tool: str) -> Any:
        from app.intake.http import check_reference_url

        check_reference_url(url)  # api.keenable.ai is on the reference allowlist
        key = self._key()

        async def go() -> Any:
            _, out = await http.send("POST", url, json_body=body, headers={"Accept": "application/json", **_auth_headers(key)}, timeout=15.0)
            return out

        return await cache.cached(tool, body, go)

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        body = await self._post(SEARCH_URL, {"query": query, "limit": max_results}, "keenable.search")
        return parse_hits(body, self.provider_id)[:max_results]

    async def fetch_page(self, url: str) -> dict[str, Any] | None:
        """Page text through Keenable. The caller has already refused never-request and store hosts."""
        body = await self._post(FETCH_URL, {"url": url}, "keenable.fetch")
        row = body if isinstance(body, dict) else {}
        text = _text(row) or _text(next(iter(_rows(body)), {}))
        return {"url": url, "text": text, "title": row.get("title"), "fetched_via": "keenable"} if text else None
