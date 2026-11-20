"""Verify a run's audit trail from the command line (PLAN §3.7). Owner: D.

    cd backend && uv run python scripts/verify_chain.py --receipt path/to/receipt.json   # a downloaded receipt
    uv run python scripts/verify_chain.py r_ab12cd34                                      # runs/<run_id>/ or SingleStore
    uv run python scripts/verify_chain.py --fixture so101                                 # the mock sample chain

Prints ok / broken_at, then every check (signatures and bindings). Exit code 0 when the chain recomputes and every
signature and binding checks out, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.audit import chain, mandate, verify  # noqa: E402


def _run_receipt(run_id: str) -> dict[str, Any]:
    recs, where = chain.load_records(run_id)
    if not recs:
        raise SystemExit(f"no chain found for {run_id} (looked in SingleStore when live, memory, runs/{run_id}/chain.jsonl)")
    mandates = {}
    mfile = chain.runs_dir() / run_id / "mandates.jsonl"
    if mfile.is_file():
        for line in mfile.read_text(encoding="utf-8").splitlines():
            if line.strip():
                m = json.loads(line)
                mandates[m["type"].rsplit(".", 1)[-1]] = m
    if not mandates:
        try:
            from app import registry

            if registry.impl_mode("singlestore") == "live":
                for row in registry.get("singlestore").mandates_sync(run_id):
                    mandates[row["type"].rsplit(".", 1)[-1]] = row["body"]
        except Exception:
            pass
    print(f"read {len(recs)} records from {where}")
    return {"open_mandate": mandates.get("open"), "closed_mandate": mandates.get("closed"),
            "payment_mandate": mandates.get("payment"), "records": recs, "head_hash": recs[-1]["hash"],
            "public_key_jwk": mandate.public_jwk()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recompute a hash chain and check every mandate signature.")
    ap.add_argument("run_id", nargs="?")
    ap.add_argument("--receipt", help="a receipt JSON file (GET /api/runs/{id}/receipt)")
    ap.add_argument("--fixture", choices=["so101", "drone"], help="the mock sample receipt in backend/fixtures")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = ap.parse_args(argv)
    if args.receipt:
        receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    elif args.fixture:
        receipt = json.loads((BACKEND / "fixtures" / f"receipt_{args.fixture}.json").read_text(encoding="utf-8"))
    elif args.run_id:
        receipt = _run_receipt(chain.check_run_id(args.run_id))
    else:
        ap.error("give a run_id, --receipt FILE or --fixture so101|drone")
    detail = verify.verify_receipt({k: v for k, v in receipt.items() if v is not None})
    if args.json:
        print(json.dumps(detail, indent=2))
    else:
        print(("ok" if detail["ok"] else f"BROKEN at seq {detail['broken_at']}") + f": {detail['records']} records, "
              f"head {detail['head_hash'][:23]}…")
        for c in detail["checks"]:
            print(f"  {'ok  ' if c['ok'] else 'FAIL'} {c['name']}: {c['detail']}")
        print("signatures and bindings: " + ("ok" if detail["signatures_ok"] else "NOT ok"))
        if detail.get("simulated"):
            print("note: this receipt is mock data (simulated: true)")
    return 0 if detail["ok"] and detail["signatures_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
