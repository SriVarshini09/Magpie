"""Record the hero runs (hero_drone, hero_arm) into cache/ during the event (PLAN §3.11, gate G4). Owner: B.

Two ways to record, both with the backend in DEMO_MODE=record:

1. Through the running backend (the full run: intake, template, references, offers, carts):
       DEMO_MODE=record on the server, then
       uv run python scripts/record_hero.py api --base http://localhost:8000 --hero arm
   drives POST /api/intake -> answers (defaults) -> POST /api/runs and waits for run.waiting_approval.
   The server's cache.py writes every external call to cache/ and logs the keys in cache/_recording.jsonl.

2. Store calls only, in this process (no server needed; useful before A's loop is finished):
       DEMO_MODE=record uv run python scripts/record_hero.py stores --hero arm [--bom bom.json] [--dry-run]
   runs every store adapter's search for each BOM line of the hero and writes cache/hero_<name>.manifest.json.

Then check that replay has everything, with the network unplugged:
       DEMO_MODE=replay uv run python scripts/record_hero.py check --hero arm

`cart-links` prints the prefilled cart links a human opens once in a real browser at 1:15 (PLAN §2.1)
before setting cart_link_verified in data/stores.json. This script never opens or requests them.

SerpAPI: each line costs one search per engine (google_shopping + amazon by default). The guard refuses past
45 uncached searches in an hour; `stores --dry-run` prints the estimate first.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

HEROES: dict[str, dict[str, Any]] = {
    "arm": {"fixture": "run_so101.json", "run_id": "hero_arm", "text": "https://github.com/TheRobotStudio/SO-ARM100",
            "allowed": ["wowrobo", "armdojo", "geekworm", "amazon", "seeed", "adafruit", "sparkfun"]},
    "drone": {"fixture": "run_drone.json", "run_id": "hero_drone", "text": "a small camera drone under $200",
              "allowed": ["wowrobo", "openelab", "robotshop", "rokland", "amazon", "adafruit"]},
}


def _bom(hero: str, path: str | None) -> list[dict[str, Any]]:
    """BOM lines to search: a JSON file of [{bom_line_id, query, qty}] or the hero fixture's lines to buy."""
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    from app import fixtures

    run = fixtures.load(HEROES[hero]["fixture"])
    out = []
    for ln in run["bom"]:
        if ln["status"] in ("owned", "removed", "skipped") or ln.get("category") == "printed" or ln["line_kind"] == "tool":
            continue
        out.append({"bom_line_id": ln["bom_line_id"], "query": ln.get("spec") or ln["raw_name"], "qty": ln["qty"]})
    return out


async def record_stores(hero: str, bom_path: str | None, dry_run: bool) -> int:
    from app import cache, registry
    from app.config import get_settings
    from app.models import PartQuery
    from app.stores import registry as store_registry
    from app.stores import serpapi
    from app.stores.base import RunCtx

    mode = get_settings().demo_mode
    lines = _bom(hero, bom_path)
    engines = serpapi.LiveSerpApi().engines
    print(f"hero={hero} mode={mode} lines={len(lines)} serpapi engines={','.join(engines)} "
          f"-> at most {len(lines) * len(engines)} SerpAPI searches (uncached only); quota now: {serpapi.usage()}")
    if dry_run:
        for ln in lines:
            print(f"  {ln['bom_line_id']}: {ln['query']}")
        return 0
    if mode != "record":
        print("Set DEMO_MODE=record (or replay to check). Refusing to run in", mode)
        return 2
    spec = HEROES[hero]
    ctx = RunCtx(run_id=spec["run_id"], allowed_merchants=tuple(spec["allowed"]), demo_mode=mode)
    manifest: dict[str, Any] = {"hero": hero, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "lines": []}
    start = len(cache.recorded_keys())
    for ln in lines:
        q = PartQuery(bom_line_id=ln["bom_line_id"], query=ln["query"], qty=int(ln.get("qty") or 1))
        row: dict[str, Any] = {"bom_line_id": q.bom_line_id, "query": q.query, "adapters": {}}
        for name, adapter in store_registry.adapters().items():
            if registry.impl_mode(name) == "mock":
                row["adapters"][name] = "mock (not recorded)"
                continue
            try:
                offers = await adapter.search(q, ctx)
                row["adapters"][name] = f"{len(offers)} offers"
            except Exception as exc:  # noqa: BLE001 - record what we can; the report says what failed
                row["adapters"][name] = f"{type(exc).__name__}: {str(exc)[:120]}"
        manifest["lines"].append(row)
        print(f"  {q.bom_line_id}: {row['adapters']}")
    manifest["keys"] = [r["key"] for r in cache.recorded_keys()[start:]]
    out = cache.CACHE_DIR / f"hero_{hero}.manifest.json"
    out.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"wrote {out} ({len(manifest['keys'])} cache keys); SerpAPI quota now {serpapi.usage()}")
    return 0


def check(hero: str) -> int:
    from app import cache

    path = cache.CACHE_DIR / f"hero_{hero}.manifest.json"
    keys = json.loads(path.read_text(encoding="utf-8"))["keys"] if path.is_file() else [r["key"] for r in cache.recorded_keys()]
    missing = [k for k in keys if cache.read(k) is None]
    print(f"{len(keys) - len(missing)}/{len(keys)} recorded entries present for {hero}" + (f"; missing: {missing[:5]}" if missing else ""))
    return 1 if missing or not keys else 0


def drive_api(base: str, hero: str, timeout_s: int) -> int:
    """Drive one full run through the backend's own API (the server must be in DEMO_MODE=record)."""
    import httpx

    spec = HEROES[hero]
    with httpx.Client(base_url=base, timeout=60) as c:
        health = c.get("/api/health").json()
        if health.get("mode") != "record":
            print(f"The backend at {base} is in {health.get('mode')!r} mode; start it with DEMO_MODE=record")
            return 2
        intake = c.post("/api/intake", data={"text": spec["text"]}).raise_for_status().json()
        intake = c.post(f"/api/intake/{intake['intake_id']}/answers", json={"answers": {}, "skip_defaults": True}).raise_for_status().json()
        preset = intake["mandate_preset"]
        run = c.post("/api/runs", json={"intake_id": intake["intake_id"], "mandate": preset}).raise_for_status().json()
        run_id = run["run_id"]
        print("run", run_id)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            state = c.get(f"/api/runs/{run_id}").json()
            if state.get("status") in ("waiting_approval", "error", "done"):
                print("status", state.get("status"))
                return 0 if state.get("status") == "waiting_approval" else 1
            time.sleep(2)
    print("timed out waiting for the run")
    return 1


def cart_links() -> int:
    from app.stores import registry as store_registry
    from app.stores.cartlinks import candidate_links

    print("Open each link once in a real browser (signed out is fine). Do not buy. Then set cart_link_verified")
    print("in backend/data/stores.json, or CART_LINKS_VERIFIED=<store,...> in .env. The backend never requests these.\n")
    for store_id, url in candidate_links().items():
        print(f"{store_id:8s} verified={store_registry.cart_link_verified(store_id)!s:5s} {url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stores")
    s.add_argument("--hero", choices=sorted(HEROES), required=True)
    s.add_argument("--bom")
    s.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("api")
    a.add_argument("--hero", choices=sorted(HEROES), required=True)
    a.add_argument("--base", default="http://localhost:8000")
    a.add_argument("--timeout", type=int, default=300)
    c = sub.add_parser("check")
    c.add_argument("--hero", choices=sorted(HEROES), required=True)
    sub.add_parser("cart-links")
    args = p.parse_args(argv)
    if args.cmd == "stores":
        return asyncio.run(record_stores(args.hero, args.bom, args.dry_run))
    if args.cmd == "api":
        return drive_api(args.base, args.hero, args.timeout)
    if args.cmd == "check":
        return check(args.hero)
    return cart_links()


if __name__ == "__main__":
    raise SystemExit(main())
