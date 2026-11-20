"""Fetch policy for reference designs and pasted project pages (PLAN §3.16 rule 3, §3.17, §3.18). Owner: A.

Shares the never-request list with stores/http.py. The policy is real and tested
(tests/test_reference_denylist.py); the fetch function is a stub.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from app.stores.http import HostNotAllowed, host_of, is_never_request

REFERENCE_ALLOWLIST: frozenset[str] = frozenset({
    "api.keenable.ai",
    "api.github.com",
    "raw.githubusercontent.com",
    "docs.px4.io",
    "docs.holybro.com",
    "docs.donkeycar.com",
    "huggingface.co",
    "docs.arduino.cc",
    "docs.espressif.com",
})

REFUSAL_TEXT = "We can't read that site. Paste the parts list as text instead."


def check_reference_url(url: str, *, user_pasted: bool = False) -> str:
    """Return the URL if we (or a provider on our behalf) may read it; raise HostNotAllowed otherwise.

    `user_pasted=True` allows the one exact page a user pasted (P22), unless it is a never-request host.
    Call this BEFORE handing a URL to Keenable, Exa, Claude web search or any other fetcher.
    """
    if urlsplit(url).scheme != "https":
        raise HostNotAllowed(url, rule="reference_host_not_allowed", reason="https only")
    if is_never_request(url):
        raise HostNotAllowed(url, rule="reference_host_not_allowed", reason="never-request list")
    if not user_pasted and host_of(url) not in REFERENCE_ALLOWLIST:
        raise HostNotAllowed(url, rule="reference_host_not_allowed", reason="host not on the reference allowlist")
    return url


def drop_never_request(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Discard search results that point at a never-request host, before their text is read."""
    return [h for h in hits if not is_never_request(str(h.get("url", "")))]


MAX_PAGE_BYTES = 2_000_000
_BLOCK_TAGS = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "section", "article", "pre", "dt", "dd"}
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head", "nav", "footer", "iframe"}


def html_to_text(html: str) -> tuple[str, str]:
    """(title, visible text) of an HTML page. Tables become `a | b | c` rows so the table parser can read them."""
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.out: list[str] = []
            self.skip = 0
            self.title: list[str] = []
            self.in_title = False
            self.in_head_row = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "title":
                self.in_title = True
            if tag in _SKIP_TAGS and tag != "head":
                self.skip += 1
            elif tag in ("td", "th"):
                self.out.append(" | ")
                self.in_head_row = self.in_head_row or tag == "th"
            elif tag in ("h1", "h2", "h3", "h4"):
                self.out.append("\n" + "#" * int(tag[1]) + " ")
            elif tag == "li":
                self.out.append("\n- ")
            elif tag in _BLOCK_TAGS:
                self.out.append("\n")

        def handle_endtag(self, tag: str) -> None:
            if tag == "title":
                self.in_title = False
            if tag in _SKIP_TAGS and tag != "head":
                self.skip = max(0, self.skip - 1)
            elif tag == "tr":
                self.out.append(" |")
                if self.in_head_row:
                    self.out.append("\n| --- | --- |")
                    self.in_head_row = False
            elif tag in _BLOCK_TAGS:
                self.out.append("\n")

        def handle_data(self, data: str) -> None:
            if self.in_title:
                self.title.append(data)
            elif not self.skip:
                self.out.append(data)

    p = _P()
    p.feed(html)
    lines = [" ".join(ln.split()) for ln in "".join(p.out).split("\n")]
    text = "\n".join(ln for i, ln in enumerate(lines) if ln or (i and lines[i - 1]))
    return " ".join("".join(p.title).split()), text.strip()


async def fetch_page(url: str, *, user_pasted: bool = False, transport: Any = None) -> dict[str, Any]:
    """One GET of a reference or pasted page; text extracted; bytes hashed on arrival (PLAN §3.17, §3.18).

    Returns {url, title, text, doc_sha256, bytes, content_type, fetched_at, fetched_via: "http"}.
    `doc_sha256` is the hash of `text`, the exact string quotes are checked against. Redirects are not
    followed: a redirect target is a different host that has not been checked.
    """
    import os

    import httpx

    from app.audit.chain import sha256_hex
    from app.runstate import now_iso

    check_reference_url(url, user_pasted=user_pasted)
    from app import cache

    if cache.mode() in ("record", "replay") and transport is None:  # replay reads the recording, never the network (PLAN §3.11)
        async def go() -> dict[str, Any]:
            return await _get_page(url)

        return await cache.cached("intake.fetch_page", {"url": url}, go)
    return await _get_page(url, transport)


async def _get_page(url: str, transport: Any = None) -> dict[str, Any]:
    import os

    import httpx

    from app.audit.chain import sha256_hex
    from app.runstate import now_iso

    if transport is None and os.getenv("PYTEST_CURRENT_TEST"):
        raise RuntimeError("no network under pytest")
    async with httpx.AsyncClient(timeout=10, transport=transport, follow_redirects=False) as client:
        resp = await client.get(url, headers={"User-Agent": "build-to-cart", "Accept": "text/html,text/markdown,text/plain;q=0.9"})
    if resp.is_redirect:
        raise HostNotAllowed(url, rule="reference_host_not_allowed", reason="the page redirects; paste the final address")
    resp.raise_for_status()
    raw = resp.content[:MAX_PAGE_BYTES]
    ctype = resp.headers.get("content-type", "")
    body = raw.decode(resp.encoding or "utf-8", "replace")
    if "html" in ctype or body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        title, text = html_to_text(body)
    else:
        title, text = "", body
    return {"url": url, "title": title, "text": text, "doc_sha256": sha256_hex(text), "bytes": len(raw), "raw_sha256": sha256_hex(raw),
            "content_type": ctype, "fetched_at": now_iso(), "fetched_via": "http"}
