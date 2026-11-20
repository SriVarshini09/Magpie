# Build-to-Cart

Say what you want to build. Get one cart for every store, with every part saying where it came from.

> **Built before the event with the organizers' permission.** The plan (`PLAN.md`), the research notes
> (`research/`), the template contents (PLAN Appendix B) and the procedural-model specs (Appendix C) were written
> before hacking started, and the code in this repo was built before the event with the organizers' explicit
> permission. Anything recorded for the demo (the replay cache, the team photos) is listed under
> [Prepared before the event](#prepared-before-the-event) with when it was made.

**No real money moves in this app, in any mode.** The optional single payment is Stripe **TEST MODE**. In mock
mode (the default) every price, store result, cart and signature on screen is simulated and labelled "Mock data".

<!-- D: sections marked "fill after the hero runs" get real numbers at 2:45 and 2:55 (PLAN §5.1, §9).
     Describe every feature and sponsor as what it actually is at submission time (PLAN §2.0). -->

## What it does

One box: **"What do you want to build?"** Type a sentence ("a small camera drone under $200"), paste a GitHub
link, drop a photo of your breadboard, or mix them.

1. The agent names the **build type** (robot arm, quadcopter, RC car, claw, electronics, or generic). You can change it.
2. It asks at most three questions as tappable chips, then you **sign a mandate**: budget, allowed stores, what data
   it may share, what it may do. It may never pay.
3. It writes the bill of materials. **Every line says where it came from** (quoted, reference design, template,
   seen in your photo, or assumed). Assumed lines are amber and block approval until you confirm them.
4. It removes what you already own, finds offers across Shopify stores, Amazon and maker stores, and checks that
   the parts fit together with a generic electrical rule pack plus a domain pack.
5. Everything lands in **one Universal Cart on our site**, grouped by store, each store with the strongest hand-off
   it supports. You approve the cart (a signed closed mandate), then a guided checkout run takes you store by store.
6. Every step is a signed, hash-chained record. **Verify** recomputes the chain and checks every signature.

## Run it

Needs Python 3.13, [uv](https://docs.astral.sh/uv/), Node 24.

```
cp .env.example .env            # mock mode needs no keys
cd backend  && uv sync
cd frontend && npm install
scripts/dev.ps1                 # or scripts/dev.sh: backend on :8000, frontend on :5173
```

`DEMO_MODE` in `.env`: `mock` (fixtures, default) · `live` · `record` · `replay` (the recorded hero runs, no keys
needed). `IMPL_<SERVICE>=mock|live` overrides one service (e.g. `IMPL_SINGLESTORE=live` with no `S2_URL` runs the
real knowledge base on SQLite).

Checks: `cd backend && uv run pytest` · `cd frontend && npx tsc --noEmit && npm run build`

**The demo setup: real pipeline, live sponsors, mock stores.** Put the sponsor keys in `.env` (names in
`.env.example`; never commit it), then:

```
cd backend && uv run python scripts/check_integrations.py --ping      # which keys are set; one small real call each
cd backend && uv run python scripts/dev_pipeline.py --live auto        # every sponsor with keys runs live; stores stay mock
```

`check_integrations.py` never prints a key. `--live auto` switches on SingleStore, SIE, Cognee, Amplitude, Statsig,
Exa and the GitHub connector when their keys are present; the store adapters stay mock and every store result is
labelled "Simulated store data". Remove a key (or run without `--live`) and that service falls back to its labelled
mock.

Useful scripts (all in `backend/scripts/`):

| Script | What it does |
|---|---|
| `seed_kb.py [--schema] [--no-embed] [--check]` | Loads `data/kb/*.md` and the six templates into SingleStore (or SQLite), one row per chunk, with line numbers; embeds with SIE when it is live |
| `verify_chain.py <run_id> \| --receipt FILE \| --fixture so101` | Recomputes a chain and checks every mandate signature and binding; exit 1 on any failure |
| `seed_memory.py [--preset NAME]` | Preloads the seed memories into Cognee (or the `owned_parts` table) |
| `warm_sie.py` | One small call per SIE model so the cold start happens before the demo |
| `sign_fixtures.py [--out DIR]` | Rebuilds the mock fixtures with real ES256 signatures (fixture key) into a separate folder |

## How it works

```
Browser (React 19, Vite, Tailwind, shadcn/ui, three.js)            Backend (FastAPI, Python 3.13)
  Composer ── POST /api/intake ─────────────────────────────►  classify: build type, chips, photo parts (Claude)
  Sign mandate ── POST /api/runs ───────────────────────────►  OPEN mandate (ES256) → agent task
  Workspace ◄── SSE events ─────────────────────────────────   every tool call: mandate guard → cache → evidence file
    view router: URDF arm · procedural model · board diagram           → hash chain → SingleStore audit_events
    · kit view · photo hotspots; one part panel                        → Amplitude tool-call event
  Universal Cart ── approve ────────────────────────────────►  CLOSED mandate (bound to plan, hand-offs, chain head)
  Checkout run: open cart / open prefilled cart / product page          hand-offs: Shopify UCP cart, cart-link strings
  Receipt ◄── GET …/receipt, …/verify ──────────────────────   recompute chain + check every signature

Agent tools (Claude Sonnet 5.5): ingest_source · load_template · find_reference_design · identify_parts · extract_bom
  · lookup_trusted_spec · resolve_part · recall_owned · search_offers · rank_offers · check_compatibility
  · optimize_cart · stage_cart · (stop for approval) · create_carts · remember.  No checkout or payment tool exists.
```

### The mandate

Before any tool runs, `POST /api/runs` signs an **open mandate** (`backend/app/audit/mandate.py`): budget, deadline,
allowed stores (`store_id`s), data-sharing flags (country only by default), allowed actions (`pay: false` and
`checkout: false`, always) and the hashes of what you typed, linked or uploaded. The guard checks every tool call
against it in code, outside the model. Approving the cart signs a **closed mandate** that binds the open mandate's
hash, the plan's hash, every hand-off URL's hash and the chain head at approval. A Tier 2 test payment signs a
third, **payment mandate**, before the PaymentIntent exists. The format is "AP2-inspired", not AP2-compliant.

### Where every line comes from

| Chip | Type | What it proves | What it does not prove |
|---|---|---|---|
| **Quoted** | `readme_quote` | The exact text is in the project's README, fetched by us and pinned to a commit (checked as a substring of those bytes) | That the README is right |
| **Reference design** | `reference_project` | The exact text is in an open design the agent found (provider named), fetched and hashed by us | That the design fits your build |
| **Template** | `template_row` | The line is a row of a template we wrote from cited references, stored as a KB row (`kb://tpl_<type>#<row>`) whose hash matches. Rows marked **rule of thumb** are common practice, not a design, and the rules they feed only warn | That the template is a verified design |
| **Seen in your photo** | `photo_region` | A region of your photo was detected with that label (approximate box) | The part's spec; that always has a second source |
| **Assumed · confirm** | `assumption` | Nothing: it is the agent's judgment, shown amber, and Approve is refused (409) until you confirm, edit or remove it | Anything |

**Templates are starting points, not verified designs. The rule pack checks listing text for common mismatches; it
does not certify a build.**

Lines per type in the hero runs (fill after the 2:45 recordings; the mock fixtures have SO-101: 7 quoted; drone:
template rows and one open assumption):

| Run | Quoted | Reference design | Template | Photo | Assumed (confirmed) |
|---|---|---|---|---|---|
| SO-101 link | _fill_ | _fill_ | _fill_ | _fill_ | _fill_ |
| Drone text | _fill_ | _fill_ | _fill_ | _fill_ | _fill_ |

### Stores and action levels

Our site cannot put items in a non-Shopify store's cart except through that store's own prefilled link, and it
never pays.

| Store | Search source | Action level | Caveat |
|---|---|---|---|
| WowRobo, ArmDojo, Geekworm, OpenELAB, RobotShop USA, Rokland | Shopify UCP | **Agent cart**: the agent built a real cart through the store's API | Anonymous carts confirmed at WowRobo; RobotShop only through `robotshop-us.myshopify.com` |
| Amazon | SerpAPI (`amazon`, Google Shopping) | **Prefilled cart**: Amazon's own cart-add link; the store adds the items | Amazon asks you to sign in first. We never request amazon.com |
| Best Buy | SerpAPI (Google Shopping) | Prefilled cart | Adds one of each item |
| Walmart | SerpAPI (`walmart`) | Shown as **product link** until a human verifies the cart link in a browser | |
| Digi-Key | Digi-Key API | Prefilled cart | Off unless the API key exists |
| Adafruit | Adafruit catalog JSON | **Product link**: you add it yourself | No rating, shipping or ETA |
| Seeed Studio, SparkFun | Magento GraphQL | Product link | |
| eBay | SerpAPI (`ebay`) | Product link | New, fixed-price only; in no preset |
| The Pi Hut, Pimoroni, DFRobot, Waveshare | | off | UK/GBP, or stretch |

A store whose cart link was not opened in a real browser today is shown as a product link (`cart_link_verified`).

### The audit trail

`backend/app/audit/`: every record is `hash = "sha256:" + sha256(prev_hash + canonical_json(record without hash))`
(sorted keys, no whitespace, UTF-8), starting from 64 zeros. Records are append-only, kept in memory, written to
`runs/<run_id>/chain.jsonl` and to SingleStore `audit_events`. Mandates are ES256 (P-256) detached JWS (RFC 7797)
over the canonical mandate body; `GET /api/runs/{id}/receipt` returns both mandates, every record and the public key
as a JWK. **Verify** recomputes every hash and checks every signature plus the bindings between them (open mandate
↔ chain, closed mandate ↔ open mandate, closed mandate's chain head ↔ a record before approval, hand-off URLs ↔
their hashes, payment mandate ↔ closed mandate). Change one byte and it reports the first broken record.

What is refused, in code: stores outside the mandate (one refusal per line and store), buyer data the mandate does
not share (email, phone, address, name), any pay or checkout action, approval without the one-time token, a stale
price, an unconfirmed assumption, a host on the never-request list, a photo the mandate does not let us send to a
model, and a run whose build type or inputs do not match the mandate.

Raw responses are evidence files, `evidence/<run_id>/<sha256>.json`, named by the hash of their bytes, with API
keys, tokens and buyer fields stripped before hashing.

## What is real, what is test, what is mock

| | |
|---|---|
| **Real** | The README read from GitHub and its commit; offers and prices as seen (with `seen_at` and the source API); Shopify carts the agent built; cart links; merchant checkout pages; the hash chain and signatures |
| **User-reported** | "Bought" ticks in the checkout run |
| **Test mode** | The single payment, the per-store virtual cards and the store authorizations (Stripe TEST MODE, `livemode: false` asserted on every object) |
| **Mock** | Everything in `DEMO_MODE=mock`: fixtures labelled `source_api: "mock"`, `simulated: true` and the "Mock data" badge. Mock fixtures are signed with a **fixture key derived from a public seed** (once the coordinator applies `sign_fixtures.py`): those signatures show the format and prove nothing |
| **Never** | Real money |

**In the demo build** (`dev_pipeline.py --live auto`): the pipeline, rules, optimizer, signatures and chain are
real, and so are the sponsor services listed live below. **The stores, offers and prices are mock**, labelled
"Simulated store data" / "Mock Hobby Store (simulated)" on every card; live store calls need store keys and are
not part of the demo.

## Templates and their sources

Six templates in `backend/data/kb/templates/`, one KB row per part row. A human reads every row before the demo.

| Template | Rows | Basis | References (licence) |
|---|---|---|---|
| `tpl_robot_arm` (SO-101 follower) | 7 | all reference | SO-ARM100 README (Apache-2.0) |
| `tpl_quadcopter` | 13 | all **rule of thumb** | PX4 Holybro X500 V2 page (CC BY 4.0); Holybro kit page (licence unverified, cited); oscarliang.com/motors (not an open licence; one short quote) |
| `tpl_rc_car` (Donkey Car) | 11 | reference, 1 rule of thumb | Donkey Car docs (code MIT; docs licence unverified; cited, short quotes) |
| `tpl_claw_gripper` | 7 | reference; screw counts are assumptions | SO-ARM100 (Apache-2.0); LeRobot SO-101 docs (licence unverified, cited) |
| `tpl_electronics_mcu` | 10 | mostly rule of thumb | Arduino Uno datasheet (cited); Arduino Starter Kit contents from a reseller page (unverified against Arduino's own page); esp32-weather-epd README (GPL-3.0: parts list read, no code used) |
| `tpl_generic` | 6 | every line an assumption | none |

**No open-licence 5-inch or 3-inch FPV parts list was found.** The 3-inch quadcopter numbers (the default variant)
have no source read and are marked "rule of thumb; unverified, human check". The PX4 pages disagree on the X500
motor KV (880 vs. 920): both are cited. The Donkey Car docs do not state the chassis battery voltage, so it is
`null`, never guessed. Every reference is also a citable KB row in `data/kb/template_sources.md`.

## Generality test

Run once, live, at _time_, with inputs nobody rehearsed. Unedited (PLAN §5.1).

| # | Input | Kind | Build type (right?) | Lines: quoted / reference / template / photo / assumed | View shown | Rules run / needing a human | Reached a cart? | What went wrong |
|---|---|---|---|---|---|---|---|---|
| 1 | _fill_ | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |

## Inputs and privacy

- Photos are sent to Claude and, for detection, to Superlinked SIE, only when the mandate's `photo_to_models` flag
  is on. They are re-encoded, stripped of EXIF and stored on the local disk only; Cognee never stores a photo.
- No buyer data is written to any table, event, evidence file, URL or memory. Amplitude properties are an
  allow-list (counts, rule ids, tool names, latencies, totals); message contents are never sent.
- Reference-design search providers actually used: _fill_ (Keenable, Exa via Airbyte, Claude web search, GitHub).

## Data sources and terms

SerpAPI for Google Shopping, Amazon, Walmart and eBay results; store APIs for the rest (Shopify UCP, Adafruit,
Seeed, SparkFun, Digi-Key). **No scraping of bot-walled sites, directly or through any search or fetch provider**
(`backend/app/stores/http.py` holds the never-request list and its tests). No affiliate tags; cart links carry
item ids and quantities only.

## Sponsors

Each section says what is built. "Tested with fakes" means the client is written from the installed SDK's own
source and covered by tests that stub the network; "live" means it ran against the real service with a key.
Status, checked live on Nov 20 2026 with the team's keys (none are in the repo): **SingleStore, Superlinked SIE,
Cognee, Amplitude and Statsig ran live** in full builds; Airbyte is wired and tested with fakes (live status below).
Claude is not connected in the demo build: intake uses the keyword router and the agent runs its fixed tool order.

### Data layer: SingleStore

`backend/app/integrations/s2.py`, `backend/scripts/s2_schema.sql`, `backend/scripts/seed_kb.py`.
One database is the knowledge base, the price memory and the audit store, in 7 of the 10 tables Shared allows:
`kb_docs`, `kb_chunks` (`VECTOR(EMBED_DIM)` plus a `FULLTEXT USING VERSION 2` index), `price_observations`,
`audit_events`, `mandates`, `runs`, `owned_parts`.

- **Hybrid search**: one full-text `MATCH (TABLE kb_chunks) AGAINST ('body:(…)')` and one vector `emb <*> @q`
  query, ranks fused 0.7 / 0.3 with reciprocal-rank fusion. The SQL that ran is returned with every result and
  shown in the part panel and the Data drawer. Full-text only when no embedder is live.
- **Templates are rows**: "which template" (the user's words against template summaries) and "which row" are the
  same query with `kind = 'template'`; `load_template` rebuilds a template from its rows.
- **Prices**: latest observation per offer, age in minutes and distance from the median of allowed offers.
- **Audit sink**: every chain record goes to `audit_events`; Verify reads it back from there when SingleStore is live.
- Without `S2_URL` (or if SingleStore is unreachable) the same interface runs on **SQLite** with an FTS5 index, seeded
  from the markdown on first use. The SingleStore SQL shapes are unverified until check C11.
- **Why this matched**: the Data drawer shows how the query was split into index tokens (`ANALYZE FULLTEXT` on
  SingleStore; the SQLite stand-in says so), each row's matched terms highlighted, and its vector and full-text rank.
- Status: **live** on a SingleStore Starter (Shared) cluster, engine 10.9: 16 KB documents / 169 chunks with SIE
  vectors, templates loaded by SQL, and a real run's audit events, mandate and price observations written there.
  Fresh rows join the full-text index after `OPTIMIZE TABLE kb_chunks FLUSH`, which seeding now runs.

### Task-specific inference: Superlinked SIE

`backend/app/integrations/sie.py`, `backend/scripts/warm_sie.py`. Four uses through `sie-sdk`: `encode` (KB vectors at
seed time and each lookup), `score` (rerank listings against the resolved spec), `extract` (attribute spans: voltage,
current, connector, pitch, quantity) and **`grounding-dino-base` detection** for photo hotspots. The SDK's box format
is `[x, y, w, h]` per its docstring; `SIE_BOX_FORMAT` (xywh | xyxy) and one function, `to_xyxy`, convert it.
Detections under 0.35 are dropped. Every call is timed per step and model (Data drawer SIE table, footer counts).
**Spec reads**: `extract` reads each listing (motor stator size, stack pattern, KV, current, connector, cells), our
own parsers normalize the spans, and the compatibility rules judge those values: a rejection says who read it, e.g.
"G12: 25.5x25.5 mm stack ≠ 30x30 mm stack (SIE read “25.5x25.5”)". With no read, the title patterns apply.
Status: **live** on SIE Serverless: `BAAI/bge-m3` (1024-d), `Qwen/Qwen3-Reranker-0.6B`, `urchade/gliner_multi-v2.1`
(generic labels such as "model number" and "dimensions" at threshold 0.3, measured to work better than
domain labels), `IDEA-Research/grounding-dino-base`. A 5-inch drone build makes about 24 calls, median ~320 ms.

### Memory: Cognee

`backend/app/integrations/cognee_mem.py`, `backend/scripts/seed_memory.py`. `remember` / `recall` per user dataset.
Seeded facts: a screwdriver set, two USB-C data cables, a 3D printer and PLA, a soldering iron and jumper wires,
"US sellers; no Alibaba or AliExpress". After approval the purchase is written back. Cloud mode uses
`cognee.serve(url, api_key)`; local mode refuses to start unless both the LLM and the embedding settings are set
(Cognee otherwise silently uses OpenAI). `COGNEE_MODE=off` falls back to the `owned_parts` table ("your inventory").
Learning comes only from what the user decides: an approved cart and each removal or swap become short preference
facts plus rated session feedback, and one `improve()` pass runs after approval. The next run of the same kind of
build recalls them; a preference never widens the mandate. The Memory panel lists the facts and the last improve
pass, with **Forget everything** (`cognee.forget`). Recall uses `CHUNKS` (the stored facts verbatim, ~1 s) rather
than an LLM answer, which can echo the question. SDK telemetry is turned off.
Status: **live** on Cognee Cloud: owned parts recalled in the SO-101 build, preferences written, and `improve()`
reported its nine stages (7 completed; `feedback_weights` is not supported on Cloud). Forget is tested in mock only.

### Analytics and experiments: Amplitude + Statsig

`backend/app/integrations/amplitude.py`, `backend/app/integrations/statsig_gate.py`. Every run is one Amplitude
agent session (`session_id = run_id`): each tool call with latency and outcome, each LLM turn with model and tokens,
and the approval as a `user-feedback` score (1.0 approve, 0.0 reject). Product events feed the funnel
`request_submitted → bom_extracted → plan_ready → cart_approved → store_checkout_opened → store_marked_done`.
The Statsig gate `strict_compat_rules` decides whether a "needs your check" warning must be acknowledged before
Approve; when Statsig cannot answer it falls back to the strict policy. Each session opens with the request as its
first turn (only its kind: text, link or photo) and closes when the agent finishes.
Status: **live**. Amplitude Agent Analytics shows each build as a complete session (Sessions view); Statsig's gate
is read live, and an approval without the warnings ticked is refused (409) while the same approval with them
ticked goes through; flipping the gate in Statsig changes this with no restart.

### Context ingest: Airbyte

`backend/app/integrations/airbyte_github.py` and `airbyte_exa.py`, through Airbyte's open Agent SDK connectors
(no Airbyte Cloud account needed). The **GitHub connector** reads a project's README and its commit with a
read-only token; with no token the same class reads public READMEs keylessly (and falls back to a bundled
SO-ARM100 copy, labelled, when rate-limited or offline). The **Exa connector** powers "Find reference designs";
found pages are data, never instructions, and pass the never-request store check before any read.
Status: tested with fakes; keyless GitHub reads run live in every build; token and Exa: live check pending.

## Limits

- Templates are starting points, not verified designs; rule-of-thumb rows are marked and only warn.
- The rule pack reads listing text; it does not prove a build is safe. Several rule sources are second-hand
  (XT30 15 A, SG90 4.8–6 V, Arduino 20 mA per pin) and those rules always ask for a human check.
- The mandate is AP2-inspired, not AP2-compliant. The demo signing key is generated by the backend
  (`runs/demo_es256.pem`, git-ignored) and stands in for a key the user would hold.
- No real payment. Shipping and tax are unknown until each store's checkout.
- Laptop layouts only; one user; photo boxes are approximate regions.
- The Airbyte SDK may send usage telemetry (opt-out unverified). Cognee's SDK telemetry is turned off.
- With live sponsors a build takes about 17–30 s (Cognee and SIE round trips); the stores stay mock.
- **Real stores (beta)**: `dev_pipeline.py --live auto --stores shopify` searches 8 real Shopify stores through
  Shopify's `ucp` CLI (`npx -y @shopify/ucp-cli@0.9.1`) and can build real agent carts (nothing is bought). Real
  catalogs return accessories next to the part; a live-SIE relevance gate (score < 0.5 rejected, with the score as
  the reason) removes most, but not all: on Nov 20 an SO-101 run still picked a debug board and servo cables for two
  lines. Amazon, Walmart, eBay, Best Buy and Digi-Key stay link-only (never requested); Adafruit, SerpAPI and
  Digi-Key adapters were not run live.
- Chat sessions live in the backend's memory: a restart starts a fresh list (runs and receipts stay on disk).

## Production note

A real single payment needs one of two things. (a) We become the merchant of record: we charge the buyer and pay
each store with single-use virtual cards, which makes sales tax, refunds, chargebacks and each store's resale terms
ours, and needs an eligibility review and legal advice. (b) A licensed or permissioned provider moves the money and
the merchant stays merchant of record: Shopify's purchase permission with the Shop Pay handler, or payment tokens
capped per seller, where we never hold funds. Neither is self-serve today. The demo shows the control design
(per-store caps, mandate-bound payment), not a licensed payment service. This is not legal advice.

## Prepared before the event

Built before the event with the organizers' permission: the plan and research in `PLAN.md`, `CHECKLIST.md` and
`research/`; the scaffold and the code in `backend/` and `frontend/`; the six templates (from PLAN Appendix B); the
procedural models (from Appendix C); the KB notes in `backend/data/kb/`. Recorded later (fill with times): the replay
cache in `backend/cache/`, the team photos, any generated model.

## Repo map

`PLAN.md` (the plan) · `CHECKLIST.md` · `research/` · `CLAUDE.md` (rules for coding agents) · `OWNERSHIP.md`
(who owns what, deviations from the plan) · `THIRD_PARTY.md` · `backend/` (FastAPI) · `frontend/` (Vite + React) ·
`docs/demo-script.md` (the stage script).

## Licence

TODO(team): choose a licence and add `LICENSE`. Third-party material is listed in `THIRD_PARTY.md`.
