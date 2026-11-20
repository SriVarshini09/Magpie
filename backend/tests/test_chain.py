"""Audit trail: chain, mandates, evidence, verify (PLAN §3.7, §12.4). Owner: D. No network, temp folders only."""

from __future__ import annotations

import json

import pytest

from app import models as M
from app.audit import chain, evidence, mandate, verify
from app.audit.chain import GENESIS, canonical_json, record_hash, recompute, sha256_hex


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Temp key, temp folders, empty stores. Nothing is written under backend/."""
    monkeypatch.setattr(mandate, "key_path", lambda: tmp_path / "demo_es256.pem")
    mandate._cache.clear()
    mandate.use_key(None)
    mandate.reset()
    chain.STORE.reset()
    chain.configure(persist=False)
    evidence.configure(tmp_path / "evidence")
    yield
    mandate.use_key(None)
    mandate.reset()
    chain.STORE.reset()
    chain.configure()
    evidence.configure(None)


SCOPE = {"build_type": "quadcopter", "build_type_set_by": "classifier", "goal": "a small camera drone", "intake_sha256": "ab" * 32,
         "inputs": {"source_url": None, "text_sha256": "cd" * 32, "image_sha256": []}, "template_id": "tpl_quadcopter",
         "reference_search": True}
CONS = {"budget_usd": 200, "deadline": "2026-12-04", "ship_to_country": "US", "allowed_merchants": ["adafruit", "amazon"],
        "data_sharing": {"country": True}, "actions": {"search": True, "create_cart": True, "build_cart_link": True,
                                                        "checkout": True, "pay": True, "message_seller": False}}


def handoff(store: str, url: str, level: str = "product_link") -> dict:
    return {"store_id": store, "action_level": level, "cart_id": None, "url": url, "url_sha256": sha256_hex(url),
            "subtotal_usd": 10.0, "items": [{"offer_id": "o1", "title": "x", "qty": 1, "unit_price_usd": 10.0,
                                             "seen_at": "2026-11-20T13:00:00-08:00", "source_api": "adafruit", "evidence_sha256": "ef" * 32}]}


def full_run(run_id: str = "r_test1") -> dict:
    om = mandate.build_open_mandate(run_id, SCOPE, CONS, created_at="2026-11-20T13:00:05-08:00")
    chain.append(run_id, "intake", {"intake_id": "in_1", "build_type": "quadcopter"})
    chain.append(run_id, "mandate_open", {"mandate_id": om["mandate_id"], "mandate_sha256": mandate.mandate_sha256(om)})
    chain.append(run_id, "refusal", {"refusal": {"rule": "merchant_allowed", "clause": "constraints.allowed_merchants"}})
    approval = chain.append(run_id, "approval", {"plan_id": "p_1", "approved_by": "ui_button"})
    cm = mandate.build_closed_mandate(om, plan_id="p_1", plan_sha256="11" * 32, tier="cheapest",
                                      handoffs=[handoff("adafruit", "https://www.adafruit.com/product/1578")], total_usd=10.0,
                                      prices_checked_at="2026-11-20T13:06:00-08:00", approval_token="tok-secret",
                                      chain_head=approval["hash"])
    chain.append(run_id, "mandate_closed", {"mandate_sha256": mandate.mandate_sha256(cm), "total_usd": 10.0})
    pm = mandate.build_payment_mandate(cm, consent_text="You authorise up to $10.00. TEST MODE: no real money moves.",
                                       allocations=[{"store_id": "adafruit", "action_level": "product_link",
                                                     "url_sha256": cm["handoffs"][0]["url_sha256"], "limit": 1000}])
    chain.append(run_id, "payment_mandate", {"mandate_sha256": mandate.mandate_sha256(pm)})
    return {"open": om, "closed": cm, "payment": pm}


# --------------------------------------------------------------------------- chain


def test_format_is_unchanged():
    rec = {"run_id": "r_x", "seq": 1, "ts": "t", "kind": "intake", "prev_hash": GENESIS}
    assert record_hash(rec, GENESIS) == "sha256:" + sha256_hex(GENESIS + canonical_json(rec))
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'


def test_append_links_records_and_recomputes():
    recs = [chain.append("r_a", "intake", {"n": i}) for i in range(5)]
    assert [r["seq"] for r in recs] == [1, 2, 3, 4, 5]
    assert recs[0]["prev_hash"] == GENESIS and all(recs[i]["prev_hash"] == recs[i - 1]["hash"] for i in range(1, 5))
    ok, broken, head = recompute(chain.records("r_a"))
    assert ok and broken is None and head == recs[-1]["hash"] == chain.head("r_a")


def test_reserved_keys_cannot_be_forged_and_ts_is_kept():
    rec = chain.append("r_a", "intake", {"seq": 99, "prev_hash": "sha256:evil", "hash": "x", "run_id": "r_other",
                                         "ts": "2026-11-20T13:00:00-08:00"})
    assert rec["seq"] == 1 and rec["prev_hash"] == GENESIS and rec["run_id"] == "r_a"
    assert rec["ts"] == "2026-11-20T13:00:00-08:00" and rec["hash"] == record_hash(rec, GENESIS)


def test_append_only_caller_copy_cannot_change_the_chain():
    rec = chain.append("r_a", "intake", {"answers": {"size": "3in"}})
    rec["answers"]["size"] = "5in"
    assert chain.records("r_a")[0]["answers"]["size"] == "3in"
    got = chain.records("r_a")
    got.clear()
    assert len(chain.records("r_a")) == 1


def test_unknown_kind_and_bad_run_id_are_refused():
    with pytest.raises(ValueError):
        chain.append("r_a", "not_a_kind", {})
    with pytest.raises(ValueError):
        chain.append("../etc", "intake", {})


def test_pydantic_bodies_are_stored_as_json():
    chk = M.Check(rule_id="G3 CELL_COUNT", result="fail", message="4S ≠ 6S")
    rec = chain.append("r_a", "compat_fix", {"check": chk, "box": (1, 2, 3, 4)})
    assert rec["check"]["rule_id"] == "G3 CELL_COUNT" and rec["box"] == [1, 2, 3, 4]
    assert recompute(chain.records("r_a"))[0]


def test_flipping_one_byte_breaks_the_chain_at_that_record():
    for i in range(4):
        chain.append("r_a", "intake", {"note": f"record {i}"})
    recs = chain.records("r_a")
    text = canonical_json(recs[2])
    flipped = json.loads(text.replace("record 2", "record 3", 1))
    ok, broken, _ = recompute(recs[:2] + [flipped] + recs[3:])
    assert not ok and broken == 3


def test_load_refuses_a_broken_chain_and_an_existing_run(tmp_path):
    recs = [chain.append("r_a", "intake", {"n": i}) for i in range(3)]
    chain.STORE.reset("r_a")
    bad = json.loads(json.dumps(recs))
    bad[1]["n"] = 42
    with pytest.raises(ValueError):
        chain.STORE.load("r_a", bad)
    chain.STORE.load("r_a", recs)
    with pytest.raises(ValueError):
        chain.STORE.load("r_a", recs)


def test_disk_persistence_round_trips(tmp_path):
    chain.configure(persist=True, runs_dir=tmp_path / "runs")
    recs = [chain.append("r_disk", "intake", {"n": i}) for i in range(3)]
    chain.STORE.reset("r_disk")
    got, where = chain.load_records("r_disk")
    assert where == "disk" and got == recs and recompute(got)[0]


# --------------------------------------------------------------------------- mandates


def test_demo_key_is_created_once_and_reused(tmp_path):
    k1 = mandate.load_or_create_key()
    assert (tmp_path / "demo_es256.pem").is_file()
    mandate._cache.clear()
    k2 = mandate.load_or_create_key()
    assert k1.private_numbers() == k2.private_numbers()


def test_open_mandate_is_signed_and_verifies_and_pay_is_forced_false():
    om = mandate.build_open_mandate("r_m", SCOPE, CONS)
    M.OpenMandate.model_validate(om)
    assert om["constraints"]["actions"]["pay"] is False and om["constraints"]["actions"]["checkout"] is False
    assert om["signature"]["alg"] == "ES256" and om["signature"]["kid"] == "demo-key-1"
    header, empty, sig = om["signature"]["jws"].split(".")
    assert empty == "" and sig  # detached payload (RFC 7797)
    assert mandate.verify_mandate(om)


def test_tampering_with_any_signed_field_fails_verification():
    om = mandate.build_open_mandate("r_m", SCOPE, CONS)
    for path in (("constraints", "budget_usd"), ("scope", "goal")):
        t = json.loads(json.dumps(om))
        t[path[0]][path[1]] = 999 if path[1] == "budget_usd" else "something else"
        assert not mandate.verify_mandate(t)
    t = json.loads(json.dumps(om))
    t["constraints"]["allowed_merchants"].append("alibaba")
    assert not mandate.verify_mandate(t)


def test_wrong_key_and_placeholder_signatures_fail():
    om = mandate.build_open_mandate("r_m", SCOPE, CONS)
    assert not mandate.verify_mandate(om, public_key=mandate.fixture_key().public_key())
    mock = {**om, "signature": {"alg": "ES256", "kid": "demo-key-1", "jws": "MOCK.fixture-signature.not-verifiable"}}
    ok, why = mandate.verify_detail(mock)
    assert not ok and "placeholder" in why
    assert not mandate.verify_mandate({**om, "signature": {"alg": "none", "kid": "unsigned", "jws": ""}})


def test_pyjwt_accepts_the_jws_with_the_public_jwk():
    om = mandate.build_open_mandate("r_m", SCOPE, CONS)
    jwk = mandate.public_jwk()
    assert jwk["kty"] == "EC" and jwk["crv"] == "P-256" and "d" not in jwk
    assert mandate.verify_mandate(om, jwk=jwk)


def test_signatures_are_deterministic_for_the_same_body():
    mandate.use_key(mandate.fixture_key(), mandate.FIXTURE_KID)
    body = {"type": "b2c.mandate.open", "run_id": "r_m", "x": 1}
    assert mandate.sign_mandate(body, record=False)["signature"] == mandate.sign_mandate(body, record=False)["signature"]


def test_mandate_hash_ignores_the_signature():
    om = mandate.build_open_mandate("r_m", SCOPE, CONS)
    assert mandate.mandate_sha256(om) == mandate.mandate_sha256({k: v for k, v in om.items() if k != "signature"})


def test_closed_mandate_binds_open_mandate_plan_handoffs_and_token():
    m = full_run()
    cm = m["closed"]
    M.ClosedMandate.model_validate(cm)
    assert cm["open_mandate_sha256"] == mandate.mandate_sha256(m["open"])
    assert cm["approval_token_sha256"] == sha256_hex("tok-secret") and "tok-secret" not in json.dumps(cm)
    assert mandate.verify_mandate(cm)
    with pytest.raises(ValueError):
        mandate.build_closed_mandate(m["open"], plan_id="p", plan_sha256="0", tier="cheapest",
                                     handoffs=[{**handoff("a", "https://x.invalid/a"), "url_sha256": "00"}], total_usd=1,
                                     prices_checked_at="t", approval_token="t", chain_head=GENESIS)


def test_payment_mandate_is_test_mode_and_execution_updates_keep_the_signature():
    pm = full_run()["payment"]
    M.PaymentMandate.model_validate(pm)
    assert pm["mode"] == "test" and pm["simulated"] is True and pm["total"]["amount"] == 1000
    assert pm["mandate_hash"] == mandate.payment_mandate_hash(pm) and mandate.verify_mandate(pm)
    pm2 = json.loads(json.dumps(pm))
    pm2["status"] = "closed"
    pm2["allocations"][0].update(status="authorized", authorization_id="iauth_test", instrument={"id": "ic_test", "last4": "4242"})
    pm2["payment"] = {"payment_intent": "pi_test", "authorized": 1000, "captured": 1000, "released": 0}
    assert mandate.verify_mandate(pm2)
    pm2["allocations"][0]["limit"] = 99999
    assert not mandate.verify_mandate(pm2)
    with pytest.raises(ValueError):
        mandate.build_payment_mandate(full_run("r_test2")["closed"], consent_text="no label", allocations=[])


# --------------------------------------------------------------------------- evidence


def test_evidence_is_content_addressed_and_stripped(tmp_path, monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "serp-live-value-123456")
    payload = {"search_metadata": {"url": "https://serpapi.com/search.json?engine=amazon&api_key=serp-live-value-123456&q=x"},
               "api_key": "serp-live-value-123456", "headers": {"Authorization": "Bearer abcdefghijkl"},
               "note": "token sk_test_abcdefgh1234 and ghp_" + "a" * 30, "buyer": {"email": "a@b.example", "phone": "555"},
               "results": [{"title": "STS3215", "price": 13.89}]}
    path, sha = evidence.write_evidence("r_e", payload)
    assert path == f"evidence/r_e/{sha}.json"
    text = evidence.read_evidence(path).decode()
    for secret in ("serp-live-value-123456", "abcdefghijkl", "sk_test_abcdefgh1234", "ghp_aaaa", "a@b.example"):
        assert secret not in text
    assert "STS3215" in text and evidence.verify_evidence(path, sha)
    assert evidence.write_evidence("r_e", payload) == (path, sha)  # same bytes, same file
    assert evidence.list_evidence("r_e") == [path]


def test_evidence_tamper_and_path_traversal_are_detected(tmp_path):
    path, sha = evidence.write_evidence("r_e", {"a": 1})
    (tmp_path / "evidence" / "r_e" / f"{sha}.json").write_text('{"a":2}', encoding="utf-8")
    assert not evidence.verify_evidence(path)
    assert not evidence.verify_evidence("evidence/../../.env")
    with pytest.raises(ValueError):
        evidence.write_evidence("../x", {})


def test_raw_bytes_keep_their_hash():
    data = b"# README\n| STS3215 | 6 |\n"
    path, sha = evidence.write_evidence("r_e", data)
    assert sha == sha256_hex(data) and path.endswith(".bin")


# --------------------------------------------------------------------------- verify


def test_verify_run_ok_with_every_signature_and_binding():
    full_run()
    detail = verify.verify_run_detail("r_test1")
    assert detail["ok"] and detail["signatures_ok"], detail["checks"]
    names = {c["name"] for c in detail["checks"]}
    assert {"open_mandate.signature", "closed_mandate.signature", "payment_mandate.signature", "open_mandate.chain",
            "closed_mandate.chain", "closed_mandate.chain_head", "payment_mandate.closed_binding"} <= names
    res = verify.verify_run("r_test1")
    assert isinstance(res, M.VerifyResult) and res.records == 6 and res.broken_at is None


def test_receipt_shape_and_public_key():
    full_run()
    rec = verify.receipt("r_test1")
    M.Receipt.model_validate(rec.model_dump(mode="json", by_alias=True))
    assert rec.closed_mandate is not None and rec.payment_mandate is not None and len(rec.records) == 6
    assert rec.public_key_jwk["kid"] == "demo-key-1" and "d" not in rec.public_key_jwk
    with pytest.raises(LookupError):
        verify.receipt("r_nobody")


def test_verify_catches_a_tampered_record_and_a_swapped_mandate():
    full_run()
    r = verify.receipt("r_test1").model_dump(mode="json", by_alias=True)
    r["records"][2]["refusal"]["rule"] = "budget"
    d = verify.verify_receipt(r)
    assert not d["ok"] and d["broken_at"] == 3
    r = verify.receipt("r_test1").model_dump(mode="json", by_alias=True)
    r["closed_mandate"]["total_usd"] = 1.0
    d = verify.verify_receipt(r)
    assert d["ok"] and not d["signatures_ok"]


def test_closed_mandate_must_point_at_a_record_before_approval():
    m = full_run()
    r = verify.receipt("r_test1").model_dump(mode="json", by_alias=True)
    last = r["records"][-1]["hash"]
    cm = mandate.sign_mandate({**m["closed"], "chain_head": last}, record=False)
    r["closed_mandate"] = cm
    checks = {c["name"]: c for c in verify.verify_receipt(r)["checks"]}
    assert checks["closed_mandate.signature"]["ok"] and not checks["closed_mandate.chain_head"]["ok"]


def test_signed_fixture_verifies_and_a_placeholder_signature_does_not():
    """The fixtures are signed with the public FIXTURE key (scripts/sign_fixtures.py, applied at integration).
    A placeholder signature, as the scaffold fixtures carried, must still fail and say why."""
    import copy

    from app import fixtures

    receipt = fixtures.load("receipt_so101.json")
    d = verify.verify_receipt(receipt)
    assert d["ok"] and d["signatures_ok"] and d["simulated"] is True
    forged = copy.deepcopy(receipt)
    forged["open_mandate"]["signature"]["jws"] = "MOCK.fixture-signature.not-verifiable"
    d = verify.verify_receipt(forged)
    checks = {c["name"]: c for c in d["checks"]}
    assert d["ok"] and not d["signatures_ok"] and not checks["open_mandate.signature"]["ok"]
