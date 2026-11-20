"""Verify: recompute the chain and check every mandate signature and binding (PLAN §3.7, §4.2). Owner: D.

    verify_receipt(receipt) -> dict   {ok, records, head_hash, broken_at, signatures_ok, checks[], simulated}
    verify_run(run_id)      -> VerifyResult (the §4.2 shape; `checks` stays server-side until the contract has it)
    receipt(run_id)         -> Receipt

`ok` is the chain alone (every prev_hash and hash recomputes). `signatures_ok` is true only when every
mandate present has a valid ES256 signature AND is bound to the rest of the trail:
  - the `mandate_open` record's `mandate_sha256` equals the open mandate's hash,
  - the closed mandate's `open_mandate_sha256` equals the open mandate's hash,
  - the closed mandate's `chain_head` is the hash of a record that comes before its `mandate_closed` record,
  - the `mandate_closed` record's `mandate_sha256` equals the closed mandate's hash,
  - every hand-off's `url_sha256` is the hash of its `url`,
  - the payment mandate's `closed_mandate_sha256` and `mandate_hash` match.
Placeholder signatures (the scaffold fixtures) fail the signature check and say so.
"""

from __future__ import annotations

from typing import Any

from app.audit import chain as chain_mod
from app.audit import mandate as mandate_mod
from app.audit.chain import GENESIS, recompute, sha256_hex
from app.models import Receipt, VerifyResult


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _record_sha(records: list[dict[str, Any]], kind: str) -> list[tuple[int, str | None]]:
    return [(r.get("seq", 0), r.get("mandate_sha256")) for r in records if r.get("kind") == kind]


def _drop_nulls(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _drop_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_drop_nulls(v) for v in obj]
    return obj


def verify_receipt(receipt: dict[str, Any] | Receipt, *, trust_receipt_key: bool = True) -> dict[str, Any]:
    """Full verification of a receipt-shaped dict. Never raises on bad input; it reports."""
    r = receipt.model_dump(mode="json", by_alias=True, exclude_none=True) if hasattr(receipt, "model_dump") else dict(receipt)
    # A mandate is signed with its null fields left out (exclude_none). A receipt that went through the API's
    # response model (the "Download receipt.json" button) carries them back as nulls; drop them again so the
    # signature is checked against the body that was signed. A signed body never holds a null, so this hides nothing.
    for k in ("open_mandate", "closed_mandate", "payment_mandate"):
        if isinstance(r.get(k), dict):
            r[k] = _drop_nulls(r[k])
    records = list(r.get("records") or [])
    ok, broken_at, head = recompute(records)
    checks: list[dict[str, Any]] = [
        _check("chain", ok, f"{len(records)} records recompute" if ok else f"broken at seq {broken_at}")]
    if ok and r.get("head_hash") and r["head_hash"] != head:
        checks.append(_check("head_hash", False, "receipt head_hash is not the last record's hash"))
    jwk = r.get("public_key_jwk") or {}
    receipt_key = None
    if trust_receipt_key and jwk.get("kty") == "EC" and jwk.get("x") not in (None, "MOCK"):
        try:
            receipt_key = mandate_mod.key_from_jwk(jwk)
        except Exception:
            receipt_key = None

    def sig(name: str, m: dict[str, Any]) -> None:
        kid = (m.get("signature") or {}).get("kid")
        key = receipt_key if receipt_key is not None and jwk.get("kid") == kid else None
        good, why = mandate_mod.verify_detail(m, public_key=key)
        checks.append(_check(f"{name}.signature", good, why))

    hashes = {rec.get("hash"): rec.get("seq", 0) for rec in records}
    om, cm, pm = r.get("open_mandate"), r.get("closed_mandate"), r.get("payment_mandate")
    if om:
        sig("open_mandate", om)
        om_sha = mandate_mod.mandate_sha256(om)
        for seq, val in _record_sha(records, "mandate_open"):
            checks.append(_check("open_mandate.chain", val == om_sha, f"mandate_open record seq {seq}"
                                 + ("" if val == om_sha else ": hash does not match the open mandate")))
        if om.get("run_id") and records and any(rec.get("run_id") != om["run_id"] for rec in records):
            checks.append(_check("run_id", False, "a record belongs to another run"))
    if cm:
        sig("closed_mandate", cm)
        cm_sha = mandate_mod.mandate_sha256(cm)
        if om:
            same = cm.get("open_mandate_sha256") == mandate_mod.mandate_sha256(om)
            checks.append(_check("closed_mandate.open_binding", same, "open_mandate_sha256 matches" if same
                                 else "open_mandate_sha256 does not match the open mandate"))
        closed_recs = _record_sha(records, "mandate_closed")
        # "Edit cart" re-opens an approved cart and the next approval signs a new closed mandate: the receipt's
        # closed mandate must match the LATEST `mandate_closed` record; earlier ones stay in the chain, superseded.
        for seq, val in closed_recs[-1:]:
            checks.append(_check("closed_mandate.chain", val == cm_sha, f"mandate_closed record seq {seq}"
                                 + ("" if val == cm_sha else ": hash does not match the closed mandate")))
        head_seq = hashes.get(cm.get("chain_head"))
        first_closed = max((s for s, _ in closed_recs), default=None)  # the record of THIS closed mandate
        in_chain = head_seq is not None and (first_closed is None or head_seq < first_closed)
        if cm.get("chain_head") == GENESIS:
            in_chain = False
        checks.append(_check("closed_mandate.chain_head", in_chain,
                             f"chain_head is record seq {head_seq}" if in_chain else "chain_head is not a record before approval"))
        bad = [h.get("store_id") for h in cm.get("handoffs", []) if h.get("url") and h.get("url_sha256") != sha256_hex(h["url"])]
        checks.append(_check("closed_mandate.handoff_urls", not bad, "every hand-off URL matches its hash" if not bad
                             else f"url_sha256 mismatch: {', '.join(map(str, bad))}"))
    if pm:
        sig("payment_mandate", pm)
        if cm:
            same = pm.get("closed_mandate_sha256") == mandate_mod.mandate_sha256(cm)
            checks.append(_check("payment_mandate.closed_binding", same, "closed_mandate_sha256 matches" if same
                                 else "closed_mandate_sha256 does not match the closed mandate"))
        mh_ok = pm.get("mandate_hash") == mandate_mod.payment_mandate_hash(pm)
        checks.append(_check("payment_mandate.mandate_hash", mh_ok, "mandate_hash matches" if mh_ok else "mandate_hash mismatch"))
    mandate_checks = [c for c in checks if c["name"].split(".")[0] in ("open_mandate", "closed_mandate", "payment_mandate", "run_id")]
    signatures_ok = bool(mandate_checks) and all(c["ok"] for c in mandate_checks)
    return {"ok": ok and all(c["ok"] for c in checks if c["name"] == "head_hash"), "records": len(records),
            "head_hash": head if ok else (records[-1].get("hash", GENESIS) if records else GENESIS),
            "broken_at": broken_at, "signatures_ok": signatures_ok, "checks": checks,
            "simulated": bool(r.get("simulated"))}


def _result(detail: dict[str, Any]) -> VerifyResult:
    return VerifyResult(ok=detail["ok"], records=detail["records"], head_hash=detail["head_hash"],
                        broken_at=detail["broken_at"], signatures_ok=detail["signatures_ok"], checks=detail.get("checks") or [],
                        simulated=detail["simulated"])


def receipt(run_id: str, *, open_mandate: dict[str, Any] | None = None, closed_mandate: dict[str, Any] | None = None,
            payment_mandate: dict[str, Any] | None = None, records: list[dict[str, Any]] | None = None,
            simulated: bool | None = None) -> Receipt:
    """The run's receipt: mandates, every chain record, head hash, the public key (PLAN §4.2).

    Mandates and records default to what this module saw signed and appended; A may pass its own.
    Raises LookupError when there is no open mandate for the run.
    """
    chain_mod.check_run_id(run_id)
    known = mandate_mod.mandates_for(run_id)
    om = open_mandate or known.get("open")
    if om is None:
        raise LookupError(f"no open mandate for run {run_id}")
    recs = records if records is not None else chain_mod.load_records(run_id)[0]
    ok, _, head = recompute(recs)
    kid = (om.get("signature") or {}).get("kid") if isinstance(om, dict) else None
    key = mandate_mod.fixture_key() if kid == mandate_mod.FIXTURE_KID else None
    jwk = mandate_mod.public_jwk(key, kid) if key is not None else mandate_mod.public_jwk()
    sim = simulated if simulated is not None else bool(om.get("simulated") if isinstance(om, dict) else False)
    return Receipt(open_mandate=om, closed_mandate=closed_mandate or known.get("closed"),
                   payment_mandate=payment_mandate or known.get("payment"), records=recs,
                   head_hash=head if ok else (recs[-1]["hash"] if recs else GENESIS), public_key_jwk=jwk,
                   source_api="mock" if sim else None, simulated=sim)


def verify_run_detail(run_id: str, **overrides: Any) -> dict[str, Any]:
    rec = receipt(run_id, **overrides)
    detail = verify_receipt(rec)
    detail["read_from"] = chain_mod.load_records(run_id)[1] if "records" not in overrides else "caller"
    return detail


def verify_run(run_id: str, **overrides: Any) -> VerifyResult:
    """{ok, records, head_hash, broken_at, signatures_ok} for a run (PLAN §4.2)."""
    return _result(verify_run_detail(run_id, **overrides))


def verify_receipt_result(receipt_obj: dict[str, Any] | Receipt) -> VerifyResult:
    return _result(verify_receipt(receipt_obj))
