# Build-to-Cart: everything required (v3, final plan, team of 4)

tokens& Personal Agents Hackathon, Fri Nov 20, 2026, San Francisco. Details are in `PLAN.md` v3; section numbers are in brackets. Older versions are kept in `research/`.

`[x]` = already done tonight. **Bold** = without it you can't compete, submit, or claim that sponsor.

**What we're building:**
- Paste a hardware project link → a parts list with source quotes → offers from **many stores** → a clickable **3D arm**, where clicking a part shows every store's offer and link → one **Universal Cart on our site** → a guided checkout, store by store.
- Every offer shows one of three badges: **Agent cart** (Shopify), **Prefilled cart** (Amazon, Digi-Key, Best Buy, Walmart) or **Product link** (Adafruit, Seeed, SparkFun and the rest).
- No real money moves.

**Cash sponsors (1st-place value):**
- Amplitude + Statsig: $1,000
- SingleStore: $1,000 in gift cards
- Airbyte: $1,000 Visa
- Superlinked: two prizes of $500 cash
- Cognee: $500 cash
- Persona (optional): $250 Keychron gift card per member

**Roles [§4.1]:**
- **A:** agent core, mandate guard, Amplitude
- **B:** stores, cart links, checkout, Stripe
- **C:** frontend, 3D, polish (C has the final say on visuals)
- **D:** SingleStore, Superlinked, Cognee, audit chain and Verify, the video

---

## 1. Tonight (Thu): rules-safe prep only, no project code

### Team and rules
- [ ] **All 4 Luma registrations say Approved.**
- [ ] **Roles A–D assigned.** Each person reads §0, §4 and their own column of §4.4.
- [ ] **Sign in to the submission form** (https://tokensand.com/personalagenthack/submit) and look for a sponsor or track field.
- [ ] Decide who owns the GitHub repo. Create it at 11:00 tomorrow, **not tonight**.

### Required keys
Save them in a shared password-manager note. No `.env` file tonight. Details are in [§1.1].
- [ ] **Anthropic**: check that both `claude-sonnet-5-5` and `claude-opus-5-5` respond, and check your credit.
- [ ] **SerpAPI**, now **required**: 250 searches a month and 50 an hour. That limit is shared by the whole team, so use at most 10 tonight.
- [ ] **Amplitude**: free plan, API key.
- [ ] **SingleStore**: free Shared database and its connection string.
- [ ] **GitHub fine-grained token** for Airbyte: public repos, read-only, 7 days.
- [ ] **Superlinked**: the Serverless base URL from the console, the model IDs (an embedding model, a reranker, a GLiNER extractor) and the embedding dimension.
- [ ] **Stripe test sandbox + Issuing**:
  - [ ] Create the sandbox.
  - [ ] Turn on Issuing.
  - [ ] Top up the test balance.
  - [ ] Create one cardholder.
  - [ ] Run one simulated authorization.
  - [ ] Confirm the keys start with **`sk_test_` / `pk_test_`**.
- [ ] **Video host**: YouTube (unlisted) or Loom.

### Recommended and optional keys
- [ ] **Digi-Key developer app** (recommended): a production app for the Product Information v4 API, giving a client ID and secret. Without it, Digi-Key is skipped.
- [ ] Cognee Cloud key (recommended). If you skip it, Cognee runs locally.
- [ ] Statsig server key (optional).
- [ ] Serper.dev key (optional), as a backup if SerpAPI signup fails.
- [ ] Persona sandbox key and template IDs (optional).
- **Don't bother** with the Best Buy API (no free email addresses), eBay, the Amazon Creators API, AliExpress, LCSC or Mouser.

### Laptop setup (environment, not project code)
Already done on this laptop:
- [x] Node 24.12
- [x] Python 3.13.7
- [x] uv 0.13.7
- [x] Git 2.51
- [x] OBS appears installed. Do a 10-second test recording.

Still to do:
- [ ] `npm install -g @shopify/ucp-cli`, then `ucp doctor`, on whichever laptop B uses.
- [ ] Warm the packages in a **throwaway** venv, then delete it [§1.2].
- [ ] Claude Code signed in on **all 4** laptops. All 4 also need Node 22.19+, Python 3.13, uv and Git.
- [ ] Claude Code skills [§11.12]:
  - [ ] Each person runs `/plugin install frontend-design@claude-plugins-official`.
  - [ ] At 11:00, C copies the CloudAI-X `threejs-*` skills and the Moh4696 `exploded-view` skill into the repo's `.claude/skills/` and lists them in `THIRD_PARTY.md`.
  - [ ] Install nothing else.

### Checks [§1.3]
These are throwaway checks in a temp folder. Write the results in notes; nothing goes into the repo.

Done:
- [x] WowRobo servo search, plus a real $90.94 cart that was created, opened and cancelled.
- [x] Shopify's cross-store search covers every SO-101 part.
- [x] ArmDojo and Geekworm list cart tools.
- [x] The ESP32 demo's parts are all sold in the US.
- [x] Digi-Key quick-add, Best Buy's cart link and Amazon's add-to-cart link all respond. Adafruit, Seeed and SparkFun search works with no key.
- [x] The board-voltage conflict became rule R10.

To do:
- [ ] **C5:** drag `Simulation/SO101/` into the URDF viewer; all parts should show and the joints should move.
- [ ] C10: one test cart at ArmDojo and one at Geekworm, opened, then cancelled.
- [ ] C11: SingleStore full-text and vector queries run on the free tier.
- [ ] C12: Superlinked embedding and ranking calls return 200.
- [ ] C13: Airbyte's GitHub connector reads the SO-ARM100 README. **Write down the entity and action names.**
- [ ] C14: `amplitude-ai doctor` passes.
- [ ] C15: one Stripe simulated authorization shows in the Dashboard.
- [ ] C16 (optional): the Checkout Kit popup opens.
- [ ] C17: one Cognee remember and recall.
- [ ] **C18: Amazon cart link in your own browser**, signed in with two ASINs. Note whether the items go in silently or there's a confirm page, then empty the cart.
- [ ] **C19:** Digi-Key quick-add in a browser, not signed in.
- [ ] **C20:** Best Buy cart link in a browser, then empty the cart.
- [ ] **C21:** Walmart cart link in a browser, then empty the cart.
- [ ] **C22: SerpAPI shapes**, at most 10 searches. Note the query parameter name for each engine and where the ASIN, store link and delivery text appear.
- [ ] C23: one Digi-Key API search, only if you registered.

**A store whose cart link didn't work in a real browser shows as "Product link".**

### Writing and prep
- [ ] Read the 3-minute script [§6.2] out loud with a timer.
- [ ] Learn the 30-second pitch [§6.4].
- [x] Wireframes, as a design canvas of 7 screens: https://claude.ai/artifact/PM9k2pvQujjqTEkWvuejmY
  - [x] landing, workspace with the part panel open, ESP32 board diagram
  - [x] Universal Cart as a draft, the approval dialog, the checkout run, the receipt
  - [ ] The team reviews them together at 10:30. They're a design doc: disclose them in the README and don't copy their HTML into the repo.
- [ ] Knowledge-base notes:
  - [ ] the README parts table
  - [ ] README line 73
  - [ ] the Waveshare 9–12.6V note
  - [ ] the DFRobot and JST battery notes
  - [ ] store policy links

### Pack
- [ ] **Physical government photo ID for each person**, 18+.
- [ ] Laptops and chargers, plus phones and chargers.
- [ ] HDMI or USB-C video adapter, and a power strip.
- [ ] No scooters or bikes.

---

## 2. Friday 9:30–11:00 (no code before 11:00)

- [ ] **Ask the organizers first: can one project win more than one sponsor prize?** If you have to pick one track, go deep on **SingleStore** [§2.5].
- [ ] How many sponsors can we tick on the form? Is a design doc written beforehand OK if disclosed? Are open-source assets OK? Judging criteria? Demo format and laptop? Video rules? Is localhost OK?
- [ ] Sponsor tables in this order: **Amplitude → SingleStore → Airbyte → Superlinked → Cognee**. Questions are in [§1.5].
- [ ] 10:30: confirm roles and share keys, then walk through the wireframes. **Report the C18–C23 results; B writes down which cart-link formats actually work.**

---

## 3. Build: 11:00–4:30 [§5]

### Gates
| Time | Done means | If not |
|---|---|---|
| [ ] **11:00** | Repo, `.gitignore`, `.env`, `CLAUDE.md` pointing at PLAN.md, scaffold | — |
| [ ] **11:20 G0** | Both apps start; sample parts list and sample part panel styled; SingleStore answers; non-`sk_test_` key refused; fetch-allowlist test green | Pair up. SingleStore down at 11:45 → SQLite |
| [ ] **12:30 G1** | Paste link → README → parts with quotes → fake offers → cart page with one link; mandate signed; timeline streams; arm on screen | No arm by 12:45 → 2D diagram |
| [ ] **1:30 G2** | Live offers from Shopify **and** SerpAPI with badges; one real Shopify cart opened; the Amazon cart link opened; knowledge-base citation for line 73; clicking a servo opens the part panel with 3+ stores; prices in SingleStore | A link that fails becomes a product link; full-text search only |
| [ ] **2:30 G3** | Full hero run [§5 G3 list]: refusals, 12V fix, R10 warning, part panel correct, Universal Cart lists every store with the right badge, Approve, one agent cart and one prefilled cart open, progress bar moves, Verify green, run visible in Amplitude | Apply cuts; `scripted.py` if the agent loop is flaky |
| [ ] **3:00 G4** | Replay works with Wi-Fi **off**, through the Universal Cart and the checkout run | Everyone stops features until it does |
| [ ] **3:30 G5** | Feature freeze; every "must" quality check (Q1–Q9) ticked | Hide anything unfinished |
| [ ] **4:00 G6** | Video uploaded; plays in a private window | Upload the first take |
| [ ] **4:20 G7** | **Form submitted**; screenshot saved | 4:30 is the hard deadline |

### Cut decisions by the clock [§2.1, §2.2]
A makes the call, with no debate past the stated time.
- [ ] **11:45** SingleStore connects. If not → SQLite, and drop it from your claims.
- [ ] **12:15** Airbyte has read the README (one retry at 1:30). If not → plain fetch.
- [ ] **12:45** 3D arm with click picking. If not → 2D diagram; the part panel still opens from the list.
- [ ] **1:15** SerpAPI offers in the shared format. If not → Serper.dev, or Shopify plus the no-key stores.
- [ ] **1:30** A person has opened every cart-link format in a browser. Any that failed → product link. Walmart, Best Buy and the SerpAPI Walmart/eBay engines can be cut here.
- [ ] **1:45** Superlinked scores. If not → Claude does the ranking.
- [ ] **2:00** Superlinked extraction. Also the Tier 2 start gate (needs G2 green, C15 passed, hand-offs working).
- [ ] **2:15** Cognee recall (if not → a SingleStore table). Statsig and Digi-Key start gates.
- [ ] **2:30** Amplitude events visible. Colour modes may start. Cart editing round-trips. Adafruit, Seeed and SparkFun adapters return offers. Second demo may start.
- [ ] **2:45** Tier switch recolours the model. Tier 2 shows three "Authorized" rows. B records the hero run.
- [ ] **3:00** Digi-Key done or dropped.
- [ ] **3:15** Second demo replay recorded. If not → mention it in one sentence.
- [ ] **3:50** Hard stop for the public replay URL.

**A cut sponsor comes out of the README, the form and the pitch.**

### Never cut [§2.3]
- Source quotes, signed mandate, refusals, and the 12V fix with a cited source.
- Offers from Shopify plus one other source, with timestamped prices.
- **Badges that tell the truth.**
- Approval → one agent cart and one prefilled cart.
- **The Universal Cart with every store and the guided checkout.**
- Timeline and Verify.
- **Click → part panel.**
- Design tokens and loading states, replay, and the "real vs. test" labels.

### Hard rules
- [ ] No real money, no live keys; the app never completes a checkout or collects card numbers.
- [ ] Permanent TEST MODE badge on anything Stripe.
- [ ] **Never send requests to bot-walled sites** (Amazon, Digi-Key's website, eBay, Walmart, Micro Center, Octopart, RobotShop's main domain). Use APIs and SerpAPI only, and cache everything.
- [ ] The replay cache is recorded **today**, not from tonight's notes.
- [ ] **3D works offline** [§11.12]:
  - [ ] Lighting from `RoomEnvironment` (no drei `preset=`).
  - [ ] No Draco-compressed models.
  - [ ] No drei `<Text>` without a local font.
  - [ ] With Wi-Fi off, DevTools shows no requests to githack, gstatic, Google Fonts or jsDelivr.
- [ ] Pinned 3D versions: react 19.3.1, three 0.186.1, fiber 9.8.2, drei 10.7.9, postprocessing 3.2.2 / 6.39.6.
- [ ] Nobody types a password or real card on stage.

### Must-pass quality checks at 3:30 [§11.10]
- [ ] Q1: everything styled from the design tokens.
- [ ] Q2: the hero loads in under 1 second, with an obvious main action.
- [ ] Q3: no layout jumps.
- [ ] Q4: loading, empty and error states.
- [ ] Q5: no "undefined" or "NaN" on screen.
- [ ] Q6: money formatted consistently, with when each price was seen.
- [ ] Q7: everything test-mode is violet and labelled.
- [ ] Q8: readable at 125% zoom.
- [ ] Q9: your own favicon, title and logo.

---

## 4. Submission [§9]
- [ ] **Repo public**; opens in a private window.
- [ ] **No secrets.** Search the history for `sk-`, `sk_test_`, `sk_live_`, `pk_`, `ghp_`, `github_pat_`, `persona_` and the SerpAPI key.
- [ ] README:
  - [ ] Screenshots: the 3D part panel, the Universal Cart, refusals.
  - [ ] **Each store's action level, stated honestly.**
  - [ ] **One section per sponsor actually wired.**
  - [ ] **"What is real vs. test"**, the production note, limitations, and a disclosure of tonight's prep.
- [ ] `THIRD_PARTY.md`: SO-ARM100 3D files, urdf-loader, fonts and libraries. Note that we only read the GPL-3.0 weather-display README and used none of its code.
- [ ] `cache/` recorded today and committed. Also `docs/demo-script.md` and `docs/receipt.sample.json`.
- [ ] **Video, 2–3 min:** readable, voice-over, TEST MODE visible; **unlisted, and the link tested while logged out.**
- [ ] **Form:**
  - [ ] Repo link and video link.
  - [ ] What you built.
  - [ ] **Every sponsor that's wired** (SingleStore if you can pick only one).
  - [ ] Tools actually used.
  - [ ] **Team names and emails.**
  - [ ] Confirmation screenshot.

---

## 5. Demo: 4:30–5:00, then on stage [§6.1]
- [ ] Laptop charged and plugged in; 125% zoom; popups allowed for localhost; replay mode on; Superlinked warmed up.
- [ ] Tabs open:
  - [ ] the app
  - [ ] Amplitude on the 2:30 session
  - [ ] one fresh spare Shopify cart per store, made at 4:45
- [ ] Mandate preset:
  - [ ] Budget $160.
  - [ ] Stores: WowRobo, ArmDojo, Geekworm (agent cart), Amazon (prefilled), Seeed, Adafruit, SparkFun (product link).
  - [ ] Share country only.
  - [ ] Deadline Dec 4.
- [ ] **Rehearse the one cart swap that's in the recording; don't improvise another.**
- [ ] **Amazon on stage:** stop at the sign-in page, or use a demo profile that's already signed in and shows no name or address. If Digi-Key was built, prefer its link, since it needs no sign-in.
- [ ] One person talks, one clicks. The only card number typed is Stripe's test card 4242 4242 4242 4242, in the TEST MODE panel.
- [ ] Fallbacks ready [§6.5]: replay, spare cart tabs, 2D diagram, the video.
