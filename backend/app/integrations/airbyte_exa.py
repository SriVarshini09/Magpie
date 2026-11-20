"""Exa through the Airbyte agent SDK: reference search with contents, provider 2 (PLAN §3.15, §3.18). Owner: B.

Verified against the installed SDK (airbyte_agent_sdk 0.1.403, connectors/exa):
    from airbyte_agent_sdk.connectors.exa import ExaConnector, ExaAuthConfig
    conn = ExaConnector(auth_config=ExaAuthConfig(api_key=EXA_API_KEY))      # local mode, calls api.exa.ai
    res = await conn.execute("search_results", "list", {"query": ..., "num_results": n, "type": "auto",
                             "exclude_domains": [...], "contents": {"text": {"maxCharacters": N}}})
    res.data -> [{url, title, text, highlights, score, ...}]
The SDK makes its own requests (PLAN §3.16 rule 3 allows the Airbyte SDK's calls). We never point it at a
never-request host or a store: those domains go in `exclude_domains`, and intake/reference.py drops any
result that points there before its text is read. EXA_API_KEY is never logged.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from app import cache
from app.integrations.base import mock_reference_hit
from app.stores.base import env_secret, not_configured

MAX_CHARS = int(os.getenv("EXA_MAX_CHARACTERS") or 20000)


def _row(r: Any) -> dict[str, Any]:
    if isinstance(r, dict):
        return r
    if hasattr(r, "model_dump"):
        return r.model_dump(by_alias=False)
    return {}


def parse_hits(data: Any) -> list[dict[str, Any]]:
    rows = data if isinstance(data, list) else (data.get("results") if isinstance(data, dict) else []) or []
    out = []
    for r in map(_row, rows):
        url = r.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        text = r.get("text") if isinstance(r.get("text"), str) and r["text"].strip() else None
        out.append({"url": url, "title": str(r.get("title") or url)[:300], "text": text, "licence": None,
                    "found_via": "exa_airbyte", "fetched_via": "exa_airbyte" if text else None,
                    "source_api": "exa_airbyte", "simulated": False})
    return out


class MockExa:
    provider_id = "exa_airbyte"

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        return [mock_reference_hit(self.provider_id, query)]


class LiveExa:
    provider_id = "exa_airbyte"

    def __init__(self, connector_factory: Callable[[str], Any] | None = None) -> None:
        self._factory = connector_factory

    def configured(self) -> bool:
        return bool(env_secret("EXA_API_KEY"))

    def _connector(self) -> Any:
        key = env_secret("EXA_API_KEY")
        if not key:
            raise not_configured("§3.15, §3.18 (P19)", "EXA_API_KEY is not set (optional provider; the next one is used)")
        if self._factory is not None:
            return self._factory(key)
        from airbyte_agent_sdk.connectors.exa import ExaAuthConfig, ExaConnector  # imported here: a broken SDK breaks one service

        return ExaConnector(auth_config=ExaAuthConfig(api_key=key))

    async def search(self, query: str, max_results: int = 3, *, exclude_domains: list[str] | None = None) -> list[dict[str, Any]]:
        from app.intake.reference import blocked_domains

        params = {"query": query, "num_results": max_results, "type": "auto",
                  "exclude_domains": sorted(set(exclude_domains or []) | blocked_domains()),
                  "contents": {"text": {"maxCharacters": MAX_CHARS}}}
        conn = self._connector()

        async def go() -> Any:
            try:
                res = await conn.execute("search_results", "list", params)
            finally:
                close = getattr(conn, "close", None)
                if close is not None:
                    await close()
            data = getattr(res, "data", res)
            return [_row(r) for r in data] if isinstance(data, list) else data

        data = await cache.cached("exa_airbyte.search", params, go)
        return parse_hits(data)[:max_results]
