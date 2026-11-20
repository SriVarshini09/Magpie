"""KB search "why this matched": query tokens, matched terms per chunk, and the rank in each half (PLAN §3.14).

SQLite FTS5 is the local stand-in for SingleStore; the SingleStore path (ANALYZE FULLTEXT, SingleStore 9.1+) is
tested with a fake `singlestoredb` connection because no cluster is available here.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import types

import pytest

from app.integrations import s2
from app.integrations.s2 import LiveKnowledgeStore, MockKnowledgeStore, SqliteBackend


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def store(tmp_path):
    st = LiveKnowledgeStore(SqliteBackend(tmp_path / "kb.sqlite"), embedder=None)
    st.backend.apply_schema(8)
    st.seed(embed=False)
    yield st
    st.close()


# --------------------------------------------------------------------------- tokenizers


SAMPLES = [
    "XT60 connector 4S", "Café naïve résumé", "5.5x2.1mm 12V/5A", "foo_bar e.g. U.S.A", "øre Æsir ß straße",
    "İstanbul ǅ", "café ée", "中文字符 テスト", "a·b c’d", "x­yz", "①② ٣٤ ½ ²", "ŁÓDŹ đ", "ÀÉÎÕÜ ÿ Ÿ",
    "ǖ ḗ ặ", "Ωmega ΆΈ σς", "x̀yͯz", "हिन्दी", "JST-XH 2.54 mm; 30 A (60 A burst)", "",
]


def test_fts5_tokens_match_sqlites_own_unicode61_tokenizer():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE t USING fts5(b)")
    con.execute("CREATE VIRTUAL TABLE v USING fts5vocab(t, instance)")
    for text in SAMPLES:
        con.execute("DELETE FROM t")
        con.execute("INSERT INTO t VALUES (?)", (text,))
        real = [r[0] for r in con.execute("SELECT term FROM v ORDER BY offset")]
        assert s2.fts5_tokens(text) == real, text
    con.close()


def test_standard_tokens_follow_lucene_standard_tokenizer_rules():
    # the docs' StandardAnalyzer example keeps stopwords: four tokens
    assert s2.standard_tokens("the train is moving") == ["the", "train", "is", "moving"]
    assert s2.standard_tokens("5.5x2.1mm 12V/5A") == ["5.5x2.1mm", "12v", "5a"]
    assert s2.standard_tokens("can't U.S.A e.g. 1,000.50 foo_bar v.2") == ["can't", "u.s.a", "e.g", "1,000.50", "foo_bar", "v", "2"]
    assert s2.standard_tokens("XT60 (60 A burst) 中文") == ["xt60", "60", "a", "burst", "中", "文"]
    assert s2.standard_tokens("") == []


# --------------------------------------------------------------------------- SQLite (what the demo shows)


def test_sqlite_fills_query_terms_matched_terms_and_ranks(store):
    res = store.hybrid_search_sync("XT60 connector for 4S")
    assert res.analyzer == "sqlite_fts5" and res.simulated is False
    assert res.query_terms == ["xt60", "connector", "4s"]  # "for" is a stopword, dropped before the MATCH
    assert "local stand-in for SingleStore ANALYZE FULLTEXT" in res.analyze_sql
    assert "kb_fts MATCH '\"xt60\" OR \"connector\" OR \"4s\"'" in res.analyze_sql
    assert res.chunks and res.chunks[0].kb_ref == "kb://electrical_notes#holybro_connector_table"
    assert res.chunks[0].matched_terms == ["xt60", "connector"]
    ft = [c.fulltext_rank for c in res.chunks]
    assert ft == sorted(ft) and ft[0] == 1 and len(set(ft)) == len(ft)
    assert all(c.vector_rank is None for c in res.chunks)  # no embedder: full-text only
    assert any("4s" in c.matched_terms for c in res.chunks)

    # matched_terms agree with SQLite's own index: a term is listed exactly when FTS5 matches it in that row
    con = store.backend.conn
    for c in res.chunks:
        for t in res.query_terms:
            hit = con.execute("SELECT 1 FROM kb_fts WHERE kb_fts MATCH ? AND kb_ref = ?", (f'"{t}"', c.kb_ref)).fetchone()
            assert (t in c.matched_terms) == bool(hit), (c.kb_ref, t)


def test_sqlite_splits_a_term_the_way_fts5_does(store):
    res = store.hybrid_search_sync("5.5x2.1 barrel jack")
    assert res.query_terms == ["5", "5x2", "1", "barrel", "jack"]  # FTS5 searched the phrase "5.5x2.1" as 5 5x2 1
    assert all(set(c.matched_terms) <= set(res.query_terms) for c in res.chunks)


def test_sqlite_no_terms_gives_empty_terms(store):
    res = store.hybrid_search_sync("the of and")
    assert res.chunks == [] and res.query_terms == [] and res.analyzer == "sqlite_fts5"
    assert res.analyze_sql == "-- full-text: no search terms"


def test_hybrid_ranks_explain_the_fused_score(tmp_path):
    vocab = ["servo", "battery", "connector"]

    async def embed(texts, is_query):
        return [[float(t.lower().count(w)) for w in vocab] for t in texts]

    st = LiveKnowledgeStore(SqliteBackend(tmp_path / "h.sqlite"), embedder=embed)
    st.backend.apply_schema(3)
    st.seed()
    res = run(st.hybrid_search("battery connector"))
    assert any(c.vector_rank and c.fulltext_rank for c in res.chunks)
    for c in res.chunks:
        assert c.vector_rank is not None or c.fulltext_rank is not None
        expect = (s2.W_VECTOR / (s2.RRF_K + c.vector_rank) if c.vector_rank else 0.0) + \
                 (s2.W_FULLTEXT / (s2.RRF_K + c.fulltext_rank) if c.fulltext_rank else 0.0)
        assert c.score == pytest.approx(round(expect, 5), abs=1e-5), c.kb_ref
    st.close()


# --------------------------------------------------------------------------- mock


def test_mock_fills_the_same_fields_from_its_own_text():
    res = run(MockKnowledgeStore().hybrid_search("12V servo power supply"))
    assert res.simulated is True and res.analyzer == "mock"
    assert res.query_terms == ["12v", "servo", "power", "supply"]
    assert res.analyze_sql.startswith("-- MOCK")
    by_ref = {c.kb_ref: c for c in res.chunks}
    readme = by_ref["kb://so101_readme#L73"]
    assert readme.matched_terms == ["12v", "power", "supply"] and readme.fulltext_rank == 1
    adapter = by_ref["kb://waveshare_adapter#input_voltage"]
    assert adapter.matched_terms == ["servo"] and adapter.fulltext_rank == 2  # "12.6V" is 12 + 6v, not 12v
    assert all(c.vector_rank is None for c in res.chunks)  # no vector half in mock mode

    none = run(MockKnowledgeStore().hybrid_search("XT60"))
    assert none.query_terms == ["xt60"] and all(not c.matched_terms and c.fulltext_rank is None for c in none.chunks)


def test_mock_route_serves_the_fields(client):
    body = client.get("/api/kb/search", params={"q": "12V supply"}).json()
    assert body["analyzer"] == "mock" and body["query_terms"] == ["12v", "supply"] and body["simulated"] is True
    assert body["chunks"][0]["matched_terms"] and "fulltext_rank" in body["chunks"][0]


# --------------------------------------------------------------------------- SingleStore with a fake connection

ROW = ("kb://electrical_notes#holybro_connector_table", "electrical_notes", "holybro_connector_table", 12, 18,
       "Electrical notes. Holybro's connector table rates the XT60 at 30 A continuous.", '{"text": "Holybro rates the XT60 at 30 A."}', 7.5)
ROW2 = ("kb://template_sources#px4_x500_v2", "template_sources", "px4_x500_v2", 3, 9,
        "PX4 X500 V2: 4S battery on an XT60.", "{}", 2.0)
FT_COLS = [("kb_ref",), ("doc_id",), ("chunk_id",), ("line_from",), ("line_to",), ("body",), ("meta",), ("s",)]


class ProgrammingError(Exception):
    pass


class OperationalError(Exception):
    pass


def _fake_singlestore(monkeypatch, analyze):
    """Install a fake `singlestoredb` whose cursor answers the full-text SELECT, the title lookup and ANALYZE FULLTEXT
    (`analyze(sql)` returns the Response cell, or raises)."""
    seen: list[tuple[str, object]] = []

    class Cur:
        description: list = []
        rows: list = []

        def execute(self, sql, params=None):
            seen.append((sql, params))
            if sql.startswith("ANALYZE FULLTEXT"):
                self.description, self.rows = [("Response",)], [(analyze(sql),)]
            elif "MATCH (TABLE kb_chunks)" in sql:
                self.description, self.rows = FT_COLS, [ROW, ROW2]
            elif "FROM kb_docs" in sql:
                self.description, self.rows = [("doc_id",), ("title",)], [("electrical_notes", "Electrical notes"),
                                                                          ("template_sources", "Template sources")]
            else:
                self.description, self.rows = [], []

        def fetchall(self):
            return list(self.rows)

        def close(self):
            pass

    class Conn:
        def cursor(self):
            return Cur()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "singlestoredb", types.SimpleNamespace(connect=lambda url, autocommit=True: Conn()))
    b = s2.SingleStoreBackend("singlestoredb://fake", 4)
    return LiveKnowledgeStore(b, embedder=None), seen


def _response(*tokens: str) -> str:
    out, off = [], 0
    for pos, t in enumerate(tokens):
        out.append({"position_length": 1, "end_offset": off + len(t), "start_offset": off, "position": pos, "type": "<ALPHANUM>", "token": t})
        off += len(t) + 1
    return json.dumps({"tokens": list(reversed(out))})  # out of order on purpose: sorted by position


def test_singlestore_uses_analyze_fulltext_tokens(monkeypatch):
    st, seen = _fake_singlestore(monkeypatch, lambda sql: _response("xt60", "connector", "4s"))
    res = st.hybrid_search_sync("XT60 connector for 4S")
    assert res.analyzer == "singlestore"
    assert res.analyze_sql == 'ANALYZE FULLTEXT "xt60 connector 4s"'
    assert ('ANALYZE FULLTEXT "xt60 connector 4s"', None) in seen  # sent as a literal, no driver parameters
    assert res.query_terms == ["xt60", "connector", "4s"]
    a, b = res.chunks
    assert (a.kb_ref, a.fulltext_rank, a.vector_rank, a.matched_terms) == (ROW[0], 1, None, ["xt60", "connector"])
    assert (b.kb_ref, b.fulltext_rank, b.matched_terms) == (ROW2[0], 2, ["xt60", "4s"])
    assert a.doc_title == "Electrical notes" and "MATCH (TABLE kb_chunks) AGAINST" in res.sql


def test_singlestore_analyze_accepts_bytes_and_parsed_json(monkeypatch):
    st, _ = _fake_singlestore(monkeypatch, lambda sql: _response("xt60").encode())
    assert st.hybrid_search_sync("XT60").query_terms == ["xt60"]
    st, _ = _fake_singlestore(monkeypatch, lambda sql: json.loads(_response("xt60")))
    assert st.hybrid_search_sync("XT60").analyzer == "singlestore"


def test_singlestore_rejecting_analyze_falls_back_to_python_and_remembers(monkeypatch):
    def reject(sql):
        raise ProgrammingError("(1064, \"You have an error in your SQL syntax near 'ANALYZE FULLTEXT'\")")

    st, seen = _fake_singlestore(monkeypatch, reject)
    res = st.hybrid_search_sync("XT60 connector for 4S")
    assert res.analyzer == "python (ANALYZE FULLTEXT unavailable)"
    assert res.query_terms == ["xt60", "connector", "4s"]
    assert "ANALYZE FULLTEXT unavailable on this server (ProgrammingError" in res.analyze_sql
    assert '-- ANALYZE FULLTEXT "xt60 connector 4s"' in res.analyze_sql
    assert res.chunks[0].matched_terms == ["xt60", "connector"] and res.chunks[0].fulltext_rank == 1
    tries = sum(1 for sql, _ in seen if sql.startswith("ANALYZE"))
    st.hybrid_search_sync("XT60")
    assert sum(1 for sql, _ in seen if sql.startswith("ANALYZE")) == tries == 1  # not sent again


def test_singlestore_connection_error_is_not_remembered(monkeypatch):
    def drop(sql):
        raise OperationalError("(2013, 'Lost connection')")

    st, seen = _fake_singlestore(monkeypatch, drop)
    assert st.hybrid_search_sync("XT60").analyzer.startswith("python")
    st.hybrid_search_sync("XT60")
    assert sum(1 for sql, _ in seen if sql.startswith("ANALYZE")) == 2


def test_singlestore_unrecognised_analyze_output_falls_back(monkeypatch):
    st, _ = _fake_singlestore(monkeypatch, lambda sql: "not json")
    res = st.hybrid_search_sync("XT60 connector")
    assert res.analyzer == "python (ANALYZE FULLTEXT unavailable)" and "no tokens list" in res.analyze_sql
    assert res.query_terms == ["xt60", "connector"]


def test_analyze_statement_escapes_quotes(monkeypatch):
    st, _ = _fake_singlestore(monkeypatch, lambda sql: _response())
    terms, analyzer, sql = st.backend.analyze(['say "hi"\\'])
    assert sql == 'ANALYZE FULLTEXT "say \\"hi\\"\\\\"' and analyzer == "singlestore" and terms == []
