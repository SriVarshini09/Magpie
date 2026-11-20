# Build-to-Cart: everything required (v4, team of 4)

tokens& Personal Agents Hackathon, Fri Nov 20, 2026, San Francisco. Details are in `PLAN.md` v4; section numbers are in brackets. Older versions are kept in `research/`.

`[x]` = already done. **Bold** = without it you can't compete, submit, or claim that sponsor.

**What we're building:**
- One box asks **"What do you want to build?"** You type it, paste a link, or upload a photo.
- The agent names the build type and asks up to 3 chip questions. It builds the parts list, and **every line shows where it came from**: a quote, a template, a reference design, your photo, or an assumption you must confirm.
- An **anatomy view** matches the build: the real 3D arm, a code-built 3D drone, RC car or claw, a board diagram, a kit view, or your own photo with clickable boxes.
- **Click a part** to see every store's offer.
- **One Universal Cart** holds everything, followed by a guided checkout store by store.
- Store badges: **Agent cart** (Shopify), **Prefilled cart** (Amazon, Digi-Key, Best Buy, Walmart), **Product link** (the rest). No real money moves.

**Cash sponsors (1st place):**
- Amplitude + Statsig: $1,000
- SingleStore: $1,000 gift cards. It holds the templates, the knowledge base, prices and the audit log.
- Airbyte: $1,000 Visa. It reads GitHub, and searches Exa for reference designs.
- Superlinked: 2 × $500 cash. It does extraction, ranking and photo detection.
- Cognee: $500 cash. It remembers what you own, including from photos.
- Persona (optional): $250 gift card per member.

**Roles [§4.1]:**
- **A:** agent core, intake and router, provenance, mandate guard.
- **B:** stores, cart links, checkout, search providers, Stripe.
- **C:** frontend, all views, polish. C has the final say on visuals.
- **D:** data, templates, rules, SingleStore, Superlinked, Cognee, Amplitude, the audit chain, the video.

---

## 1. Tonight: rules-safe prep only, no project code

### Team and rules
- [ ] **All 4 Luma registrations say Approved.**
- [ ] **Roles A–D assigned.** Each person reads §0, §2.0, §4 and their own column of §4.4.
- [ ] **Sign in to the submission form** (https://tokensand.com/personalagenthack/submit) and look for a sponsor or track field.
- [ ] Decide who owns the GitHub repo. Create it at 11:00, **not tonight**.

### Required keys
Save them in a shared password-manager note. No `.env` file tonight. Details are in [§1.1].
- [ ] **Anthropic**:
  - [ ] Both `claude-sonnet-5-5` and `claude-opus-5-5` respond.
  - [ ] Credit balance checked.
  - [ ] **Web search is enabled for the organization** in the Console (C26).
- [ ] **SerpAPI**: 250 searches a month and 50 an hour, shared by the whole team. Use at most 10 tonight.
- [ ] **Amplitude**: API key.
- [ ] **SingleStore**: free database and its connection string.
- [ ] **GitHub fine-grained token** for Airbyte: public repos, read-only, 7 days.
- [ ] **Superlinked**: the base URL from the console, the model IDs (embedding, reranker, GLiNER extractor, **grounding-dino-base**) and the embedding dimension.
- [ ] **Stripe test sandbox + Issuing**:
  - [ ] Turn on Issuing.
  - [ ] Top up the test balance.
  - [ ] Create one cardholder.
  - [ ] Run one simulated authorization.
  - [ ] Confirm the keys start with **`sk_test_` / `pk_test_`**.
- [ ] **Video host**: YouTube (unlisted) or Loom.

### New search keys (optional, but try tonight)
- [ ] **Keenable** (keenable.ai): try the signup. The site says 100,000 free requests a month; the docs say waitlist. If you get a key, it becomes the default reference-design search.
- [ ] **Exa** (exa.ai): $20 free credits. It's used through Airbyte's Exa connector.

### Recommended and optional keys
- [ ] Digi-Key developer app: a production app with a client ID and secret.
- [ ] Cognee Cloud key.
- [ ] Statsig server key, Serper.dev backup key, Persona sandbox key (optional).
- **Don't bother** with the Best Buy API, eBay, the Amazon Creators API, AliExpress, LCSC or Mouser.

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
  - [ ] At 11:00, C copies the CloudAI-X `threejs-*` skills and the Moh4696 `exploded-view` skill into `.claude/skills/` and lists them in `THIRD_PARTY.md`.
  - [ ] Install nothing else.

### Checks [§1.3]
These are throwaway checks in a temp folder. Write the results in notes; nothing goes into the repo.

Done:
- [x] WowRobo servos, plus a real $90.94 cart that was created, opened and cancelled.
- [x] Shopify cross-store search covers every SO-101 part.
- [x] ArmDojo and Geekworm list cart tools.
- [x] The ESP32 demo's parts are sold in the US.
- [x] Digi-Key, Best Buy and Amazon cart links respond. Adafruit, Seeed and SparkFun search needs no key.
- [x] Rule R10 added for the board-voltage conflict.

From v3 (C5, C10–C23):
- [ ] **C5:** the 3D arm loads in the URDF viewer.
- [ ] C10: test carts at ArmDojo and Geekworm, then cancel them.
- [ ] C11: SingleStore full-text and vector queries.
- [ ] C12: Superlinked embedding and ranking calls.
- [ ] C13: Airbyte's GitHub connector reads the README. **Write down the entity and action names.**
- [ ] C14: `amplitude-ai doctor`.
- [ ] C15: Stripe simulated authorization.
- [ ] C16: Checkout Kit popup (optional).
- [ ] C17: Cognee remember and recall.
- [ ] **C18–C21:** Amazon, Digi-Key, Best Buy and Walmart cart links in a real browser. Empty the carts afterwards.
- [ ] **C22:** SerpAPI response shapes, at most 10 searches.
- [ ] C23: Digi-Key API, only if you registered.

New in v4 (C24–C31):
- [ ] **C24: Claude vision smoke test.** Send one team photo; check the build type and part boxes are right; note the latency.
- [ ] **C25: Superlinked grounding-dino** on the same photo. **Write down the box format** (`x,y,w,h` or `x1,y1,x2,y2`) and the latency.
- [ ] C26: Claude web search tool, with one search restricted to allowed domains.
- [ ] **C27: Test inputs and photos.**
  - [ ] Pick 5 unrehearsed inputs (2 text, 2 photos, 1 link) and **seal them until 2:35**.
  - [ ] Take 4–6 photos of hardware the team owns (drone, RC car, breadboard with jumper wires, a gripper) on a plain background.
  - [ ] **Team photos only.** No vendor product photos.
- [ ] C28: GitHub search API, with one call.
- [ ] C29 (optional, look only): the TRELLIS.2 Space's API panel. Don't upload anything.
- [ ] C30: Keenable search plus one page fetch, if you have a key. **Never fetch a store page.**
- [ ] C31: Exa through Airbyte's connector, if you have a key. Write down the entity and action names.

**Any cart link that didn't work in a real browser shows as "Product link".**

### Wireframes
- [x] A 7-screen design canvas: https://claude.ai/artifact/PM9k2pvQujjqTEkWvuejmY
- [ ] Update the wireframes for v4 [§11.13]:
  - [ ] **Landing:** the composer.
  - [ ] **Workspace:** the assumption bar, provenance chips, and the quadcopter version.
  - [ ] **Part panel:** template and assumption sources.
  - [ ] **Photo hotspots:** a new screen.
  - [ ] **Cart:** "Confirm 2 assumptions first".
  - [ ] **Receipt:** the intake card.
- [ ] The team reviews them together at 10:30. They're a design doc: disclose them, and don't copy their HTML into the repo.

### Writing and prep
- [ ] Read the 3-minute script [§6.2] out loud with a timer. **It opens with the typed drone request.**
- [ ] Learn the 30-second pitch [§6.4].
- [ ] Knowledge-base and template notes: the README parts table and line 73, the Waveshare voltage note, the battery notes, and the reference designs in **Appendix B** (PX4 X500, Donkey Car, SO-ARM100). These are notes only; they become template files after 11:00.

### Pack
- [ ] **Physical government photo ID for each person**, 18+.
- [ ] Laptops and chargers, plus phones and chargers.
- [ ] HDMI or USB-C video adapter, and a power strip.
- [ ] **The hardware you photographed**, if it's small enough to bring. It's a great live photo demo.
- [ ] No scooters or bikes.

---

## 2. Friday 9:30–11:00 (no code before 11:00)

- [ ] **Ask the organizers first: can one project win more than one sponsor prize?** If you have to pick one track, go deep on **SingleStore** [§2.5].
- [ ] How many sponsors can we tick on the form? Is a design doc written beforehand OK if disclosed? Are open-source assets OK? Judging criteria? Demo format? Video rules? Is localhost OK?
- [ ] Sponsor tables in this order: **Amplitude → SingleStore → Airbyte → Superlinked → Cognee**.
  - [ ] Ask Superlinked about **grounding-dino on Serverless and its box format**.
  - [ ] Ask Airbyte whether **a second connector (Exa)** counts for more.
- [ ] 10:30:
  - [ ] Confirm roles and share keys.
  - [ ] Walk through the wireframes: composer and chips, part panel, Universal Cart, diagram, photo hotspots.
  - [ ] Report the C18–C31 results. B writes down the cart-link formats and search providers that work; D writes down the box format.
  - [ ] **The 5 sealed test inputs go to D.**

---

## 3. Build: 11:00–4:30 [§5]

### Gates
| Time | Done means | If not |
|---|---|---|
| [ ] **11:00** | Repo, `.gitignore`, `.env`, `CLAUDE.md` pointing at PLAN.md, scaffold, skills copied in | — |
| [ ] **11:20 G0** | Both apps start; sample parts list and part panel styled; SingleStore answers; non-`sk_test_` key refused; fetch-allowlist test green | Pair up. SingleStore down at 11:45 → SQLite |
| [ ] **12:30 G1** | **Both paths, with fake offers.** SO-101 link → quoted parts → cart page. **Typed drone request → "Quadcopter" label → chips → template lines** → plan. Mandate signed; the arm or the quadcopter is on screen | No arm or quad by 12:45 → diagram. No templates from SingleStore by 1:00 → read them from disk |
| [ ] **1:30 G2** | Live offers from Shopify **and** SerpAPI; one real cart and the Amazon cart link opened by hand; knowledge-base citation for line 73; servo click opens a panel with 3+ stores; **the drone run has live offers for motors, battery and flight controller, and rules G1/G3/G5/G7 run; a person has read every row of both MVP templates** | A link that fails becomes a product link; full-text search only |
| [ ] **2:30 G3** | **Both hero runs live.** Drone: 10+ lines with provenance chips, one assumption blocking Approve, the quad assembles, motor panel with 2+ stores. Arm: everything from v3 (refusals, 12V fix, R10, cart, hand-offs, Verify). Both runs show in Amplitude | Apply fallbacks; `scripted.py` if the agent loop is flaky |
| [ ] **2:35–2:55** | **Generality test:** 5 sealed inputs, run live, results recorded **unedited** for the slide [§5.1] | Never skipped. If G3 is red, run 3 inputs at 3:05 |
| [ ] **3:00 G4** | Replay works with Wi-Fi **off**, for both hero flows from the composer through the checkout run | Everyone stops features until it does |
| [ ] **3:30 G5** | Feature freeze; every "must" quality check (Q1–Q9) ticked | Hide anything unfinished |
| [ ] **4:00 G6** | Video uploaded; plays in a private window | Upload the first take |
| [ ] **4:20 G7** | **Form submitted**; screenshot saved | 4:30 is the hard deadline |

### Fallback times (safety nets, nothing removed) [§2.0–2.2]
A calls them, with no debate past the stated time.
- [ ] **11:45** SingleStore connects. If not → SQLite.
- [ ] **12:15** Airbyte reads the README. If not → plain fetch; one retry at 1:30.
- [ ] **12:45** 3D arm and **procedural quadcopter** with click picking. If not → diagram; the quad may still land until 2:30.
- [ ] **1:00** Templates load from SingleStore. If not → read them from disk.
- [ ] **1:15** SerpAPI offers. **1:30** cart links opened by a person; any that failed → product link.
- [ ] **1:45** Superlinked scores. **The other 4 templates** pass their tests; any that fail → routed to "Generic".
- [ ] **2:00** Superlinked extraction. Tier 2 start gate.
- [ ] **2:15** Cognee, Statsig, Digi-Key start gate. **Photo input** works on 2 team photos. **Full rule pack** passes. **Keenable** returns results.
- [ ] **2:30** Amplitude events visible. Colour modes. Cart editing. Adafruit, Seeed and SparkFun. **Superlinked detection. Kit view. Exa via Airbyte. Non-GitHub links.**
- [ ] **2:45** Tier switch. Tier 2 finish gate. **Photo hotspots. RC car and claw models. Reference search** (otherwise templates only). B records both hero runs.
- [ ] **3:00** Digi-Key. **3:15** second demo, and the TRELLIS stretch. **3:50** public replay URL.

**Whatever is still on its fallback at 3:30 is described as exactly that in the README, the form and the pitch.**

### Never cut [§2.3]
- One composer, the build-type label and chips.
- **Provenance on every line, and no Approve while an assumption is unconfirmed.**
- The typed drone path, and a view for every build type.
- Link-path quotes, the signed mandate, refusals, and the 12V fix with a cited source.
- Offers from Shopify plus one other source, with timestamped prices.
- **Badges that tell the truth.**
- One agent cart and one prefilled cart.
- **The Universal Cart and the checkout run.**
- Timeline and Verify.
- **Click → part panel.**
- Design tokens and loading states, replay, and the "real vs. test" labels.

### Hard rules
- [ ] No real money, no live keys; the app never completes a checkout or collects card numbers. Permanent TEST MODE badge on anything Stripe.
- [ ] **Never request bot-walled sites** (Amazon, Digi-Key's website, eBay, Walmart, Micro Center, Octopart, RobotShop's main domain), **directly or through Keenable, Exa or any other fetcher.**
- [ ] **Photos:**
  - [ ] Team photos only. EXIF data stripped. Kept on disk and git-ignored.
  - [ ] Never sent to SingleStore, Amplitude or any store.
  - [ ] The composer says the photo is sent to Claude and Superlinked.
- [ ] **Template lines are labelled as templates** ("rule of thumb" where they are), never shown as quotes.
- [ ] The replay cache is recorded **today**.
- [ ] **3D works offline** [§11.12]:
  - [ ] Lighting from `RoomEnvironment`.
  - [ ] No Draco-compressed models.
  - [ ] No drei `<Text>` without a local font.
  - [ ] With Wi-Fi off, DevTools shows no requests to githack, gstatic, Google Fonts or jsDelivr.
- [ ] Pinned versions: react 19.3.1, three 0.186.1, fiber 9.8.2, drei 10.7.9, postprocessing 3.2.2 / 6.39.6.
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
- [ ] **No secrets.** Search the history for `sk-`, `sk_test_`, `sk_live_`, `pk_`, `ghp_`, `github_pat_`, `persona_` and the SerpAPI, Keenable and Exa keys.
- [ ] README:
  - [ ] Screenshots: composer, 3D part panel, Universal Cart, refusals.
  - [ ] **The five provenance types, explained honestly.**
  - [ ] **Each store's action level.**
  - [ ] **One section per sponsor actually wired.**
  - [ ] **"What is real vs. test".**
  - [ ] **The generality test table, unedited.**
  - [ ] Limitations, and a disclosure of tonight's prep (the plan, the wireframes, the photos).
- [ ] `THIRD_PARTY.md`:
  - [ ] SO-ARM100 3D files, urdf-loader, the skills, fonts and libraries.
  - [ ] Reference designs used by the templates (PX4 docs CC BY 4.0, Donkey Car, SO-ARM100).
  - [ ] A note that we only read the GPL-3.0 weather-display README and used none of its code.
- [ ] `cache/` recorded today and committed. Also `docs/demo-script.md` and `docs/receipt.sample.json`.
- [ ] **Video, 2–3 min:** opens with the typed drone request. TEST MODE visible. **Unlisted, link tested while logged out.**
- [ ] **Form:**
  - [ ] Repo link and video link.
  - [ ] What you built.
  - [ ] **Every sponsor that's wired.**
  - [ ] Tools actually used.
  - [ ] **Team names and emails.**
  - [ ] Confirmation screenshot.

---

## 5. Demo: 4:30–5:00, then on stage [§6.1]
- [ ] Laptop charged and plugged in; 125% zoom; popups allowed; replay mode on; Superlinked warmed up.
- [ ] Tabs open:
  - [ ] the app on the composer
  - [ ] Amplitude
  - [ ] one fresh spare Shopify cart per store
- [ ] **Opening:** type "a small camera drone…" → chips → the quadcopter assembles → click a motor → part panel → cart. **Then** the SO-101 link → 12V fix and refusals → Approve → checkout run → Verify. Add a photo segment if it's ready.
- [ ] **Read the drone total against the spoken budget honestly.** If it's over, say so: that's the agent working.
- [ ] Rehearse the one cart swap that's in the recording; don't improvise another.
- [ ] Amazon: stop at the sign-in page, or use a demo profile that's already signed in and shows no name or address.
- [ ] One person talks, one clicks. The only card number typed is Stripe's test card 4242 4242 4242 4242.
- [ ] Fallbacks ready [§6.5]: replay, spare cart tabs, diagram, the video, and the generality slide.
