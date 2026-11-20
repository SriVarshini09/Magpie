"""Shared pieces for service modules (interfaces live next to each implementation)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

MOCK_LABEL: dict[str, Any] = {"source_api": "mock", "simulated": True}


def todo(owner: str, plan: str, what: str) -> NotImplementedError:
    """The error every Live stub raises: who builds it and where the spec is."""
    return NotImplementedError(f"TODO({owner}) — PLAN {plan}: {what}")


@runtime_checkable
class ReferenceSearchProvider(Protocol):
    """One reference-design search provider (PLAN §3.18). Results only FIND a page.

    The caller (intake/reference.py) checks every URL against the never-request list
    BEFORE calling a provider, and again on every result before its text is read.
    """

    provider_id: str  # keenable | exa_airbyte | claude_web_search | github_search

    async def search(self, query: str, max_results: int = 3) -> list[dict[str, Any]]:
        """Return [{url, title, text?, licence?, found_via, fetched_via?, source_api, simulated}]."""
        ...


def mock_reference_hit(provider_id: str, query: str) -> dict[str, Any]:
    return {
        "url": "https://mock.invalid/reference-design",
        "title": f"Mock reference design for: {query}",
        "text": "MOCK PAGE TEXT. Not a real reference design.",
        "licence": None,
        "found_via": provider_id,
        "fetched_via": "http",
        **MOCK_LABEL,
    }
