"""Check the sponsor integrations: are their settings in .env, does their SDK load, and (with --ping) does one
small real call work. Never prints a key or any other secret value.

    cd backend && uv run python scripts/check_integrations.py              # settings + SDKs only, no network
    uv run python scripts/check_integrations.py --ping                     # plus one small call per service with keys
    uv run python scripts/check_integrations.py --ping sie,cognee          # only these

What --ping sends (only for services whose settings are present):
    singlestore      one knowledge-base search ("XT60 connector"); must report the SingleStore backend, not SQLite
    sie              the warm-up: one tiny encode, score, extract and detect call
    cognee           one recall ("integration check"); nothing is written
    amplitude        one event named "b2c_integration_check" in your Amplitude project, then a flush
    statsig          one gate check (strict_compat_rules)
    exa_airbyte      one Exa search through Airbyte's agent SDK
    airbyte_github   one README read (TheRobotStudio/SO-ARM100) through Airbyte's GitHub connector
    keenable         one search
Stripe and Claude are checked for settings only: no call is made (Stripe keys must be sk_test_/pk_test_).
Then start the app with the same services live:  uv run python scripts/dev_pipeline.py --live auto [--claude]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
import time
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from dev_pipeline import LIVE_SWITCHABLE, dotenv_settings  # noqa: E402

SDKS: dict[str, tuple[str, ...]] = {
    "singlestore": ("singlestoredb",),
    "sie": ("sie_sdk",),
    "cognee": ("cognee",),
    "amplitude": ("amplitude", "amplitude_ai"),
    "statsig": ("statsig_python_core",),
    "exa_airbyte": ("airbyte_agent_sdk",),
    "airbyte_github": ("airbyte_agent_sdk",),
    "keenable": (),
    "stripe": (),
    "anthropic": ("anthropic",),
}
SETTINGS_ONLY = ("stripe", "anthropic")
PING_TIMEOUT_S = 45.0


def _sdk(name: str) -> str:
    missing = [m for m in SDKS.get(name, ()) if importlib.util.find_spec(m) is None]
    return "ok" if not missing else "missing " + ", ".join(missing)


def _keys(name: str, s: dict[str, str]) -> tuple[bool, str]:
    if name == "anthropic":
        ok = bool(s.get("ANTHROPIC_API_KEY"))
        return ok, "ANTHROPIC_API_KEY" if ok else "missing ANTHROPIC_API_KEY"
    groups = LIVE_SWITCHABLE[name]
    ok = all(any(s.get(k) for k in g) for g in groups)
    have = [k for g in groups for k in g if s.get(k)]
    need = " and ".join(" or ".join(g) for g in groups)
    return ok, (", ".join(have) if ok else f"missing {need}")


def _stripe_note(s: dict[str, str]) -> str:
    key = s.get("STRIPE_SECRET_KEY") or ""
    if not key:
        return ""
    return "test key" if key.startswith("sk_test_") else "NOT a test key: the backend refuses to start (sk_test_ only)"


async def _ping(name: str) -> str:
    from app import registry

    svc = registry.get(name)
    if name == "singlestore":
        res = await svc.hybrid_search("XT60 connector")
        backend = getattr(svc, "backend_name", "?")
        n = len(getattr(res, "chunks", []) or [])
        return f"{backend}, {n} rows" if backend == "singlestore" else f"FELL BACK to {backend} (check S2_URL and the network)"
    if name == "sie":
        out = await svc.warm()
        bad = {k: v.get("error") for k, v in out.items() if not v.get("ok")}
        good = ", ".join(f"{k} {v['ms']} ms" for k, v in out.items() if v.get("ok"))
        return good + (f"; failed: {bad}" if bad else "")
    if name == "cognee":
        got = await svc.recall("integration check")
        return f"recall answered ({len(got)} items, mode {getattr(svc, 'mode', '?')})"
    if name == "amplitude":
        svc.track_event("integration_check", "b2c_integration_check", {"source": "scripts/check_integrations.py"})
        svc.shutdown()
        return "event sent and flushed (look for b2c_integration_check in Amplitude)"
    if name == "statsig":
        on = svc.check_gate("strict_compat_rules")
        svc.shutdown()
        return f"gate strict_compat_rules = {on}"
    if name == "exa_airbyte":
        hits = await svc.search("SO-101 robot arm bill of materials", 1)
        return f"{len(hits)} result(s)"
    if name == "airbyte_github":
        doc = await svc.fetch_readme("https://github.com/TheRobotStudio/SO-ARM100")
        return f"README read, {len(doc.text)} chars, simulated={bool(getattr(doc, 'simulated', False))}"
    if name == "keenable":
        hits = await svc.search("SO-101 robot arm", 1)
        return f"{len(hits)} result(s)"
    return "no ping for this service"


async def _run_pings(names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in names:
        t0 = time.perf_counter()
        try:
            msg = await asyncio.wait_for(_ping(n), PING_TIMEOUT_S)
            out[n] = f"ok · {msg} · {int((time.perf_counter() - t0) * 1000)} ms"
        except Exception as exc:  # report, never raise: one broken service must not hide the others
            out[n] = f"FAILED · {type(exc).__name__}: {str(exc)[:160]}"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check the sponsor integrations (settings, SDKs, optional live ping).")
    ap.add_argument("--ping", nargs="?", const="all", default=None,
                    help="also make one small real call: 'all' (every service with keys) or a comma list")
    args = ap.parse_args(argv)

    settings = dotenv_settings()
    names = [*LIVE_SWITCHABLE, "anthropic"]
    rows = []
    for n in names:
        ok, detail = _keys(n, settings)
        note = _stripe_note(settings) if n == "stripe" else ""
        url = (settings.get("S2_URL") or "").strip()
        if n == "singlestore" and any(ch.isspace() for ch in url.rpartition("@")[2]):
            note = "the host/port/database part of S2_URL contains a space: check what was pasted after the last @"
        rows.append((n, ok, detail, _sdk(n), note))

    to_ping: list[str] = []
    if args.ping:
        wanted = names if args.ping == "all" else [x.strip() for x in args.ping.split(",") if x.strip()]
        to_ping = [n for n, ok, *_ in rows if ok and n in wanted and n not in SETTINGS_ONLY]
        if to_ping:
            from dotenv import load_dotenv

            load_dotenv(BACKEND.parent / ".env", override=False)
            load_dotenv(BACKEND / ".env", override=False)
            os.environ["DEMO_MODE"] = "live"
            for n in to_ping:
                os.environ[f"IMPL_{n.upper()}"] = "live"
    pings = asyncio.run(_run_pings(to_ping)) if to_ping else {}

    width = max(len(n) for n in names)
    print("Sponsor integrations (values are never shown)\n")
    for n, ok, detail, sdk, note in rows:
        line = f"  {n:<{width}}  settings: {'set' if ok else 'not set':<7}  sdk: {sdk:<10}  {detail}"
        if note:
            line += f"  [{note}]"
        print(line)
        if n in pings:
            print(f"  {'':<{width}}  ping: {pings[n]}")
    ready = [n for n, ok, *_ in rows if ok]
    print(f"\nReady to run live: {', '.join(ready) if ready else 'none yet: add keys to .env (see .env.example)'}")
    if ready:
        claude = " --claude" if "anthropic" in ready else ""
        print(f"Start with them live:  cd backend && uv run python scripts/dev_pipeline.py --live auto{claude}")
    return 1 if any(v.startswith("FAILED") for v in pings.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
