"""Fetch allowlist and never-request list for every store request (PLAN §3.16 rule 3). Owner: B.

The policy below is real and tested (tests/test_http_allowlist.py, tests/test_b_http_fetch.py).
`fetch` is the one path every store adapter uses: host allowlist -> cache -> network (10 s timeout).
Redirects are never followed, so a 3xx can never carry us to a never-request host.

- A never-request host is refused on EVERY path: our own code, and any third-party fetcher or
  search provider (Keenable, Exa, Claude web search, context.dev). Check the URL before the call.
- Cart links to those sites are strings the user's browser opens. We never request them.
- Prices from those stores come only from SerpAPI or an official API.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

# Bot-walled or off-limits sites: never requested, directly or through any fetcher.
NEVER_REQUEST: frozenset[str] = frozenset({
    "amazon.com",
    "digikey.com",  # the website; the official API host is the one exception below
    "ebay.com",
    "walmart.com",
    "bestbuy.com",
    "microcenter.com",
    "octopart.com",
    "robotshop.com",  # the main domain; the store is reached only as robotshop-us.myshopify.com through `ucp`
})
# Official API hosts under a never-request domain that we may call with our own key.
NEVER_REQUEST_EXCEPTIONS: frozenset[str] = frozenset({"api.digikey.com"})
# Regional sites of the same marketplaces (amazon.fr, ebay.co.uk, walmart.ca, ...).
_REGIONAL = re.compile(r"(^|\.)(amazon|ebay|walmart)\.(com?\.)?[a-z]{2,3}$")

# host -> allowed path prefixes. An adapter may only reach hosts in its own `hosts` set as well.
STORE_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "serpapi.com": ("/",),
    "api.digikey.com": ("/",),
    "www.adafruit.com": ("/api/",),
    "www.seeedstudio.com": ("/graphql",),
    "www.sparkfun.com": ("/graphql",),
    "google.serper.dev": ("/",),  # backup for Google Shopping
    "www.dfrobot.com": ("/",),  # stretch 7
    "www.waveshare.com": ("/",),  # stretch 7
}


class HostNotAllowed(Exception):
    """A blocked request. `refusal` is the body of the refusal record (PLAN §3.7)."""

    def __init__(self, url: str, rule: str = "host_not_allowed", reason: str = "") -> None:
        self.url, self.rule, self.reason = url, rule, reason
        self.refusal: dict[str, Any] = {
            "kind": "refusal", "rule": rule, "attempted": {"tool": "http", "value": host_of(url)},
            "clause": reason or "fetch allowlist (PLAN §3.16 rule 3)", "triggered_by": "agent",
        }
        super().__init__(f"{rule}: {host_of(url) or url} ({reason})")


def host_of(url_or_host: str) -> str:
    """Lower-case host of a URL (or of a bare host), without port, userinfo or trailing dot."""
    s = url_or_host.strip()
    if "://" not in s:
        s = "//" + s
    try:
        host = urlsplit(s).hostname or ""
    except ValueError:
        return ""
    return host.rstrip(".").lower()


def is_never_request(url_or_host: str) -> bool:
    """True when the host is on the never-request list (including subdomains and regional sites)."""
    host = host_of(url_or_host)
    if not host:
        return True  # unparseable: refuse
    if host in NEVER_REQUEST_EXCEPTIONS:
        return False
    if any(host == d or host.endswith("." + d) for d in NEVER_REQUEST):
        return True
    return bool(_REGIONAL.search(host))


def check_store_url(url: str, adapter_hosts: frozenset[str] | None = None) -> str:
    """Return the URL if a store adapter may request it; raise HostNotAllowed otherwise."""
    parts = urlsplit(url)
    host = host_of(url)
    if parts.scheme != "https":
        raise HostNotAllowed(url, reason="https only")
    if is_never_request(url):
        raise HostNotAllowed(url, reason="never-request list")
    prefixes = STORE_ALLOWLIST.get(host)
    if prefixes is None:
        raise HostNotAllowed(url, reason="host not on the store allowlist")
    if adapter_hosts is not None and host not in adapter_hosts:
        raise HostNotAllowed(url, reason="host not in this adapter's hosts")
    path = parts.path or "/"
    if not any(path.startswith(p) for p in prefixes):
        raise HostNotAllowed(url, reason=f"path not allowed on {host}")
    return url


TIMEOUT_S = 10.0
USER_AGENT = "build-to-cart/0.4 (hackathon demo; read-only price lookups)"

# Tests install an httpx.MockTransport here. Under pytest, a request with no transport installed is
# refused outright: nothing in the test suite may reach the network.
_transport: Any = None


def set_transport(transport: Any) -> None:
    global _transport
    _transport = transport


class LiveNetworkInTests(RuntimeError):
    """A test tried to reach the network without a MockTransport."""


class StoreHTTPError(RuntimeError):
    """A non-2xx answer. The message has the host and path only, never the query (keys live there)."""

    def __init__(self, status: int, url: str, body_hint: str = "") -> None:
        self.status = status
        parts = urlsplit(url)
        self.where = f"{parts.hostname}{parts.path}"
        super().__init__(f"HTTP {status} from {self.where}{(': ' + body_hint[:160]) if body_hint else ''}")


@dataclass(frozen=True)
class Fetched:
    value: Any  # parsed JSON, or text for non-JSON bodies
    seen_at: str
    cached: bool
    status: int = 200


def _client(timeout: float) -> Any:
    import httpx

    if _transport is None and os.getenv("PYTEST_CURRENT_TEST"):
        raise LiveNetworkInTests("network access in a test without a MockTransport (stores/http.set_transport)")
    return httpx.AsyncClient(transport=_transport, timeout=timeout, follow_redirects=False,
                             headers={"User-Agent": USER_AGENT})


async def send(method: str, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None,
               json_body: Any = None, data: Any = None, timeout: float = TIMEOUT_S) -> tuple[int, Any]:
    """One HTTP request with no policy check of its own: callers check the URL first.

    Returns (status, parsed body). Raises StoreHTTPError on non-2xx, with the query stripped.
    """
    import httpx

    try:
        async with _client(timeout) as client:
            resp = await client.request(method, url, params=params, headers=headers, json=json_body, data=data)
    except httpx.HTTPError as exc:  # the exception text can contain the full URL: never pass it on
        parts = urlsplit(url)
        raise StoreHTTPError(0, url, f"{type(exc).__name__} talking to {parts.hostname}") from None
    ctype = resp.headers.get("content-type", "")
    body: Any
    if "json" in ctype:
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
    else:
        body = resp.text
    if resp.status_code >= 400 or 300 <= resp.status_code < 400:
        hint = ""
        if isinstance(body, dict):
            err = body.get("error")
            hint = (err.get("message") if isinstance(err, dict) else str(err or ""))[:160]
        raise StoreHTTPError(resp.status_code, url, hint)
    return resp.status_code, body


async def fetch(
    url: str,
    *,
    adapter_hosts: frozenset[str],
    params: dict[str, Any] | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    data: Any = None,
    secret_params: dict[str, str] | None = None,
    secret_headers: dict[str, str] | None = None,
    tool: str | None = None,
    cache_tag: dict[str, Any] | None = None,
    bypass_cache: bool = False,
    use_cache: bool = True,
    before_network: Any = None,
    timeout: float = TIMEOUT_S,
) -> Fetched:
    """Every outbound store request: host allowlist -> cache -> network (PLAN §3.1, §3.11).

    `secret_params` / `secret_headers` (API keys, bearer tokens) are sent but never enter the cache key,
    the cache file, an evidence file or an error message. `before_network` runs only on a cache miss,
    right before the request (the SerpAPI quota guard). Evidence files are written by the adapter, once
    per response, so every offer from that response carries the same evidence_sha256.
    """
    check_store_url(url, adapter_hosts)
    from app import cache

    args = {"method": method, "url": url, "params": params or {}, "json": json_body, "data": data, **(cache_tag or {})}

    async def go() -> Any:
        if before_network is not None:
            before_network()
        _, body = await send(method, url, params={**(params or {}), **(secret_params or {})} or None,
                             headers={**(headers or {}), **(secret_headers or {})} or None,
                             json_body=json_body, data=data, timeout=timeout)
        return body

    if not use_cache:
        from app.stores.base import now_iso

        return Fetched(await go(), now_iso(), False)
    entry = await cache.cached_entry(tool or f"http:{host_of(url)}", args, go, bypass=bypass_cache)
    return Fetched(entry.value, entry.seen_at, entry.hit)
