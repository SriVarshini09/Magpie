# Build status: Build-to-Cart

Built overnight on Nov 20, 2026, before the event, with the organizers' permission. No git was used and nothing is committed.

## Where it stands
- **Backend:** 601 tests pass.
- **Frontend:** the type check and production build are clean. The landing page loads 138 kB up front; the other pages and the 3D load on demand.
- **Both hero flows run end to end in pipeline mode** (the real pipeline against mock services), through the API and in the UI, to a green Verify:
  - **The typed drone request:** the quadcopter label, chips, template lines with provenance, an assumption blocking Approve until confirmed, a plan across 3 stores, then part panel → Universal Cart → approve → checkout run → receipt.
  - **The SO-101 link:** 7 lines quoted from the README, the 12V fix, the refusals (Alibaba, and an offer that asked for address and email), then cart → approve → Edit cart → re-approve → Verify.
- **Real public GitHub links work with no key** (60 reads an hour per IP):
  - **ESP32 weather display:** 6 quoted lines, cart $85.86.
  - **OpenCat:** 3 lines, cart $17.50.
  - **duckyPad:** no parts table, so 6 assumptions to confirm.
- **Replay works:** recorded runs came back identical with the network blocked. The dev recordings are in `backend/dev_recordings/`. They are mock-store recordings, **not** the stage cache.

## How to run
| Mode | Command (from the project folder) | What it is |
|---|---|---|
| Mock | `scripts\dev.ps1` | Sample data only |
| **Pipeline** | `scripts\dev-pipeline.ps1` | The real agent, rules, optimizer, cart and audit trail against mock stores. **Use this for development.** |
| Replay | `DEMO_MODE=replay` | Plays back a recorded run |
| Live | `DEMO_MODE=live` with keys in `.env` | Real services |

Then open http://localhost:5173. Add `?fps` for a frame-rate readout, and `?ao=off` to turn ambient occlusion off.

## What's built
- **Intake:** one composer for text, link or photo. A build-type router (arm, quadcopter, RC car, claw, electronics, generic) and up to 3 chips.
- **Provenance on every line:** README quote, template row, reference design, photo region, or assumption. Approve returns 409 until every assumption is confirmed.
- **Six build-type templates,** grounded in cited open designs. Generic electrical rules G1–G11, the arm pack R1–R11 and the battery pack R12–R17.
- **Stores, each labelled truthfully:**
  - Shopify UCP agent carts
  - SerpAPI with 5 engines
  - Adafruit, Seeed, SparkFun, Digi-Key
  - cart links for Amazon, Digi-Key, Best Buy and Walmart, which **show as product links until a person verifies each format in a browser**
- **Universal Cart:** edit, refresh prices, CSV, approve, hand-offs, a guided checkout run, and Edit cart / reopen.
- **Stripe test-mode single payment (Tier 2):** wired, but not yet exercised. It needs Stripe test keys and `PAY_TIER=2`.
- **The audit trail:** a hash chain, ES256-signed mandates (open, closed, payment), an evidence store, Verify, and a receipt page.
- **3D and views:**
  - the SO-101 arm, with smoothed meshes precomputed by `frontend/scripts/smooth-so101.mjs`
  - procedural quadcopter, RC car and claw
  - the board diagram, the kit view, and photo hotspots
  - colour modes, two-way highlight, progressive reveal
  - isolate (double-click), hide (Ctrl-click), leader-line labels
  - explode, and **Kit view**, which flies the parts into a priced grid
  - ambient occlusion and anti-aliasing, measured at about 105 fps
- **Sponsor clients, built and tested against fakes:** SingleStore (with a SQLite fallback), Superlinked SIE (including grounding-dino detection), Cognee, Amplitude, Statsig, Airbyte (GitHub, and Exa), Keenable, and Claude web search.
- **Truthful labels everywhere:** "Mock stores · real pipeline", "SQLite fallback", "simulated", TEST MODE.

## Not verified yet
- **Nobody has watched the 3D motion play:** the intro move, staged explode, Kit view flight and hero rotation. The browser pane was hidden all night, so only still frames were checked. **Watch these first.**
- **No live service has been called.** Every live adapter is written from the plan's verified call shapes and tested against fakes only.

## For your team to do, with keys
1. **Fill in `.env` from `.env.example`:**
   - `ANTHROPIC_API_KEY`
   - `AIRBYTE_GITHUB_TOKEN` (this lifts the 60-an-hour GitHub limit)
   - `SERPAPI_KEY`
   - `S2_URL` (SingleStore)
   - the SIE key and model IDs
   - Cognee, Amplitude and Statsig keys
   - Stripe `sk_test_` / `pk_test_` and the cardholder
   - Keenable and Exa keys
2. **Run checks C10–C31** from CHECKLIST.md. Settle the SIE box format (C25), and the SingleStore SQL (C11).
3. **Open each prefilled cart link once in a real browser,** then set `CART_LINKS_VERIFIED` (for example `amazon,digikey`).
4. **A person reads every template row** (PLAN gate G2), especially the 3-inch drone rows, which have no single source.
5. **Record the stage cache with live keys** into `backend/cache/` at the event.
6. **README:** fill the `_fill_` placeholders (hero counts, the generality table, live status).

## Known gaps, most important first
1. The ESP32 link still asks "Which board?" with Arduino as the default. Intake ignores board mentions in the link.
2. Runs live in memory only; a backend restart loses them. Snapshots are written but never reloaded.
3. Mock-data quirks:
   - the SO-101 "table clamp" mock matches a light-pad clamp;
   - the Prices tab mixes pack and unit prices;
   - in the CSV, "unit price" is per pack.
4. 3D:
   - Kit parts aren't laid flat, and they're scaled per cell;
   - tags can touch with 12 or more lines;
   - leader labels can swap columns while orbiting;
   - the legend overlaps slightly;
   - `og.png` is 646 kB and crops the gripper.
5. Dev only: hot-reloading `Stage3D.tsx` needs a page refresh; there's a `THREE.Clock` deprecation warning.
6. PuLP ships without a solver here, so the optimizer uses an exact search instead, which is fine for about 10 parts.

## Where things are
- `PLAN.md`, `CHECKLIST.md` and `research/`: the plan.
- `CLAUDE.md` and `OWNERSHIP.md`: the rules for agents.
- `README.md`: product docs. It needs the final numbers.
- `backend/`: FastAPI, at `app/`; the tests are in `tests/`.
- `frontend/`: Vite and React; the source is in `src/`.
