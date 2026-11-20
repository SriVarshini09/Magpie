"""Reference search, provider 3: Claude web search (PLAN §3.5, §3.18). Wired at integration (B's request, A's client).

    reference.register_provider("claude_web_search", ClaudeWebSearch())     # done by `register()` at startup

The provider only FINDS a page: A's `LiveLLM.web_search` runs the server tool `web_search_20260209` with
`allowed_domains`, and B's chain (`intake/reference.py`) then reads the page through the allowlisted fetchers
and hashes the text on arrival. Rules enforced here, in code:

- `allowed_domains` is built from the reference allowlist (documentation hosts and github.com). A store's domain
  or a never-request host is never put in it: no store page is ever searched or fetched (PLAN §3.16 rule 3).
- Results that point anywhere else are dropped before B's chain sees them.
- No Anthropic credentials, or the `anthropic` service on its mock: the provider says "not configured" and
  the chain moves on. It never returns invented results.
"""

from __future__ import annotations

from typing import Any

from app.stores.base import NotConfigured
from app.stores.http import host_of, is_never_request

PROVIDER_ID = "claude_web_search"
_NOT_SEARCHABLE_PREFIXES = ("api.", "raw.")  # API and raw-content hosts are fetch targets, not search targets


def allowed_domains() -> list[str]:
    """Where Claude web search may look: reference documentation hosts and github.com, minus anything blocked."""
    from app.intake import reference
    from app.intake.http import REFERENCE_ALLOWLIST

    blocked = reference.blocked_domains()
    hosts = {h for h in REFERENCE_ALLOWLIST if not h.startswith(_NOT_SEARCHABLE_PREFIXES)} | {"github.com"}
    return sorted(h for h in hosts if not is_never_request(h) and h not in blocked and not reference.is_blocked_url(h))


class ClaudeWebSearch:
    provider_id = PROVIDER_ID

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm  # tests inject a fake with `web_search`

    def _client(self) -> Any:
        if self._llm is not None:
            return self._llm
        from app import registry
        from app.integrations import anthropic_client

        if registry.impl_mode("anthropic") != "live" or not anthropic_client.has_credentials():
            raise NotConfigured("TODO(A) — PLAN §3.18: Claude web search needs ANTHROPIC_API_KEY (optional provider; the next one is used)")
        return registry.get("anthropic")

    def configured(self) -> bool:
        try:
            self._client()
            return True
        except NotConfigured:
            return False

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        from app.intake import reference

        reference.check_query(query)  # a store or never-request host in the query is refused before any call
        llm = self._client()
        domains = allowed_domains()
        if not domains:
            return []
        hits = await llm.web_search(query, domains, max_uses=1)
        allowed = set(domains)
        out: list[dict[str, Any]] = []
        for h in hits or []:
            url = str(h.get("url") or "")
            host = host_of(url)
            if not url.startswith("https://") or reference.is_blocked_url(url):
                continue
            if host not in allowed and not any(host.endswith("." + d) for d in allowed):
                continue  # the tool was told where to look; anything else is dropped, not trusted
            out.append({"url": url, "title": str(h.get("title") or url)[:300], "text": None, "licence": None,
                        "found_via": PROVIDER_ID, "fetched_via": None, "source_api": PROVIDER_ID, "simulated": False})
            if len(out) >= max_results:
                break
        return out


def register() -> None:
    """Plug the provider into B's chain. Safe to call more than once."""
    from app.intake import reference

    reference.register_provider(PROVIDER_ID, ClaudeWebSearch())
