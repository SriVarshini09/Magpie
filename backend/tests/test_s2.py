"""SingleStore client on its SQLite fallback: KB parsing, hybrid search, templates, prices, audit, stats (PLAN §3.14).

Owner: D. No network: SQLite in a temp folder; a fake embedder stands in for SIE.
"""

from __future__ import annotations

import asyncio
import json
import re

import pytest

from app import models as M
from app.audit.chain import canonical_json, sha256_hex
from app.integrations import s2
from app.integrations.s2 import LiveKnowledgeStore, MockKnowledgeStore, OwnedPartsMemory, SqliteBackend

KB = s2.KB_DIR


@pytest.fixture()
def store(tmp_path):
    st = LiveKnowledgeStore(SqliteBackend(tmp_path / "kb.sqlite"), embedder=None)
    st.backend.apply_schema(8)
    st.seed(embed=False)
    yield st
    st.close()


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------- KB files


def test_every_kb_file_parses_with_unique_refs_and_line_ranges():
    docs, chunks = s2.load_kb_dir()
    kinds = {d["kind"] for d in docs}
    assert {"doc", "template", "rule_source", "reference"} <= kinds
    assert len({c["kb_ref"] for c in chunks}) == len(chunks)
    for c in chunks:
        assert re.fullmatch(r"kb://[a-z0-9_]+(#[A-Za-z0-9_]+)?", c["kb_ref"]), c["kb_ref"]
        assert 1 <= c["line_from"] <= c["line_to"] and c["body"].strip()


def test_markdown_chunk_line_numbers_point_at_the_chunk_heading():
    doc, chunks = s2.parse_kb_markdown(KB / "so101_readme_notes.md")
    lines = (KB / "so101_readme_notes.md").read_text(encoding="utf-8").split("\n")
    l73 = next(c for c in chunks if c["chunk_id"] == "L73")
    assert lines[l73["line_from"] - 1] == "## chunk: L73"
    assert l73["kb_ref"] == "kb://so101_readme#L73" and doc["licence"].startswith("Apache-2.0")
    assert "12V 5A+ power supply" in " ".join(l73["meta"]["quotes"])


def test_readme_quotes_in_the_kb_are_exact_substrings_of_the_pinned_readme():
    readme = (s2.BACKEND_DIR / "fixtures" / "sources" / "SO-ARM100_README.md").read_text(encoding="utf-8").split("\n")
    _, chunks = s2.parse_kb_markdown(KB / "so101_readme_notes.md")
    for c in chunks:
        lo, *hi = (int(x) for x in c["meta"]["readme_lines"].split("-"))
        text = "\n".join(readme[lo - 1:(hi[0] if hi else lo)])
        for q in c["meta"].get("quotes", []):
            assert q in text, (c["chunk_id"], q)


def test_fixture_kb_refs_that_d_owns_resolve_on_disk():
    from app.config import FIXTURES_DIR

    text = "".join(p.read_text(encoding="utf-8") for p in FIXTURES_DIR.glob("*.json*"))
    refs = set(re.findall(r'kb://[A-Za-z0-9_]+(?:#[A-Za-z0-9_]+)?', text))
    missing = sorted(r for r in refs if s2.resolve_kb_ref_on_disk(r) is None)
    assert not missing, missing


def test_template_rows_carry_the_row_json_and_its_hash():
    doc, chunks = s2.template_rows(KB / "templates" / "quadcopter.json")
    tpl = json.loads((KB / "templates" / "quadcopter.json").read_text(encoding="utf-8"))
    assert doc["kind"] == "template" and doc["build_type"] == "quadcopter"
    motor = next(c for c in chunks if c["row_id"] == "motor")
    row = next(p for p in tpl["parts"] if p["row_id"] == "motor")
    assert motor["kb_ref"] == "kb://tpl_quadcopter#motor" and motor["meta"]["row"] == row
    assert motor["sha256"] == sha256_hex(canonical_json(row))
    assert chunks[0]["kb_ref"] == "kb://tpl_quadcopter" and chunks[0]["row_id"] is None


# --------------------------------------------------------------------------- SQLite store


def test_seed_creates_the_seven_tables_and_counts(store):
    counts = store.table_counts()
    assert set(counts) == set(s2.TABLES) and len(s2.TABLES) == 7
    assert counts["kb_chunks"] > 50 and counts["kb_docs"] >= 10


def test_fulltext_search_finds_the_12v_row_and_returns_its_sql(store):
    res = run(store.hybrid_search("12V servo power supply 5A"))
    assert isinstance(res, M.KbSearchResponse)
    refs = [c.kb_ref for c in res.chunks]
    assert "kb://so101_readme#L73" in refs[:3], refs
    assert "MATCH" in res.sql and "Full-text only" in res.sql and res.took_ms >= 0
    assert store.last_query["sql"] == res.sql


def test_kind_filter_restricts_to_templates(store):
    res = run(store.hybrid_search("small camera drone FPV quad", kind="template"))
    assert res.chunks and all(c.kb_ref.startswith("kb://tpl_") for c in res.chunks)
    assert res.chunks[0].kb_ref.startswith("kb://tpl_quadcopter")
    assert "kind = 'template'" in res.sql


def test_hybrid_fuses_vector_and_fulltext_ranks(tmp_path):
    vocab = ["servo", "battery", "camera"]

    def vec(text: str) -> list[float]:
        t = text.lower()
        return [float(t.count(w)) for w in vocab]

    async def embed(texts, is_query):
        return [vec(t) for t in texts]

    st = LiveKnowledgeStore(SqliteBackend(tmp_path / "h.sqlite"), embedder=embed)
    st.backend.apply_schema(3)
    st.seed()
    res = run(st.hybrid_search("battery connector"))
    assert "emb · @q" in res.sql and "0.7 * 1/(60 + vector_rank)" in res.sql
    assert res.chunks and res.chunks[0].score > 0.3 / 61  # both lists contributed to the top hit
    assert s2.fuse(["a", "b"], ["b", "a"]) == pytest.approx({"a": 0.7 / 62 + 0.3 / 61, "b": 0.7 / 61 + 0.3 / 62})
    st.close()


def test_load_template_round_trips_every_template_file(store):
    for path in sorted((KB / "templates").glob("*.json")):
        tpl = json.loads(path.read_text(encoding="utf-8"))
        got = store.load_template_sync(tpl["build_type"])
        assert got is not None and got["template"] == tpl, path.name
        assert "kind = 'template'" in got["sql"] and got["source"] == "sqlite"
        M.Template.model_validate(got["template"])
    assert store.load_template_sync("no_such_type") is None
    assert run(store.load_template("quadcopter"))["template"]["template_id"] == "tpl_quadcopter"


def test_resolve_kb_ref(store):
    r = store.resolve_kb_ref("kb://tpl_quadcopter#motor")
    assert r and r["meta"]["row"]["row_id"] == "motor" and r["kind"] == "template"
    assert store.resolve_kb_ref("kb://tpl_quadcopter#nope") is None
    assert MockKnowledgeStore().resolve_kb_ref("kb://waveshare_adapter#input_voltage")["doc_id"] == "waveshare_adapter"


def test_prices_latest_per_offer_age_and_median(store):
    base = {"run_id": "r_p", "bom_line_id": "b1", "store_id": "wowrobo", "action_level": "agent_cart", "currency": "USD",
            "units_per_pack": 1, "stock": "in_stock", "source_api": "shopify_ucp", "evidence_sha256": "ab" * 32}
    store.insert_price_observation_sync({**base, "offer_id": "o1", "title": "old", "price_usd": 20.0, "seen_at": "2026-11-20T13:00:00-08:00"})
    store.insert_price_observation_sync({**base, "offer_id": "o1", "title": "STS3215", "price_usd": 15.0, "seen_at": "2026-11-20T13:10:00-08:00"})
    store.insert_price_observation_sync({**base, "offer_id": "o2", "title": "B", "price_usd": 25.0, "seen_at": "2026-11-20T13:10:00-08:00"})
    store.insert_price_observation_sync({**base, "offer_id": "o3", "store_id": "alibaba", "title": "refused", "price_usd": 5.0,
                                         "seen_at": "2026-11-20T13:10:00-08:00", "refused": "merchant_not_in_mandate"})
    from datetime import datetime

    res = store.prices_sync("r_p", "b1", now=datetime.fromisoformat("2026-11-20T13:40:00-08:00"))
    assert isinstance(res, M.PricesResponse)
    by_title = {r.title: r for r in res.rows}
    assert set(by_title) == {"STS3215", "B", "refused"}  # latest observation per offer only
    assert by_title["STS3215"].age_min == 30.0 and by_title["STS3215"].vs_median_pct == -25.0  # median of allowed = 20
    assert by_title["refused"].refused is True
    assert "MAX(seen_at)" in res.sql and "'r_p'" in res.sql


def test_price_observations_never_store_buyer_fields(store):
    store.insert_price_observation_sync({"run_id": "r_p", "bom_line_id": "b1", "offer_id": "o9", "store_id": "x", "price_usd": 1.0,
                                         "seen_at": "2026-11-20T13:00:00-08:00", "email": "a@b.example", "address": "1 Main St"})
    dump = json.dumps(store.backend.query("SELECT * FROM price_observations"))
    assert "a@b.example" not in dump and "Main St" not in dump


def test_audit_mandates_runs_round_trip(store):
    from app.audit import chain

    chain.STORE.reset("r_au")
    recs = [chain.STORE.append("r_au", "intake", {"n": i}) for i in range(3)]
    for r in recs:
        store.insert_audit_sync(r)
    assert store.audit_events_sync("r_au") == recs
    store.insert_mandate_sync({"mandate_id": "m_1", "run_id": "r_au", "type": "b2c.mandate.open", "body": {"a": 1}, "sha256": "00"})
    assert store.mandates_sync("r_au")[0]["body"] == {"a": 1}
    store.upsert_run_sync("r_au", build_type="quadcopter", status="running")
    store.upsert_run_sync("r_au", status="done", total_usd=99.5)
    rows = store.backend.query("SELECT * FROM runs")
    assert len(rows) == 1 and rows[0]["status"] == "done" and rows[0]["build_type"] == "quadcopter"
    chain.STORE.reset("r_au")


def test_owned_parts_memory_fallback(store):
    mem = OwnedPartsMemory(store)
    run(mem.remember("owns a precision screwdriver set"))
    run(mem.remember("owns two USB-C data cables"))
    hits = run(mem.recall("Screwdriver Set"))
    assert hits and hits[0]["memory_text"] == "owns a precision screwdriver set" and hits[0]["provider"] == "owned_parts"
    assert run(mem.recall("brushless motor")) == []


def test_stats_shape_for_the_data_drawer(store):
    run(store.hybrid_search("XT60 connector"))
    st = store.stats()
    assert st["backend"] == "sqlite" and st["tables"]["kb_chunks"] > 0
    assert {"template", "rule_source", "doc", "reference"} <= set(st["kb_by_kind"])
    assert st["last_query"]["sql"] and st["simulated"] is False
    mock = MockKnowledgeStore().stats()
    assert mock["simulated"] is True and mock["backend"] == "mock"


def test_auto_seed_on_first_use_and_no_singlestore_url(tmp_path, monkeypatch):
    monkeypatch.delenv("S2_URL", raising=False)
    st = LiveKnowledgeStore(embedder=None, sqlite_path=tmp_path / "auto.sqlite")
    assert st.backend_name == "sqlite" and st.table_counts()["kb_chunks"] > 50
    st.close()


def test_unreachable_singlestore_falls_back_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("S2_URL", "user:pw@127.0.0.1:1/db")

    def boom(*a, **k):
        raise ConnectionError("refused")

    monkeypatch.setattr(s2, "SingleStoreBackend", boom)
    st = LiveKnowledgeStore(embedder=None, sqlite_path=tmp_path / "fb.sqlite")
    assert st.backend_name == "sqlite" and "SingleStore unreachable" in st.fallback_reason
    st.close()


def test_singlestore_sql_shapes_with_a_fake_connection(monkeypatch):
    """The SingleStore backend's SQL (no server): MATCH ... AGAINST with Lucene syntax, `<*>` with a cast."""
    seen: list[tuple[str, tuple]] = []

    class Cur:
        description = [("kb_ref",), ("doc_id",), ("chunk_id",), ("line_from",), ("line_to",), ("body",), ("meta",), ("s",)]

        def execute(self, sql, params=None):
            seen.append((sql, params))

        def fetchall(self):
            return [("kb://so101_readme#L73", "so101_readme", "L73", 20, 26, "12V 5A+", "{}", 1.0)]

        def close(self):
            pass

    b = object.__new__(s2.SingleStoreBackend)
    s2._Backend.__init__(b)
    b.embed_dim, b.conn, b._last_use, b._keepalive = 4, type("C", (), {"cursor": lambda self: Cur()})(), 0.0, None
    rows, sql = b.fulltext(["12v", "supply"], " AND kind = ?", ["doc"], 20)
    assert rows and "MATCH (TABLE kb_chunks) AGAINST ('body:(12v OR supply)')" in sql and "kind = 'doc'" in sql
    assert seen[-1][1] == ("body:(12v OR supply)", "body:(12v OR supply)", "doc")
    rows, sql = b.vector([0.1, 0.2, 0.3, 0.4], "", [], 20)
    assert "emb <*> (@q" in sql and ":> VECTOR(4)" in sql and json.loads(seen[-1][1][0]) == [0.1, 0.2, 0.3, 0.4]
    assert s2._lucene(["a:b", "c(d)"]) == r"body:(a\:b OR c\(d\))"
