# Ownership

Four builders work in parallel. **Edit only what you own.** If you need a change somewhere else, put it
in your final report; the coordinator applies it. Roles follow `PLAN.md` §4.1.

## Shared files: owned by the coordinator, builders do not edit them

| File | Why it is shared |
|---|---|
| `backend/app/models.py` | The contract. Single source of truth |
| `frontend/src/lib/types.ts` | Generated from `models.py` (`backend/scripts/gen_types.py`) |
| `backend/pyproject.toml`, `backend/uv.lock` | Python dependencies |
| `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/components.json` | Pinned frontend dependencies and build config |
| `backend/app/registry.py` | Service registry (mock or live per service) |
| `backend/app/config.py` | Environment, `DEMO_MODE`, the Stripe test-key guard |
| `backend/app/mock_backend.py`, `backend/app/fixtures.py`, `backend/fixtures/**`, `backend/scripts/build_fixtures.py`, `backend/scripts/gen_types.py` | Mock mode, which C builds against |
| `backend/tests/conftest.py`, `test_contract_parity.py`, `test_fixtures.py`, `test_routes_mock.py`, `test_smoke_app.py`, `test_registry.py`, `test_stripe_guard.py` | Scaffold tests. Add your own test files; do not loosen these |
| `CLAUDE.md`, `OWNERSHIP.md`, `.env.example`, `.gitignore`, `.claude/**`, `scripts/dev.*`, `THIRD_PARTY.md` | Project rules and tooling |

`frontend/src/styles/tokens.css` and `globals.css` are C's alone (PLAN §4.1: "only C edits `tokens.css`").

## Folder → role

### Backend (`backend/`)

| Path | Owner | Notes |
|---|---|---|
| `app/main.py` | **A** | Routes for every role live here. B and D hand A the body of their routes (or a router to include); keep the mock branch |
| `app/runstate.py` | A | |
| `app/cache.py` | **B** | Record / replay |
| `app/agent/` | A | loop, tools, prompts, scripted, guard |
| `app/intake/` | A | classify, clarify, vision, uploads, http. **`reference.py`: B** (providers) |
| `app/pipeline/` | A | incl. `provenance.py`, `template.py`, `optimize.py`, `panel.py` |
| `app/rules/base.py`, `rules/robot_arm.py` | A | |
| `app/rules/generic_electrical.py`, `rules/mcu_battery.py` | **D** | |
| `app/stores/` | B | base, registry, http (allowlist), every adapter, `cartlinks.py`, `mock.py` |
| `app/checkout/` | B | cart, handoff, refresh, export, `stripe_test.py` |
| `app/audit/` | D | chain, mandate, evidence, verify |
| `app/integrations/anthropic_client.py`, `airbyte_github.py` | A | |
| `app/integrations/keenable.py`, `airbyte_exa.py`, `github_search.py` | B | Reference-search providers |
| `app/integrations/s2.py`, `sie.py`, `cognee_mem.py`, `amplitude.py`, `statsig_gate.py` | D | |
| `app/integrations/base.py` | coordinator | Shared helpers |
| `data/stores.json`, `data/mock_store.json` | B | |
| `data/kb/**` (incl. `templates/`) | D | Written during the event from PLAN Appendix B |
| `data/projects/**` | D (presets), C (`electronics_mcu/diagram.json` layout) | |
| `scripts/s2_schema.sql`, `seed_kb.py`, `seed_memory.py`, `warm_sie.py`, `verify_chain.py` | D | |
| `scripts/record_hero.py` | B | |
| `tests/` | Each role adds its own files | A: guard, extract_quotes, readme_table, provenance, intake_router, compat, optimize, cart_edit. B: cartlinks, registry (stores), reference_denylist additions. D: chain, template, generic_rules |
| `cache/`, `evidence/`, `runs/`, `uploads/` | runtime | `cache/` is recorded during the event (B) |

### Frontend (`frontend/src/`)

| Path | Owner | Notes |
|---|---|---|
| Everything not listed below | **C** | Polish owner |
| `components/receipt/` | **D** | Uses C's components; C reviews |
| `components/workspace/PhotoHotspots.tsx`, `components/workspace/DataDrawer.tsx` | **D** | |
| `components/cart/StripeTestPanel.tsx` | **B** | |
| `lib/types.ts` | coordinator | Generated |
| `components/ui/` | C | shadcn/ui output; add components with `npx shadcn@latest add <name>` only after the coordinator agrees (it edits `package.json`) |

### Root

`README.md`: D writes the content (skeleton is in place). `docs/`: D. `PLAN.md`, `CHECKLIST.md`, `research/`: nobody edits.

## Deviations from PLAN §3.2 (and why)

| # | PLAN | Here | Why |
|---|---|---|---|
| 1 | Root folder `build-to-cart/` | `pgent/` | The given project folder |
| 2 | `frontend/src/{api,types,store,modelMap}.ts` | `frontend/src/lib/` | Asked for in the scaffold brief; matches the shadcn `@/lib` alias. Hooks are in `src/hooks/`, pages in `src/pages/` |
| 3 | Fixtures in `frontend/src/fixtures/` | `backend/fixtures/`, served by the mock API | One copy, validated against the models. `frontend/src/fixtures/` is kept for the static replay build only |
| 4 | `DEMO_MODE=live\|record\|replay`, default `live` | adds `mock`; **default `mock`** | Builders can run with no keys. Set `DEMO_MODE=live` in `.env` when keys exist |
| 5 | No service registry | `app/registry.py` + `IMPL_<SERVICE>` overrides | Asked for in the brief. `stores/registry.py` (PLAN) still loads `data/stores.json` |
| 6 | Not in the file list | `app/mock_backend.py`, `app/fixtures.py`, `app/integrations/base.py`, `integrations/anthropic_client.py`, `integrations/github_search.py`, `scripts/build_fixtures.py`, `scripts/gen_types.py`, root `scripts/`, `.claude/`, `OWNERSHIP.md` | Mock mode, the Anthropic and GitHub-search interfaces, tooling |
| 7 | `react@19.2` (§3.4) | 19.3.1 | §11.12 overrides §3.4 |
| 8 | TypeScript unpinned | 6.0.3 | npm `latest` is 7.0.2 (the native compiler); 6.0.3 is the safer choice for shadcn and Vite tooling tonight |
| 9 | `npx shadcn@latest init` | Radix base, `nova` preset, recoloured from `tokens.css`; `next-themes`, the Geist font and the `cn` package the preset adds were removed (light only, Inter, `clsx` + `tailwind-merge`) | §11.3: light only, Inter |
| 10 | `LICENSE` | **not created** | Choosing a licence is the team's decision |
| 11 | `data/kb/*.md`, `data/kb/templates/*.json`, `data/projects/*/preset.json`, `scripts/s2_schema.sql`, `docs/demo-script.md`, `public/og.png` | not created (folders exist) | PLAN says they are written during the event; scaffold only |
| 12 | Tests listed in §3.2 | Only `test_http_allowlist`, `test_reference_denylist`, `test_registry`, `test_stripe_guard` exist, plus scaffold tests | The rest test features that are still stubs |
| 13 | SO-101 assets: the URDF's meshes | All 18 STLs in `Simulation/SO101/assets/` (the URDF uses 13) | The brief asked for `assets/*.stl` |
| 14 | `exploded-view` skill | Copied without `assets/demo/` | The demo page loads three.js from a CDN import map |
| 15 | Endpoints of §4.2 | plus `GET /health` (alias) and `GET /api/mock/fixtures[/{name}]` (mock mode only) | Health check; extra view samples for C |
| 16 | One `.env` per app | One `.env` at the repo root; Vite reads it (`envDir: ".."`, only `VITE_*` reach the browser) | One place for keys |

## Architect decisions (where PLAN was ambiguous; the simpler option was taken)

1. **Timestamps are ISO strings** in the models, not `datetime`.
2. **`CheckResult` includes `needs_human`** (§3.6 and §3.8 require it; the §4.2 type lists only pass, warn, fail).
3. **Mock labels.** Top-level responses and offers carry `simulated: true`; anything with a `source_api` carries
   `"mock"`. `Offer.mock_of` / `OfferRow.mock_of` name the adapter a mock offer stands in for, so the UI can still
   show "via SerpAPI"-style variety. `/api/health` adds `mock: bool` and `impl`; every response has
   `X-B2C-Mode` and `X-B2C-Mock` headers.
4. **Fields added to PLAN's types:** `ReadmeQuoteProvenance` keeps both `span` (JSON in §3.7) and
   `line_from` / `line_to` (§4.2) plus `more_quotes` for two-quote lines; `ViewData.urdf_url`, `.diagram`, `.tokens`,
   `.tray`; `PhotoView.sha256`; `UniversalCart.run_id`, `.open_assumptions`, `.current_store_id`; `Check.bom_line_ids`,
   `.needs_ack`; `BOMLine.qty_note`, `.category`; `CartPlan.lines`, `.plan_sha256`; `OfferRow` nullable cells are optional.
5. **Quote span.** `span` is the occurrence on `line_from`, not `text.find(quote)` (the first occurrence): the
   follower-arm rows repeat text from the two-arm table above them. A decides the final rule in `provenance.py`.
6. **Errors** are `{"detail": {error, message, refusal?, bom_line_ids, todo?}}` (`ApiError`).
7. **SSE** uses default `message` events with the `Event` JSON in `data` and `id` = `seq`. Query params:
   `after`, and in mock mode `delay_ms` and `close`. `Last-Event-ID` is honoured.
8. **Mock runs** are `r_mock_so101` and `r_mock_drone` (intakes `in_mock_so101`, `in_mock_drone`). A photo upload
   returns `in_mock_photo` but has no run (501): the hotspot and ESP32 diagram samples are `ViewData` fixtures.
   Mock state is in memory; cart edits are accepted and ignored.
9. **Mock URLs** use the reserved `mock.invalid` host, so nothing in mock mode can open or hit a real store.
10. **Fixture numbers.** Arm prices repeat PLAN Appendix A and the tonight checks; the Amazon rows and **every drone
    price are placeholders** (marked `PLACEHOLDER` in `build_fixtures.py`); the `fewest_checkouts` plan is a placeholder.
11. **Fixture signatures are placeholders**, so `/verify` reports `signatures_ok: false` in mock mode. The sample hash
    chain is real (`audit/chain.py` `canonical_json`, `record_hash`, `recompute` define the format D must keep).
12. **The fetch policy is implemented and tested** (`stores/http.py`, `intake/http.py`); the fetch functions are stubs.
    Regional marketplace sites (amazon.fr, ebay.co.uk) are refused too; `api.digikey.com` is the one exception.
13. **`main.py` stays one file** owned by A (PLAN §4.1); a route's owner is named in its `live("B", "§…")` call.
