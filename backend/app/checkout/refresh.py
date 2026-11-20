"""Re-fetch only the offers in the cart: the one call that bypasses the cache (PLAN §11, §12.3 price freshness).

Owner: B.
- Shopify (catalog lookup), Adafruit, Magento and Digi-Key are re-read live.
- SerpAPI offers only if older than 30 minutes and the quota allows; otherwise their age stays visible.
- A changed price or lost stock flags the row ("$17.00 -> $18.50"), updates the total and writes a
  `price_refresh` record. Approve then waits until the change has been seen (checkout/cart.py).
- Replay: no network; the note reads "Replay: prices as recorded at 2:45 PM" and the age check is off.
- After approval the prices are locked into the signed mandate: nothing is re-read.
"""

from __future__ import annotations

from typing import Any

from app.checkout import cart as cart_mod
from app.checkout.cart import BOOK, CartContext, emit_event, emit_record
from app.config import get_settings
from app.models import CartRefreshResponse, PriceChange
from app.stores import registry as store_registry
from app.stores.base import RefreshSkipped, RunCtx, now_iso, parse_ts


def _clock_label(ts: str) -> str:
    dt = parse_ts(ts)
    return dt.strftime("%I:%M %p").lstrip("0") if dt else ts


async def refresh_prices(run_id: str, ctx: CartContext | None = None, *, adapter_for: Any = None) -> CartRefreshResponse:
    """POST /cart/refresh. Flags changed prices and lost stock; writes a price_refresh record."""
    rec = BOOK.get(run_id)
    cart = cart_mod.build_cart(run_id, ctx)
    checked_at = now_iso()
    if get_settings().demo_mode == "replay":
        return CartRefreshResponse(checked_at=cart.prices_checked_at, changes=[],
                                   note=f"Replay: prices as recorded at {_clock_label(cart.prices_checked_at)}")
    if rec.state != "draft":
        return CartRefreshResponse(checked_at=checked_at, changes=[],
                                   note="The cart is approved: its prices are locked into the signed mandate")
    ctx = cart_mod.context(run_id, ctx)
    lookup = adapter_for or store_registry.adapter_for_source
    run_ctx = RunCtx(run_id=run_id, allowed_merchants=tuple(ctx.allowed_merchants), demo_mode=get_settings().demo_mode, bypass_cache=True)
    changes: list[PriceChange] = []
    skipped: dict[str, str] = {}
    refreshed = 0
    seen_ids: set[str] = set()
    for g in cart.stores:
        for it in g.items:
            if it.offer_id in seen_ids:
                continue
            seen_ids.add(it.offer_id)
            offer = rec.overrides.get(it.offer_id) or ctx.offers.get(it.offer_id)
            if offer is None:
                continue
            adapter = lookup(offer.source_api)
            if adapter is None:
                skipped[it.offer_id] = "no adapter can re-read this source"
                continue
            try:
                fresh = await adapter.refresh(offer, run_ctx)
            except RefreshSkipped as exc:
                skipped[it.offer_id] = str(exc)
                continue
            except Exception as exc:  # noqa: BLE001 - a failed re-read keeps the old price and its age
                skipped[it.offer_id] = f"refresh failed: {type(exc).__name__}"
                continue
            if fresh is None:
                skipped[it.offer_id] = "this source has no live re-read"
                continue
            refreshed += 1
            rec.unrefreshable.pop(it.offer_id, None)
            price_moved = abs(fresh.price_usd - offer.price_usd) >= 0.005
            stock_lost = fresh.stock == "out_of_stock" and offer.stock != "out_of_stock"
            if price_moved or stock_lost:
                original = rec.changed_old.get(it.offer_id, offer.price_usd)
                rec.changed_old[it.offer_id] = original
                changes.append(PriceChange(offer_id=it.offer_id, old_usd=offer.price_usd, new_usd=fresh.price_usd, stock=fresh.stock))
            rec.overrides[it.offer_id] = fresh
    rec.unrefreshable.update(skipped)
    rec.last_refresh_at = checked_at
    if changes:
        rec.prices_version += 1
        by_id = {c.offer_id: c for c in rec.price_changes}
        by_id.update({c.offer_id: c for c in changes})
        rec.price_changes = list(by_id.values())
    h = emit_record(run_id, "price_refresh", {"checked_at": checked_at, "refreshed": refreshed,
                                              "changes": [c.model_dump() for c in changes], "kept_as_seen": skipped})
    note = None
    if skipped:
        note = f"{len(skipped)} price{'s' if len(skipped) != 1 else ''} kept as seen (age shown): " + "; ".join(sorted(set(skipped.values())))[:200]
    emit_event(run_id, "price.refreshed", f"Prices checked: {len(changes)} changed" if changes else "Prices checked: no changes",
               severity="warn" if changes else "ok", record_hash=h, detail=note,
               data={"changes": [c.model_dump() for c in changes], "kept_as_seen": len(skipped)})
    return CartRefreshResponse(checked_at=checked_at, changes=changes, note=note,
                               simulated=all(i.simulated for g in cart.stores for i in g.items) if cart.stores else False)
