"""Start the backend in PIPELINE MODE: the real pipeline on mock services. No keys, no network.

    cd backend && uv run python scripts/dev_pipeline.py            # http://127.0.0.1:8000
    uv run python scripts/dev_pipeline.py --port 8001 --reload
    uv run python scripts/dev_pipeline.py --claude                 # also use Claude, if ANTHROPIC_API_KEY is set

What runs for real: intake (the keyword router), the scripted agent and every tool, provenance checks, the
compatibility rules, the optimizer, the mandate guard, the Universal Cart, ES256 signing, the hash chain and
Verify. SingleStore is the SQLite fallback (the same seven tables, seeded from data/kb on first start).

What is mock: every store adapter, cart links, reference search, SIE, Cognee, Amplitude, Statsig and Stripe.
Everything they return is labelled simulated; the UI shows the "Mock stores" badge. Claude is off unless --claude
is given: with no key the intake uses the keyword router and the agent runs its fixed tool order.

GitHub (--github, default live): READMEs of public repositories are read for real and keylessly, through the
GitHub source's raw fetch (api.github.com for the commit SHA, raw.githubusercontent.com for the README; no token,
60 requests an hour per IP). Any public GitHub project link works. When that read fails (the hourly limit, or no network)
the SO-ARM100 link falls back to its bundled copy, labelled as the mock connector's. `--github mock` keeps the offline profile:
only the bundled SO-ARM100 README, no network at all. Tests use the offline profile and never touch the network.

The same settings as a profile: `.env.pipeline` at the repo root (copy it to `.env`).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# Services that stay on their Live class: both work with no key and make no network call without one.
#   anthropic    no key -> LLMUnavailable -> keyword router + scripted agent
#   singlestore  no S2_URL -> SQLite
LIVE_WITHOUT_KEYS = ("anthropic", "singlestore")
# The GitHub source's Live class falls back to a keyless raw fetch (api.github.com + raw.githubusercontent.com only)
# when AIRBYTE_GITHUB_TOKEN is not set. Turned on by the CLI (`--github live`, the default), off in `pipeline_env()`.
GITHUB_KEYLESS = ("airbyte_github",)
MOCKED = ("airbyte_github", "sie", "cognee", "amplitude", "statsig", "keenable", "exa_airbyte", "github_search", "stripe",
          "shopify_ucp", "serpapi", "adafruit", "magento", "digikey", "cartlinks")


# Sponsor services `--live` may switch on, and the settings each needs (any one of a group is enough). Stores stay
# mock in pipeline mode whatever is set: live store calls need DEMO_MODE=live and the store keys (CLAUDE.md rule 5).
LIVE_SWITCHABLE: dict[str, tuple[tuple[str, ...], ...]] = {
    "singlestore": (("S2_URL",),),
    "sie": (("SIE_API_KEY", "SIE_BASE_URL"),),
    "cognee": (("COGNEE_URL",),),  # Cognee Cloud; local mode (COGNEE_MODE=local + LLM/embedding settings) is not switched on here
    "amplitude": (("AMPLITUDE_AI_API_KEY",),),
    "statsig": (("STATSIG_SERVER_SECRET",),),
    "exa_airbyte": (("EXA_API_KEY",),),
    "airbyte_github": (("AIRBYTE_GITHUB_TOKEN",),),
    "keenable": (("KEENABLE_API_KEY",),),
    "stripe": (("STRIPE_SECRET_KEY",),),
}


def dotenv_settings() -> dict[str, str]:
    """The non-empty settings in `.env` (repo root, then backend/) and the process environment. Values never printed."""
    try:
        from dotenv import dotenv_values
    except ImportError:  # pragma: no cover
        dotenv_values = None
    found: dict[str, str] = {}
    if dotenv_values is not None:
        for path in (BACKEND.parent / ".env", BACKEND / ".env"):
            if path.is_file():
                found |= {k: v for k, v in dotenv_values(path).items() if v}
    found |= {k: v for k, v in os.environ.items() if v}
    return found


def keyed_services(settings: dict[str, str] | None = None) -> list[str]:
    """Sponsor services whose settings are present (`--live auto`)."""
    s = dotenv_settings() if settings is None else settings
    return [name for name, groups in LIVE_SWITCHABLE.items() if all(any(s.get(k) for k in group) for group in groups)]


# Store adapters `--stores` may switch to real calls: Shopify stores through Shopify's own `ucp` CLI (search and
# real agent carts; nothing is bought). Every other store stays mock. The never-request list still applies in code.
LIVE_STORES = ("shopify_ucp",)


def pipeline_env(*, use_claude: bool = False, sqlite_path: str | None = None, github_live: bool = False,
                 live: tuple[str, ...] | list[str] = (), stores: tuple[str, ...] | list[str] = ()) -> dict[str, str]:
    """The environment of pipeline mode. `use_claude=False` blanks the Anthropic credentials for this process.

    `github_live=True` (what the CLI does unless `--github mock`) reads public READMEs for real through the GitHub
    source's keyless raw fetch. The default here is the offline profile, so a caller that builds the environment
    itself (the tests) never reaches the network by accident.

    `live` names sponsor services to run on their Live class with the keys in `.env` (see `LIVE_SWITCHABLE`);
    the stores stay mock. SingleStore keeps `S2_URL` from `.env` only when it is in `live`.
    """
    unknown = [n for n in live if n not in LIVE_SWITCHABLE]
    if unknown:
        raise ValueError(f"--live: unknown service(s) {', '.join(unknown)}; choose from {', '.join(LIVE_SWITCHABLE)}")
    env = {"DEMO_MODE": "live", "B2C_SQLITE_PATH": sqlite_path or str(BACKEND / "runs" / "pipeline.sqlite")}
    if "singlestore" not in live:
        env["S2_URL"] = ""
    env |= {f"IMPL_{name.upper()}": "mock" for name in MOCKED}
    env |= {f"IMPL_{name.upper()}": "live" for name in LIVE_WITHOUT_KEYS}
    if github_live:
        env |= {f"IMPL_{name.upper()}": "live" for name in GITHUB_KEYLESS}
        env["B2C_GITHUB_BUNDLED_FALLBACK"] = "1"  # rate-limited or offline: SO-ARM100 from its bundled copy, labelled simulated
    env |= {f"IMPL_{name.upper()}": "live" for name in live}
    bad_stores = [s for s in stores if s not in LIVE_STORES]
    if bad_stores:
        raise ValueError(f"--stores: only {', '.join(LIVE_STORES)} can run live, not {', '.join(bad_stores)}")
    env |= {f"IMPL_{name.upper()}": "live" for name in stores}
    if not use_claude:
        env |= {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}
    return env


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Run the backend in pipeline mode (real pipeline, mock services).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true", help="restart on changes under app/")
    ap.add_argument("--claude", action="store_true", help="use Claude when ANTHROPIC_API_KEY is set (off by default)")
    ap.add_argument("--github", choices=("live", "mock"), default="live",
                    help="live (default): read public READMEs keylessly from GitHub; mock: only the bundled SO-ARM100 README, no network")
    ap.add_argument("--demo-mode", choices=("live", "record", "replay"), default="live",
                    help="record: write every external call (here: the GitHub reads) to --cache-dir; replay: read them back, no network")
    ap.add_argument("--cache-dir", default=None,
                    help="where record/replay keep their files; use a dev folder (e.g. dev_recordings/mock_stores_pipeline), "
                         "never cache/, which holds the stage recordings made with live keys")
    ap.add_argument("--live", default="",
                    help="sponsor services to run for real with the keys in .env: 'auto' (every one whose keys are set), "
                         f"or a comma list of {','.join(LIVE_SWITCHABLE)}. Stores stay mock.")
    ap.add_argument("--stores", choices=("mock", "shopify"), default="mock",
                    help="shopify: real Shopify stores through Shopify's ucp CLI (real search, real agent carts, nothing bought); "
                         "every other store stays mock. Default mock.")
    args = ap.parse_args(argv)
    if args.live.strip() == "auto":
        live = keyed_services()
    else:
        live = [n.strip() for n in args.live.split(",") if n.strip()]
        missing = [n for n in live if n in LIVE_SWITCHABLE and n not in keyed_services()]
        if missing:
            ap.error(f"--live {','.join(missing)}: its settings are not in .env ({'; '.join('/'.join(g) for n in missing for g in LIVE_SWITCHABLE[n])})")
    try:
        env = pipeline_env(use_claude=args.claude, github_live=args.github == "live" or "airbyte_github" in live, live=live,
                           stores=LIVE_STORES if args.stores == "shopify" else ())
    except ValueError as exc:
        ap.error(str(exc))
    os.environ.update(env)  # before the app loads; .env never overrides real env vars
    os.environ["DEMO_MODE"] = args.demo_mode
    if args.cache_dir:
        os.environ["B2C_CACHE_DIR"] = str((BACKEND / args.cache_dir).resolve())
    elif args.demo_mode != "live":
        ap.error("--demo-mode record/replay needs --cache-dir (a dev folder, not cache/)")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    import uvicorn

    print(f"Live sponsor services: {', '.join(live) if live else 'none (all mock)'}. "
          f"Stores: {'real Shopify stores (ucp CLI), the rest mock' if args.stores == 'shopify' else 'all mock'}.", flush=True)
    print(f"Build-to-Cart backend, PIPELINE MODE ({args.demo_mode}): real pipeline, mock stores and services (labelled simulated). "
          f"Claude: {'on if a key is set' if args.claude else 'off (keyword router + scripted agent)'}. "
          f"GitHub: {'public READMEs read for real, keyless' if args.github == 'live' else 'bundled SO-ARM100 README only (offline)'}.", flush=True)
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload, reload_dirs=["app"] if args.reload else None)


if __name__ == "__main__":
    main()
