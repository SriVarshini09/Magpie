"""Shopify UCP through the `ucp` CLI: search and agent carts (PLAN §3.16, Appendix A.1, A.2). Owner: B.

Verified syntax (Appendix A.1, checked Nov 19 with @shopify/ucp-cli 0.9.1):
    ucp catalog search --input '<json>' --format json                       (Global Catalog)
    ucp catalog search --business <url> --input '<json>' --format json      (one store)
    ucp cart create --business <url> --input '<json>' --format json
    ucp cart cancel <id>
- Payloads go in `--input '<json>'`; `--set` into arrays fails validation.
- Pass the seller's myshopify domain (`variants[].seller.domain`) as --business; RobotShop's public domain 403s.
- `address_country` does not filter currency or origin: send filters.ships_from US and keep only USD here.
- One CLI call at a time (a parallel run crashed libuv on Windows, SD §7.9), behind an asyncio lock.

The CLI runs as a subprocess with an argument list, never a shell string. On Windows `ucp` is an npm
`.cmd` shim, which CreateProcess hands to cmd.exe; so we run the shim's node script directly when we can
find it, and every listing-derived string we put in an argument is reduced to a safe character set.

Response shapes below are from the Nov 19 recordings (research/tonight-checks.md, SD §3): amounts are
integers in minor units (`variants[].price.amount / 100`), sellers in `variants[].seller`.
The `catalog lookup` call used by the price refresh is [unverified]: it falls back to a per-store search.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import weakref
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app import cache
from app.config import get_settings
from app.integrations.base import MOCK_LABEL
from app.models import Offer, PartQuery
from app.stores import registry as store_registry
from app.stores.base import (
    AdapterError,
    FixtureAdapter,
    RunCtx,
    make_offer_id,
    minor_to_major,
    not_configured,
    now_iso,
    parse_pack_units,
    registrable_domain,
    save_evidence,
    slug,
    strip_html,
)

# The only merchant tools we ever call (PLAN §3.6). Checkout and order tools are never exposed.
ALLOWED_UCP_TOOLS = frozenset({"search_catalog", "lookup_catalog", "get_product", "create_cart", "get_cart", "cancel_cart"})
# argv prefixes we allow; anything else (checkout, order, update with buyer data) is refused in code.
_ALLOWED_COMMANDS = {("catalog", "search"), ("catalog", "lookup"), ("cart", "create"), ("cart", "cancel"), ("discover",)}

UCP_CLI_PACKAGE = "@shopify/ucp-cli@0.9.1"
CLI_TIMEOUT_S = float(os.getenv("UCP_TIMEOUT_S") or 60)
PER_STORE_MAX = int(os.getenv("UCP_PER_STORE_MAX") or 4)
_GID = re.compile(r"^gid://shopify/ProductVariant/\d{1,20}$")
_CART_ID = re.compile(r"^gid://shopify/Cart/[A-Za-z0-9]+(\?key=[A-Za-z0-9]+)?$")
_SAFE_QUERY = re.compile(r"[^A-Za-z0-9 .,_/+#\-x×]")


class UcpError(AdapterError):
    """The CLI failed or returned something without a `result`."""


def clean_query(text: str, limit: int = 160) -> str:
    """A search string reduced to characters that are inert in cmd.exe and JSON (no & | < > ^ % ! " ( ))."""
    s = _SAFE_QUERY.sub(" ", text or "")
    return re.sub(r"\s+", " ", s).strip()[:limit]


def _business(url_or_domain: str) -> str:
    host = urlsplit(url_or_domain if "://" in url_or_domain else "https://" + url_or_domain).hostname or ""
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", host):
        raise UcpError(f"not a store domain: {host!r}")
    return f"https://{host}"


# --------------------------------------------------------------------------- the CLI


def _shim_target(cmd_path: str) -> list[str] | None:
    """For an npm `.cmd` shim, the [node, script.js] it would run, so cmd.exe never parses our arguments."""
    try:
        text = Path(cmd_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # cmd-shim writes "%dp0%\node_modules\…\run.js"; Node's own npx.cmd writes %~dp0\node_modules\npm\bin\npx-cli.js
    found = [p for p in re.findall(r'%~?dp0%?\\([^"%\r\n]+?\.(?:c|m)?js)', text) if "prefix" not in p.lower()]
    if not found:
        return None
    pick = next((p for p in found if "cli" in Path(p).name.lower()), found[-1])
    base = Path(cmd_path).parent
    script = (base / pick).resolve()
    if not script.is_file():
        return None
    node = base / "node.exe"
    node_path = str(node) if node.is_file() else shutil.which("node")
    return [node_path, str(script)] if node_path else None


def resolve_cli() -> list[str]:
    """The command that runs the ucp CLI: UCP_BIN on PATH, else `npx -y @shopify/ucp-cli@0.9.1`.

    UCP_BIN may be a name ("ucp") or a full path. UCP_NPX_FALLBACK=0 turns the npx fallback off.
    """
    configured = os.getenv("UCP_BIN") or get_settings().ucp_bin or "ucp"
    found = shutil.which(configured) or (configured if Path(configured).is_file() else None)
    if found:
        if found.lower().endswith((".cmd", ".bat")):
            direct = _shim_target(found)
            if direct:
                return direct
        return [found]
    if (os.getenv("UCP_NPX_FALLBACK") or "1") != "0":
        npx = shutil.which("npx")
        if npx:
            direct = _shim_target(npx) if npx.lower().endswith((".cmd", ".bat")) else None
            return [*(direct or [npx]), "-y", UCP_CLI_PACKAGE]
    raise not_configured("§3.16, App. A.1", f"the ucp CLI was not found (UCP_BIN={configured!r}); install Node so npx can run {UCP_CLI_PACKAGE}")


_locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = weakref.WeakKeyDictionary()


def _lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    if loop not in _locks:
        _locks[loop] = asyncio.Lock()
    return _locks[loop]


Runner = Callable[[list[str]], Awaitable[dict[str, Any]]]


class UcpCli:
    """Runs one `ucp` command at a time and returns its parsed JSON."""

    def __init__(self, command: list[str] | None = None, exec_fn: Any = None) -> None:
        self._command = command
        self._exec = exec_fn or asyncio.create_subprocess_exec

    def command(self) -> list[str]:
        if self._command is None:
            self._command = resolve_cli()
        return self._command

    async def run(self, args: list[str]) -> dict[str, Any]:
        head = tuple(args[:2]) if args and args[0] != "discover" else ("discover",)
        if head not in _ALLOWED_COMMANDS:
            raise UcpError(f"ucp command not allowed: {' '.join(args[:2])}")
        argv = [*self.command(), *args]
        async with _lock():
            proc = await self._exec(*argv, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE)
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=CLI_TIMEOUT_S)
            except TimeoutError:
                proc.kill()
                raise UcpError(f"ucp {' '.join(args[:2])} timed out after {CLI_TIMEOUT_S:.0f} s") from None
        text = out.decode("utf-8", errors="replace").strip()
        try:
            data = json.loads(text) if text else None
        except ValueError:
            data = None
        # The Windows libuv assertion (SD §7.9) can set a non-zero exit code after valid JSON was written.
        if isinstance(data, dict) and "result" in data:
            return data
        hint = err.decode("utf-8", errors="replace").strip().splitlines()[-1:] or [""]
        raise UcpError(f"ucp {' '.join(args[:2])} failed (exit {proc.returncode}): {hint[0][:200]}")


# --------------------------------------------------------------------------- parsing


def _variant_offers(data: dict[str, Any], *, business: str | None, query: str, seen_at: str, evidence: tuple[str, str]) -> list[Offer]:
    """Offers from one catalog search response. USD only; one offer per variant (variants are pack sizes)."""
    result = data.get("result") or {}
    out: list[Offer] = []
    seen: set[str] = set()
    for product in result.get("products") or []:
        p_desc = (product.get("description") or {})
        for v in product.get("variants") or []:
            gid = str(v.get("id") or "")
            price = v.get("price") or {}
            currency = (price.get("currency") or "").upper()
            if currency != "USD" or not gid or gid in seen:
                continue  # address_country does not filter currency (SD §3): USD only, here
            usd = minor_to_major(price.get("amount"), currency)
            if usd is None or usd <= 0:
                continue
            seen.add(gid)
            seller = v.get("seller") or {}
            seller_domain = (seller.get("domain") or "").lower() or (urlsplit(business).hostname if business else "")
            s = store_registry.store_for_shopify_domain(seller_domain) or (
                store_registry.store_for_shopify_domain(business) if business else None)
            if s is None and seller.get("url"):
                s = store_registry.store_for_shopify_domain(seller["url"])
            if s:
                store_id, store_name = s["store_id"], s["display_name"]
            else:
                public = urlsplit(seller.get("url") or "").hostname or seller_domain
                store_id, store_name = registrable_domain(public) or slug(seller.get("name") or "shopify"), seller.get("name") or public
            option_labels = " ".join(str(o.get("label") or "") for o in v.get("options") or [])
            title = str(v.get("title") or product.get("title") or "")
            p_title = str(product.get("title") or "")
            full_title = p_title if not v.get("title") or v.get("title") == p_title else f"{p_title} ({v.get('title')})"
            units = parse_pack_units(option_labels, title, p_title if title == p_title else None)
            desc_obj = v.get("description") or p_desc
            description = strip_html(desc_obj.get("plain") or desc_obj.get("html")) if isinstance(desc_obj, dict) else None
            avail = (v.get("availability") or {}).get("available")
            cond = [str(c).lower() for c in (v.get("condition") or [])]
            level, reason = store_registry.effective_level(store_id, has_item_ids=bool(_GID.match(gid)), qty=1)
            url = v.get("url") or product.get("url") or (f"https://{seller_domain}" if seller_domain else "")
            ids = {"variant_gid": gid}
            if seller_domain:
                ids["seller_domain"] = seller_domain
            if product.get("id"):
                ids["product_gid"] = str(product["id"])
            ids["ucp_query"] = query
            out.append(Offer(
                offer_id=make_offer_id("shopify_ucp", store_id, gid), store_id=store_id, store_name=store_name,
                seller_name=seller.get("name"), title=full_title[:300], description=description, url=url,
                price_usd=usd, currency="USD", units_per_pack=units,
                stock="in_stock" if avail is True else "out_of_stock" if avail is False else "unknown",
                condition="new" if "new" in cond else "used" if cond else "unknown",
                ids=ids, action_level=level, downgrade_reason=reason, source_api="shopify_ucp", seen_at=seen_at,
                evidence_path=evidence[0], evidence_sha256=evidence[1],
            ))
    return out


def _slim(data: dict[str, Any]) -> dict[str, Any]:
    """Evidence without the merchant's capability profile (large, the same on every call)."""
    return {k: v for k, v in data.items() if k not in ("ucp", "cta")}


# --------------------------------------------------------------------------- adapters


class MockShopifyUCP(FixtureAdapter):
    stands_for = ("shopify_ucp",)

    async def create_cart(self, business_url: str, lines: list[dict[str, Any]]) -> dict[str, Any]:
        return {"cart_id": "c_mock", "continue_url": "https://mock.invalid/cart/c_mock", **MOCK_LABEL}

    async def cancel_cart(self, cart_id: str, business_url: str | None = None) -> None:
        return None


class LiveShopifyUCP:
    source_api = "shopify_ucp"
    hosts: frozenset[str] = frozenset()  # the ucp CLI makes the requests; one call at a time behind a lock

    def __init__(self, runner: Runner | None = None, per_store: bool | None = None) -> None:
        self._cli = UcpCli()
        self._run: Runner = runner or self._cli.run
        self._per_store = (os.getenv("UCP_PER_STORE") or "1") != "0" if per_store is None else per_store

    def configured(self) -> bool:
        try:
            self._cli.command()
            return True
        except NotImplementedError:
            return False

    async def _call(self, tool: str, args: dict[str, Any], argv: list[str], *, bypass: bool = False) -> cache.Entry:
        async def go() -> dict[str, Any]:
            return await self._run(argv)

        return await cache.cached_entry(tool, args, go, bypass=bypass)

    async def _search_one(self, query: str, business: str | None, ctx: RunCtx, *, bypass: bool = False) -> list[Offer]:
        payload: dict[str, Any] = {"query": query, "context": {"address_country": "US"}}
        if business is None:
            payload["filters"] = {"ships_from": [{"country": "US"}]}
        argv = ["catalog", "search"]
        if business:
            argv += ["--business", business]
        argv += ["--input", json.dumps(payload, separators=(",", ":")), "--format", "json"]
        entry = await self._call("ucp.catalog.search", {"business": business or "global", "payload": payload}, argv, bypass=bypass)
        evidence = save_evidence(ctx.run_id, {"source_api": "shopify_ucp", "business": business or "global", "query": payload,
                                               "seen_at": entry.seen_at, "response": _slim(entry.value)})
        return _variant_offers(entry.value, business=business, query=query, seen_at=entry.seen_at, evidence=evidence)

    async def search(self, q: PartQuery, ctx: RunCtx) -> list[Offer]:
        """Global Catalog (ships_from US) plus each allowed Shopify store in the registry, USD only."""
        query = clean_query(q.query or q.spec or "")
        if not query:
            return []
        offers = await self._search_one(query, None, ctx)
        if self._per_store:
            done = 0
            for store_id in ctx.allowed_merchants:
                s = store_registry.store(store_id)
                if not s or s.get("search_source") != "shopify_ucp" or not s.get("enabled") or not s.get("business_url"):
                    continue
                if done >= PER_STORE_MAX:
                    break
                done += 1
                try:
                    offers += await self._search_one(query, _business(s["business_url"]), ctx)
                except (UcpError, NotImplementedError):
                    continue  # one store failing is a grey dot, never a failed run
        unique: dict[str, Offer] = {}
        for o in offers:
            unique.setdefault(o.offer_id, o)
        return list(unique.values())

    async def refresh(self, offer: Offer, ctx: RunCtx) -> Offer | None:
        """Live price and stock for one variant: `catalog lookup` [unverified], else a per-store search."""
        gid = offer.ids.get("variant_gid", "")
        domain = offer.ids.get("seller_domain") or (store_registry.store(offer.store_id) or {}).get("business_url")
        if not _GID.match(gid) or not domain:
            return None
        business = _business(domain)
        fresh: list[Offer] = []
        try:
            argv = ["catalog", "lookup", "--business", business, "--input", json.dumps({"ids": [gid]}, separators=(",", ":")), "--format", "json"]
            entry = await self._call("ucp.catalog.lookup", {"business": business, "ids": [gid]}, argv, bypass=True)
            evidence = save_evidence(ctx.run_id, {"source_api": "shopify_ucp", "lookup": gid, "seen_at": entry.seen_at, "response": _slim(entry.value)})
            fresh = _variant_offers(entry.value, business=business, query=offer.ids.get("ucp_query", ""), seen_at=entry.seen_at, evidence=evidence)
        except UcpError:
            fresh = []
        match = next((o for o in fresh if o.ids.get("variant_gid") == gid), None)
        if match is None:
            query = clean_query(offer.ids.get("ucp_query") or offer.title)
            fresh = await self._search_one(query, business, ctx, bypass=True)
            match = next((o for o in fresh if o.ids.get("variant_gid") == gid), None)
        if match is None:
            return offer.model_copy(update={"stock": "out_of_stock", "seen_at": now_iso()})
        return offer.model_copy(update={"price_usd": match.price_usd, "stock": match.stock, "seen_at": match.seen_at,
                                        "evidence_path": match.evidence_path, "evidence_sha256": match.evidence_sha256})

    async def create_cart(self, business_url: str, lines: list[dict[str, Any]]) -> dict[str, Any]:
        """A real anonymous Shopify cart -> continue_url. Sends variant ids, quantities and country only.

        `lines`: [{"variant_gid": "gid://shopify/ProductVariant/…", "quantity": n}] (or UCP's {"item": {"id"}}).
        """
        business = _business(business_url)
        items = []
        for line in lines:
            gid = str(line.get("variant_gid") or (line.get("item") or {}).get("id") or "")
            qty = line.get("quantity")
            if not _GID.match(gid) or not isinstance(qty, int) or not 1 <= qty <= 999:
                raise UcpError(f"bad cart line: {gid!r} x {qty!r}")
            items.append({"item": {"id": gid}, "quantity": qty})
        if not items:
            raise UcpError("a cart needs at least one line")
        payload = {"line_items": items, "context": {"address_country": "US"}}  # no buyer data, ever (PLAN §12.2 rule 9)
        argv = ["cart", "create", "--business", business, "--input", json.dumps(payload, separators=(",", ":")), "--format", "json"]
        entry = await self._call("ucp.cart.create", {"business": business, "payload": payload}, argv, bypass=True)
        result = entry.value.get("result") or {}
        cart_id, continue_url = str(result.get("id") or ""), str(result.get("continue_url") or "")
        if not cart_id or not continue_url.startswith("https://"):
            raise UcpError("ucp cart create returned no cart id or continue_url")
        subtotal = next((t.get("amount") for t in result.get("totals") or [] if t.get("type") == "subtotal"), None)
        currency = (result.get("currency") or "USD").upper()
        return {"cart_id": cart_id, "continue_url": continue_url, "business_url": business,
                "subtotal_usd": minor_to_major(subtotal, currency) if subtotal is not None else None,
                "currency": currency, "expires_at": result.get("expires_at"), "seen_at": entry.seen_at, "simulated": False}

    async def cancel_cart(self, cart_id: str, business_url: str | None = None) -> None:
        """`ucp cart cancel <id>` (the id is positional, Appendix A.1). A no-op in replay."""
        if cache.mode() == "replay":
            return None
        if not _CART_ID.match(cart_id):
            raise UcpError("not a Shopify cart id")
        argv = ["cart", "cancel", cart_id]
        if business_url:
            argv += ["--business", _business(business_url)]
        argv += ["--format", "json"]
        await self._run(argv)
        return None
