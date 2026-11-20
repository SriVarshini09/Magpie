"""SIE `extract` reads the specs the compatibility rules judge (rules/spec_reads.py, pipeline/rank.py).

No network: the live path runs against a fake client object; the mock is the local pattern reader.
"""

from __future__ import annotations

import asyncio

import pytest

from app.integrations import sie
from app.models import Offer
from app.pipeline import rank
from app.rules import generic_electrical as ge
from app.rules import spec_reads as sr
from tests.test_integration_e2e import ok, pipeline, start  # noqa: F401  (pipeline is a fixture)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean():
    sr.reset()
    sie.CALL_LOG.clear()
    yield
    sr.reset()
    sie.CALL_LOG.clear()


def offer(oid: str, title: str, description: str | None = None, price: float = 10.0) -> Offer:
    return Offer(offer_id=oid, store_id="s1", store_name="Store", title=title, description=description, url="https://mock.invalid/x",
                 price_usd=price, stock="in_stock", condition="new", action_level="product_link", source_api="mock", seen_at="2026-11-20T00:00:00Z",
                 evidence_sha256="0" * 64, simulated=True)


class FakeClient:
    """Stands in for sie_sdk.SIEAsyncClient: returns {"entities": [...]} for each text."""

    def __init__(self, entities_for, fail: Exception | None = None):
        self.entities_for, self.fail, self.calls = entities_for, fail, []

    async def extract(self, model, item, labels=None, options=None):
        self.calls.append((model, item["text"], list(labels or [])))
        self.options = options
        if self.fail:
            raise self.fail
        return {"entities": self.entities_for(item["text"])}


def live(client, model="ner-test"):
    return sie.LiveSIE(client, models={"extract": model, "score": "rr-test"})


def span(text: str, piece: str, label: str, score: float = 0.9) -> dict:
    i = text.index(piece)
    return {"text": piece, "label": label, "score": score, "start": i, "end": i + len(piece)}


VTX = {"bom_line_id": "b10", "name": "Video transmitter + antenna", "category": "radio", "attrs": {"mount_mm": "30x30"}}


# --------------------------------------------------------------------------- normalizers


def test_span_normalizers_use_the_rules_parsers():
    assert sr.normalize("mount_mm", "30.5x30.5 mm") == "30x30"
    assert sr.normalize("mount_mm", "20×20") == "20x20" and sr.normalize("mount_mm", "25.5x25.5") == "25.5x25.5"
    assert sr.normalize("mount_mm", "5x4.3") is None and sr.normalize("mount_mm", "M3 holes") is None
    assert sr.normalize("stator", "2207") == "2207" and sr.normalize("stator", "big") is None
    assert sr.normalize("cells", "4S") == "4" and sr.normalize("cells", "6 cell") == "6"
    assert sr.normalize("cells", "3-6S") is None  # a range is not one cell count
    assert sr.normalize("cells", "14.8V") is None  # inferred from a voltage: not a read cell count
    assert sr.normalize("capacity_mah", "1,500 mAh") == "1500"
    assert sr.normalize("kv", "2400KV") == "2400" and sr.normalize("kv", "KV920") == "920"
    assert sr.normalize("connector", "XT-60") == "XT60" and sr.normalize("connector", "JST PH 2.0") == "JST-PH"
    assert sr.normalize("connector", "JST") is None  # names no family
    assert sr.normalize("current_a", "45A") == "45" and sr.normalize("current_a", "500mA") == "0.5"
    assert sr.normalize("current_a", "55A", before="burst ") is None  # a burst current is not the rating
    assert sr.normalize("voltage_v", "12 V") == "12" and sr.normalize("voltage_v", "100-240V") is None
    assert sr.normalize("prop_in", "5-inch") == "5" and sr.normalize("prop_in", "5043 props") == "5"
    assert sr.normalize("prop_in", "carbon") is None


def test_unparseable_unknown_and_unlocatable_spans_are_dropped():
    title = "4-in-1 ESC 45A 30x30 XT60"
    spans = [span(title, "45A", "current rating"), span(title, "4-in-1", "mounting pattern"),  # not a pattern: dropped
             span(title, "ESC", "component"),  # a label we do not judge: dropped
             {"text": "20x20", "label": "mounting pattern", "score": 0.9, "start": None, "end": None},  # not in the text: dropped
             span(title, "XT60", "connector", score=0.1)]  # under the score floor: dropped
    reads = sr.to_reads(spans, title)
    assert [(r.attr, r.value, r.text, r.field, r.provider, r.simulated) for r in reads] == [("current_a", "45", "45A", "title", "sie", False)]


# --------------------------------------------------------------------------- the mock reader


def test_mock_extract_reads_fixture_titles_and_is_labelled_mock():
    m = sie.MockSIE()

    def read(title: str) -> dict[str, str]:
        spans = run(m.extract(title, sr.LABELS))
        assert all(s["provider"] == "mock" and s["simulated"] is True and s["source_api"] == "mock" for s in spans)
        assert all(title[s["start"]:s["end"]] == s["text"] for s in spans)  # real offsets into the text
        return {r.attr: r.value for r in sr.to_reads(spans, title)}

    assert read("5.8GHz VTX 20x20 with antenna") == {"mount_mm": "20x20"}
    assert read("2207 2400KV brushless motor") == {"stator": "2207", "kv": "2400"}
    assert read("4-in-1 ESC 45A 30x30 XT60") == {"mount_mm": "30x30", "current_a": "45", "connector": "XT60"}
    assert read("4S 1500mAh LiPo battery, XT60") == {"cells": "4", "capacity_mah": "1500", "connector": "XT60"}
    assert read("5-inch FPV frame, 220 mm wheelbase") == {"prop_in": "5"}
    assert read("12V 5A power supply, 5.5x2.1 mm barrel") == {"voltage_v": "12", "current_a": "5", "connector": "BARREL-5.5x2.1"}
    assert read("Carbon fibre standoffs") == {}
    reads = sr.to_reads(run(m.extract("5.8GHz VTX 20x20 with antenna", sr.LABELS)), "5.8GHz VTX 20x20 with antenna")
    assert reads[0].provider == "mock" and reads[0].simulated and reads[0].model == "mock-patterns" and reads[0].score is None
    assert sr.note(reads[0].model_dump()) == "mock SIE read “20x20”"  # never called plain "SIE"


def test_mock_reads_title_and_description_with_their_own_offsets():
    o = offer("o1", "LiPo battery pack", "4S 1500mAh, XT60 plug")
    stats = run(sr.read_offers(sie.MockSIE(), [o]))
    assert stats["provider"] == "mock" and stats["calls"] == 1 and stats["listings"] == 1
    by = {r.attr: r for r in o.spec_reads}
    assert by["cells"].field == "description" and o.description[by["cells"].start:by["cells"].end] == "4S"
    assert by["connector"].value == "XT60" and all(r.provider == "mock" and r.simulated for r in o.spec_reads)


# --------------------------------------------------------------------------- rules prefer the read


def test_rules_prefer_a_spec_read_over_the_title_pattern():
    title = "5.8GHz VTX 30x30 with antenna"  # the title pattern says 30x30: passes on its own
    assert [c.result for c in ge.check_offer(VTX, {"title": title}) if c.rule_id.startswith("G12")] == ["pass"]
    read = {"attr": "mount_mm", "value": "20x20", "text": "20x20", "label": "mounting pattern", "score": 0.93, "start": 0, "end": 5,
            "field": "description", "provider": "sie", "model": "ner-test", "simulated": False}
    checks = [c for c in ge.check_offer(VTX, {"title": title, "description": "20x20 mounting", "spec_reads": [read]}) if c.rule_id.startswith("G12")]
    assert [c.result for c in checks] == ["fail"]
    assert checks[0].message == "G12: 20x20 mm stack ≠ 30x30 mm stack (SIE read “20x20” in the description)."
    # G7: the read stator decides the class, not the first four digits in the title
    motor = {"bom_line_id": "b2", "name": "Brushless motor", "category": "motor", "attrs": {"prop_in": "5"}}
    stator = {**read, "attr": "stator", "value": "1404", "text": "1404", "label": "motor stator size", "field": "title", "provider": "mock",
              "model": "mock-patterns", "simulated": True, "score": None}
    g7 = [c for c in ge.check_offer(motor, {"title": "2207 class motor, 1404 stator", "spec_reads": [stator]}) if c.rule_id.startswith("G7")]
    assert g7[0].result == "fail" and g7[0].message == "G7: 3-inch listing ≠ 5-inch build (mock SIE read “1404”)."
    # no read: today's patterns and today's message
    plain = [c for c in ge.check_offer(VTX, {"title": "5.8GHz VTX 20x20 with antenna"}) if c.rule_id.startswith("G12")]
    assert plain[0].message == "G12: 20x20 mm stack ≠ 30x30 mm stack (5.8GHz VTX 20x20 with antenna)."


def test_offer_dict_merges_reads_over_the_title_patterns():
    o = offer("o1", "ESC 30A XT30")
    assert rank.offer_dict(o)["attrs"]["current_a"] == 30 and rank.offer_dict(o)["spec_reads"] == []
    o.spec_reads = sr.to_reads([span(o.title, "30A", "current rating") | {"text": "30A"}, span(o.title, "XT30", "connector")], o.title)
    o.spec_reads[0].value = "45"  # what SIE read differs from the pattern: the read wins
    od = rank.offer_dict(o)
    assert od["attrs"]["current_a"] == 45.0 and od["attrs"]["connector"] == "XT30" and od["attrs"]["connectors"] == ["XT30"]
    assert rank._required({"require": {"min_current_a": 40}}, od["attrs"]) is None


# --------------------------------------------------------------------------- the live path, with a fake client


def test_live_extract_through_rank_line_rejects_on_what_sie_read():
    titles = ["5.8GHz VTX 30x30 with antenna", "5.8GHz video transmitter, compact stack"]
    client = FakeClient(lambda text: [span(text, "30x30", "mounting pattern")] if "30x30" in text else
                        [{"text": "20x20", "label": "mounting pattern", "score": 0.88, "start": text.index("20x20"), "end": text.index("20x20") + 5}]
                        if "20x20" in text else [])
    offers = [offer("a", titles[0]), offer("b", titles[1], "Board 27 mm, 20x20 mm holes")]
    okay, rejected, stats = run(rank.rank_line(VTX, offers, plan={"lines": []}, pack_names=["generic_electrical"], sie=live(client)))
    assert [o.offer_id for o in okay] == ["a"]
    assert rejected == {"b": "G12: 20x20 mm stack ≠ 30x30 mm stack (SIE read “20x20” in the description)."}
    assert len(client.calls) == 2 and client.calls[0][0] == "ner-test" and client.calls[0][2] == sr.LIVE_LABELS
    assert client.options == {"threshold": 0.3}  # GLiNER's own 0.5 default drops real specs
    assert client.calls[1][1] == titles[1] + "\nBoard 27 mm, 20x20 mm holes"  # one call per offer: title, then description
    read = offers[1].spec_reads[0]
    assert (read.attr, read.value, read.field, read.provider, read.model, read.simulated, read.score) == ("mount_mm", "20x20", "description", "sie", "ner-test", False, 0.88)
    assert offers[1].description[read.start:read.end] == "20x20"
    assert stats["calls"] == 2 and stats["extract"]["reads"] == 2 and stats["extract"]["provider"] == "sie"
    assert {r["step"]: r["calls"] for r in sie.call_table()}["extract"] == 2  # the Data drawer's SIE table
    # the same texts again: answered from the process cache, no new call
    _, rejected2, stats2 = run(rank.rank_line(VTX, offers, plan={"lines": []}, pack_names=["generic_electrical"], sie=live(client)))
    assert len(client.calls) == 2 and stats2["calls"] == 0 and stats2["extract"]["cached"] == 2 and rejected2 == rejected


def test_extract_failure_falls_back_to_the_title_patterns():
    offers = [offer("a", "5.8GHz VTX 30x30 with antenna"), offer("b", "5.8GHz VTX 20x20 with antenna")]
    client = FakeClient(lambda text: [], fail=RuntimeError("network down"))
    okay, rejected, stats = run(rank.rank_line(VTX, offers, plan={"lines": []}, pack_names=["generic_electrical"], sie=live(client, "ner-down")))
    assert [o.offer_id for o in okay] == ["a"] and all(not o.spec_reads for o in offers)
    assert rejected == {"b": "G12: 20x20 mm stack ≠ 30x30 mm stack (5.8GHz VTX 20x20 with antenna)."}  # the pattern's message
    assert stats["extract"]["ok"] is False
    n = len(client.calls)
    run(rank.rank_line(VTX, offers, plan={"lines": []}, pack_names=["generic_electrical"], sie=live(client, "ner-down")))
    assert len(client.calls) == n  # cooling off: the next line does not wait on a dead service


def test_unconfigured_extract_makes_no_call(monkeypatch):
    monkeypatch.delenv("SIE_EXTRACT_MODEL", raising=False)
    client = FakeClient(lambda text: [])
    unconfigured = sie.LiveSIE(client, models={"score": "rr-test"})  # no extract model named
    offers = [offer("b", "5.8GHz VTX 20x20 with antenna")]
    _, rejected, stats = run(rank.rank_line(VTX, offers, plan={"lines": []}, pack_names=["generic_electrical"], sie=unconfigured))
    assert client.calls == [] and stats["calls"] == 0 and rejected["b"].endswith("(5.8GHz VTX 20x20 with antenna).")
    _, rejected, _ = run(rank.rank_line(VTX, offers, plan={"lines": []}, pack_names=["generic_electrical"], sie=None))
    assert rejected["b"].endswith("(5.8GHz VTX 20x20 with antenna).")


# --------------------------------------------------------------------------- a whole run (mock services)


def test_five_inch_drone_run_says_who_read_the_rejected_vtx(pipeline):  # noqa: F811
    c = pipeline
    _, st, rid = start(c, "a small camera drone under $200", answers={"size_class": "5in"})
    vtx = next(ln for ln in st["bom"] if "transmitter" in ln["raw_name"].lower())
    panel = ok(c.get(f"/api/runs/{rid}/parts/{vtx['bom_line_id']}"))
    bad = [o for o in panel["offers"] if o["status"] == "rejected" and "20x20" in o["title"]]
    assert bad and all(o["reason"] == "G12: 20x20 mm stack ≠ 30x30 mm stack (mock SIE read “20x20”)." for o in bad)
    reads = [r for o in panel["offers"] for r in o["spec_reads"]]
    assert reads and all(r["provider"] == "mock" and r["simulated"] is True for r in reads)  # labelled mock on every row
    assert any(r["attr"] == "mount_mm" and r["value"] == "20x20" for o in bad for r in o["spec_reads"])
    chosen = [o for o in panel["offers"] if o["status"] == "chosen"]
    assert chosen and all("20x20" not in o["title"] for o in chosen)
    assert ok(c.get(f"/api/runs/{rid}"))["stats"]["sie_calls"] > len(st["bom"])  # extract calls are counted


def test_generic_live_labels_map_through_the_parsers():
    """What GLiNER returned on live listings: a model number that is a stator size, dimensions that are a stack pattern."""
    title = "All-in-one F4 flight controller + 20A 4-in-1 ESC, 25.5x25.5, 2-4S"
    spans = [span(title, "25.5x25.5", "dimensions"), span(title, "2-4S", "dimensions"), span(title, "20A", "dimensions"),
             span(title, "F4", "model number")]
    reads = sr.to_reads(spans, title)
    assert [(r.attr, r.value) for r in reads] == [("mount_mm", "25.5x25.5")]  # 2-4S, 20A and F4 are not what their label claims
    motor = "1404 3800KV brushless motor, 4 pcs"
    reads = sr.to_reads([span(motor, "1404", "model number"), span(motor, "3800KV", "motor KV")], motor)
    assert {(r.attr, r.value) for r in reads} == {("stator", "1404"), ("kv", "3800")}
