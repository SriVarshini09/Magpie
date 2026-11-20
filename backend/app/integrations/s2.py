"""SingleStore: knowledge base (hybrid search), templates, price observations, audit sink (PLAN §3.14). Owner: D.

Three implementations of one interface:
  MockKnowledgeStore   DEMO_MODE=mock: fixtures, no database (labelled simulated)
  LiveKnowledgeStore   S2_URL set: SingleStore through `singlestoredb`
                       S2_URL empty (or SingleStore unreachable): SQLite at runs/b2c.sqlite with the same 7 tables,
                       an FTS5 index for full-text and Python dot products for vectors. The SQLite KB seeds itself
                       from data/kb on first use, so everything runs locally with no account.

Hybrid search (PLAN §3.14, "Plan B" form): one full-text SELECT and one vector SELECT, ranks fused in Python with
    score = 0.7 * 1/(60 + vector_rank) + 0.3 * 1/(60 + fulltext_rank)
The vector half runs only when an embedder is available (SIE `encode` live, or one passed in); otherwise the
search is full-text only and the SQL it returns says so. Every result carries the SQL text that ran.

Citations: `kb://<doc_id>#<chunk_id>`. KB markdown chunks start at `## chunk: <id>`; template rows are
`kb://tpl_<build_type>#<row_id>` and the template itself is `kb://tpl_<build_type>`.
No table ever holds buyer data.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import statistics
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from app import fixtures
from app.audit.chain import canonical_json, sha256_hex
from app.config import BACKEND_DIR, DATA_DIR
from app.models import KbChunk, KbSearchResponse, PriceRow, PricesResponse

KB_DIR = DATA_DIR / "kb"
TEMPLATES_DIR = KB_DIR / "templates"
SCHEMA_SQL = BACKEND_DIR / "scripts" / "s2_schema.sql"
TABLES = ("kb_docs", "kb_chunks", "price_observations", "audit_events", "mandates", "runs", "owned_parts")
RRF_K = 60
W_VECTOR, W_FULLTEXT = 0.7, 0.3
STOPWORDS = frozenset("a an and are as at be by for from has have i in is it my of on or the to with what which "
                      "do does need needs want build make small under over".split())
PRICE_COLUMNS = ("run_id", "bom_line_id", "offer_id", "store_id", "action_level", "title", "price_usd", "shipping_usd",
                 "rating", "currency", "units_per_pack", "stock", "seen_at", "source_api", "evidence_sha256", "refused",
                 "simulated")
_CHUNK_ID = re.compile(r"^## chunk:\s*([A-Za-z0-9_]+)\s*$")
_BULLET = re.compile(r"^- ([a-z_]+):\s*(.*)$")


# =========================================================================== KB documents -> rows


def parse_kb_markdown(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One KB markdown file -> (kb_docs row, kb_chunks rows). Format: see module docstring and data/kb/*.md."""
    raw = path.read_bytes()
    lines = raw.decode("utf-8").split("\n")
    front: dict[str, str] = {}
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            if ":" in lines[i]:
                k, v = lines[i].split(":", 1)
                front[k.strip()] = v.split("#", 1)[0].strip() if k.strip() == "kind" else v.strip()
            i += 1
        i += 1
    doc_id = front.get("doc_id") or path.stem
    title = front.get("title") or doc_id
    doc = {"doc_id": doc_id, "kind": front.get("kind") or "doc", "title": title, "source_url": front.get("source_url"),
           "licence": front.get("licence"), "commit_sha": front.get("commit_sha"), "sha256": sha256_hex(raw),
           "fetched_at": None, "via": "file", "build_type": front.get("build_type") or None}
    starts = [(n, m.group(1)) for n, line in enumerate(lines) if (m := _CHUNK_ID.match(line))]
    chunks = []
    for idx, (n, cid) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = lines[n + 1:end]
        while block and not block[-1].strip():
            block.pop()
        meta: dict[str, Any] = {}
        prose: list[str] = []
        for line in block:
            m = _BULLET.match(line)
            if m and not prose:
                key, val = m.group(1), m.group(2).strip()
                if key == "quote":
                    val = val.strip().strip('"')
                    meta.setdefault("quotes", []).append(val)
                elif key in meta:
                    meta[key] = meta[key] if isinstance(meta[key], list) else [meta[key]]
                    meta[key].append(val)
                else:
                    meta[key] = val
            elif line.strip():
                prose.append(line.strip())
        text = " ".join(prose)
        quotes = meta.get("quotes", [])
        display = text + ("" if not quotes else " Quoted: " + " · ".join(f'"{q}"' for q in quotes))
        rules = meta.get("rules") or meta.get("rule") or ""
        body = " ".join(x for x in (title + ".", cid.replace("_", " "), display, f"Rules: {rules}." if rules else "") if x)
        chunks.append({"chunk_id": cid, "doc_id": doc_id, "kb_ref": f"kb://{doc_id}#{cid}", "kind": doc["kind"],
                       "build_type": doc["build_type"], "row_id": None, "line_from": n + 1, "line_to": n + 1 + len(block),
                       "body": body, "meta": {"title": title, "text": display, **meta}, "sha256": sha256_hex(body)})
    return doc, chunks


def _row_lines(text_lines: list[str], row_id: str) -> tuple[int, int]:
    """1-based lines of a template row inside the "parts" array (best effort, for the citation's line range)."""
    start = next((n for n, line in enumerate(text_lines) if re.match(r'^\s*"parts"\s*:', line)), 0)
    pat = re.compile(r'"row_id"\s*:\s*"' + re.escape(row_id) + r'"')
    for n in range(start, len(text_lines)):
        if pat.search(text_lines[n]):
            lo = n
            while lo > start and not text_lines[lo].lstrip().startswith("{"):
                lo -= 1
            hi = n
            depth = 0
            for m in range(lo, len(text_lines)):
                depth += text_lines[m].count("{") - text_lines[m].count("}")
                if depth <= 0:
                    hi = m
                    break
            return lo + 1, hi + 1
    return 1, 1


def template_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One template JSON -> (kb_docs row, kb_chunks rows): a header chunk plus one chunk per part row."""
    raw = path.read_bytes()
    tpl = json.loads(raw.decode("utf-8"))
    text_lines = raw.decode("utf-8").split("\n")
    tid, bt = tpl["template_id"], tpl["build_type"]
    refs = tpl.get("references") or []
    licences = list(dict.fromkeys(r.get("licence") for r in refs if r.get("licence")))
    doc = {"doc_id": tid, "kind": "template", "title": tpl.get("title") or tid,
           "source_url": refs[0]["url"] if refs else None, "licence": "; ".join(licences) or None, "commit_sha": None,
           "sha256": sha256_hex(canonical_json(tpl)), "fetched_at": None, "via": "file", "build_type": bt}
    header = {k: v for k, v in tpl.items() if k != "parts"}
    names = ", ".join(p.get("name", p["row_id"]) for p in tpl.get("parts", []))
    head_body = f"{tpl.get('title')} template ({bt.replace('_', ' ')}). {tpl.get('summary', '')} Parts: {names}."
    chunks = [{"chunk_id": tid, "doc_id": tid, "kb_ref": f"kb://{tid}", "kind": "template", "build_type": bt, "row_id": None,
               "line_from": 1, "line_to": len(text_lines), "body": head_body,
               "meta": {"header": header, "title": tpl.get("title"), "text": head_body}, "sha256": doc["sha256"]}]
    for pos, row in enumerate(tpl.get("parts", [])):
        rid = row["row_id"]
        overrides = {v["id"]: v["overrides"][rid] for v in tpl.get("variants", []) if rid in (v.get("overrides") or {})}
        qty = row.get("qty")
        basis = row.get("basis")
        src = (row.get("source") or {}).get("url")
        sentence = (f"{tpl.get('title')} template, row {rid}: {qty if qty is not None else 'unknown number of'} × "
                    f"{row.get('name')} ({row.get('category')}). Typical spec: {row.get('typical_spec') or 'not stated'}. "
                    f"Basis: {'rule of thumb' if basis == 'rule_of_thumb' else basis}."
                    + (f" Source: {src}." if src else "")
                    + (f" Rules: {', '.join(row['rules'])}." if row.get("rules") else ""))
        lo, hi = _row_lines(text_lines, rid)
        chunks.append({"chunk_id": rid, "doc_id": tid, "kb_ref": f"kb://{tid}#{rid}", "kind": "template", "build_type": bt,
                       "row_id": rid, "line_from": lo, "line_to": hi, "body": sentence,
                       "meta": {"row": row, "position": pos, "variants": overrides, "template_id": tid,
                                "title": tpl.get("title"), "text": sentence},
                       "sha256": sha256_hex(canonical_json(row))})
    return doc, chunks


def load_kb_dir(kb_dir: Path = KB_DIR) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every KB markdown file and template under data/kb -> (docs, chunks). Duplicate kb_refs are an error."""
    docs, chunks = [], []
    for path in sorted(kb_dir.glob("*.md")):
        d, c = parse_kb_markdown(path)
        docs.append(d)
        chunks += c
    for path in sorted((kb_dir / "templates").glob("*.json")):
        d, c = template_rows(path)
        docs.append(d)
        chunks += c
    seen: dict[str, str] = {}
    for c in chunks:
        if c["kb_ref"] in seen:
            raise ValueError(f"duplicate kb_ref {c['kb_ref']}")
        seen[c["kb_ref"]] = c["doc_id"]
    return docs, chunks


def search_terms(query: str) -> list[str]:
    """Search words: lower-case, stopwords dropped, kept in order, deduplicated. "12V" and "5.5x2.1" stay whole."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9.+×x\-]*[A-Za-z0-9]|[A-Za-z0-9]", query or "")
    out: list[str] = []
    for w in words:
        lw = w.lower()
        if lw in STOPWORDS or lw in out:
            continue
        out.append(lw)
    return out[:12]


def _lucene(terms: list[str]) -> str:
    """SingleStore FULLTEXT VERSION 2 query (Lucene syntax), every term escaped."""
    esc = [re.sub(r'([+\-!(){}\[\]^"~*?:\\/&|])', r"\\\1", t) for t in terms]
    return "body:(" + " OR ".join(esc) + ")"


def _fts5(terms: list[str]) -> str:
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)


def _sql_lit(s: str) -> str:
    return "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


# =========================================================================== "why this matched": index tokens
# The full-text half searches index tokens, not words. These helpers split text the way each index does, so a
# result can say which of the query's tokens it holds (KbChunk.matched_terms) and how the query was split
# (KbSearchResponse.query_terms).


def _dedupe(tokens: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(t for t in tokens if t))


_DIACRITIC_MASKS = (0x08029FDF, 0x000361F8)  # sqlite3Fts5UnicodeIsdiacritic: U+0300..U+0331, masked


def _is_diacritic(cp: int) -> bool:
    if cp < 0x300 or cp > 0x331:
        return False
    return bool((_DIACRITIC_MASKS[0] >> (cp - 0x300)) & 1) if cp < 0x320 else bool((_DIACRITIC_MASKS[1] >> (cp - 0x320)) & 1)


def _fts5_fold(ch: str) -> str | None:
    """One character as FTS5's unicode61 tokenizer sees it with its defaults (categories "L* N* Co", remove_diacritics=1):
    None for a separator, else the folded text ("" for a combining diacritic, which joins but adds nothing)."""
    cp = ord(ch)
    if cp < 128:
        return ch.lower() if ch.isalnum() else None
    if _is_diacritic(cp):
        return ""
    cat = unicodedata.category(ch)
    if cat[0] not in "LN" and cat not in ("Co", "Cn"):
        return None
    lo = ch.lower()[:1] or ch  # "İ".lower() is "i" + U+0307
    if lo == "ς":
        return "σ"
    d = unicodedata.normalize("NFD", lo)
    if len(d) == 2 and _is_diacritic(ord(d[1])) and unicodedata.name(d[0], "").startswith("LATIN"):
        return d[0]  # remove_diacritics=1: a Latin letter with one diacritic becomes its base letter
    return lo


def fts5_tokens(text: str) -> list[str]:
    """`text` split as SQLite FTS5's default unicode61 tokenizer splits it: lower-case, split on everything that is
    not a letter or a number, diacritics removed from Latin letters ("5.5x2.1mm" -> 5, 5x2, 1mm; "Café" -> cafe).
    tests/test_kb_why_matched.py checks it against SQLite's own tokenizer (fts5vocab)."""
    out: list[str] = []
    cur: list[str] = []
    for ch in text or "":
        f = _fts5_fold(ch)
        if f is None:
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(f)
    if cur:
        out.append("".join(cur))
    return [t for t in out if t]


# UAX #29 word-break classes, the part Lucene's StandardTokenizer uses for Latin-script text.
_MID_LETTER = frozenset(":··״‧︓﹕：")
_MID_NUM_LET = frozenset(".'‘’․﹒＇．")
_MID_NUM = frozenset(",;;։،؍٬߸⁄︐︔﹐﹔，；")


def _wb_class(ch: str) -> str:
    """L letter, N number, E ExtendNumLet ("_"), X extend/format (joins the previous char), I one-char token
    (ideograph, hiragana), ML / MNL / MN the mid-word punctuation classes, O anything else (a break)."""
    if ch in _MID_NUM_LET:
        return "MNL"
    if ch in _MID_LETTER:
        return "ML"
    if ch in _MID_NUM:
        return "MN"
    cat = unicodedata.category(ch)
    if cat == "Nd":
        return "N"
    if cat[0] == "L" or cat == "Nl":
        cp = ord(ch)
        if 0x3040 <= cp <= 0x309F or 0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
            return "I"
        return "L"
    if cat == "Pc":
        return "E"
    if cat[0] == "M" or cat == "Cf":
        return "X"
    return "O"


def standard_tokens(text: str) -> list[str]:
    """Approximation of Lucene's StandardAnalyzer (StandardTokenizer = UAX #29 word boundaries, then lower-case), the
    analyzer of SingleStore's FULLTEXT VERSION 2 index when none is set: "5.5x2.1mm" and "can't" stay whole,
    "12V/5A" -> 12v, 5a. Used for each result chunk's tokens on SingleStore, and for the query only when the server
    has no ANALYZE FULLTEXT. Not exact for scripts that need a dictionary (Thai) or for emoji."""
    s = text or ""
    n = len(s)
    cls = [_wb_class(c) for c in s]

    def next_main(j: int) -> tuple[int, str]:
        while j < n and cls[j] == "X":
            j += 1
        return j, (cls[j] if j < n else "O")

    out: list[str] = []
    i = 0
    while i < n:
        c = cls[i]
        if c == "I":
            out.append(s[i])
            i += 1
            continue
        if c not in ("L", "N", "E"):
            i += 1
            continue
        start, prev, j = i, c, i + 1
        while j < n:
            cj = cls[j]
            if cj == "X":
                j += 1
            elif cj in ("L", "N", "E"):
                prev, j = cj, j + 1
            elif (cj in ("ML", "MNL") and prev == "L") or (cj in ("MN", "MNL") and prev == "N"):
                k, ck = next_main(j + 1)
                if ck != prev:
                    break
                j = k
            else:
                break
        tok = s[start:j]
        if any(ch.isalnum() for ch in tok):
            out.append(tok.lower())
        i = j
    return out


def _analyze_response_tokens(rows: list[dict[str, Any]]) -> list[str] | None:
    """Tokens from ANALYZE FULLTEXT's result: one row whose one column (`Response`) holds JSON
    {"tokens": [{"token", "position", "position_length", "type", "start_offset", "end_offset"}, ...]}.
    Returns them in position order, or None when the result does not have that shape."""
    found: list[dict[str, Any]] | None = None
    for r in rows:
        for v in r.values():
            if isinstance(v, (bytes, bytearray)):
                v = v.decode("utf-8", "replace")
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except ValueError:
                    continue
            if isinstance(v, dict) and isinstance(v.get("tokens"), list):
                found = (found or []) + [t for t in v["tokens"] if isinstance(t, dict) and isinstance(t.get("token"), str)]
    if found is None:
        return None
    found.sort(key=lambda t: t["position"] if isinstance(t.get("position"), int) else 0)
    return [t["token"] for t in found]


def fuse(ft: list[str], vs: list[str]) -> dict[str, float]:
    """Weighted reciprocal-rank fusion over kb_refs (1-based ranks)."""
    scores: dict[str, float] = {}
    for rank, ref in enumerate(vs, 1):
        scores[ref] = scores.get(ref, 0.0) + W_VECTOR / (RRF_K + rank)
    for rank, ref in enumerate(ft, 1):
        scores[ref] = scores.get(ref, 0.0) + W_FULLTEXT / (RRF_K + rank)
    return scores


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_min(seen_at: str, now: datetime | None = None) -> float:
    try:
        seen = datetime.fromisoformat(seen_at)
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
        return round(max(0.0, ((now or _now()) - seen).total_seconds() / 60), 1)
    except ValueError:
        return 0.0


# =========================================================================== backends


class _Backend:
    """What differs between SingleStore and SQLite. Everything else is in LiveKnowledgeStore."""

    name = "?"
    ph = "?"

    def __init__(self) -> None:
        self.lock = threading.RLock()

    def q(self, sql: str) -> str:
        return sql if self.ph == "?" else sql.replace("?", "%s")

    def execute(self, sql: str, params: tuple | list = ()) -> None: ...

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        for r in rows:
            self.execute(sql, r)

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]: ...

    def apply_schema(self, embed_dim: int) -> None: ...

    def insert_chunks(self, chunks: list[dict[str, Any]], embs: list[list[float] | None]) -> None: ...

    def delete_doc(self, doc_id: str) -> None: ...

    def fulltext(self, terms: list[str], where: str, params: list, limit: int) -> tuple[list[dict[str, Any]], str]: ...

    def vector(self, qvec: list[float], where: str, params: list, limit: int) -> tuple[list[dict[str, Any]], str]: ...

    def analyze(self, terms: list[str]) -> tuple[list[str], str, str]:
        """(query_terms, analyzer, analyze_sql): the index tokens the full-text half searched for, who split them,
        and the statement (or note) that did it."""
        return _dedupe(standard_tokens(" ".join(terms))), "python", "-- query split in Python (Lucene StandardTokenizer rules)"

    def index_tokens(self, text: str) -> set[str]:
        """The tokens this backend's full-text index holds for `text` (for KbChunk.matched_terms)."""
        return set(standard_tokens(text))

    def close(self) -> None: ...


class SqliteBackend(_Backend):
    name = "sqlite"
    ph = "?"

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL" if self.path != ":memory:" else "PRAGMA journal_mode=MEMORY")

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        with self.lock:
            self.conn.execute(sql, tuple(params))

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        with self.lock:
            self.conn.executemany(sql, rows)

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]

    def apply_schema(self, embed_dim: int) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS kb_docs (doc_id TEXT NOT NULL, kind TEXT NOT NULL, title TEXT, source_url TEXT, licence TEXT,
          commit_sha TEXT, sha256 TEXT, fetched_at TEXT, via TEXT, build_type TEXT);
        CREATE TABLE IF NOT EXISTS kb_chunks (chunk_id TEXT NOT NULL, doc_id TEXT NOT NULL, kb_ref TEXT NOT NULL, kind TEXT NOT NULL,
          build_type TEXT, row_id TEXT, line_from INTEGER, line_to INTEGER, body TEXT NOT NULL, meta TEXT, sha256 TEXT, emb TEXT);
        CREATE INDEX IF NOT EXISTS kb_chunks_ref ON kb_chunks (kb_ref);
        CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(kb_ref UNINDEXED, body);
        CREATE TABLE IF NOT EXISTS price_observations (run_id TEXT NOT NULL, bom_line_id TEXT NOT NULL, offer_id TEXT NOT NULL,
          store_id TEXT NOT NULL, action_level TEXT, title TEXT, price_usd REAL, shipping_usd REAL, rating REAL, currency TEXT,
          units_per_pack INTEGER, stock TEXT, seen_at TEXT NOT NULL, source_api TEXT, evidence_sha256 TEXT, refused TEXT,
          simulated INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS price_obs_line ON price_observations (run_id, bom_line_id);
        CREATE TABLE IF NOT EXISTS audit_events (run_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL, ts TEXT NOT NULL,
          record TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS audit_run ON audit_events (run_id, seq);
        CREATE TABLE IF NOT EXISTS mandates (mandate_id TEXT NOT NULL, run_id TEXT NOT NULL, type TEXT NOT NULL, body TEXT NOT NULL,
          sha256 TEXT NOT NULL, jws TEXT);
        CREATE TABLE IF NOT EXISTS runs (run_id TEXT NOT NULL, build_type TEXT, source_url TEXT, status TEXT, total_usd REAL, created_at TEXT);
        CREATE TABLE IF NOT EXISTS owned_parts (user_id TEXT NOT NULL, item TEXT NOT NULL, note TEXT, source TEXT, added_at TEXT);
        """
        with self.lock:
            self.conn.executescript(ddl)

    def insert_chunks(self, chunks: list[dict[str, Any]], embs: list[list[float] | None]) -> None:
        rows = [(c["chunk_id"], c["doc_id"], c["kb_ref"], c["kind"], c.get("build_type"), c.get("row_id"), c.get("line_from"),
                 c.get("line_to"), c["body"], json.dumps(c.get("meta") or {}, ensure_ascii=False), c.get("sha256"),
                 json.dumps(e) if e else None) for c, e in zip(chunks, embs)]
        with self.lock:
            self.conn.executemany("INSERT INTO kb_chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            self.conn.executemany("INSERT INTO kb_fts (kb_ref, body) VALUES (?, ?)", [(c["kb_ref"], c["body"]) for c in chunks])

    def delete_doc(self, doc_id: str) -> None:
        with self.lock:
            refs = [r[0] for r in self.conn.execute("SELECT kb_ref FROM kb_chunks WHERE doc_id = ?", (doc_id,))]
            self.conn.executemany("DELETE FROM kb_fts WHERE kb_ref = ?", [(r,) for r in refs])
            self.conn.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
            self.conn.execute("DELETE FROM kb_docs WHERE doc_id = ?", (doc_id,))

    def fulltext(self, terms: list[str], where: str, params: list, limit: int) -> tuple[list[dict[str, Any]], str]:
        if not terms:
            return [], "-- full-text: no search terms"
        match = _fts5(terms)
        sql = ("SELECT c.kb_ref, c.doc_id, c.chunk_id, c.line_from, c.line_to, c.body, c.meta, bm25(kb_fts) AS s "
               "FROM kb_fts JOIN kb_chunks c ON c.kb_ref = kb_fts.kb_ref "
               f"WHERE kb_fts MATCH ?{where} ORDER BY s ASC LIMIT {int(limit)}")
        rows = self.query(sql, [match, *params])
        shown = sql.replace("MATCH ?", f"MATCH {_sql_lit(match)}", 1)
        for p in params:
            shown = shown.replace("?", _sql_lit(p), 1)
        return rows, "-- full-text (SQLite FTS5 fallback; SingleStore uses MATCH (TABLE kb_chunks) AGAINST)\n" + shown

    def vector(self, qvec: list[float], where: str, params: list, limit: int) -> tuple[list[dict[str, Any]], str]:
        sql = f"SELECT kb_ref, doc_id, chunk_id, line_from, line_to, body, meta, emb FROM kb_chunks WHERE emb IS NOT NULL{where}"
        rows = []
        for r in self.query(sql, params):
            e = json.loads(r.pop("emb"))
            if len(e) == len(qvec):
                r["s"] = sum(a * b for a, b in zip(e, qvec))
                rows.append(r)
        rows.sort(key=lambda r: r["s"], reverse=True)
        shown = sql
        for p in params:
            shown = shown.replace("?", _sql_lit(p), 1)
        return rows[:limit], ("-- vector (SQLite fallback: dot product emb · @q computed in Python; SingleStore uses emb <*> @q)\n"
                              + shown + f" -- top {int(limit)} by dot product")

    def analyze(self, terms: list[str]) -> tuple[list[str], str, str]:
        """The local stand-in for SingleStore's ANALYZE FULLTEXT: FTS5 splits each quoted term of the MATCH expression
        with unicode61, so the same rules applied in Python give the tokens it searched for."""
        if not terms:
            return [], "sqlite_fts5", "-- full-text: no search terms"
        tokens = _dedupe(t for term in terms for t in fts5_tokens(term))
        return tokens, "sqlite_fts5", (
            "-- SQLite FTS5, the local stand-in for SingleStore ANALYZE FULLTEXT (no SingleStore in this run).\n"
            "-- Tokens: unicode61 rules (lower-case, split on non-alphanumerics, diacritics removed), applied in Python\n"
            f"-- to each phrase of the FTS5 query that ran:\nSELECT kb_ref FROM kb_fts WHERE kb_fts MATCH {_sql_lit(_fts5(terms))}")

    def index_tokens(self, text: str) -> set[str]:
        return set(fts5_tokens(text))

    def close(self) -> None:
        with self.lock:
            self.conn.close()


_S2_HOSTPART = re.compile(r"^(?P<host>[^:/@\s]+)(?::(?P<port>\d+))?(?:/(?P<database>[^/?#\s]+))?/?$")


def s2_url_parts(url: str) -> dict[str, Any] | None:
    """`user:password@host:port/db` (no scheme) as connect() fields, splitting at the LAST @ and the FIRST colon,
    so a password with @ : / # ? in it still works. None for a URL with a scheme (passed to connect() as is)."""
    url = (url or "").strip()
    if not url or "://" in url or "@" not in url:
        return None
    userinfo, _, hostpart = url.rpartition("@")
    user, sep, password = userinfo.partition(":")
    m = _S2_HOSTPART.match(hostpart)
    if not sep or not user or not m:
        return None
    out: dict[str, Any] = {"host": m["host"], "user": user, "password": password}
    if m["port"]:
        out["port"] = int(m["port"])
    if m["database"]:
        out["database"] = m["database"]
    return out


class SingleStoreBackend(_Backend):
    """SingleStore through `singlestoredb` (MySQL wire). The SQL shapes are [unverified] until check C11."""

    name = "singlestore"
    ph = "%s"

    def __init__(self, url: str, embed_dim: int) -> None:
        super().__init__()
        import singlestoredb  # lazy: a missing SDK breaks only this service

        self.embed_dim = embed_dim
        parts = s2_url_parts(url)
        # A generated password often holds @ : / # ?, which a URL cannot carry unencoded: connect by fields instead.
        self.conn = singlestoredb.connect(**parts, autocommit=True) if parts else singlestoredb.connect(url, autocommit=True)
        self._last_use = time.monotonic()
        self._keepalive: threading.Thread | None = None
        self._analyze_error: str | None = None  # set once the server rejects ANALYZE FULLTEXT (older than 9.1)

    def _cur(self):
        self._last_use = time.monotonic()
        return self.conn.cursor()

    def execute(self, sql: str, params: tuple | list = ()) -> None:
        with self.lock:
            cur = self._cur()
            cur.execute(sql, tuple(params) if params else None)
            cur.close()

    def executemany(self, sql: str, rows: list[tuple]) -> None:
        if not rows:
            return
        with self.lock:
            cur = self._cur()
            cur.executemany(sql, rows)
            cur.close()

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self.lock:
            cur = self._cur()
            cur.execute(sql, tuple(params) if params else None)
            cols = [d[0] for d in (cur.description or [])]
            out = [dict(zip(cols, r)) for r in cur.fetchall()]
            cur.close()
            return out

    def apply_schema(self, embed_dim: int) -> None:
        text = SCHEMA_SQL.read_text(encoding="utf-8").replace("VECTOR(1024)", f"VECTOR({int(embed_dim)})")
        text = "\n".join(line.split("--", 1)[0] for line in text.splitlines())
        for stmt in (s.strip() for s in text.split(";")):
            if stmt:
                self.execute(stmt)

    def insert_chunks(self, chunks: list[dict[str, Any]], embs: list[list[float] | None]) -> None:
        sql = "INSERT INTO kb_chunks (chunk_id, doc_id, kb_ref, kind, build_type, row_id, line_from, line_to, body, meta, sha256, emb) " \
              "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        rows = [(c["chunk_id"], c["doc_id"], c["kb_ref"], c["kind"], c.get("build_type"), c.get("row_id"), c.get("line_from"),
                 c.get("line_to"), c["body"], json.dumps(c.get("meta") or {}, ensure_ascii=False), c.get("sha256"),
                 json.dumps(e) if e else None) for c, e in zip(chunks, embs)]
        self.executemany(sql, rows)

    def delete_doc(self, doc_id: str) -> None:
        self.execute("DELETE FROM kb_chunks WHERE doc_id = %s", (doc_id,))
        self.execute("DELETE FROM kb_docs WHERE doc_id = %s", (doc_id,))

    def fulltext(self, terms: list[str], where: str, params: list, limit: int) -> tuple[list[dict[str, Any]], str]:
        if not terms:
            return [], "-- full-text: no search terms"
        against = _lucene(terms)
        sql = ("SELECT kb_ref, doc_id, chunk_id, line_from, line_to, body, meta, MATCH (TABLE kb_chunks) AGAINST (%s) AS s "
               f"FROM kb_chunks WHERE MATCH (TABLE kb_chunks) AGAINST (%s){where.replace('?', '%s')} "
               f"ORDER BY s DESC LIMIT {int(limit)}")
        rows = self.query(sql, [against, against, *params])
        shown = sql.replace("%s", _sql_lit(against), 2)
        for p in params:
            shown = shown.replace("%s", _sql_lit(p), 1)
        return rows, "-- full-text (FULLTEXT USING VERSION 2)\n" + shown

    def vector(self, qvec: list[float], where: str, params: list, limit: int) -> tuple[list[dict[str, Any]], str]:
        sql = (f"SELECT kb_ref, doc_id, chunk_id, line_from, line_to, body, meta, emb <*> (%s :> VECTOR({self.embed_dim})) AS s "
               f"FROM kb_chunks WHERE emb IS NOT NULL{where.replace('?', '%s')} ORDER BY s DESC LIMIT {int(limit)}")
        rows = self.query(sql, [json.dumps(qvec), *params])
        shown = sql.replace("%s", f"@q /* {len(qvec)}-dim query vector from SIE encode */", 1)
        for p in params:
            shown = shown.replace("%s", _sql_lit(p), 1)
        return rows, "-- vector (dot product, brute force, no vector index)\n" + shown

    # ANALYZE FULLTEXT (SingleStore 9.1+) shows the tokens a full-text analyzer makes of a string:
    #     ANALYZE FULLTEXT "<text>" [OPTIONS '<analyzer options>'];
    # It returns one row with one column, `Response`, holding JSON
    #     {"tokens": [{"token": "the", "position": 0, "position_length": 1, "type": "<ALPHANUM>",
    #                  "start_offset": 0, "end_offset": 3}, ...]}
    # Without OPTIONS it uses Lucene's StandardAnalyzer, the same analyzer kb_ft uses (s2_schema.sql sets no
    # INDEX_OPTIONS). If the index ever gets an analyzer, pass its INDEX_OPTIONS analyzer JSON here as OPTIONS.
    # Docs: https://docs.singlestore.com/db/v9.1/reference/sql-reference/full-text-search-functions/analyze-fulltext/
    #       https://docs.singlestore.com/db/v9.1/developer-resources/functional-extensions/full-text-version-2-custom-analyzers/
    # [unverified against a live server: no SingleStore cluster was available when this was written.]
    def analyze(self, terms: list[str]) -> tuple[list[str], str, str]:
        if not terms:
            return [], "singlestore", "-- full-text: no search terms"
        text = " ".join(terms)  # the words that went into AGAINST ('body:(... OR ...)'), stopwords already dropped
        stmt = 'ANALYZE FULLTEXT "' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
        why = getattr(self, "_analyze_error", None)
        if why is None:
            try:
                tokens = _analyze_response_tokens(self.query(stmt))
                if tokens is not None:
                    return _dedupe(tokens), "singlestore", stmt
                why = "its output had no tokens list"
            except Exception as exc:  # older server: syntax error. Connection errors are not remembered.
                why = f"{type(exc).__name__}: {str(exc)[:120]}".rstrip(": ")
                if type(exc).__name__ not in ("OperationalError", "InterfaceError"):
                    self._analyze_error = why
        return _dedupe(standard_tokens(text)), "python (ANALYZE FULLTEXT unavailable)", (
            f"-- ANALYZE FULLTEXT unavailable on this server ({why}).\n"
            "-- Tokens approximated in Python with Lucene StandardTokenizer rules (UAX #29 words, lower-cased). Tried:\n"
            f"-- {stmt}")

    def index_tokens(self, text: str) -> set[str]:
        return set(standard_tokens(text))  # approximation: one ANALYZE FULLTEXT per result row would cost a round trip each

    def ping(self) -> bool:
        try:
            self.query("SELECT 1 AS ok")
            return True
        except Exception:
            return False

    def start_keepalive(self, every_s: float = 60.0) -> None:
        """PLAN §3.14: idle free databases detach; a SELECT 1 every 60 s keeps the first real query fast."""
        if self._keepalive is not None:
            return

        def loop() -> None:
            while True:
                time.sleep(every_s)
                if time.monotonic() - self._last_use >= every_s * 0.9:
                    self.ping()

        self._keepalive = threading.Thread(target=loop, name="s2-keepalive", daemon=True)
        self._keepalive.start()

    def close(self) -> None:
        with self.lock:
            self.conn.close()


# =========================================================================== the store


class KnowledgeStore(Protocol):
    async def hybrid_search(self, query: str, kind: str | None = None) -> KbSearchResponse:
        """Full-text + vector search over kb_chunks. Returns the SQL text it ran."""
        ...

    async def prices(self, run_id: str, bom_line_id: str) -> PricesResponse: ...

    async def insert_audit(self, record: dict[str, Any]) -> None: ...

    async def insert_price_observation(self, row: dict[str, Any]) -> None: ...

    async def load_template(self, build_type: str) -> dict[str, Any] | None:
        """{"template": {...}, "sql": "...", "source": "singlestore" | "sqlite"} or None."""
        ...

    def resolve_kb_ref(self, kb_ref: str) -> dict[str, Any] | None: ...

    def stats(self) -> dict[str, Any]: ...


Embedder = Callable[[list[str], bool], Any]  # async (texts, is_query) -> list[list[float]]


def _sie_embedder() -> Embedder | None:
    """SIE `encode` when the sie service is live, else None (full-text only)."""
    try:
        from app import registry

        if registry.impl_mode("sie") != "live":
            return None
        sie = registry.get("sie")
        if not getattr(sie, "configured", lambda: True)():
            return None

        async def enc(texts: list[str], is_query: bool) -> list[list[float]]:
            return await sie.encode(texts, is_query=is_query)

        return enc
    except Exception:
        return None


def _run_coro(coro: Any) -> Any:
    """Run a coroutine from sync code (scripts, sinks). Inside a running loop, run it on a worker thread."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["v"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            box["e"] = exc

    t = threading.Thread(target=work)
    t.start()
    t.join()
    if "e" in box:
        raise box["e"]
    return box.get("v")


class LiveKnowledgeStore:
    """SingleStore when S2_URL is set and reachable, otherwise SQLite. One interface either way."""

    def __init__(self, backend: _Backend | None = None, *, embedder: Embedder | None | str = "auto",
                 sqlite_path: str | Path | None = None, auto_seed: bool = True) -> None:
        self._backend = backend
        self._embedder = embedder
        self._sqlite_path = sqlite_path
        self._auto_seed = auto_seed
        self._init_lock = threading.Lock()
        self.fallback_reason: str | None = None
        self.last_query: dict[str, Any] | None = None
        self.queries = 0

    # ------------------------------------------------------------------ setup

    @property
    def backend(self) -> _Backend:
        if self._backend is None:
            with self._init_lock:
                if self._backend is None:
                    self._backend = self._open()
        return self._backend

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def _open(self) -> _Backend:
        from app.config import get_settings

        dim = get_settings().embed_dim
        url = (os.getenv("S2_URL") or "").strip()
        if url:
            try:
                b = SingleStoreBackend(url, dim)
                b.apply_schema(dim)
                b.start_keepalive()
                return b
            except Exception as exc:  # PLAN §2.1 11:45 fallback: SQLite + local KB
                self.fallback_reason = f"SingleStore unreachable ({type(exc).__name__}); using SQLite"
        from app.audit.chain import runtime_dir

        path = self._sqlite_path or os.getenv("B2C_SQLITE_PATH") or (runtime_dir("runs") / "b2c.sqlite")
        b = SqliteBackend(path)
        b.apply_schema(dim)
        if self._auto_seed and not b.query("SELECT 1 AS x FROM kb_chunks LIMIT 1"):
            docs, chunks = load_kb_dir()
            self._seed_into(b, docs, chunks, [None] * len(chunks))
        return b

    def embedder(self) -> Embedder | None:
        if self._embedder == "auto":
            return _sie_embedder()
        return self._embedder  # type: ignore[return-value]

    # ------------------------------------------------------------------ seeding

    @staticmethod
    def _seed_into(b: _Backend, docs: list[dict[str, Any]], chunks: list[dict[str, Any]], embs: list[list[float] | None]) -> None:
        for d in docs:
            b.delete_doc(d["doc_id"])
        cols = ("doc_id", "kind", "title", "source_url", "licence", "commit_sha", "sha256", "fetched_at", "via", "build_type")
        b.executemany(b.q(f"INSERT INTO kb_docs ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"),
                      [tuple(d.get(c) for c in cols) for d in docs])
        b.insert_chunks(chunks, embs)
        if b.name == "singlestore":
            # New rows reach a FULLTEXT index only after a flush; without it full-text search finds nothing right after a seed.
            b.execute("OPTIMIZE TABLE kb_chunks FLUSH")

    def seed(self, docs: list[dict[str, Any]] | None = None, chunks: list[dict[str, Any]] | None = None, *,
             embed: bool = True, batch: int = 32) -> dict[str, Any]:
        """Replace the given documents (default: everything in data/kb) and their chunks. Embeds with SIE if live."""
        if docs is None or chunks is None:
            docs, chunks = load_kb_dir()
        embs: list[list[float] | None] = [None] * len(chunks)
        enc = self.embedder() if embed else None
        embedded = 0
        if enc is not None:
            async def embed_all() -> list[list[float]]:
                # One event loop for every batch: the SIE client keeps its HTTP session on the loop it was opened in.
                out: list[list[float]] = []
                for i in range(0, len(chunks), batch):
                    out.extend(await enc([c["body"] for c in chunks[i:i + batch]], False))
                return out

            for i, v in enumerate(_run_coro(embed_all())):
                if v and any(v):
                    embs[i] = [float(x) for x in v]
                    embedded += 1
        self._seed_into(self.backend, docs, chunks, embs)
        return {"backend": self.backend_name, "docs": len(docs), "chunks": len(chunks), "embedded": embedded}

    # ------------------------------------------------------------------ KB search

    def _where(self, kind: str | None, build_type: str | None, prefix: str = "") -> tuple[str, list]:
        where, params = "", []
        if kind:
            where += f" AND {prefix}kind = ?"
            params.append(kind)
        if build_type:
            where += f" AND {prefix}build_type = ?"
            params.append(build_type)
        return where, params

    async def hybrid_search(self, query: str, kind: str | None = None, *, build_type: str | None = None,
                            limit: int = 8) -> KbSearchResponse:
        t0 = time.perf_counter()
        qvec = None
        enc = self.embedder()
        note = ""
        if enc is not None:
            try:
                got = await enc([query], True)
                qvec = got[0] if got and got[0] and any(got[0]) else None
            except Exception as exc:  # PLAN §2.1 1:30 fallback: full-text only
                note = f"-- vector half skipped: {type(exc).__name__}\n"
        return self._search(query, kind, build_type, limit, qvec, t0, note)

    def hybrid_search_sync(self, query: str, kind: str | None = None, *, build_type: str | None = None,
                           limit: int = 8, query_vector: list[float] | None = None) -> KbSearchResponse:
        return self._search(query, kind, build_type, limit, query_vector, time.perf_counter(), "")

    def _search(self, query: str, kind: str | None, build_type: str | None, limit: int, qvec: list[float] | None,
                t0: float, note: str) -> KbSearchResponse:
        b = self.backend
        terms = search_terms(query)
        prefix = "c." if b.name == "sqlite" else ""
        where, params = self._where(kind, build_type, prefix)
        ft_rows, ft_sql = b.fulltext(terms, where, params, 20)
        vs_rows, vs_sql = [], "-- vector half: not run (no embedder: SIE not live). Full-text only."
        if qvec:
            vw, vp = self._where(kind, build_type)
            vs_rows, vs_sql = b.vector(qvec, vw, vp, 20)
        by_ref = {r["kb_ref"]: r for r in ft_rows + vs_rows}
        scores = fuse([r["kb_ref"] for r in ft_rows], [r["kb_ref"] for r in vs_rows])
        top = sorted(scores, key=lambda ref: scores[ref], reverse=True)[:limit]
        titles = self._doc_titles({by_ref[ref]["doc_id"] for ref in top})
        sql = (note + ft_sql + ";\n" + vs_sql + ";\n-- fused in Python: 0.7 * 1/(60 + vector_rank) + 0.3 * 1/(60 + fulltext_rank)")
        # "Why this matched": how the index split the query, which of those tokens each row's indexed body holds,
        # and the row's 1-based rank in each half (None when it was not in that half's top 20).
        query_terms, analyzer, analyze_sql = b.analyze(terms)
        ft_rank: dict[str, int] = {}
        vs_rank: dict[str, int] = {}
        for n, r in enumerate(ft_rows, 1):
            ft_rank.setdefault(r["kb_ref"], n)
        for n, r in enumerate(vs_rows, 1):
            vs_rank.setdefault(r["kb_ref"], n)
        chunks = []
        for ref in top:
            r = by_ref[ref]
            meta = json.loads(r["meta"]) if isinstance(r.get("meta"), str) else (r.get("meta") or {})
            held = b.index_tokens(r.get("body") or "")
            chunks.append(KbChunk(kb_ref=ref, doc_title=titles.get(r["doc_id"], r["doc_id"]), line_from=int(r.get("line_from") or 0),
                                  line_to=int(r.get("line_to") or 0), text=meta.get("text") or r["body"],
                                  score=round(scores[ref], 5), sql=None, matched_terms=[t for t in query_terms if t in held],
                                  vector_rank=vs_rank.get(ref), fulltext_rank=ft_rank.get(ref)))
        took = int((time.perf_counter() - t0) * 1000)
        self.queries += 1
        self.last_query = {"sql": sql, "took_ms": took, "at": _now().astimezone().isoformat(timespec="seconds"),
                           "query": query[:200], "backend": b.name}
        return KbSearchResponse(sql=sql, took_ms=took, chunks=chunks, query_terms=query_terms, analyzer=analyzer,
                                analyze_sql=analyze_sql, simulated=False)

    def _doc_titles(self, doc_ids: set[str]) -> dict[str, str]:
        if not doc_ids:
            return {}
        b = self.backend
        ids = sorted(doc_ids)
        rows = b.query(b.q(f"SELECT doc_id, title FROM kb_docs WHERE doc_id IN ({', '.join('?' * len(ids))})"), ids)
        return {r["doc_id"]: r["title"] for r in rows}

    def resolve_kb_ref(self, kb_ref: str) -> dict[str, Any] | None:
        """The kb_chunks row for a citation, with `meta` parsed, or None. Used by A's template_row check."""
        b = self.backend
        rows = b.query(b.q("SELECT kb_ref, doc_id, chunk_id, row_id, line_from, line_to, body, meta, sha256, kind "
                           "FROM kb_chunks WHERE kb_ref = ?"), [kb_ref])
        if not rows:
            return None
        r = rows[0]
        r["meta"] = json.loads(r["meta"]) if isinstance(r.get("meta"), str) else (r.get("meta") or {})
        return r

    # ------------------------------------------------------------------ templates

    def load_template_sync(self, build_type: str) -> dict[str, Any] | None:
        b = self.backend
        sql = b.q("SELECT kb_ref, row_id, meta FROM kb_chunks WHERE kind = 'template' AND build_type = ? ORDER BY line_from")
        rows = b.query(sql, [build_type])
        header = next((json.loads(r["meta"]) if isinstance(r["meta"], str) else r["meta"] for r in rows if not r["row_id"]), None)
        if header is None:
            return None
        parts = []
        for r in rows:
            if r["row_id"]:
                meta = json.loads(r["meta"]) if isinstance(r["meta"], str) else r["meta"]
                parts.append((meta.get("position", 0), meta["row"]))
        tpl = dict(header["header"])
        tpl["parts"] = [row for _, row in sorted(parts, key=lambda x: x[0])]
        shown = sql.replace("?", _sql_lit(build_type), 1) if b.ph == "?" else sql.replace("%s", _sql_lit(build_type), 1)
        self.queries += 1
        self.last_query = {"sql": shown, "took_ms": 0, "at": _now().astimezone().isoformat(timespec="seconds"),
                           "query": f"template {build_type}", "backend": b.name}
        return {"template": tpl, "sql": shown, "source": b.name, "simulated": False}

    async def load_template(self, build_type: str) -> dict[str, Any] | None:
        return self.load_template_sync(build_type)

    # ------------------------------------------------------------------ prices

    def insert_price_observation_sync(self, row: dict[str, Any]) -> None:
        r = {k: row.get(k) for k in PRICE_COLUMNS}  # allow-list: no buyer field can get in
        if not r["run_id"] or not r["offer_id"] or not r["seen_at"]:
            raise ValueError("price observation needs run_id, offer_id and seen_at")
        if isinstance(r.get("refused"), bool):
            r["refused"] = "refused" if r["refused"] else None
        r["simulated"] = 1 if r.get("simulated") else 0
        r["store_id"] = r["store_id"] or "unknown"
        r["bom_line_id"] = r["bom_line_id"] or "?"
        b = self.backend
        b.execute(b.q(f"INSERT INTO price_observations ({', '.join(PRICE_COLUMNS)}) VALUES ({', '.join('?' * len(PRICE_COLUMNS))})"),
                  [r[k] for k in PRICE_COLUMNS])

    async def insert_price_observation(self, row: dict[str, Any]) -> None:
        self.insert_price_observation_sync(row)

    def insert_offers_sync(self, run_id: str, bom_line_id: str, offers: list[Any]) -> int:
        """Every offer returned by search_offers -> price_observations (refused ones too, as evidence)."""
        n = 0
        for o in offers:
            d = o.model_dump(mode="json") if hasattr(o, "model_dump") else dict(o)
            self.insert_price_observation_sync({**d, "run_id": run_id, "bom_line_id": bom_line_id})
            n += 1
        return n

    def prices_sync(self, run_id: str, bom_line_id: str, *, now: datetime | None = None) -> PricesResponse:
        """Latest observation per offer for one BOM line, with age in minutes and distance from the median."""
        b = self.backend
        sql = ("SELECT p.store_id, p.title, p.price_usd, p.seen_at, p.source_api, p.refused, p.simulated, p.offer_id "
               "FROM price_observations p JOIN (SELECT offer_id, MAX(seen_at) AS last_seen FROM price_observations "
               "WHERE run_id = ? AND bom_line_id = ? GROUP BY offer_id) l ON p.offer_id = l.offer_id AND p.seen_at = l.last_seen "
               "WHERE p.run_id = ? AND p.bom_line_id = ? ORDER BY p.price_usd")
        rows = b.query(b.q(sql), [run_id, bom_line_id, run_id, bom_line_id])
        allowed = [float(r["price_usd"]) for r in rows if r["price_usd"] is not None and not r["refused"]]
        median = statistics.median(allowed) if allowed else None
        out = []
        for r in rows:
            price = float(r["price_usd"] or 0.0)
            vs = round((price - median) / median * 100, 1) if median else 0.0
            out.append(PriceRow(store_id=r["store_id"], title=r["title"] or "", price_usd=price, seen_at=r["seen_at"],
                                age_min=_age_min(r["seen_at"], now), vs_median_pct=vs, source_api=r["source_api"] or "",
                                refused=bool(r["refused"]), simulated=bool(r["simulated"])))
        shown = sql
        for p in (run_id, bom_line_id, run_id, bom_line_id):
            shown = shown.replace("?", _sql_lit(p), 1)
        shown += ";\n-- age_min and vs_median_pct (median of allowed offers) computed in Python"
        self.queries += 1
        self.last_query = {"sql": shown, "took_ms": 0, "at": _now().astimezone().isoformat(timespec="seconds"),
                           "query": f"prices {run_id}/{bom_line_id}", "backend": b.name}
        return PricesResponse(sql=shown, rows=out, simulated=any(r.simulated for r in out))

    async def prices(self, run_id: str, bom_line_id: str) -> PricesResponse:
        return self.prices_sync(run_id, bom_line_id)

    # ------------------------------------------------------------------ audit, mandates, runs

    def insert_audit_sync(self, record: dict[str, Any]) -> None:
        b = self.backend
        b.execute(b.q("INSERT INTO audit_events (run_id, seq, kind, ts, record, prev_hash, hash) VALUES (?,?,?,?,?,?,?)"),
                  [record["run_id"], int(record["seq"]), record["kind"], record.get("ts") or "", canonical_json(record),
                   record["prev_hash"], record["hash"]])

    async def insert_audit(self, record: dict[str, Any]) -> None:
        self.insert_audit_sync(record)

    def audit_events_sync(self, run_id: str) -> list[dict[str, Any]]:
        b = self.backend
        rows = b.query(b.q("SELECT record FROM audit_events WHERE run_id = ? ORDER BY seq"), [run_id])
        return [json.loads(r["record"]) if isinstance(r["record"], str) else r["record"] for r in rows]

    def insert_mandate_sync(self, row: dict[str, Any]) -> None:
        b = self.backend
        b.execute(b.q("INSERT INTO mandates (mandate_id, run_id, type, body, sha256, jws) VALUES (?,?,?,?,?,?)"),
                  [row["mandate_id"], row["run_id"], row["type"], canonical_json(row["body"]), row["sha256"], row.get("jws")])

    def mandates_sync(self, run_id: str) -> list[dict[str, Any]]:
        b = self.backend
        rows = b.query(b.q("SELECT mandate_id, type, body, sha256 FROM mandates WHERE run_id = ?"), [run_id])
        return [{**r, "body": json.loads(r["body"]) if isinstance(r["body"], str) else r["body"]} for r in rows]

    def upsert_run_sync(self, run_id: str, *, build_type: str | None = None, source_url: str | None = None,
                        status: str | None = None, total_usd: float | None = None, created_at: str | None = None) -> None:
        b = self.backend
        old = b.query(b.q("SELECT * FROM runs WHERE run_id = ?"), [run_id])
        cur = old[0] if old else {}
        b.execute(b.q("DELETE FROM runs WHERE run_id = ?"), [run_id])  # columnstore: no unique key to upsert on
        b.execute(b.q("INSERT INTO runs (run_id, build_type, source_url, status, total_usd, created_at) VALUES (?,?,?,?,?,?)"),
                  [run_id, build_type or cur.get("build_type"), source_url or cur.get("source_url"), status or cur.get("status"),
                   total_usd if total_usd is not None else cur.get("total_usd"),
                   created_at or cur.get("created_at") or _now().astimezone().isoformat(timespec="seconds")])

    # ------------------------------------------------------------------ owned parts (Cognee fallback)

    def add_owned_sync(self, item: str, *, user_id: str = "demo_user", note: str | None = None, source: str = "user") -> None:
        b = self.backend
        b.execute(b.q("INSERT INTO owned_parts (user_id, item, note, source, added_at) VALUES (?,?,?,?,?)"),
                  [user_id, item, note, source, _now().astimezone().isoformat(timespec="seconds")])

    def owned_sync(self, user_id: str = "demo_user") -> list[dict[str, Any]]:
        b = self.backend
        return b.query(b.q("SELECT item, note, source, added_at FROM owned_parts WHERE user_id = ? ORDER BY added_at"), [user_id])

    # ------------------------------------------------------------------ data drawer

    def table_counts(self) -> dict[str, int]:
        b = self.backend
        return {t: int(b.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]) for t in TABLES}

    def stats(self) -> dict[str, Any]:
        """`GET /api/data/stats` body (requested route): row counts, KB rows by kind, last query, SIE table."""
        b = self.backend
        by_kind = {r["kind"]: int(r["n"]) for r in b.query("SELECT kind, COUNT(*) AS n FROM kb_chunks GROUP BY kind")}
        try:
            from app.integrations import sie as sie_mod

            sie_rows = sie_mod.call_table()
        except Exception:
            sie_rows = []
        try:
            from app.audit.chain import SINK_ERRORS

            sink = {k: v for k, v in SINK_ERRORS.items() if isinstance(v, int)}
        except Exception:
            sink = {}
        return {"backend": b.name, "tables": self.table_counts(), "kb_by_kind": by_kind, "last_query": self.last_query,
                "sie": sie_rows, "queries": self.queries, "fallback_reason": self.fallback_reason, "sink_errors": sink,
                "simulated": False}

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
            self._backend = None


class MockKnowledgeStore:
    """DEMO_MODE=mock: answers from fixtures; writes nothing. Everything it returns is labelled simulated."""

    backend_name = "mock"

    async def hybrid_search(self, query: str, kind: str | None = None, **_: Any) -> KbSearchResponse:
        """The fixture rows, with "why this matched" computed from their own text: the query split with SQLite FTS5's
        unicode61 rules, each row's matched tokens, and a full-text rank by matched-token count. No vector half
        runs in mock mode, so vector_rank stays null. The rows are the fixture's whatever the query."""
        res = KbSearchResponse.model_validate(fixtures.load("kb_search.json"))
        terms = search_terms(query)
        qt = _dedupe(t for term in terms for t in fts5_tokens(term))
        for c in res.chunks:
            held = set(fts5_tokens(c.text))
            c.matched_terms = [t for t in qt if t in held]
            c.vector_rank = None
            c.fulltext_rank = None
        for n, c in enumerate(sorted((c for c in res.chunks if c.matched_terms), key=lambda c: -len(c.matched_terms)), 1):
            c.fulltext_rank = n
        res.query_terms = qt
        res.analyzer = "mock"
        res.analyze_sql = ("-- MOCK: no database. The query was split in Python with SQLite FTS5's unicode61 rules;\n"
                           "-- matched terms and full-text ranks are computed from the fixture rows' own text.\n"
                           f"-- search terms: {' '.join(terms) or '(none)'}")
        res.simulated = True
        return res

    async def prices(self, run_id: str, bom_line_id: str) -> PricesResponse:
        return PricesResponse.model_validate(fixtures.load("prices_b1.json"))

    async def insert_audit(self, record: dict[str, Any]) -> None:
        return None

    async def insert_price_observation(self, row: dict[str, Any]) -> None:
        return None

    async def load_template(self, build_type: str) -> dict[str, Any] | None:
        return None  # A's loader falls back to data/kb/templates on disk (same kb:// ids)

    def insert_audit_sync(self, record: dict[str, Any]) -> None:
        return None

    def audit_events_sync(self, run_id: str) -> list[dict[str, Any]]:
        return []

    def insert_mandate_sync(self, row: dict[str, Any]) -> None:
        return None

    def insert_price_observation_sync(self, row: dict[str, Any]) -> None:
        return None

    def resolve_kb_ref(self, kb_ref: str) -> dict[str, Any] | None:
        """Resolved from the files on disk (no database in mock mode)."""
        return _disk_index().get(kb_ref)

    def stats(self) -> dict[str, Any]:
        kb = fixtures.load("kb_search.json")
        _, chunks = load_kb_dir()
        by_kind: dict[str, int] = {}
        for c in chunks:
            by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1
        return {"backend": "mock", "tables": {t: 0 for t in TABLES} | {"kb_chunks": len(chunks)}, "kb_by_kind": by_kind,
                "last_query": {"sql": kb["sql"], "took_ms": kb["took_ms"], "at": "2026-11-20T13:03:50-08:00"},
                "sie": [], "queries": 0, "fallback_reason": "mock mode: no database", "sink_errors": {}, "simulated": True}


_DISK: dict[str, Any] = {}


def _disk_index() -> dict[str, dict[str, Any]]:
    if "idx" not in _DISK:
        _, chunks = load_kb_dir()
        _DISK["idx"] = {c["kb_ref"]: c for c in chunks}
    return _DISK["idx"]


def resolve_kb_ref_on_disk(kb_ref: str) -> dict[str, Any] | None:
    """A kb_ref against data/kb on disk (no database needed). Useful as A's `kb_resolver` fallback."""
    return _disk_index().get(kb_ref)


class OwnedPartsMemory:
    """The `owned_parts` table as a Memory (PLAN §2.1 2:15 fallback when Cognee is cut). Shown as "your inventory"."""

    provider = "owned_parts"

    def __init__(self, store: LiveKnowledgeStore | None = None) -> None:
        self.store = store or LiveKnowledgeStore()

    KINDS = ("owned", "preference", "purchase", "seed")

    async def remember(self, text: str, user_id: str = "demo_user", *, kind: str | None = None, source: str | None = None) -> None:
        """`kind` goes in the row's `note` column (owned | preference | purchase | seed), `source` in `source`."""
        self.store.add_owned_sync(text, user_id=user_id, note=kind if kind in self.KINDS else None, source=source or "user")

    async def list_facts(self, user_id: str = "demo_user") -> list[dict[str, Any]]:
        """Every row of this user's list, as `MemoryFact` bodies. A row written before kinds existed is `owned`."""
        return [{"text": r["item"], "kind": r["note"] if r.get("note") in self.KINDS else "owned",
                 "source": {"user": "you said"}.get(r.get("source") or "", r.get("source")), "run_id": None,
                 "at": str(r["added_at"]) if r.get("added_at") else None, "provider": "owned_parts", "simulated": False}
                for r in self.store.owned_sync(user_id)]

    async def forget(self, user_id: str = "demo_user", scope: str = "everything") -> int:
        """Delete this user's rows (`preferences`: only the rows whose kind is preference). Returns how many."""
        b = self.store.backend
        if scope == "preferences":
            n = int(b.query(b.q("SELECT COUNT(*) AS n FROM owned_parts WHERE user_id = ? AND note = ?"), [user_id, "preference"])[0]["n"])
            b.execute(b.q("DELETE FROM owned_parts WHERE user_id = ? AND note = ?"), [user_id, "preference"])
        else:
            n = int(b.query(b.q("SELECT COUNT(*) AS n FROM owned_parts WHERE user_id = ?"), [user_id])[0]["n"])
            b.execute(b.q("DELETE FROM owned_parts WHERE user_id = ?"), [user_id])
        return n

    async def recall(self, query: str, user_id: str = "demo_user") -> list[dict[str, Any]]:
        words = {w for w in search_terms(query) if len(w) > 2}
        hits = []
        for r in self.store.owned_sync(user_id):
            item_words = set(search_terms(r["item"]))
            overlap = words & item_words
            if overlap:
                hits.append({"memory_text": r["item"], "provider": "owned_parts", "score": len(overlap) / max(len(words), 1),
                             "simulated": False})
        return sorted(hits, key=lambda h: h["score"], reverse=True)


__all__ = ["KnowledgeStore", "LiveKnowledgeStore", "MockKnowledgeStore", "OwnedPartsMemory", "SqliteBackend",
           "SingleStoreBackend", "load_kb_dir", "parse_kb_markdown", "template_rows", "search_terms", "fuse",
           "resolve_kb_ref_on_disk", "TABLES"]
