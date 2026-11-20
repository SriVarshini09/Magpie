"""Build the part panel for one BOM line (PLAN §11.6, §4.2 `PartPanel`). Owner: A.

Every row state the UI designs against comes from here: chosen (one or more packs), alternatives at
each action level, rejected with the rule that rejected it, refused with the mandate clause, an owned
line with its memory, a line with no acceptable offer, and an open assumption.
"""

from __future__ import annotations

import math
from typing import Any

from app.models import Check, OfferRow, OwnedInfo, PanelRefusal, PartPanel, Why
from app.pipeline.explain import explain

__all__ = ["build_panel", "offer_rows", "decision_body"]

STATUS_ORDER = {"chosen": 0, "alternative": 1, "rejected": 2, "refused": 3}
# Offer.refused -> the mandate clause the refused row names
REFUSED_CLAUSE = {"merchant_not_in_mandate": "constraints.allowed_merchants",
                  "listing_asked_for_buyer_data": "constraints.data_sharing"}


def offer_rows(run: Any, bom_line_id: str, tier: str | None = None) -> list[OfferRow]:
    line = run.line(bom_line_id)
    qty = run.pins.qty.get(bom_line_id, line.qty if line else 1)
    plan = run.plan(tier)
    chosen = {pl.offer_id: pl.packs for pl in (plan.lines if plan else []) if pl.bom_line_id == bom_line_id}
    rejected = run.rejected.get(bom_line_id, {})
    chosen_total = round(sum(run.offer_index[oid].price_usd * k for oid, k in chosen.items() if oid in run.offer_index), 2)
    rows: list[OfferRow] = []
    for o in run.offers.get(bom_line_id, []):
        if o.offer_id in chosen:
            status, reason, packs = "chosen", None, chosen[o.offer_id]
        elif o.refused:
            clause = REFUSED_CLAUSE.get(o.refused, "constraints.allowed_merchants")
            status, reason, packs = "refused", clause, math.ceil(qty / max(1, o.units_per_pack))
        elif o.offer_id in rejected:
            status, reason, packs = "rejected", rejected[o.offer_id], math.ceil(qty / max(1, o.units_per_pack))
        else:
            status, reason, packs = "alternative", None, math.ceil(qty / max(1, o.units_per_pack))
        line_usd = round(packs * o.price_usd, 2)
        rows.append(OfferRow(
            offer_id=o.offer_id, store_id=o.store_id, store_name=o.store_name, seller_name=o.seller_name, title=o.title, url=o.url,
            price_usd=o.price_usd, units_per_pack=o.units_per_pack, packs_needed=packs, line_usd=line_usd, shipping_usd=o.shipping_usd,
            eta_text=o.eta_text, stock=o.stock, rating=o.rating, reviews=o.reviews, action_level=o.action_level,
            downgrade_reason=o.downgrade_reason, source_api=o.source_api, mock_of=o.mock_of, seen_at=o.seen_at,
            evidence_sha256=o.evidence_sha256, status=status, reason=reason,  # type: ignore[arg-type]
            rerank_score=o.rerank.score if o.rerank else None,
            vs_chosen_usd=round(line_usd - chosen_total, 2) if status == "alternative" and chosen else None,
            spec_reads=list(o.spec_reads), simulated=o.simulated))
    rows.sort(key=lambda r: (STATUS_ORDER[r.status], r.line_usd if r.status != "chosen" else -r.units_per_pack, r.offer_id))
    return rows


def _refusals(run: Any, bom_line_id: str) -> list[PanelRefusal]:
    grouped: dict[tuple[str, str, str, str], int] = {}
    for r in run.refusals:
        if r.get("bom_line_id") != bom_line_id:
            continue
        att = r.get("attempted") or {}
        attempted = att.get("value") or att.get("field") or att.get("tool") or ""
        key = (r["rule"], r["clause"], str(attempted), r.get("triggered_by", "agent"))
        grouped[key] = grouped.get(key, 0) + int(r.get("count") or 1)
    return [PanelRefusal(rule=k[0], clause=k[1], attempted=k[2], triggered_by=k[3], count=n) for k, n in grouped.items()]  # type: ignore[arg-type]


def _why(run: Any, line: Any, rows: list[OfferRow]) -> Why:
    chosen = [r for r in rows if r.status == "chosen"]
    out = explain({
        "name": line.raw_name, "qty": run.pins.qty.get(line.bom_line_id, line.qty), "tier": run.active_tier, "status": line.status,
        "owned_note": line.owned_note,
        "chosen": [{"title": r.title, "store_name": r.store_name, "action_level": r.action_level, "packs": r.packs_needed,
                    "units_per_pack": r.units_per_pack, "price_usd": r.price_usd} for r in chosen],
        "alternatives": [{"line_usd": r.line_usd, "action_level": r.action_level, "store_name": r.store_name} for r in rows if r.status == "alternative"],
        "rejected": sum(r.status == "rejected" for r in rows), "refused": sum(r.status == "refused" for r in rows),
        "edited_by_user": line.bom_line_id in run.edited_lines,
    })
    return Why(tier=run.active_tier, reason_codes=out["reason_codes"], explanation=out["explanation"], edited_by_user=line.bom_line_id in run.edited_lines)


def build_panel(run: Any, bom_line_id: str) -> PartPanel | None:
    line = run.line(bom_line_id)
    if line is None:
        return None
    res = run.resolved.get(bom_line_id)
    rows = offer_rows(run, bom_line_id)
    owned = run.owned.get(bom_line_id)
    if owned is None and line.status == "owned" and line.owned_note and line.provenance.type != "assumption":
        owned = OwnedInfo(memory_text=line.owned_note, provider="owned_parts")
    checks: list[Check] = [c for c in run.checks if bom_line_id in c.bom_line_ids]
    simulated = run.simulated or any(r.simulated for r in rows)
    return PartPanel(
        bom_line_id=bom_line_id, name=line.raw_name, qty=run.pins.qty.get(bom_line_id, line.qty), line_kind=line.line_kind, status=line.status,
        mesh_keys=line.mesh_keys, provenance=line.provenance, spec=(res.spec if res else None) or line.spec or line.raw_name,
        attrs=res.attrs if res else {}, confidence=res.confidence if res else (line.confidence or 0.0), method=res.method if res else "llm_inferred",
        owned=owned, offers=rows, why=_why(run, line, rows), checks=checks, refusals=_refusals(run, bom_line_id), kb=run.kb.get(bom_line_id, []),
        needs_confirmation=bom_line_id in run.open_assumptions(), record_hash=run.decisions.get(bom_line_id) or run.head_hash,
        source_api="mock" if simulated else None, simulated=simulated)


def decision_body(run: Any, bom_line_id: str, model_name: str = "") -> dict[str, Any]:
    """The body of a `part_decision` chain record (PLAN §3.7 DecisionRecord), without the chain fields."""
    line = run.line(bom_line_id)
    panel = build_panel(run, bom_line_id)
    res = run.resolved.get(bom_line_id)
    owned = run.owned.get(bom_line_id)
    rows = panel.offers if panel else []
    return {
        "part": {"bom_line_id": bom_line_id, "raw_name": line.raw_name, "qty": line.qty, "line_kind": line.line_kind,
                 "provenance": line.provenance.model_dump(mode="json")},
        "resolution": res.model_dump(mode="json") if res else {"spec": line.raw_name, "attrs": {}, "confidence": 0.0, "method": "llm_inferred", "trusted_context": []},
        "owned_check": {"provider": owned.provider if owned else "cognee", "matched": owned.memory_text if owned else None,
                        "action": "remove" if line.status == "owned" else "keep"},
        "candidates": [{"offer_id": o.offer_id, "store_id": o.store_id, "action_level": o.action_level, "url": o.url, "title": o.title, "price": o.price_usd,
                        "currency": o.currency, "units_per_pack": o.units_per_pack, "shipping": o.shipping_usd, "eta": o.eta_text, "stock": o.stock,
                        "rating": o.rating, "reviews": o.reviews, "seen_at": o.seen_at, "source_api": o.source_api, "evidence_path": o.evidence_path,
                        "evidence_sha256": o.evidence_sha256, "rerank": o.rerank.model_dump() if o.rerank else None, "simulated": o.simulated}
                       for o in run.offers.get(bom_line_id, []) if not o.refused],
        "rejected": [{"offer_id": oid, "reason": why} for oid, why in run.rejected.get(bom_line_id, {}).items()],
        "mandate_checks": [{"rule": r.rule, "result": "refused", "attempted": r.attempted, "clause": r.clause} for r in (panel.refusals if panel else [])],
        "compatibility": [{"rule_id": c.rule_id, "result": c.result, "message": c.message, "kb_ref": c.kb_refs[0] if c.kb_refs else None, "fix": c.fix}
                          for c in (panel.checks if panel else [])],
        "decision": {"chosen": [{"offer_id": r.offer_id, "packs": r.packs_needed} for r in rows if r.status == "chosen"], "tier": run.active_tier,
                     "reason_codes": panel.why.reason_codes if panel else [], "explanation": panel.why.explanation if panel else "",
                     "edited_by_user": bom_line_id in run.edited_lines},
        "model": {"name": model_name, "input_tokens": 0, "output_tokens": 0},
        "simulated": bool(panel and panel.simulated),
    }
