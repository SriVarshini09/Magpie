"""Reason codes and a one-sentence explanation for each decision (PLAN §11.6, the Why tab). Owner: A.

Deterministic: every number in the sentence comes from the offers of this run.
"""

from __future__ import annotations

from typing import Any

__all__ = ["explain"]

LEVEL_TEXT = {"agent_cart": "a cart the agent builds", "prefilled_cart": "a prefilled cart link", "product_link": "a product page you add by hand"}


def explain(decision: dict[str, Any]) -> dict[str, Any]:
    """{reason_codes, explanation}.

    decision = {name, qty, tier, status, chosen: [{title, store_name, action_level, packs, units_per_pack, price_usd}],
                alternatives: [{line_usd, action_level, store_name}], rejected: n, refused: n, edited_by_user, owned_note}
    """
    chosen = decision.get("chosen") or []
    alts = decision.get("alternatives") or []
    tier = decision.get("tier", "cheapest")
    name, qty = decision.get("name", "this part"), decision.get("qty", 1)
    status = decision.get("status")
    if status == "owned":
        return {"reason_codes": ["owned"], "explanation": f"Left out: {decision.get('owned_note') or 'you already have it'}."}
    if status in ("skipped", "removed"):
        return {"reason_codes": [status], "explanation": decision.get("owned_note") or "Left out of the cart."}
    if not chosen:
        n = int(decision.get("rejected") or 0) + int(decision.get("refused") or 0)
        why = f"{n} listing{'s were' if n != 1 else ' was'} found, and none is acceptable" if n else "no store returned a listing"
        return {"reason_codes": ["no_acceptable_offer"], "explanation": f"No offer chosen: {why}. A near miss is never picked."}
    codes: list[str] = []
    total = round(sum(c["packs"] * c["price_usd"] for c in chosen), 2)
    store = chosen[0]["store_name"]
    if decision.get("edited_by_user"):
        codes.append("edited_by_user")
    elif tier == "fewest_checkouts":
        codes.append("fewest_checkouts")
    elif not alts:
        codes.append("only_offer")
    else:
        codes.append("cheapest_allowed")
    if len(chosen) > 1 or any(c.get("units_per_pack", 1) > 1 for c in chosen):
        codes.append("pack_break")
    cheaper_weaker = [a for a in alts if abs(a["line_usd"] - total) < 0.005 and a["action_level"] != chosen[0]["action_level"]]
    if cheaper_weaker and chosen[0]["action_level"] == "agent_cart":
        codes.append("agent_cart_at_equal_price")
    parts = []
    for c in chosen:
        u = c.get("units_per_pack", 1)
        parts.append(f"{c['packs']} x {u}-pack" if u > 1 else f"{c['packs']} single{'s' if c['packs'] != 1 else ''}")
    how = " plus ".join(parts) if "pack_break" in codes else f"{chosen[0]['title']}"
    if "edited_by_user" in codes:
        text = f"You picked this: {how} from {store}, ${total:.2f}."
    elif "fewest_checkouts" in codes:
        text = f"{how} from {store} (${total:.2f}) keeps the number of checkouts down."
    elif "only_offer" in codes:
        text = f"{how} from {store} (${total:.2f}) is the only acceptable offer for {qty} x {name}."
    else:
        nxt = min((a["line_usd"] for a in alts), default=None)
        text = f"{how} from {store} is the cheapest allowed way to get {qty} x {name}: ${total:.2f}"
        text += f", against ${nxt:.2f} for the next option." if nxt is not None else "."
    text += f" It is {LEVEL_TEXT[chosen[0]['action_level']]}."
    return {"reason_codes": codes, "explanation": text}
