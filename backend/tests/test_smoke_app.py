"""The app imports, starts, and exposes every endpoint of PLAN §4.2."""

from __future__ import annotations

PLAN_4_2 = {
    ("GET", "/api/projects"), ("POST", "/api/intake"), ("POST", "/api/intake/{intake_id}/answers"),
    ("GET", "/api/uploads/{image_id}"), ("GET", "/api/stores"), ("POST", "/api/runs"),
    ("POST", "/api/runs/{run_id}/assumptions"), ("GET", "/api/runs/{run_id}/events"), ("GET", "/api/runs/{run_id}"),
    ("GET", "/api/runs/{run_id}/parts/{bom_line_id}"), ("GET", "/api/runs/{run_id}/prices/{bom_line_id}"),
    ("GET", "/api/kb/search"), ("POST", "/api/runs/{run_id}/message"), ("POST", "/api/runs/{run_id}/owned"),
    ("POST", "/api/runs/{run_id}/variant"), ("POST", "/api/runs/{run_id}/replan"), ("GET", "/api/runs/{run_id}/cart"),
    ("POST", "/api/runs/{run_id}/cart/edit"), ("POST", "/api/runs/{run_id}/cart/refresh"), ("POST", "/api/runs/{run_id}/approve"),
    ("POST", "/api/runs/{run_id}/cart/handoff"), ("GET", "/api/runs/{run_id}/cart/export.csv"),
    ("POST", "/api/runs/{run_id}/pay/intent"), ("POST", "/api/runs/{run_id}/pay/fanout"),
    ("GET", "/api/runs/{run_id}/receipt"), ("GET", "/api/runs/{run_id}/verify"), ("GET", "/api/health"),
    # added at integration (C's and D's change requests)
    ("POST", "/api/runs/{run_id}/cart/reopen"), ("POST", "/api/runs/{run_id}/cart/item-added"), ("GET", "/api/data/stats"),
}


def test_every_plan_endpoint_is_routed():
    from app.main import app

    routed = {(m, r.path) for r in app.routes for m in getattr(r, "methods", set())}
    assert PLAN_4_2 <= routed, f"missing routes: {sorted(PLAN_4_2 - routed)}"


def test_health_reports_mock_mode(client):
    for path in ("/health", "/api/health"):
        r = client.get(path)
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "mock" and body["mock"] is True
        assert set(body["integrations"].values()) == {"mock"}
        assert set(body["stores"].values()) == {"mock"}
        assert r.headers["X-B2C-Mode"] == "mock" and r.headers["X-B2C-Mock"] == "true"


def test_cors_allows_the_vite_dev_server(client):
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5175"):
        r = client.options("/api/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        assert r.headers.get("access-control-allow-origin") == origin
    r = client.options("/api/health", headers={"Origin": "https://example.com", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") is None


def test_stub_modules_import_and_name_their_owner():
    import importlib
    import pkgutil

    import app

    seen = 0
    for mod in pkgutil.walk_packages(app.__path__, "app."):
        importlib.import_module(mod.name)
        seen += 1
    assert seen > 50

    import pytest

    from app.pipeline import optimize

    # A implemented the optimizer: it plans for runs in this process, and an unknown run raises instead of inventing a plan
    with pytest.raises(NotImplementedError, match=r"no run 'r_unknown'"):
        optimize.optimize_cart("r_unknown", "cheapest")
