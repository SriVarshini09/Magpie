"""Environment and guards (PLAN §3.3, §3.11, §12.2).

SHARED FILE, owned by the coordinator (OWNERSHIP.md). Builders do not edit it: list the
setting you need in your final report.

Loads `.env` from the repo root, then `backend/.env` (neither overrides real env vars).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
FIXTURES_DIR = BACKEND_DIR / "fixtures"
DATA_DIR = BACKEND_DIR / "data"

DEMO_MODES = ("mock", "live", "record", "replay")
# The Vite dev server (5173) and the port it moves to when 5173 is taken by another preview (5175)
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5175,http://127.0.0.1:5175"


class ConfigError(RuntimeError):
    pass


class StripeKeyError(ConfigError):
    """A Stripe key that is not a test key, or an object that is not in test mode."""


def assert_stripe_test_keys(secret_key: str | None, publishable_key: str | None) -> None:
    """Refuse any Stripe key that is not a TEST key (PLAN §3.3, §12.2). Empty means "not configured".

    The key itself is never put in the error message.
    """
    if secret_key and not secret_key.startswith("sk_test_"):
        raise StripeKeyError("STRIPE_SECRET_KEY must start with sk_test_. Live and restricted keys are refused.")
    if publishable_key and not publishable_key.startswith("pk_test_"):
        raise StripeKeyError("VITE_STRIPE_PUBLISHABLE_KEY must start with pk_test_. Live keys are refused.")


def assert_livemode_false(stripe_object: Any) -> None:
    """Assert a Stripe API object came from test mode. Call it on every object Stripe returns."""
    if isinstance(stripe_object, dict):
        livemode = stripe_object.get("livemode")
    else:
        livemode = getattr(stripe_object, "livemode", None)
    if livemode is not False:
        raise StripeKeyError(f"Stripe object livemode must be false, got {livemode!r}. No real money may move.")


@dataclass(frozen=True)
class Settings:
    demo_mode: str
    pinned_now: str
    price_max_age_min: int
    pay_tier: int
    cors_origins: tuple[str, ...]
    mock_sse_delay_ms: int
    # models
    model_fast: str
    model_plan: str
    model_vision: str
    # uploads
    upload_max_mb: int
    upload_max_edge_px: int
    upload_max_images: int
    # reference search
    reference_providers: tuple[str, ...]
    reference_max_searches: int
    reference_max_pages: int
    # serpapi
    serpapi_max_searches: int
    # misc
    embed_dim: int
    cognee_mode: str
    mandate_key_path: str
    ucp_bin: str
    # Stripe keys, already checked by the guard. Never log them.
    stripe_secret_key: str
    stripe_publishable_key: str

    @property
    def is_mock(self) -> bool:
        return self.demo_mode == "mock"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in (os.getenv(name) or default).split(",") if x.strip())


def secret(name: str) -> str:
    """Read a secret from the environment at call time. Do not log the return value."""
    return os.getenv(name, "")


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    load_dotenv(BACKEND_DIR / ".env", override=False)
    mode = (os.getenv("DEMO_MODE") or "mock").strip().lower()
    if mode not in DEMO_MODES:
        raise ConfigError(f"DEMO_MODE must be one of {DEMO_MODES}, got {mode!r}")
    sk, pk = secret("STRIPE_SECRET_KEY"), secret("VITE_STRIPE_PUBLISHABLE_KEY")
    assert_stripe_test_keys(sk, pk)  # the backend refuses to start otherwise
    return Settings(
        demo_mode=mode,
        pinned_now=os.getenv("PINNED_NOW") or "2026-11-20T13:00:00-08:00",
        price_max_age_min=_int("PRICE_MAX_AGE_MIN", 15),
        pay_tier=_int("PAY_TIER", 1),
        cors_origins=_csv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
        mock_sse_delay_ms=_int("MOCK_SSE_DELAY_MS", 250),
        model_fast=os.getenv("MODEL_FAST") or "claude-sonnet-5-5",
        model_plan=os.getenv("MODEL_PLAN") or "claude-opus-5-5",
        model_vision=os.getenv("MODEL_VISION") or "claude-sonnet-5-5",
        upload_max_mb=_int("UPLOAD_MAX_MB", 5),
        upload_max_edge_px=_int("UPLOAD_MAX_EDGE_PX", 1024),
        upload_max_images=_int("UPLOAD_MAX_IMAGES", 2),
        reference_providers=_csv("REFERENCE_PROVIDERS", "keenable,exa_airbyte,claude_web_search,github_search"),
        reference_max_searches=_int("REFERENCE_MAX_SEARCHES", 3),
        reference_max_pages=_int("REFERENCE_MAX_PAGES", 2),
        serpapi_max_searches=_int("SERPAPI_MAX_SEARCHES", 150),
        embed_dim=_int("EMBED_DIM", 1024),
        cognee_mode=os.getenv("COGNEE_MODE") or "cloud",
        mandate_key_path=os.getenv("MANDATE_KEY_PATH") or "runs/demo_es256.pem",
        ucp_bin=os.getenv("UCP_BIN") or "ucp",
        stripe_secret_key=sk,
        stripe_publishable_key=pk,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reload_settings() -> Settings:
    """Re-read the environment (tests)."""
    get_settings.cache_clear()
    return get_settings()
