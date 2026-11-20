from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# Tests always run in mock mode with no keys, whatever the developer's .env says.
os.environ["DEMO_MODE"] = "mock"
os.environ["MOCK_SSE_DELAY_MS"] = "0"
# Every sponsor/store credential is blanked too: an empty variable already in the environment is never replaced by
# .env (load_dotenv(override=False)), so no test can reach a real SingleStore, SIE, Cognee, ... with the team's keys.
_SECRETS = ["STRIPE_SECRET_KEY", "VITE_STRIPE_PUBLISHABLE_KEY", "S2_URL", "SIE_API_KEY", "SIE_BASE_URL", "COGNEE_URL",
            "COGNEE_API_KEY", "AMPLITUDE_AI_API_KEY", "STATSIG_SERVER_SECRET", "EXA_API_KEY", "AIRBYTE_GITHUB_TOKEN",
            "KEENABLE_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "SERPAPI_KEY", "SERPER_API_KEY",
            "DIGIKEY_CLIENT_ID", "DIGIKEY_CLIENT_SECRET", "HF_TOKEN", "LLM_API_KEY", "PERSONA_SANDBOX_KEY"]
for _name in [n for n in os.environ if n.startswith("IMPL_")] + _SECRETS:
    os.environ[_name] = ""


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app import main

    main.mock.__init__()  # fresh mock state for every test
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def live_mode(monkeypatch):
    """Switch the app to DEMO_MODE=live for one test."""
    from app import config, registry

    monkeypatch.setenv("DEMO_MODE", "live")
    config.reload_settings()
    registry.reset()
    yield
    monkeypatch.setenv("DEMO_MODE", "mock")
    config.reload_settings()
    registry.reset()
