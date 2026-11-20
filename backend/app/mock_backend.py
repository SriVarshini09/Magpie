"""Mock-mode backend: every §4.2 endpoint answered from backend/fixtures/ (no network, no keys).

SHARED FILE, owned by the coordinator. It exists so C can build the UI before A, B and D finish.
It is NOT the implementation: builders replace the route bodies in app/main.py, not this file.

State is in memory and resets when the server restarts or a run is created again.
Everything returned is labelled mock (source_api "mock", simulated true).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import HTTPException

from app import fixtures
from app.config import get_settings
from app.stores.http import is_never_request

RUNS = {"r_mock_so101": "so101", "r_mock_drone": "drone"}
INTAKES = {"in_mock_so101": "so101", "in_mock_drone": "drone", "in_mock_photo": "photo"}
PANELS = {("so101", "b1"): "panel_b1.json", ("drone", "b2"): "panel_motor.json"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def api_error(status: int, error: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": error, "message": message, **extra})


def _refusal(rule: str, clause: str, triggered_by: str, **attempted: str) -> dict[str, Any]:
    return {"kind": "refusal", "rule": rule, "attempted": attempted, "clause": clause, "triggered_by": triggered_by,
            "ts": get_settings().pinned_now}


class MockBackend:
    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.carts: dict[str, dict[str, Any]] = {}
        self.intakes: dict[str, dict[str, Any]] = {}
        for run_id in RUNS:
            self.reset_run(run_id)

    # ------------------------------------------------------------------ helpers

    def reset_run(self, run_id: str) -> None:
        key = RUNS[run_id]
        self.runs[run_id] = fixtures.load(f"run_{key}.json")
        self.carts[run_id] = fixtures.load(f"cart_{key}.json")

    def key(self, run_id: str) -> str:
        if run_id not in RUNS:
            raise api_error(404, "run_not_found", f"No run {run_id}. Mock mode has: {', '.join(RUNS)}")
        return RUNS[run_id]

    def run(self, run_id: str) -> dict[str, Any]:
        self.key(run_id)
        return self.runs[run_id]

    def cart(self, run_id: str) -> dict[str, Any]:
        self.key(run_id)
        return self.carts[run_id]

    def line(self, run_id: str, bom_line_id: str) -> dict[str, Any]:
        for ln in self.run(run_id)["bom"]:
            if ln["bom_line_id"] == bom_line_id:
                return ln
        raise api_error(404, "line_not_found", f"No BOM line {bom_line_id} in {run_id}")

    # ------------------------------------------------------------------ intake

    def intake(self, text: str | None, images: list[tuple[str, str | None, int]]) -> dict[str, Any]:
        """`images` is [(filename, content_type, size_bytes)]. Mock mode stores no upload."""
        s = get_settings()
        if len(images) > s.upload_max_images:
            raise api_error(422, "too_many_images", f"At most {s.upload_max_images} photos per request")
        for name, ctype, size in images:
            if ctype not in ALLOWED_IMAGE_TYPES:
                raise api_error(422, "unsupported_file", f"{name}: use JPEG, PNG or WebP")
            if size > s.upload_max_mb * 1024 * 1024:
                raise api_error(422, "file_too_large", f"{name}: larger than {s.upload_max_mb} MB")
        if not text and not images:
            raise api_error(422, "empty_request", "Type what you want to build, paste a link, or add a photo")
        for word in (text or "").split():
            if word.startswith(("http://", "https://")) and is_never_request(word):
                raise api_error(409, "reference_host_not_allowed", "We can't read that site. Paste the parts list as text instead.",
                                refusal=_refusal("reference_host_not_allowed", "fetch allowlist (PLAN §3.16 rule 3)", "user_chat", value=word))
        if images:
            name = "intake_photo.json"
        elif text and "so-arm100" in text.lower():
            name = "intake_so101.json"
        else:
            name = "intake_drone.json"
        data = fixtures.load(name)
        self.intakes[data["intake_id"]] = data
        return data

    def get_intake(self, intake_id: str) -> dict[str, Any]:
        if intake_id not in INTAKES:
            raise api_error(404, "intake_not_found", f"No intake {intake_id}. Mock mode has: {', '.join(INTAKES)}")
        if intake_id not in self.intakes:
            self.intakes[intake_id] = fixtures.load(f"intake_{INTAKES[intake_id]}.json")
        return self.intakes[intake_id]

    def answers(self, intake_id: str, answers: dict[str, str], build_type: str | None, skip_defaults: bool | None) -> dict[str, Any]:
        data = self.get_intake(intake_id)
        if build_type:
            data["build_type"] = build_type  # mock: the label changes, the questions do not
        for q in data["questions"]:
            if q["id"] in answers:
                q["answer"] = answers[q["id"]]
            elif skip_defaults and not q.get("answer"):
                q["answer"] = q["default"]
        data["ready"] = all(q.get("answer") for q in data["questions"])
        return data

    # ------------------------------------------------------------------ runs

    def create_run(self, intake_id: str | None, source_url: str | None) -> dict[str, Any]:
        if intake_id:
            self.get_intake(intake_id)
            key = INTAKES[intake_id]
        elif source_url and "so-arm100" in source_url.lower():
            key = "so101"
        elif source_url:
            raise api_error(501, "not_implemented", "Mock mode only knows the SO-ARM100 link", todo="TODO(A) — PLAN §3.17")
        else:
            raise api_error(422, "missing_input", "Send intake_id or source_url")
        if key == "photo":
            raise api_error(501, "not_implemented", "Mock mode has no photo run. The hotspot sample is at /api/mock/fixtures/view_photo_sample.json",
                            todo="TODO(A, D) — PLAN §3.17, §3.20 (P14, P15)")
        run_id = f"r_mock_{key}"
        self.reset_run(run_id)
        return {"run_id": run_id, "mandate": self.runs[run_id]["mandate"], "simulated": True}

    def events(self, run_id: str) -> list[dict[str, Any]]:
        return fixtures.load(f"events_{self.key(run_id)}.jsonl")

    def panel(self, run_id: str, bom_line_id: str) -> dict[str, Any]:
        key = self.key(run_id)
        ln = self.line(run_id, bom_line_id)
        if (key, bom_line_id) in PANELS:
            panel = fixtures.load(PANELS[(key, bom_line_id)])
            panel["provenance"] = ln["provenance"]
        else:
            panel = self._synth_panel(key, ln)
        panel["needs_confirmation"] = bom_line_id in self.run(run_id)["open_assumptions"]
        return panel

    def _synth_panel(self, key: str, ln: dict[str, Any]) -> dict[str, Any]:
        """A plain panel for lines with no hand-made fixture: this line's offers, chosen first."""
        chosen = {c["offer_id"]: c["packs"] for c in ln.get("chosen") or []}
        rows = []
        for o in fixtures.load(f"offers_{key}.json"):
            if o["bom_line_id"] != ln["bom_line_id"]:
                continue
            packs = chosen.get(o["offer_id"]) or -(-ln["qty"] // o["units_per_pack"])
            status = "chosen" if o["offer_id"] in chosen else "refused" if o.get("refused") else "alternative"
            rows.append({
                "offer_id": o["offer_id"], "store_id": o["store_id"], "store_name": o["store_name"], "seller_name": None,
                "title": o["title"], "url": o["url"], "price_usd": o["price_usd"], "units_per_pack": o["units_per_pack"],
                "packs_needed": packs, "line_usd": round(packs * o["price_usd"], 2), "shipping_usd": None, "eta_text": None,
                "stock": o["stock"], "rating": o.get("rating"), "reviews": o.get("reviews"), "action_level": o["action_level"],
                "source_api": "mock", "mock_of": o.get("mock_of"), "seen_at": o["seen_at"], "evidence_sha256": o["evidence_sha256"],
                "status": status, "reason": "constraints.allowed_merchants" if status == "refused" else None, "simulated": True,
            })
        rows.sort(key=lambda r: (["chosen", "alternative", "rejected", "refused"].index(r["status"]), r["line_usd"]))
        run_checks = self.runs[f"r_mock_{key}"]["checks"]
        return {
            "bom_line_id": ln["bom_line_id"], "name": ln["raw_name"], "qty": ln["qty"], "line_kind": ln["line_kind"], "status": ln["status"],
            "mesh_keys": ln["mesh_keys"], "provenance": ln["provenance"], "spec": ln.get("spec") or ln["raw_name"], "attrs": {},
            "confidence": ln.get("confidence") or 0.0, "method": "kb",
            "owned": {"memory_text": ln["owned_note"], "provider": "cognee"} if ln["status"] == "owned" and ln.get("owned_note") else None,
            "offers": rows,
            "why": {"tier": "cheapest", "reason_codes": ["cheapest_allowed"] if chosen else [], "edited_by_user": False,
                    "explanation": "Mock panel built from the fixture offers for this line."},
            "checks": [c for c in run_checks if ln["bom_line_id"] in c.get("bom_line_ids", [])],
            "refusals": [], "kb": [], "needs_confirmation": False, "record_hash": self.runs[f"r_mock_{key}"]["head_hash"],
            "source_api": "mock", "simulated": True,
        }

    def assumption(self, run_id: str, bom_line_id: str, action: str, spec: str | None, qty: int | None) -> dict[str, Any]:
        run, ln = self.run(run_id), self.line(run_id, bom_line_id)
        prov = ln["provenance"]
        if prov["type"] != "assumption":
            raise api_error(409, "not_an_assumption", f"{bom_line_id} is not an assumption")
        if action == "edit":
            ln["spec"] = spec or ln.get("spec")
            ln["qty"] = qty if qty is not None else ln["qty"]
        elif action == "remove":
            ln["status"] = "removed"
        prov["confirmed_by_user"], prov["confirmed_at"] = True, get_settings().pinned_now
        for holder in (run, self.cart(run_id)):
            holder["open_assumptions"] = [b for b in holder["open_assumptions"] if b != bom_line_id]
        return run

    def replan(self, run_id: str, tier: str, budget_cap_usd: float | None) -> dict[str, Any]:
        run = self.run(run_id)
        if budget_cap_usd is not None and budget_cap_usd > run["mandate"]["constraints"]["budget_usd"]:
            raise api_error(422, "budget_above_mandate", "Raising the budget needs a new signed mandate",
                            refusal=_refusal("budget", "constraints.budget_usd", "user_edit", field="budget_cap_usd"))
        if tier not in run["plans"]:
            raise api_error(422, "unknown_tier", f"Mock mode has tiers: {', '.join(run['plans'])}")
        run["active_tier"] = tier
        return {"plan": run["plans"][tier], "simulated": True}

    # ------------------------------------------------------------------ cart

    def cart_edit(self, run_id: str) -> dict[str, Any]:
        cart = self.cart(run_id)
        if not cart["editable"]:
            raise api_error(409, "cart_locked", "An approved cart is locked. Edit cart returns it to draft.")
        return cart  # mock: edits are accepted and ignored

    def approve(self, run_id: str, plan_id: str) -> dict[str, Any]:
        key, run, cart = self.key(run_id), self.run(run_id), self.cart(run_id)
        if run["open_assumptions"]:
            lines = list(run["open_assumptions"])
            raise api_error(409, "assumption_unconfirmed", f"Confirm {len(lines)} assumption{'s' if len(lines) != 1 else ''} first",
                            bom_line_ids=lines,
                            refusal=_refusal("assumption_unconfirmed", "PLAN §3.18: Approve is refused while an assumption is open", "agent", tool="approve"))
        if plan_id != cart["plan_id"]:
            raise api_error(409, "stale_plan", "The cart changed since you last saw it. Review it again.")
        if cart["state"] == "draft":
            self.carts[run_id] = cart = fixtures.load(f"cart_{key}_approved.json")
            run["status"] = "approved"
        return {"closed_mandate": fixtures.load(f"closed_mandate_{key}.json"), "cart": cart, "simulated": True}

    def handoff(self, run_id: str, store_id: str, state: str, done_via: str | None, order_id: str | None) -> dict[str, Any]:
        cart = self.cart(run_id)
        if cart["state"] == "draft":
            raise api_error(409, "approval_required", "Approve the cart before opening a store")
        group = next((g for g in cart["stores"] if g["store_id"] == store_id), None)
        if group is None:
            raise api_error(404, "store_not_in_cart", f"{store_id} is not in this cart")
        group["handoff"].update(state=state, done_via=done_via if state == "done" else None, order_id=order_id)
        done = [g for g in cart["stores"] if g["handoff"]["state"] == "done"]
        finished = [g for g in cart["stores"] if g["handoff"]["state"] in ("done", "skipped")]
        pending = [g for g in cart["stores"] if g["handoff"]["state"] not in ("done", "skipped")]
        cart["counts"]["done"] = len(done)
        cart["bought_usd"] = round(sum(g["subtotal_usd"] for g in done), 2)
        cart["remaining_usd"] = round(cart["total_usd"] - cart["bought_usd"], 2)
        cart["current_store_id"] = pending[0]["store_id"] if pending else None
        opened = any(g["handoff"]["state"] != "ready" for g in cart["stores"])
        cart["state"] = "complete" if len(finished) == len(cart["stores"]) else "checking_out" if opened else "approved"
        return cart

    def reopen(self, run_id: str) -> dict[str, Any]:
        """The "Edit cart" button: back to the draft fixture. A complete run stays complete."""
        cart = self.cart(run_id)
        if cart["state"] == "complete":
            raise api_error(409, "run_complete", "This checkout run is complete. Start a new run to change the cart.")
        if cart["state"] != "draft":
            self.carts[run_id] = cart = fixtures.load(f"cart_{self.key(run_id)}.json")
            cart["open_assumptions"] = list(self.run(run_id)["open_assumptions"])
            self.run(run_id)["status"] = "waiting_approval"
        return cart

    def item_added(self, run_id: str, offer_id: str, added: bool) -> dict[str, Any]:
        cart = self.cart(run_id)
        item = next((i for g in cart["stores"] for i in g["items"] if i["offer_id"] == offer_id), None)
        if item is None:
            raise api_error(404, "item_not_found", f"No cart item {offer_id}")
        item["added"] = bool(added)
        return cart

    def export_csv(self, run_id: str) -> str:
        cart = self.cart(run_id)
        names = {ln["bom_line_id"]: ln["raw_name"] for ln in self.run(run_id)["bom"]}
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["line", "part", "store", "action level", "qty", "unit price", "line total", "seen at", "source", "URL"])
        for g in cart["stores"]:
            for it in g["items"]:
                w.writerow([it["bom_line_id"], names.get(it["bom_line_id"], ""), g["display_name"], g["action_level"], it["qty"],
                            f"{it['unit_price_usd']:.2f}", f"{it['line_usd']:.2f}", it["seen_at"], "mock (simulated)", it["url"]])
        return out.getvalue()

    def receipt(self, run_id: str) -> dict[str, Any]:
        return fixtures.load(f"receipt_{self.key(run_id)}.json")

    def verify(self, run_id: str) -> dict[str, Any]:
        return fixtures.load(f"verify_{self.key(run_id)}.json")
