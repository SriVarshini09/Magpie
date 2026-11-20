"""Seed the knowledge base: data/kb/*.md and data/kb/templates/*.json -> kb_docs + kb_chunks (PLAN §3.14).

Owner: D.

    cd backend && uv run python scripts/seed_kb.py              # S2_URL set: SingleStore; else SQLite (runs/b2c.sqlite)
    uv run python scripts/seed_kb.py --schema                   # apply scripts/s2_schema.sql first (idempotent)
    uv run python scripts/seed_kb.py --no-embed                 # full-text only (no SIE calls)
    uv run python scripts/seed_kb.py --sqlite runs/test.sqlite  # force SQLite at a path
    uv run python scripts/seed_kb.py --check                    # parse only: list docs and chunk counts, write nothing

Chunks keep their line numbers; each one is cited as kb://<doc_id>#<chunk_id> (template rows: kb://tpl_<type>#<row>).
Embeddings come from SIE `encode` when the sie service is live (SIE_API_KEY, DEMO_MODE=live or IMPL_SIE=live);
otherwise chunks are stored without vectors and hybrid search runs full-text only. Re-running replaces each document.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.integrations import s2  # noqa: E402


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--schema", action="store_true", help="apply the schema before seeding")
    ap.add_argument("--no-embed", action="store_true", help="do not call SIE encode")
    ap.add_argument("--sqlite", default=None, help="force the SQLite fallback at this path")
    ap.add_argument("--check", action="store_true", help="parse only, write nothing")
    args = ap.parse_args(argv)

    docs, chunks = s2.load_kb_dir()
    if args.check:
        per_doc: dict[str, int] = {}
        for c in chunks:
            per_doc[c["doc_id"]] = per_doc.get(c["doc_id"], 0) + 1
        for d in docs:
            print(f"{d['kind']:12} {d['doc_id']:28} {per_doc.get(d['doc_id'], 0):3} chunks  {d.get('licence') or ''}")
        print(f"{len(docs)} documents, {len(chunks)} chunks (nothing written)")
        return {"docs": len(docs), "chunks": len(chunks), "written": False}

    if args.sqlite:
        store = s2.LiveKnowledgeStore(s2.SqliteBackend(args.sqlite), auto_seed=False)
    else:
        store = s2.LiveKnowledgeStore(auto_seed=False)
    if args.schema or store.backend_name == "sqlite":
        from app.config import get_settings

        store.backend.apply_schema(get_settings().embed_dim)
    if store.fallback_reason:
        print(f"note: {store.fallback_reason}")
    out = store.seed(docs, chunks, embed=not args.no_embed)
    print(f"seeded {out['docs']} documents, {out['chunks']} chunks into {out['backend']} "
          f"({out['embedded']} with vectors{'' if out['embedded'] else ': full-text only'})")
    counts = store.table_counts()
    print("rows: " + ", ".join(f"{t}={n}" for t, n in counts.items()))
    store.close()
    return {**out, "tables": counts, "written": True}


if __name__ == "__main__":
    main()
