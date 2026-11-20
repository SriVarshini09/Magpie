"""The chat's guard: what a message would need the agent to do, checked in code before either agent sees it.

Chat approves nothing, pays nothing, shares no buyer detail and cannot widen a mandate. A message that asks
for any of those is refused here, whichever agent is active; the refusal is logged as a refusal record.
The rules themselves are the mandate guard's (`app.agent.guard`): this module adds the chat phrasings.
"""

from __future__ import annotations

import re

from app.agent import guard
from app.models import OpenMandate, RefusalRecord

__all__ = ["precheck", "redact", "refusal_text", "WIDENING_RULES"]

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_STREET = re.compile(r"(?i)\b\d{1,6}\s+(?:[A-Za-z0-9.'-]+\s+){0,4}(?:st|street|ave|avenue|rd|road|blvd|boulevard|ln|lane|dr|drive|way|ct|court|pl|place)\b\.?(?:\s*,?\s*(?:apt|unit|suite|#)\s*\w+)?")
_PHONE = re.compile(r"(?<!\w)\+?(?:\d[\s().-]{0,2}){9,14}\d(?!\w)")

_BUY = re.compile(r"(?i)\b(buy|order|purchase)\s+(it|this|that|them|these|everything|all|now|the\s+(cart|parts|lot|whole\s+\w+))\b|\b(approve|approval)\b")
_CHECKOUT = re.compile(r"(?i)\bcheck\s?out\b(?!s)|\bplace\s+(the|my|an)\s+order\b|\bcomplete\s+(the|my)\s+(order|purchase)\b")
_PAY = re.compile(r"(?i)\b(pay|charge my|use my card)\b")
_ADDRESS = re.compile(r"(?i)\b(my|our)\s+(\w+\s+)?address\b|\bship\s+(it\s+|them\s+)?to\b")

# A refusal under one of these rules means the user asked for more than the signed mandate allows.
WIDENING_RULES = {"merchant_allowed", "budget", "data_sharing"}


def redact(text: str) -> tuple[str, bool]:
    """Buyer details typed into chat are not kept: an email, a phone number or a street address is cut out."""
    out = _EMAIL.sub("[email removed]", text)
    out = _STREET.sub("[address removed]", out)
    out = _PHONE.sub("[phone removed]", out)
    return out, out != text


def precheck(mandate: OpenMandate, text: str, *, known_stores: dict[str, str] | None = None) -> list[RefusalRecord]:
    """Every refusal the message triggers. An empty list means the agent may handle it."""
    out = guard.scan_chat(mandate, text, known_stores=known_stores)

    def add(r: RefusalRecord | None) -> None:
        if r is not None and all((r.rule, r.clause) != (x.rule, x.clause) for x in out):
            out.append(r)

    ctx = {"triggered_by": "user_chat", "approval_tokens": {"-": "-"}}
    if _BUY.search(text):
        add(guard.refusal("approval_required", "only the Approve button issues an approval token", tool="create_carts",
                          field="approval_token", triggered_by="user_chat"))
    if _CHECKOUT.search(text):
        add(guard.check(mandate, "checkout", {}, ctx))
    if _PAY.search(text):
        add(guard.check(mandate, "pay", {}, ctx))
    if _EMAIL.search(text):
        add(guard.check(mandate, "create_carts", {"buyer": {"email": "<from chat>"}}, ctx)
            or guard.refusal("data_sharing", "chat never carries buyer details", tool="create_carts", field="buyer.email", triggered_by="user_chat"))
    if _ADDRESS.search(text) or _STREET.search(text):
        add(guard.check(mandate, "create_carts", {"buyer": {"street_address": "<from chat>"}}, ctx)
            or guard.refusal("data_sharing", "chat never carries buyer details", tool="create_carts", field="buyer.street_address", triggered_by="user_chat"))
    return out


def refusal_title(r: RefusalRecord) -> str:
    if r.rule == "approval_required":
        return "Refused: chat can't approve a cart"
    if r.rule == "action_allowed":
        return f"Refused: the agent can't {(r.attempted.tool or 'do that').replace('_', ' ')}"
    if r.rule == "data_sharing":
        return f"Refused: {(r.attempted.field or 'that detail').split('.')[-1].replace('_', ' ')} is not shared"
    if r.rule == "merchant_allowed":
        return f"Refused: {r.attempted.value or 'that store'} isn't in your mandate"
    if r.rule == "host_not_allowed":
        return f"Refused: {r.attempted.value or 'that site'} can't be read"
    return f"Refused: {r.rule.replace('_', ' ')}"


def refusal_text(r: RefusalRecord, *, has_cart: bool) -> str:
    where = "Open Review cart and press Approve cart." if has_cart else "Once the cart is ready, you approve it with the Approve cart button."
    if r.rule == "approval_required":
        return f"I can't approve or buy from chat. An approval typed here approves nothing: only the Approve button does. {where}"
    if r.rule == "action_allowed":
        return f"I can't pay or check out. You pay at each store yourself, after you approve the cart. {where}"
    if r.rule == "data_sharing":
        what = (r.attempted.field or "that detail").split(".")[-1].replace("_", " ")
        return (f"I won't pass on your {what}. Your mandate doesn't share it, and chat never carries buyer details to a store. "
                "What is shared can only change in a new signed mandate.")
    if r.rule == "merchant_allowed":
        return f"Refused: {r.attempted.value or 'that store'} isn't in your mandate. Adding a store needs a new signed mandate."
    if r.rule == "budget":
        return "Raising the budget needs a new signed mandate. I can only plan inside the one you signed."
    if r.rule == "host_not_allowed":
        return f"We can't read {r.attempted.value or 'that site'}. Paste the parts list as text instead."
    return f"Refused under the mandate rule \"{r.rule.replace('_', ' ')}\"."
