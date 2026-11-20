-- Build-to-Cart: SingleStore schema (PLAN §3.14). Owner: D.
--
-- 7 of the 10 tables SingleStore Shared allows. Columnstore only (the only table type on Shared), so no
-- unique key is relied on: the hash chain and row ids are enforced in app code (integrations/s2.py).
-- No table holds buyer data (name, email, phone, address). The database is reachable from the internet.
--
-- Apply with:   cd backend && uv run python scripts/seed_kb.py --schema
-- VECTOR(1024) is rewritten to VECTOR(<EMBED_DIM>) by the client; EMBED_DIM must equal the SIE embedding
-- model's dimension (check C12). The FULLTEXT VERSION 2 syntax and the `<*>` dot product follow the docs page
-- "Hybrid Search - Reranking Full-Text and Vector Search Results" [unverified on Shared until check C11].
-- The SQLite fallback (no S2_URL) creates the same 7 tables plus an FTS5 index in integrations/s2.py.

-- 1. Every trusted document, template and fetched reference design.
CREATE TABLE IF NOT EXISTS kb_docs (
  doc_id      VARCHAR(128) NOT NULL,
  kind        VARCHAR(16)  NOT NULL,          -- doc | template | rule_source | reference
  title       TEXT,
  source_url  TEXT,
  licence     TEXT,
  commit_sha  VARCHAR(64),
  sha256      CHAR(64),                       -- of the file / fetched bytes
  fetched_at  VARCHAR(40),
  via         VARCHAR(32),                    -- file | airbyte.github | http | keenable | exa_airbyte
  build_type  VARCHAR(32),
  SORT KEY (doc_id),
  SHARD KEY (doc_id)
);

-- 2. Chunks for hybrid search. Citation: kb://<doc_id>#<chunk_id>; a template row is kb://tpl_quadcopter#motor
--    and its `meta` holds the row JSON. `kind` and `build_type` are copied from kb_docs so the template
--    query ("WHERE kind = 'template'") needs no join.
CREATE TABLE IF NOT EXISTS kb_chunks (
  chunk_id    VARCHAR(160) NOT NULL,
  doc_id      VARCHAR(128) NOT NULL,
  kb_ref      VARCHAR(320) NOT NULL,
  kind        VARCHAR(16)  NOT NULL,
  build_type  VARCHAR(32),
  row_id      VARCHAR(64),
  line_from   INT,
  line_to     INT,
  body        TEXT NOT NULL,
  meta        JSON,
  sha256      CHAR(64),                       -- of the chunk body (template rows: of the row JSON)
  emb         VECTOR(1024),                   -- NULL when seeded without SIE: full-text only
  SORT KEY (doc_id, line_from),
  SHARD KEY (doc_id),
  FULLTEXT USING VERSION 2 kb_ft (body)
);

-- 3. Every offer seen, timestamped ("Prices seen", stale and outlier checks). Never buyer fields.
CREATE TABLE IF NOT EXISTS price_observations (
  run_id          VARCHAR(64) NOT NULL,
  bom_line_id     VARCHAR(32) NOT NULL,
  offer_id        VARCHAR(64) NOT NULL,
  store_id        VARCHAR(64) NOT NULL,
  action_level    VARCHAR(16),
  title           TEXT,
  price_usd       DOUBLE,
  shipping_usd    DOUBLE,
  rating          DOUBLE,
  currency        VARCHAR(8),
  units_per_pack  INT,
  stock           VARCHAR(16),
  seen_at         VARCHAR(40) NOT NULL,
  source_api      VARCHAR(48),
  evidence_sha256 CHAR(64),
  refused         VARCHAR(64),                -- e.g. merchant_not_in_mandate; NULL when allowed
  simulated       TINYINT DEFAULT 0,
  SORT KEY (run_id, bom_line_id, seen_at),
  SHARD KEY (run_id)
);

-- 4. The hash chain. /verify re-reads it from here. Append-only by convention (enforced in app code).
CREATE TABLE IF NOT EXISTS audit_events (
  run_id     VARCHAR(64) NOT NULL,
  seq        INT NOT NULL,
  kind       VARCHAR(32) NOT NULL,
  ts         VARCHAR(40) NOT NULL,
  record     JSON NOT NULL,                   -- the whole record, exactly as hashed
  prev_hash  CHAR(71) NOT NULL,               -- "sha256:" + 64 hex
  hash       CHAR(71) NOT NULL,
  SORT KEY (run_id, seq),
  SHARD KEY (run_id)
);

-- 5. Open, closed and payment mandates (signed).
CREATE TABLE IF NOT EXISTS mandates (
  mandate_id VARCHAR(64) NOT NULL,
  run_id     VARCHAR(64) NOT NULL,
  type       VARCHAR(32) NOT NULL,            -- b2c.mandate.open | .closed | .payment
  body       JSON NOT NULL,
  sha256     CHAR(64) NOT NULL,               -- audit/mandate.py mandate_sha256 (signed body)
  jws        TEXT,
  SORT KEY (run_id),
  SHARD KEY (run_id)
);

-- 6. Run list.
CREATE TABLE IF NOT EXISTS runs (
  run_id      VARCHAR(64) NOT NULL,
  build_type  VARCHAR(32),
  source_url  TEXT,
  status      VARCHAR(24),
  total_usd   DOUBLE,
  created_at  VARCHAR(40),
  SORT KEY (created_at),
  SHARD KEY (run_id)
);

-- 7. What the user owns: the fallback memory if Cognee is cut ("your inventory").
CREATE TABLE IF NOT EXISTS owned_parts (
  user_id   VARCHAR(64) NOT NULL,
  item      TEXT NOT NULL,
  note      TEXT,
  source    VARCHAR(32),                      -- seed | user | photo_confirmed | purchase
  added_at  VARCHAR(40),
  SORT KEY (user_id),
  SHARD KEY (user_id)
);
