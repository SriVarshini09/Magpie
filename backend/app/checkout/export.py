"""CSV export of the Universal Cart (PLAN §4.2, §12.3 export). Owner: B.

Columns: line, part, store, action level, qty, unit price, line total, seen at, source, URL.
Listing titles are web content: a cell that starts with = + - @ (or a tab / carriage return) is prefixed
with an apostrophe so a spreadsheet never runs it as a formula.
"""

from __future__ import annotations

import csv
import io

from app.checkout import cart as cart_mod
from app.checkout.cart import CartContext
from app.models import UniversalCart

HEADER = ["line", "part", "store", "action level", "qty", "unit price", "line total", "seen at", "source", "URL"]
LEVEL_WORDS = {"agent_cart": "Agent cart", "prefilled_cart": "Prefilled cart", "product_link": "Product link"}


def _cell(value: object) -> str:
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def source_label(source_api: str, simulated: bool = False) -> str:
    if simulated or source_api == "mock":
        return "mock (simulated)"
    if source_api.startswith("serpapi:"):
        return f"via SerpAPI ({source_api.split(':', 1)[1]})"
    return {"shopify_ucp": "Shopify UCP", "adafruit": "Adafruit catalog", "magento": "Magento GraphQL",
            "digikey": "Digi-Key API", "jsonld": "store page (JSON-LD)"}.get(source_api, source_api)


def cart_csv(cart: UniversalCart, names: dict[str, str] | None = None) -> str:
    """line, part, store, action level, qty, unit price, line total, seen at, source, URL"""
    names = names or {}
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(HEADER)
    for g in cart.stores:
        level = g.handoff.kind if g.handoff else g.action_level
        for it in g.items:
            w.writerow([_cell(it.bom_line_id), _cell(names.get(it.bom_line_id, it.title)), _cell(g.display_name), LEVEL_WORDS[level],
                        it.qty, f"{it.unit_price_usd:.2f}", f"{it.line_usd:.2f}", _cell(it.seen_at),
                        _cell(source_label(it.source_api, it.simulated)), _cell(it.url)])
    return out.getvalue()


def export_csv(run_id: str, ctx: CartContext | None = None) -> str:
    """GET /cart/export.csv for a run (names from the BOM)."""
    ctx = cart_mod.context(run_id, ctx)
    return cart_csv(cart_mod.build_cart(run_id, ctx), cart_mod.part_names(ctx))
