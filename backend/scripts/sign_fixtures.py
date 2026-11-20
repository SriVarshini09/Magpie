"""Build the sample fixtures with REAL ES256 signatures, into a separate folder (PLAN §3.7). Owner: D.

    cd backend && uv run python scripts/sign_fixtures.py                 # -> runs/signed_fixtures/
    uv run python scripts/sign_fixtures.py --out some/folder

The scaffold's fixtures carry placeholder signatures ("MOCK.fixture-signature.not-verifiable"), so mock-mode
/verify reports signatures_ok: false. This script re-runs the coordinator's `scripts/build_fixtures.py` in-process
with three things patched, and writes everything to --out (it never writes backend/fixtures or data/):
  1. `open_mandate()` / `closed_mandate()` sign what they build (ES256, detached JWS, audit/mandate.py),
  2. `sha()` of a mandate is `mandate_sha256()` (the signed body, without the signature), so the chain records
     `mandate_sha256`, `open_mandate_sha256` and the payment mandate's hashes bind exactly what was signed,
  3. receipts carry the signing key's public JWK, `verify_*.json` is what audit/verify.py computes, and the
     sample payment mandate is signed too.
The key is the FIXTURE key (kid "fixture-key-1"), derived from a public seed: these signatures show the format and
make Verify go green in mock mode; they prove nothing about any real approval. Signatures are deterministic, so
re-running gives identical files. The coordinator applies the result by copying the files over backend/fixtures/
(see the contract change request in D's report); C's UI then shows "Signatures valid" in mock mode.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.audit import mandate as mandate_mod  # noqa: E402
from app.audit import verify as verify_mod  # noqa: E402


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("b2c_build_fixtures", BACKEND / "scripts" / "build_fixtures.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main(argv: list[str] | None = None) -> dict[str, Any]:
    ap = argparse.ArgumentParser(description="Build signed sample fixtures into a separate folder.")
    ap.add_argument("--out", default=str(BACKEND / "runs" / "signed_fixtures"))
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    if out == (BACKEND / "fixtures").resolve() or out == (BACKEND / "data").resolve():
        raise SystemExit("refusing to write into backend/fixtures or backend/data: those are shared files (coordinator)")
    out.mkdir(parents=True, exist_ok=True)

    key, kid = mandate_mod.fixture_key(), mandate_mod.FIXTURE_KID
    bf = _load_builder()
    orig_open, orig_closed, orig_sha = bf.open_mandate, bf.closed_mandate, bf.sha

    def sign(m: dict[str, Any]) -> dict[str, Any]:
        return mandate_mod.sign_mandate(m, key=key, kid=kid, record=False)

    def sha(obj: Any) -> str:
        if isinstance(obj, dict) and str(obj.get("type", "")).startswith("b2c.mandate."):
            return mandate_mod.mandate_sha256(obj)
        return orig_sha(obj)

    bf.open_mandate = lambda *a, **k: sign(orig_open(*a, **k))
    bf.closed_mandate = lambda *a, **k: sign(orig_closed(*a, **k))
    bf.sha = sha
    scratch = Path(tempfile.mkdtemp(prefix="b2c_sign_"))
    (scratch / "data").mkdir()
    bf.FIX = out
    bf.BACKEND = scratch  # build_fixtures also writes data/mock_store.json (B's file): send that copy to a temp dir
    (out / "sources").mkdir(exist_ok=True)
    shutil.copy2(BACKEND / "fixtures" / "sources" / "SO-ARM100_README.md", out / "sources" / "SO-ARM100_README.md")
    try:
        bf.main()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    jwk = mandate_mod.public_jwk(key, kid)
    report: dict[str, Any] = {"out": out.as_posix(), "kid": kid, "files": {}}
    for key_name in ("so101", "drone"):
        rp = out / f"receipt_{key_name}.json"
        receipt = json.loads(rp.read_text(encoding="utf-8"))
        receipt["public_key_jwk"] = jwk
        rp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        res = verify_mod.verify_receipt_result(receipt)
        detail = verify_mod.verify_receipt(receipt)
        (out / f"verify_{key_name}.json").write_text(json.dumps(res.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8",
                                                     newline="\n")
        report["files"][key_name] = {"ok": res.ok, "signatures_ok": res.signatures_ok, "records": res.records,
                                     "failed_checks": [c["name"] for c in detail["checks"] if not c["ok"]]}
    pp = out / "pay_intent_so101.json"
    pay = json.loads(pp.read_text(encoding="utf-8"))
    pay["payment_mandate"] = sign(pay["payment_mandate"])
    pp.write_text(json.dumps(pay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    report["payment_mandate_ok"] = mandate_mod.verify_mandate(pay["payment_mandate"], public_key=key.public_key())
    for name, r in report["files"].items():
        print(f"receipt_{name}: chain {'ok' if r['ok'] else 'BROKEN'}, signatures {'ok' if r['signatures_ok'] else 'FAIL'}, "
              f"{r['records']} records" + (f", failed: {r['failed_checks']}" if r["failed_checks"] else ""))
    print(f"payment mandate signature: {'ok' if report['payment_mandate_ok'] else 'FAIL'}")
    print(f"signed fixtures written to {out} (fixture key {kid}: format only, proves nothing)")
    return report


if __name__ == "__main__":
    main()
