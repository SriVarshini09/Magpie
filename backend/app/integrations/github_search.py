"""GitHub repository search: reference-search provider 4, a pointer only (PLAN §3.18). Owner: B.

    GET https://api.github.com/search/repositories?q=<q>&sort=stars&order=desc&per_page=<n>
10 requests a minute without a token, 30 with one (AIRBYTE_GITHUB_TOKEN, read-only, optional).
A hit is only a pointer: the README is then read through the Airbyte GitHub connector (A's airbyte_github),
in intake/reference.py. The token is never logged or cached.
"""

from __future__ import annotations

import re
from typing import Any

from app import cache
from app.integrations.base import mock_reference_hit
from app.stores import http
from app.stores.base import env_secret

API = "https://api.github.com/search/repositories"
_SAFE = re.compile(r"[^A-Za-z0-9 .,_+#\-]")


def parse_hits(body: Any) -> list[dict[str, Any]]:
    out = []
    for r in (body or {}).get("items") or [] if isinstance(body, dict) else []:
        url = r.get("html_url")
        if not isinstance(url, str) or not url.startswith("https://github.com/"):
            continue
        desc = str(r.get("description") or "").strip()
        lic = (r.get("license") or {}).get("spdx_id") if isinstance(r.get("license"), dict) else None
        out.append({"url": url, "title": f"{r.get('full_name')}{': ' + desc if desc else ''}"[:300], "text": None,
                    "licence": None if lic in (None, "NOASSERTION") else lic, "stars": r.get("stargazers_count"),
                    "default_branch": r.get("default_branch"), "found_via": "github_search", "fetched_via": None,
                    "source_api": "github_search", "simulated": False})
    return out


class MockGitHubSearch:
    provider_id = "github_search"

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        return [mock_reference_hit(self.provider_id, query)]


class LiveGitHubSearch:
    provider_id = "github_search"

    def configured(self) -> bool:
        return True  # works without a token, at 10 requests a minute

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        from app.intake.http import check_reference_url

        check_reference_url(API)
        q = re.sub(r"\s+", " ", _SAFE.sub(" ", query)).strip()[:120]
        if not q:
            return []
        params = {"q": q, "sort": "stars", "order": "desc", "per_page": str(max(1, min(max_results, 10)))}
        token = env_secret("AIRBYTE_GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

        async def go() -> Any:
            _, body = await http.send("GET", API, params=params, headers={**headers, **({"Authorization": f"Bearer {token}"} if token else {})})
            return body

        body = await cache.cached("github.search_repositories", params, go)
        return parse_hits(body)[:max_results]
