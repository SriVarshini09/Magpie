# Build-to-Cart: everything required (v2, cash-sponsor plan)

tokens& Personal Agents Hackathon, Fri Nov 20, 2026, San Francisco. Details are in `PLAN.md`; section numbers are in brackets. The old checklist matched plan v1, which is kept at `research/PLAN-v1.md`.

`[x]` = already done tonight. **Bold** = without it you can't compete, submit, or claim that sponsor.

**Sponsors we're targeting (1st-place value):**
- Amplitude + Statsig: $1,000
- SingleStore: $1,000 in gift cards
- Airbyte: $1,000 Visa
- Superlinked: two prizes of $500 cash + credits
- Cognee: $500 cash + credits
- Persona (optional): $250 Keychron gift card per member

**Dropped:** Senso, Firedrill, Guild and Arcee.

---

## 1. Tonight (Thu): rules-safe prep only, no project code

### Team, registration, rules
- [ ] **Your Luma registration says Approved.** Pending applicants are turned away at the door.
- [ ] **Team of 2–4 people.** Post in the Discord; the draft post is in [§1.6].
- [ ] Choose your team-size column [§2.4]. Be honest: a team of 2 does Amplitude + SingleStore + Airbyte and Tier 1 pay only.
- [ ] **Sign in to the submission form** at https://tokensand.com/personalagenthack/submit and check whether there's a sponsor or track field and how many you can tick.
- [ ] Decide who owns the GitHub repo. Create it at 11:00 tomorrow, **not tonight**.

### Required keys
Save each key in a password-manager note, not in a project file. Details are in [§1.1].
- [ ] **Anthropic** at https://platform.claude.com: an API key; check `claude-sonnet-5-5` and `claude-opus-5-5` both respond, and check your credit balance.
- [ ] **Amplitude**: free plan, no card. API key from Settings > Projects > your project > General.
- [ ] **SingleStore**: free Shared database at portal.singlestore.com. Save the connection string.
- [ ] **GitHub fine-grained personal access token** for Airbyte: public repos, read-only, 7-day expiry.
- [ ] **Superlinked** at https://console.superlinked.com ($20 free, no card). Copy three things: the **Serverless base URL shown in the console**, the "On Serverless" model IDs (one embedding model, one reranker, one GLiNER extractor), and the embedding dimension.
- [ ] **Stripe test sandbox + Issuing** (for one-payment Tier 2; do it even for a team of 3):
  - [ ] Create a Stripe account and a sandbox.
  - [ ] Turn on Issuing in the sandbox.
  - [ ] Top up the test Issuing balance.
  - [ ] Create one cardholder.
  - [ ] Run one simulated authorization from the Dashboard.
  - [ ] Keys start with **`sk_test_` / `pk_test_`**. Never copy a live key anywhere.
- [ ] **Video host**: YouTube (unlisted) or Loom.

### Optional keys
- [ ] Cognee Cloud at platform.cognee.ai. If you skip it, Cognee runs locally with the Anthropic key.
- [ ] Statsig: free Developer plan; server secret key.
- [ ] Persona sandbox key, plus the "Basic Verification" template IDs (`itmpl_…`, `env_…`).
- [ ] SerpAPI (fallback only): use at most 5 searches tonight.

### Laptop setup (environment, not project code)
Already done on this laptop:
- [x] Node 24.12 (needs 22.19 or newer)
- [x] Python 3.13.7 (the plan now requires 3.13)
- [x] uv 0.13.7
- [x] Git 2.51
- [x] OBS appears installed. Do a 10-second test recording.

Still to do:
- [ ] `npm install -g @shopify/ucp-cli`, then `ucp doctor`.
- [ ] Warm the packages in a **throwaway** venv, then delete it [§1.2]: `uv pip install singlestoredb sie-sdk airbyte-agent-sdk "amplitude-ai[anthropic,fastapi]" cognee stripe statsig-python-core`.
- [ ] Claude Code signed in on **every** teammate's laptop. Teammates also need Node 22.19+, Python 3.13, uv and Git.

### Checks [§1.3]
These are throwaway API checks in a temp folder. Nothing goes into the repo, and their outputs are reference notes only.

Done:
- [x] C1–C3: WowRobo has all servos; a real $90.94 six-servo cart was created, opened and cancelled.
- [x] C4: Shopify's cross-store search finds every SO-101 part.
- [x] C9 (partial): the board-voltage conflict became rule R10.
- [x] Second demo (ESP32 weather display): every part has a US Shopify seller, and all 3 stores answer Shopify's store check.
- [x] C10 first half: ArmDojo and Geekworm both list Shopify's cart tools.

To do:
- [ ] C10 second half: create one cart at ArmDojo and one at Geekworm, open them, cancel them.
- [ ] **C5: the 3D model loads.** Drag `Simulation/SO101/` from the SO-ARM100 zip into https://gkjohnson.github.io/urdf-loaders/javascript/example/bundle/index.html.
- [ ] C11: SingleStore. Create a scratch table with full-text and vector search, run one query of each kind, then drop the table.
- [ ] C12: Superlinked. One embedding call and one ranking call return 200; a first 503 just means the model is cold.
- [ ] C13: Airbyte. Its GitHub connector reads the SO-ARM100 README. **Write down the entity and action names that worked.**
- [ ] C14: `amplitude-ai doctor` passes with your key.
- [ ] C15: Stripe shows one simulated authorization. If this fails, Tier 2 becomes a stretch for every team size.
- [ ] C16 (optional): Checkout Kit popup opens a fresh cart. Don't pay, then cancel the cart.
- [ ] C17: Cognee. One `remember` and one `recall` work.

### Writing and prep
- [ ] Read the 3-minute script [§6.2] out loud with a timer and trim it to 3:00.
- [ ] Learn the 30-second pitch [§6.4].
- [ ] Draw paper wireframes of the 5 designed screens [§11.5].
- [ ] Write knowledge-base notes (they become SingleStore documents after 11:00):
  - the README parts table
  - README line 73 (12V needs a 12V 5A+ supply)
  - the Waveshare 9–12.6V note
  - the DFRobot battery note and the JST-PH 2.0 mm note for the second demo
  - store policy links

### Pack for tomorrow
- [ ] **Physical government photo ID.** Digital IDs aren't accepted, and you must be 18+.
- [ ] Laptop and charger, plus phone and charger.
- [ ] HDMI or USB-C video adapter.
- [ ] Headphones and a power strip.
- [ ] No scooter or bike.

---

## 2. Friday 9:30–11:00 (no code before 11:00)

### Organizers (multi-prize question first) [§1.5]
- [ ] **Can one project win more than one sponsor prize?** If you have to pick one track, go deep on **SingleStore** [§2.5].
- [ ] **How many sponsors can we tick on the submission form?**
- [ ] Is a design doc written beforehand (this plan) allowed if disclosed? Is boilerplate?
- [ ] Are open-source assets okay to use (the SO-101 3D files, Apache-2.0)?
- [ ] What are the judging criteria, and how are finalists picked?
- [ ] Demo format: how long, which laptop, HDMI, is the Wi-Fi reliable?
- [ ] Video: maximum length, host, does it need to be public?
- [ ] Is a localhost demo fine? Is a public URL a plus?

### Sponsor tables, in this order
- [ ] **Amplitude:** is the prize cash; do they want Agent Analytics specifically; does a Statsig gate add weight?
- [ ] **SingleStore:** do vector indexes work on the free tier; what's the recommended hybrid-search SQL; what do they want to see?
- [ ] **Airbyte:** is the local GitHub connector enough, or do they want the Context Layer / MCP?
- [ ] **Superlinked:** model IDs and base URL; can one project enter both $500 prizes; what each one rewards.
- [ ] **Cognee:** Cloud or local for the prize; fastest way to preload facts.

### Before 11:00
- [ ] Final team size, so you know which [§2.4] column applies.
- [ ] Roles A–D assigned [§4.1]; C owns polish [§11.11].
- [ ] Keys shared through the password manager.
- [ ] Walk through the wireframes together.

---

## 3. Build: 11:00–4:30 [§5]

### Gates
| Time | Done means | If not |
|---|---|---|
| [ ] **11:00** | Repo, `.gitignore`, `.env`, `CLAUDE.md` pointing at PLAN.md, scaffold, 3D files copied in | — |
| [ ] **11:20 G0** | Both apps start; fixtures styled with the design tokens; SingleStore answers; backend refuses any non-`sk_test_` Stripe key | Pair up on it. SingleStore unreachable by 11:45 → SQLite |
| [ ] **12:30 G1** | Landing page → README fetched → parts with quotes → fake offers → Approve → Pay-once screen; timeline streams; arm or graph visible | No arm by 12:45 → parts graph |
| [ ] **1:30 G2** | Live offers with US/USD filters; one real cart; a knowledge-base citation for line 73; clicking a servo selects its line; prices stored in SingleStore | Use deep links for stores that refuse carts; full-text search only |
| [ ] **2:30 G3** | Full live hero run [§5 checklist], ending on the Pay-once screen with 3 stores (about $119.93); Verify green; the run shows in Amplitude | Apply the cut list; `scripted.py` if the agent loop is flaky |
| [ ] **3:00 G4** | Replay works with Wi-Fi **off** | Everyone stops features until it does |
| [ ] **3:30 G5** | Feature freeze; every "must" quality check (Q1–Q9) ticked | Hide anything unfinished |
| [ ] **4:00 G6** | Video uploaded; link plays in a private window | Upload the first take as is |
| [ ] **4:20 G7** | **Form submitted**; screenshot saved | 4:30 is the hard deadline |

### Cut decisions, by the clock [§2.1, §2.2]
- [ ] **12:15** Airbyte has returned the README (one retry at 1:30). If not → plain fetch, and drop Airbyte from your claims.
- [ ] **12:45** 3D arm on screen. If not → parts graph.
- [ ] **1:30** Tier 2 Stripe may start only if G2 is green and C15 passed.
- [ ] **1:45** Superlinked returns scores. If not → Claude does the ranking.
- [ ] **2:00** Superlinked extraction works. If not → Claude extraction.
- [ ] **2:15** Cognee recall works. If not → a SingleStore table. Statsig starts only if Amplitude is green.
- [ ] **2:30** Amplitude events are visible. If not → drop Amplitude from your claims.
- [ ] **2:45** Tier 2 shows three "Authorized" rows. If not → hide the toggle.
- [ ] **3:15** Second demo replay recorded. If not → mention it in one sentence.
- [ ] **3:50** Hard stop for the public replay URL.

**A sponsor that gets cut is removed from the README, the form and the pitch.**

### Never cut [§2.3]
Source quotes · signed mandate · refusals · 12V fix with a cited source · approval → real cart links · Pay-once screen (Tier 1) · timeline, why-cards and Verify · design tokens and loading states · replay · "real vs. test" labels.

### Payment rules [§12.2]
- [ ] No real money, ever. No live keys, and the app never completes a checkout.
- [ ] The app refuses to start unless the Stripe keys begin with `sk_test_` / `pk_test_`.
- [ ] The app never collects card numbers; cards are entered only in Stripe's own fields, using Stripe's test cards.
- [ ] A permanent **TEST MODE** badge, and a separate "Real cart" link per store.
- [ ] On stage, stop before paying on any store's checkout.

### Must-pass quality checks at 3:30 [§11.10]
- [ ] Q1: everything styled from the design tokens.
- [ ] Q2: the hero loads in under 1 second, and the main action is obvious.
- [ ] Q3: no layout jump as lines stream in.
- [ ] Q4: loading, empty and error states on every main screen.
- [ ] Q5: no "undefined", "null", "NaN" or stack traces on screen.
- [ ] Q6: all money formatted the same way, with when each price was seen.
- [ ] Q7: everything test-mode is violet, dashed and labelled.
- [ ] Q8: readable at 125% zoom from the back of the room.
- [ ] Q9: your own favicon, page title and logo.

---

## 4. Submission [§9]

### Repo
- [ ] **Public**, and it opens in a private browser window.
- [ ] **No secrets.** Search the history for `sk-`, `sk_test_`, `sk_live_`, `pk_`, `ghp_`, `github_pat_` and `persona_`.
- [ ] README:
  - [ ] Name, tagline and screenshots: the hero, parts with quotes, refusal plus why-card, Pay-once.
  - [ ] How to run, including replay mode with no keys.
  - [ ] The audit trail.
  - [ ] **One section per sponsor actually wired.**
  - [ ] **"What is real vs. test"**, the production note, limitations, and a disclosure of tonight's prep.
- [ ] `THIRD_PARTY.md`: SO-ARM100 3D files, urdf-loader, fonts and libraries. Note that we only read the weather-display README (GPL-3.0) and used none of its code.
- [ ] `cache/` recorded **today** and committed, so replay works for reviewers.
- [ ] `docs/demo-script.md` and `docs/receipt.sample.json`.

### Video (2–3 min)
- [ ] **Follows the stage script; text readable; voice-over.** The TEST MODE badge is visible whenever the Stripe panel is.
- [ ] **Uploaded unlisted; link tested while logged out.**

### Form
- [ ] **Repo link, video link**, plus the public URL if it exists, and the hero screenshot.
- [ ] What you built (the 30-second pitch).
- [ ] **Sponsor field: tick every sponsor that's wired up.** If you're limited to one, pick SingleStore.
- [ ] Tools used: only what's actually wired up.
- [ ] **Team names and emails.**
- [ ] Screenshot of the confirmation page.

---

## 5. Demo: 4:30–5:00, then on stage [§6.1]
- [ ] Laptop charged and plugged in; browser at 125% zoom; popups allowed for localhost.
- [ ] Backend in replay mode with the pinned time set. Warm up Superlinked.
- [ ] Tabs open:
  - [ ] the app on its landing page
  - [ ] Amplitude, on the 2:30 session with the funnel chart
  - [ ] one fresh spare cart per store, created at 4:45
- [ ] Mandate preset: $160, WowRobo + ArmDojo + Geekworm, share country only, deadline Dec 4.
- [ ] Roles set: one person talks, one clicks.
- [ ] **Nobody types a card number on stage**, except Stripe's test card 4242 4242 4242 4242 in the TEST MODE panel.
- [ ] Fallbacks ready [§6.5]: replay, spare cart tabs, parts graph, the video.
- [ ] If asked "is this live?", say it's a replay of a run recorded today with its original timestamps, and that the carts are real.
