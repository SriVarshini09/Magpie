"""`dev_pipeline.py --live`: sponsor services switch to their Live class only when their settings are present;
the stores always stay mock, and SingleStore keeps S2_URL only when it is switched on."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _dev():
    spec = importlib.util.spec_from_file_location("dev_pipeline_live_test", SCRIPTS / "dev_pipeline.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_default_profile_is_all_mock_and_blanks_s2():
    env = _dev().pipeline_env()
    assert env["S2_URL"] == "" and env["IMPL_SIE"] == "mock" and env["IMPL_COGNEE"] == "mock" and env["IMPL_SHOPIFY_UCP"] == "mock"


def test_live_switches_only_the_named_services_and_never_the_stores():
    env = _dev().pipeline_env(live=["sie", "cognee", "singlestore"])
    assert env["IMPL_SIE"] == env["IMPL_COGNEE"] == env["IMPL_SINGLESTORE"] == "live"
    assert "S2_URL" not in env  # S2_URL comes from .env when SingleStore is live
    assert env["IMPL_AMPLITUDE"] == "mock"
    for store in ("SHOPIFY_UCP", "SERPAPI", "ADAFRUIT", "MAGENTO", "DIGIKEY", "CARTLINKS"):
        assert env[f"IMPL_{store}"] == "mock"


def test_unknown_service_is_refused():
    with pytest.raises(ValueError):
        _dev().pipeline_env(live=["shopify_ucp"])


def test_auto_picks_services_by_their_settings():
    dev = _dev()
    s = {"SIE_API_KEY": "x", "COGNEE_MODE": "cloud", "STATSIG_SERVER_SECRET": "y", "S2_URL": ""}
    assert dev.keyed_services(s) == ["sie", "statsig"]  # COGNEE_MODE alone is not Cognee Cloud; an empty S2_URL is not set
