"""Mandate guard: allow or refuse a tool call. Enforced in code, outside the model (PLAN §3.6, §3.7).

Owner: A. The guard runs on tool calls and UI actions, never on what the model says, so it holds
even if the model is persuaded. One test per refusal rule: tests/test_guard.py.

`check(mandate, tool, args, ctx)` returns None (allowed) or a `RefusalRecord`.
`ctx` carries what only the harness knows: the offers found in this run, the open assumptions,
the approval tokens. A missing `ctx` key is treated as "nothing known", which refuses.
"""

from __future__ import annotations

import re
from typing import Any

from app.audit.chain import sha256_hex
from app.models import OpenMandate, RefusalAttempt, RefusalRecord
from app.stores.http import host_of, is_never_request

__all__ = ["check", "strip_buyer_fields", "scan_chat", "refusal", "AGENT_TOOLS", "BUYER_FIELDS", "store_of_host"]

# The only tools the agent has. Anything else (checkout, pay, message_seller, ...) is refused.
AGENT_TOOLS = frozenset({
    "ingest_source", "extract_bom", "load_template", "find_reference_design", "identify_parts", "lookup_trusted_spec",
    "resolve_part", "recall_owned", "search_offers", "rank_offers", "check_compatibility", "optimize_cart",
    "stage_cart", "create_carts", "remember",
})
UI_ACTIONS = frozenset({"replan", "cart_edit", "approve"})  # human actions, checked by the same guard
FORBIDDEN_ACTIONS = {
    "checkout": "checkout", "complete_checkout": "checkout", "create_checkout": "checkout", "place_order": "checkout",
    "pay": "pay", "create_payment": "pay", "payment_intent": "pay", "capture_payment": "pay",
    "message_seller": "message_seller", "contact_seller": "message_seller",
}
# buyer field -> the data_sharing flag that must be true to send it
BUYER_FIELDS: dict[str, str] = {
    "email": "email", "buyer_email": "email",
    "phone": "phone", "phone_number": "phone",
    "name": "name", "first_name": "name", "last_name": "name", "full_name": "name",
    "address": "street_address", "street_address": "street_address", "address1": "street_address", "address2": "street_address",
    "address_line1": "street_address", "address_line2": "street_address", "shipping_address": "street_address",
    "billing_address": "street_address", "city": "street_address",
    "postal_code": "postal_code", "zip": "postal_code", "zip_code": "postal_code", "address_zip": "postal_code",
}
_AFFILIATE = re.compile(r"(?i)[?&](tag|AssociateTag|affiliate|aff_id|ref)=")


def _now() -> str:
    from app.runstate import now_iso

    return now_iso()


def refusal(rule: str, clause: str, *, tool: str | None = None, field: str | None = None, value: str | None = None,
            triggered_by: str = "agent") -> RefusalRecord:
    return RefusalRecord(rule=rule, attempted=RefusalAttempt(tool=tool, field=field, value=value), clause=clause,  # type: ignore[arg-type]
                         triggered_by=triggered_by, ts=_now())  # type: ignore[arg-type]


def store_of_host(url_or_host: str) -> str:
    """A readable store name for a host: 'www.alibaba.com' -> 'alibaba.com'."""
    host = host_of(url_or_host)
    return host[4:] if host.startswith("www.") else host


def _find_buyer_fields(obj: Any, path: str = "") -> list[tuple[str, str]]:
    """[(dotted path, data_sharing flag)] for every buyer field with a value anywhere in a payload."""
    found: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            flag = BUYER_FIELDS.get(str(k).lower())
            if flag and v not in (None, "", [], {}):
                found.append((p, flag))
            else:
                found.extend(_find_buyer_fields(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_find_buyer_fields(v, f"{path}[{i}]"))
    return found


def strip_buyer_fields(mandate: OpenMandate, payload: Any, *, tool: str = "create_carts",
                       triggered_by: str = "agent") -> tuple[Any, list[RefusalRecord]]:
    """Remove buyer fields the mandate does not share. One refusal per stripped field (PLAN §3.6)."""
    sharing = mandate.constraints.data_sharing.model_dump()
    refusals: list[RefusalRecord] = []

    def walk(obj: Any, path: str) -> Any:
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                p = f"{path}.{k}" if path else str(k)
                flag = BUYER_FIELDS.get(str(k).lower())
                if flag and v not in (None, "", [], {}):
                    if sharing.get(flag):
                        out[k] = v
                    else:
                        refusals.append(refusal("data_sharing", f"constraints.data_sharing.{flag}=false", tool=tool, field=p, triggered_by=triggered_by))
                else:
                    out[k] = walk(v, p)
            return out
        if isinstance(obj, list):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(obj)]
        return obj

    return walk(payload, ""), refusals


def check(mandate: OpenMandate, tool: str, args: dict[str, Any], ctx: dict[str, Any] | None = None) -> RefusalRecord | None:
    """None = allowed; a RefusalRecord otherwise. The first failing rule wins."""
    ctx = ctx or {}
    c, scope = mandate.constraints, mandate.scope
    by = ctx.get("triggered_by", "agent")

    # --- actions that do not exist for the agent
    if tool in FORBIDDEN_ACTIONS:
        action = FORBIDDEN_ACTIONS[tool]
        return refusal("action_allowed", f"constraints.actions.{action}=false", tool=tool, triggered_by=by)
    if tool not in AGENT_TOOLS and tool not in UI_ACTIONS:
        return refusal("action_allowed", "tool is not on the agent's tool list", tool=tool, triggered_by=by)

    # --- buyer data: never leaves unless the mandate shares that field
    sharing = c.data_sharing.model_dump()
    for path, flag in _find_buyer_fields(args):
        if not sharing.get(flag):
            return refusal("data_sharing", f"constraints.data_sharing.{flag}=false", tool=tool, field=path, triggered_by=by)

    if tool == "ingest_source":
        url = str(args.get("url") or "")
        if is_never_request(url):
            return refusal("host_not_allowed", "fetch allowlist (PLAN §3.16 rule 3)", tool=tool, field="url", value=store_of_host(url), triggered_by=by)
        if not scope.inputs.source_url or url.rstrip("/") != scope.inputs.source_url.rstrip("/"):
            return refusal("scope_mismatch", "scope.inputs.source_url", tool=tool, field="url", value=url, triggered_by=by)

    elif tool == "load_template":
        bt = args.get("build_type")
        if bt != scope.build_type:
            return refusal("scope_mismatch", "scope.build_type", tool=tool, field="build_type", value=str(bt), triggered_by=by)

    elif tool == "find_reference_design":
        if not scope.reference_search:
            return refusal("action_allowed", "scope.reference_search=false", tool=tool, triggered_by=by)
        url = args.get("url")
        if url and is_never_request(str(url)):
            return refusal("reference_host_not_allowed", "fetch allowlist (PLAN §3.16 rule 3)", tool=tool, field="url", value=store_of_host(str(url)), triggered_by=by)

    elif tool == "identify_parts":
        sha = args.get("image_sha256")
        if not sha or sha not in scope.inputs.image_sha256:
            return refusal("scope_mismatch", "scope.inputs.image_sha256", tool=tool, field="image_id", value=str(args.get("image_id")), triggered_by=by)
        if not c.data_sharing.photo_to_models:
            return refusal("photo_not_shared", "constraints.data_sharing.photo_to_models=false", tool=tool, field="image_id", value=str(args.get("image_id")), triggered_by=by)

    elif tool in ("search_offers", "rank_offers"):
        if not c.actions.search:
            return refusal("action_allowed", "constraints.actions.search=false", tool=tool, triggered_by=by)
        store = args.get("store_id")  # a search aimed at one store must stay inside the allowlist
        if store and store not in c.allowed_merchants:
            return refusal("merchant_allowed", "constraints.allowed_merchants", tool=tool, field="store_id", value=str(store), triggered_by=by)

    elif tool in ("optimize_cart", "replan"):
        cap = args.get("budget_cap_usd")
        if cap is not None and float(cap) > float(c.budget_usd):
            return refusal("budget", "constraints.budget_usd", tool=tool, field="budget_cap_usd", value=str(cap), triggered_by=by)

    elif tool == "cart_edit":
        offer_id, store = args.get("offer_id"), args.get("store_id")
        known: dict[str, str] = ctx.get("offer_stores", {})
        if offer_id is not None:
            if offer_id not in known:
                return refusal("unknown_offer", "only offers found in this run", tool=tool, field="offer_id", value=str(offer_id), triggered_by="user_edit")
            store = store or known[offer_id]
        if store is not None and store not in c.allowed_merchants:
            return refusal("merchant_allowed", "constraints.allowed_merchants", tool=tool, field="store_id", value=str(store), triggered_by="user_edit")

    elif tool in ("create_carts", "approve"):
        if tool == "create_carts":
            if not c.actions.create_cart:
                return refusal("action_allowed", "constraints.actions.create_cart=false", tool=tool, triggered_by=by)
            token = args.get("approval_token")
            tokens: dict[str, str] = ctx.get("approval_tokens", {})
            if not token or sha256_hex(str(token)) not in tokens:
                return refusal("approval_required", "only the Approve button issues an approval token", tool=tool, field="approval_token", triggered_by=by)
            if ctx.get("plan_sha256") and tokens[sha256_hex(str(token))] != ctx["plan_sha256"]:
                return refusal("approval_required", "the approval token is bound to another plan", tool=tool, field="approval_token", triggered_by=by)
        open_lines = ctx.get("open_assumptions") or []
        if open_lines:
            return refusal("assumption_unconfirmed", "PLAN §3.18: Approve is refused while an assumption is open", tool=tool, value=",".join(open_lines), triggered_by=by)
        known = ctx.get("offer_stores", {})
        for offer_id in args.get("offer_ids") or []:
            if offer_id not in known:
                return refusal("unknown_offer", "only offers returned by search_offers in this run", tool=tool, field="offer_id", value=str(offer_id), triggered_by=by)
            if known[offer_id] not in c.allowed_merchants:
                return refusal("merchant_allowed", "constraints.allowed_merchants", tool=tool, field="store_id", value=known[offer_id], triggered_by=by)
        total = args.get("total_usd")
        if total is not None and float(total) > float(c.budget_usd) + 1e-9:
            return refusal("budget", "constraints.budget_usd", tool=tool, field="total_usd", value=f"{float(total):.2f}", triggered_by=by)
        if ctx.get("stale_prices"):
            return refusal("stale_price", f"prices older than {ctx.get('price_max_age_min', 15)} minutes", tool=tool, triggered_by=by)
        for url in args.get("urls") or []:
            if _AFFILIATE.search(str(url)) and not c.actions.build_cart_link:
                return refusal("action_allowed", "constraints.actions.build_cart_link=false", tool=tool, field="url", triggered_by=by)

    return None


# ---------------------------------------------------------------------------- chat: text approves nothing

_CHAT_RULES: list[tuple[re.Pattern[str], str, dict[str, Any]]] = [
    (re.compile(r"(?i)\b(e-?mail)\b"), "create_carts", {"buyer": {"email": "<from chat>"}}),
    (re.compile(r"(?i)\b(phone|number)\b.*\b(send|share|give)\b|\b(send|share|give)\b.*\b(phone)\b"), "create_carts", {"buyer": {"phone": "<from chat>"}}),
    (re.compile(r"(?i)\b(send|share|give|tell)\b.*\baddress\b|\baddress\b.*\b(send|share|give)\b"), "create_carts", {"buyer": {"street_address": "<from chat>"}}),
    (re.compile(r"(?i)\b(pay|purchase it|buy it now|charge)\b"), "pay", {}),
    (re.compile(r"(?i)\b(check ?out for me|place the order|complete the order)\b"), "checkout", {}),
    (re.compile(r"(?i)\b(message|contact|email) the seller\b"), "message_seller", {}),
]
_APPROVE = re.compile(r"(?i)\b(i approve|approved?|go ahead|skip approval|confirm the cart|i confirm)\b")
_HOST = re.compile(r"(?i)\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b")


def scan_chat(mandate: OpenMandate, text: str, *, known_stores: dict[str, str] | None = None) -> list[RefusalRecord]:
    """What a chat message would need the agent to do, run through the guard. Chat approves nothing.

    `known_stores` maps a lower-case store word ("alibaba") to a store_id or host, from the store
    registry and the source document. Stores outside the allowlist are refused.
    """
    out: list[RefusalRecord] = []
    for pattern, tool, args in _CHAT_RULES:
        if pattern.search(text):
            r = check(mandate, tool, args, {"triggered_by": "user_chat", "approval_tokens": {"-": "-"}})
            if r is None and tool == "create_carts":  # the field is shared; the cart still needs the Approve button
                continue
            if r is not None and all((r.rule, r.clause) != (x.rule, x.clause) for x in out):
                out.append(r)
    if _APPROVE.search(text):
        out.append(refusal("approval_required", "only the Approve button issues an approval token", tool="create_carts",
                           field="approval_token", triggered_by="user_chat"))
    seen: set[str] = set()
    lower = text.lower()
    for word, store in (known_stores or {}).items():
        if re.search(rf"\b{re.escape(word)}\b", lower) and store not in mandate.constraints.allowed_merchants and store not in seen:
            seen.add(store)
            out.append(refusal("merchant_allowed", "constraints.allowed_merchants", tool="search_offers", field="store_id", value=store, triggered_by="user_chat"))
    for host in _HOST.findall(text):
        name = store_of_host(host)
        if name.split(".")[0] in (known_stores or {}) or name in seen:
            continue
        if is_never_request(host) and name not in seen:
            seen.add(name)
            out.append(refusal("host_not_allowed", "fetch allowlist (PLAN §3.16 rule 3)", tool="ingest_source", field="url", value=name, triggered_by="user_chat"))
    return out
