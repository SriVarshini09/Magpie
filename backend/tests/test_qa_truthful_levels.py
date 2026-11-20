"""QA fixes after integration: one truthful action level everywhere, health that names its fallbacks, the keyless
GitHub source in pipeline mode (never the network in tests), the electronics mock catalog, and README-path fixes.

Every run here is pipeline mode (`scripts/dev_pipeline.py`'s environment) on mock stores. The GitHub reads go through
an httpx MockTransport: nothing leaves the process.
"""

from __future__ import annotations

import json

import httpx
import pytest
from test_integration_e2e import ESP32_URL, _dev_pipeline, ok, pipeline, start  # noqa: F401  (pipeline is a fixture)

from app.config import DATA_DIR
from app.models import Offer, UniversalCart

SHA = "c78ad15e7933684fb5af19168f6e2da003e08b84"
# A README with the same shape as esp32-weather-epd's (a components table, a panel table, a licensing table), in our
# own words: the parser must keep the six components and drop the fonts and icons.
README = """# E-paper weather display

## Hardware

### Components

  | Component Type  | Component                       | Notes                         | Link                     |
  |-----------------|---------------------------------|-------------------------------|--------------------------|
  | ESP32           | FireBeetle 2 ESP32-E            | Low-power board.              | Available from a store.  |
  | E-Paper Display | See [Panel Support](#panel-support). | See [Panel Support](#panel-support). | See above. |
  | Adapter Board   | DESPI-C02                       | Recommended adapter.          | Available from a store.  |
  | Sensor          | BME280                          | Temperature and humidity.     | Many vendors.            |
  | Battery         | 3.7V LiPo w/ JST-PH2.0 connector | Any capacity.                | Many vendors.            |
  | Enclosure       | Printed case                    | Optional.                     | Community designs.       |

### Panel Support

  | Panel                        | Resolution | Colors      |
  |------------------------------|------------|-------------|
  | Waveshare 7.5in e-paper (v2) | 800x480px  | Black/White |

## Licensing

| Name | License | Description |
|------|---------|-------------|
| [Lato](https://example.org/lato) | SIL OFL v1.1 | Font Family |
| [House Icon](https://example.org/house) | MIT License | House icon. |
"""


def github_transport(seen: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        seen.append(url)
        if request.url.host == "api.github.com" and url.endswith("/repos/lmarzen/esp32-weather-epd/commits?per_page=1"):
            return httpx.Response(200, json=[{"sha": SHA}])
        if request.url.host == "raw.githubusercontent.com" and url.endswith(f"/lmarzen/esp32-weather-epd/{SHA}/README.md"):
            return httpx.Response(200, content=README.encode())
        return httpx.Response(404)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------- (a) one action level everywhere


def test_every_place_shows_the_level_the_handoff_will_use(pipeline):
    c = pipeline
    stores = {s["store_id"]: s for s in ok(c.get("/api/stores"))}
    assert stores["mock_store"]["action_level"] == "product_link" and stores["amazon"]["action_level"] == "product_link"  # no cart ids; unverified link
    _, st, rid = start(c, "a small camera drone under $200")
    cart = ok(c.get(f"/api/runs/{rid}/cart"))
    group_level = {g["store_id"]: g["action_level"] for g in cart["stores"]}
    for ln in st["bom"]:
        for ch in ln.get("chosen") or []:
            assert ch["action_level"] == group_level[ch["store_id"]] == stores[ch["store_id"]]["action_level"], (ln["raw_name"], ch)
        for row in ok(c.get(f"/api/runs/{rid}/parts/{ln['bom_line_id']}"))["offers"]:
            if row["store_id"] in stores and row["status"] in ("chosen", "alternative"):
                assert row["action_level"] == stores[row["store_id"]]["action_level"], row
    amazon = next(g for g in cart["stores"] if g["store_id"] == "amazon")
    assert "not yet been opened in a real browser" in amazon["downgrade_reason"]


def test_a_verified_cart_link_is_a_prefilled_cart_everywhere(pipeline, monkeypatch):
    monkeypatch.setenv("CART_LINKS_VERIFIED", "amazon")
    c = pipeline
    assert {s["store_id"]: s for s in ok(c.get("/api/stores"))}["amazon"]["action_level"] == "prefilled_cart"
    _, st, rid = start(c, "a small camera drone under $200")
    cart = ok(c.get(f"/api/runs/{rid}/cart"))
    amazon = next(g for g in cart["stores"] if g["store_id"] == "amazon")
    assert amazon["action_level"] == "prefilled_cart"
    assert all(ch["action_level"] == "prefilled_cart" for ln in st["bom"] for ch in ln.get("chosen") or [] if ch["store_id"] == "amazon")


def test_a_listing_that_asks_for_buyer_data_is_never_bought_from(pipeline):
    c = pipeline
    _, st, rid = start(c, "https://github.com/TheRobotStudio/SO-ARM100", {"voltage_class": "12v"})
    b2 = next(ln for ln in st["bom"] if ln["bom_line_id"] == "b2")
    assert b2["chosen"] and all(ch["offer_id"] != "o34" for ch in b2["chosen"])
    row = next(o for o in ok(c.get(f"/api/runs/{rid}/parts/b2"))["offers"] if o["offer_id"] == "o34")
    assert row["status"] == "refused" and row["reason"] == "constraints.data_sharing"


# ---------------------------------------------------------------------------- (b) health names its fallbacks


def test_health_says_sqlite_fallback_not_off(pipeline):
    health = ok(pipeline.get("/api/health"))
    assert health["integrations"]["singlestore"] == "fallback" and health["integrations"]["anthropic"] == "off"
    assert health["integrations"]["airbyte_github"] == "mock"  # the offline profile the tests use


# ---------------------------------------------------------------------------- (d) keyless GitHub in pipeline mode


def test_pipeline_mode_turns_the_keyless_github_source_on_and_tests_stay_offline():
    mod = _dev_pipeline()
    assert mod.pipeline_env()["IMPL_AIRBYTE_GITHUB"] == "mock"  # what tests and other callers get
    assert mod.pipeline_env(github_live=True)["IMPL_AIRBYTE_GITHUB"] == "live"  # what the CLI does (--github live, default)
    assert "IMPL_AIRBYTE_GITHUB" not in {k for k, v in mod.pipeline_env(github_live=True).items() if v == "mock" and k.endswith("GITHUB")}


def test_live_github_source_without_a_token_reads_through_raw_fetch_only(monkeypatch):
    import asyncio

    from app.integrations.airbyte_github import LiveGitHubSource

    monkeypatch.delenv("AIRBYTE_GITHUB_TOKEN", raising=False)
    seen: list[str] = []
    doc = asyncio.run(LiveGitHubSource(transport=github_transport(seen))._fetch_readme(ESP32_URL))
    assert doc.via == "http" and doc.source_api == "github_raw" and doc.commit_sha == SHA and doc.simulated is False
    assert {httpx.URL(u).host for u in seen} <= {"api.github.com", "raw.githubusercontent.com"}
    with pytest.raises(RuntimeError, match="no network under pytest"):
        asyncio.run(LiveGitHubSource()._get("https://api.github.com/repos/a/b/commits"))  # no transport: never the real network


def test_esp32_link_reaches_a_cart_with_the_projects_own_variant(pipeline, monkeypatch):
    from app import registry
    from app.integrations.airbyte_github import LiveGitHubSource

    monkeypatch.setenv("IMPL_AIRBYTE_GITHUB", "live")
    monkeypatch.delenv("AIRBYTE_GITHUB_TOKEN", raising=False)
    seen: list[str] = []
    registry._instances[("airbyte_github", "live")] = LiveGitHubSource(transport=github_transport(seen))
    c = pipeline
    assert ok(c.get("/api/health"))["integrations"]["airbyte_github"] == "fallback"
    _, st, rid = start(c, ESP32_URL)
    assert st["status"] == "waiting_approval" and st["source"]["via"] == "http" and st["source"]["simulated"] is False
    names = [ln["raw_name"] for ln in st["bom"]]
    assert names == ["ESP32", "E-Paper Display", "Adapter Board", "Sensor", "Battery", "Enclosure"]  # no fonts, no icons
    assert st["template"]["variant"] == "esp32_epaper"  # the variant written for this link, not the Arduino default
    by = {ln["raw_name"]: ln for ln in st["bom"]}
    esp32 = ok(c.get(f"/api/runs/{rid}/parts/{by['ESP32']['bom_line_id']}"))
    battery = ok(c.get(f"/api/runs/{rid}/parts/{by['Battery']['bom_line_id']}"))
    assert esp32["attrs"].get("logic_v") == "3.3" and "voltage_range" not in esp32["attrs"]  # never the Uno's 7-12 V
    assert battery["attrs"]["voltage_v"] == "3.7" and battery["attrs"]["cells"] == "1S"
    assert not any("inside ESP32" in ch["message"] for ch in st["checks"])  # no 9 V-into-ESP32 "pass"
    cart = ok(c.get(f"/api/runs/{rid}/cart"))
    UniversalCart.model_validate(cart)
    assert len(cart["stores"]) >= 1 and cart["total_usd"] > 0
    assert {x["name"] for x in cart["left_out"]} <= {"Enclosure"}
    assert seen and all(httpx.URL(u).host in ("api.github.com", "raw.githubusercontent.com") for u in seen)


# ---------------------------------------------------------------------------- (c) the electronics mock catalog


def test_extra_mock_catalog_is_labelled_mock_and_valid():
    doc = json.loads((DATA_DIR / "mock_catalog_electronics.json").read_text(encoding="utf-8"))
    assert "PLACEHOLDER" in doc["_note"] and doc["lines"] and doc["offers"]
    line_ids = {ln["line_id"] for ln in doc["lines"]}
    for raw in doc["offers"]:
        assert raw["bom_line_id"] in line_ids
        o = Offer.model_validate({k: v for k, v in raw.items() if k != "bom_line_id"})
        assert o.source_api == "mock" and o.simulated is True and o.url.startswith("https://mock.invalid/") and o.mock_of


def test_generic_and_electronics_text_runs_reach_a_cart(pipeline):
    c = pipeline
    for text in ("an arduino plant watering kit with a soil moisture sensor", "a bluetooth speaker I can build myself"):
        _, st, rid = start(c, text)
        cart = ok(c.get(f"/api/runs/{rid}/cart"))
        assert cart["stores"] and cart["total_usd"] > 0, text
        assert all(i["simulated"] for g in cart["stores"] for i in g["items"])


def test_hero_runs_do_not_take_offers_from_the_extra_catalog(pipeline):
    c = pipeline
    _, st, _ = start(c, "a small camera drone under $200")
    assert all(ch["offer_id"].startswith("d") for ln in st["bom"] for ch in ln.get("chosen") or [])
    _, st, _ = start(c, "https://github.com/TheRobotStudio/SO-ARM100", {"voltage_class": "12v"})
    assert all(ch["offer_id"].startswith("o") for ln in st["bom"] for ch in ln.get("chosen") or [])


# ---------------------------------------------------------------------------- small parsers


def test_licence_tables_are_not_parts_tables():
    from app.pipeline import readme_table

    rows = [r.name for t in readme_table.parse_parts(README) for r in t.rows]
    assert "Lato" not in rows and "House Icon" not in rows and "ESP32" in rows


def test_cells_display_is_not_doubled():
    from app.pipeline.resolve import str_attrs

    assert str_attrs({"cells": "1S"})["cells"] == "1S" and str_attrs({"cells": 4})["cells"] == "4S"


def test_a_missing_github_repo_says_so_in_words(monkeypatch):
    import asyncio

    from app.integrations.airbyte_github import LiveGitHubSource

    monkeypatch.delenv("AIRBYTE_GITHUB_TOKEN", raising=False)
    gone = httpx.MockTransport(lambda request: httpx.Response(404, json={"message": "Not Found"}))
    with pytest.raises(LookupError, match="no public repository someone/nothing"):
        asyncio.run(LiveGitHubSource(transport=gone)._fetch_readme("https://github.com/someone/nothing"))
    limited = httpx.MockTransport(lambda request: httpx.Response(403, json={"message": "API rate limit exceeded"}))
    with pytest.raises(LookupError, match="60 reads an hour"):
        asyncio.run(LiveGitHubSource(transport=limited)._fetch_readme("https://github.com/someone/nothing"))


def test_g6_never_reports_zero_amps_when_no_load_is_known():
    from test_generic_rules import line, run

    checks = run("G6", line("b7", "battery", "LiPo battery", attrs={"connector": "XT30"}))
    assert checks and all("0 A through" not in c.message for c in checks)
    assert any(c.result == "needs_human" and "No load current is known for LiPo battery's XT30" in c.message for c in checks)


def test_csv_names_the_part_not_the_listing(pipeline):
    c = pipeline
    _, st, rid = start(c, "a small camera drone under $200")
    rows = c.get(f"/api/runs/{rid}/cart/export.csv").text.splitlines()
    assert rows[0].startswith("line,part,store") and any(r.startswith("b1,Frame,") for r in rows[1:])


def test_pipeline_github_falls_back_to_the_bundled_copy_only_for_the_bundled_repo(monkeypatch):
    import asyncio

    from app.integrations.airbyte_github import LiveGitHubSource

    monkeypatch.delenv("AIRBYTE_GITHUB_TOKEN", raising=False)
    limited = httpx.MockTransport(lambda request: httpx.Response(403, json={"message": "API rate limit exceeded"}))
    so101 = "https://github.com/TheRobotStudio/SO-ARM100"
    with pytest.raises(LookupError):  # without the pipeline flag: the real reason, no copy
        asyncio.run(LiveGitHubSource(transport=limited)._fetch_readme(so101))
    monkeypatch.setenv("B2C_GITHUB_BUNDLED_FALLBACK", "1")
    assert _dev_pipeline().pipeline_env(github_live=True)["B2C_GITHUB_BUNDLED_FALLBACK"] == "1"
    doc = asyncio.run(LiveGitHubSource(transport=limited)._fetch_readme(so101))
    assert doc.simulated is True and doc.source_api == "mock"  # labelled as the bundled copy, never as a fresh read
    with pytest.raises(LookupError, match="60 reads an hour"):  # any other repository still fails, in words
        asyncio.run(LiveGitHubSource(transport=limited)._fetch_readme(ESP32_URL))


def test_a_renamed_repo_redirect_is_followed_only_on_github_hosts(monkeypatch):
    import asyncio

    from app.integrations.airbyte_github import LiveGitHubSource
    from app.stores.http import HostNotAllowed

    monkeypatch.delenv("AIRBYTE_GITHUB_TOKEN", raising=False)

    def moved(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/repos/old/name/commits?per_page=1"):
            return httpx.Response(301, headers={"location": "https://api.github.com/repositories/42/commits?per_page=1"})
        if url.endswith("/repositories/42/commits?per_page=1"):
            return httpx.Response(200, json=[{"sha": SHA}])
        if request.url.host == "raw.githubusercontent.com" and url.endswith(f"/old/name/{SHA}/README.md"):
            return httpx.Response(200, content=README.encode())
        return httpx.Response(404)

    doc = asyncio.run(LiveGitHubSource(transport=httpx.MockTransport(moved))._fetch_readme("https://github.com/old/name"))
    assert doc.commit_sha == SHA and doc.via == "http"
    off = httpx.MockTransport(lambda request: httpx.Response(301, headers={"location": "https://example.com/elsewhere"}))
    with pytest.raises(Exception) as err:
        asyncio.run(LiveGitHubSource(transport=off)._fetch_readme("https://github.com/old/name"))
    assert isinstance(err.value, HostNotAllowed) or isinstance(err.value.__cause__, HostNotAllowed) or "redirected off" in str(err.value)


def test_an_edited_assumption_never_keeps_a_mock_part_that_does_not_fit(pipeline):
    c = pipeline
    _, st, rid = start(c, "a bluetooth speaker I can build myself")
    motor = next(ln for ln in st["bom"] if ln["raw_name"] == "Motor or actuator")
    assert motor["chosen"]  # the generic line finds the mock catalog's servo
    after = ok(c.post(f"/api/runs/{rid}/assumptions", json={"bom_line_id": motor["bom_line_id"], "action": "edit",
                                                          "spec": "Full-range speaker driver, 3 inch, 4 ohm"}))
    edited = next(ln for ln in after["bom"] if ln["bom_line_id"] == motor["bom_line_id"])
    assert edited["spec"].startswith("Full-range speaker driver") and not edited.get("chosen") and edited["status"] == "not_found"
