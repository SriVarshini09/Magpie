"""Fetch the source document (PLAN §3.6 `ingest_source`, §3.17 link kinds). Owner: A.

A GitHub repository goes through the Airbyte GitHub connector (raw `httpx` fallback), pinned to a
commit. Any other page (P22) is one GET of the exact URL the user pasted. The text is hashed on
arrival; every later quote is checked against exactly these bytes. The page is data, never instructions.
"""

from __future__ import annotations

from typing import Any

from app import registry
from app.integrations.airbyte_github import is_github_repo
from app.models import SourceDoc

__all__ = ["ingest_source", "IngestError"]


class IngestError(RuntimeError):
    pass


async def ingest_source(url: str, *, github: Any = None, transport: Any = None) -> tuple[SourceDoc, list[dict[str, Any]]]:
    """Returns (SourceDoc, reads). `reads` are the bodies of the `source_fetch` records.

    The caller (agent/tools.py) has already run the mandate guard: the URL equals the mandate's
    `scope.inputs.source_url` and is not on the never-request list.
    """
    from app.intake import http as intake_http
    from app.stores.http import HostNotAllowed

    if is_github_repo(url):
        src = github if github is not None else registry.get("airbyte_github")
        before = len(getattr(src, "reads", []) or [])
        try:
            doc = await src.fetch_readme(url)
        except HostNotAllowed:
            raise
        except Exception as exc:
            why = str(exc)[:200] if isinstance(exc, LookupError) else f"{type(exc).__name__}: {str(exc)[:160]}"
            raise IngestError(f"Could not read the README ({why})") from exc
        reads = list((getattr(src, "reads", []) or [])[before:]) or [
            {"entity": "file_content", "action": "get", "params": {"path": doc.path, "ref": doc.commit_sha}, "bytes": len(doc.text.encode("utf-8")),
             "sha256": doc.sha256, "via": doc.via}]
        return doc, reads
    try:
        page = await intake_http.fetch_page(url, user_pasted=True, transport=transport)
    except HostNotAllowed:
        raise
    except Exception as exc:
        raise IngestError(f"Could not read that page: {type(exc).__name__}: {str(exc)[:160]}") from exc
    doc = SourceDoc(id=f"src_{page['doc_sha256'][:10]}", url=url, path="", commit_sha="", text=page["text"], sha256=page["doc_sha256"],
                    fetched_at=page["fetched_at"], via="http", source_api="http")
    return doc, [{"entity": "page", "action": "get", "params": {"url": url}, "bytes": page["bytes"], "sha256": page["doc_sha256"], "via": "http"}]
