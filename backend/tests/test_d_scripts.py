"""D's scripts and the rule packs' fit to A's interface. Owner: D. Temp folders only, no network."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def script(name: str):
    spec = importlib.util.spec_from_file_location(f"d_script_{name}", BACKEND / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def signed(tmp_path_factory):
    out = tmp_path_factory.mktemp("signed")
    report = script("sign_fixtures").main(["--out", str(out)])
    return out, report


def test_signed_fixtures_verify_green_and_leave_shared_files_alone(signed):
    out, report = signed
    for key in ("so101", "drone"):
        r = report["files"][key]
        assert r["ok"] and r["signatures_ok"], r
        verify = json.loads((out / f"verify_{key}.json").read_text(encoding="utf-8"))
        assert verify["signatures_ok"] is True and verify["simulated"] is True
    assert report["payment_mandate_ok"] is True
    assert not (out / "data").exists() and not (BACKEND / "fixtures" / "data").exists()
    # applied at integration: the shared fixtures ARE the signed output (re-run the script and copy if this drifts)
    for name in ("receipt_so101.json", "receipt_drone.json", "verify_so101.json", "verify_drone.json", "closed_mandate_so101.json",
                 "pay_intent_so101.json", "run_drone.json"):
        assert (BACKEND / "fixtures" / name).read_text(encoding="utf-8") == (out / name).read_text(encoding="utf-8"), name
    assert "MOCK.fixture-signature" not in (BACKEND / "fixtures" / "receipt_so101.json").read_text(encoding="utf-8")


def test_signed_fixtures_still_match_the_contract_and_are_deterministic(signed, tmp_path):
    from app import models as M

    out, _ = signed
    receipt = json.loads((out / "receipt_so101.json").read_text(encoding="utf-8"))
    M.Receipt.model_validate(receipt)
    assert receipt["public_key_jwk"]["kid"] == "fixture-key-1" and receipt["open_mandate"]["signature"]["kid"] == "fixture-key-1"
    M.RunState.model_validate(json.loads((out / "run_so101.json").read_text(encoding="utf-8")))
    again = tmp_path / "again"
    script("sign_fixtures").main(["--out", str(again)])
    assert (again / "receipt_so101.json").read_text(encoding="utf-8") == (out / "receipt_so101.json").read_text(encoding="utf-8")


def test_sign_fixtures_refuses_the_shared_folders():
    with pytest.raises(SystemExit):
        script("sign_fixtures").main(["--out", str(BACKEND / "fixtures")])


def test_verify_chain_cli(signed, tmp_path, capsys):
    out, _ = signed
    vc = script("verify_chain")
    assert vc.main(["--receipt", str(out / "receipt_so101.json")]) == 0
    assert "signatures and bindings: ok" in capsys.readouterr().out
    assert vc.main(["--fixture", "so101"]) == 0  # the shared fixtures are signed with the fixture key
    capsys.readouterr()
    placeholder = json.loads((out / "receipt_so101.json").read_text(encoding="utf-8"))
    placeholder["closed_mandate"]["signature"]["jws"] = "MOCK.fixture-signature.not-verifiable"
    (tmp_path / "placeholder.json").write_text(json.dumps(placeholder), encoding="utf-8")
    assert vc.main(["--receipt", str(tmp_path / "placeholder.json")]) == 1  # chain ok, signatures not
    capsys.readouterr()
    bad = json.loads((out / "receipt_so101.json").read_text(encoding="utf-8"))
    bad["records"][3]["ts"] = "2026-01-01T00:00:00-08:00"
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    assert vc.main(["--receipt", str(tmp_path / "bad.json")]) == 1
    assert "BROKEN at seq 4" in capsys.readouterr().out


def test_verify_chain_cli_reads_a_persisted_run(tmp_path, monkeypatch):
    from app.audit import chain, mandate

    monkeypatch.setattr(mandate, "key_path", lambda: tmp_path / "k.pem")
    mandate._cache.clear()
    chain.configure(persist=True, runs_dir=tmp_path / "runs")
    try:
        chain.STORE.reset("r_cli")
        om = mandate.build_open_mandate("r_cli", {"build_type": "generic", "build_type_set_by": "user", "goal": "g",
                                                  "intake_sha256": "0" * 64, "inputs": {}, "template_id": "tpl_generic"},
                                        {"budget_usd": 50, "deadline": "2026-12-04", "allowed_merchants": ["adafruit"],
                                         "data_sharing": {}})
        chain.append("r_cli", "mandate_open", {"mandate_sha256": mandate.mandate_sha256(om)})
        chain.STORE.reset("r_cli")
        assert script("verify_chain").main(["r_cli"]) == 0
    finally:
        chain.configure()
        chain.STORE.reset("r_cli")
        mandate.reset()
        mandate._cache.clear()


def test_seed_kb_check_and_sqlite(tmp_path, capsys):
    sk = script("seed_kb")
    res = sk.main(["--check"])
    assert res["written"] is False and res["chunks"] > 50
    res = sk.main(["--sqlite", str(tmp_path / "s.sqlite"), "--no-embed"])
    assert res["written"] and res["tables"]["kb_chunks"] == res["chunks"] and res["embedded"] == 0
    assert "full-text only" in capsys.readouterr().out


def test_seed_memory_dry_run_and_with_a_fake():
    sm = script("seed_memory")
    facts = sm.main(["--dry-run", "--preset", "electronics_mcu"])
    assert facts[:5] == list(__import__("app.integrations.cognee_mem", fromlist=["x"]).SEED_MEMORIES)

    class Fake:
        provider = "fake"

        def __init__(self):
            self.got = []

        async def remember(self, text, user_id="demo_user"):
            self.got.append((text, user_id))

    f = Fake()
    sm.main([], memory=f)
    assert len(f.got) == 5 and all(u == "demo_user" for _, u in f.got)


def test_warm_sie_without_a_key_does_nothing(monkeypatch, capsys):
    for v in ("SIE_API_KEY", "SIE_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    assert script("warm_sie").main([]) == {}
    assert "not configured" in capsys.readouterr().out


def test_rule_packs_fit_a_s_interface():
    """A's rules/base.py: check(plan), fix(check, plan), reject(line, offer, plan) -> str | None; lines carry `chosen`."""
    from app.rules import generic_electrical as ge
    from app.rules import mcu_battery as mb
    from app.rules.base import LineCtx, PlanContext, listing_attrs, load_pack

    assert load_pack("generic_electrical") is ge and load_pack("mcu_battery") is mb
    desc = "3.7V 500mAh LiPo battery, JST-PH 2.0 connector, 2-pin"
    title = "Lithium Ion Polymer Battery 3.7v 500mAh"
    plan = PlanContext(build_type="electronics_mcu", lines=[LineCtx(
        bom_line_id="b5", name="Battery", category="battery", rules=["R12", "R13", "R14"], attrs={"cells": 1, "connector": "JST-PH"},
        chosen=[{"offer_id": "o1", "store_id": "adafruit", "title": title, "description": desc, "packs": 1, "units_per_pack": 1,
                 "attrs": listing_attrs(title, desc)}])]).to_dict()
    results = {c.rule_id.split()[0]: c for c in mb.check(plan)}
    assert results["R12"].result == "pass" and results["R13"].result == "pass" and results["R14"].needs_ack
    line = plan["lines"][0]
    assert mb.reject(line, {"title": "LiPo 3.7V 400mAh", "description": "Micro JST 1.25 plug"}, plan).startswith("R12")
    assert mb.reject(line, {"title": title, "description": desc}, plan) is None
    battery = {"bom_line_id": "b7", "category": "battery", "attrs": {"cells": "4S", "connector": "XT60"}, "rules": ["G3", "G5"]}
    assert ge.reject(battery, {"title": "4S 1300mAh 100C LiPo XT30"}, {}) == "G5: XT30 ≠ XT60."
    fails = [c for c in ge.check_offer(battery, {"title": "4S 1300mAh 100C LiPo XT30"}) if c.result == "fail"]
    assert ge.fix(fails[0], plan) == {"bom_line_id": "b7", "connector": "XT60"}
    assert ge._coerce_attrs({"connector": "barrel_5.5x2.1"})["barrel"] == "5.5x2.1"  # A's connector spelling


def test_audit_route_bodies(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from app.audit import api, chain, mandate

    monkeypatch.setattr(mandate, "key_path", lambda: tmp_path / "k.pem")
    mandate._cache.clear()
    chain.configure(persist=False)
    chain.STORE.reset("r_api")
    try:
        om = mandate.build_open_mandate("r_api", {"build_type": "generic", "build_type_set_by": "user", "goal": "g",
                                                  "intake_sha256": "0" * 64, "inputs": {}, "template_id": "tpl_generic"},
                                        {"budget_usd": 50, "deadline": "2026-12-04", "allowed_merchants": [], "data_sharing": {}})
        chain.append("r_api", "mandate_open", {"mandate_sha256": mandate.mandate_sha256(om)})
        assert api.receipt_body("r_api")["open_mandate"]["mandate_id"] == om["mandate_id"]
        v = api.verify_body("r_api")
        assert v["ok"] and v["signatures_ok"] and v["records"] == 1
        with pytest.raises(HTTPException) as err:
            api.receipt_body("r_none")
        assert err.value.status_code == 404
        stats = api.data_stats_body()  # mock mode in tests
        assert stats["simulated"] is True
        assert asyncio.run(api.kb_search_body("12V"))["simulated"] is True
    finally:
        chain.configure()
        chain.STORE.reset("r_api")
        mandate.reset()
        mandate._cache.clear()


_ = sys
