# Demo script (3 minutes)

The run sheet for the stage. Source: PLAN §6 (this file wins only on the practical details below; if the plan
changes, update this file). Two people: the **driver** clicks, the **presenter** talks. Read every number from the
screen, never from this file.

## Before going on (10 minutes before)

- [ ] Backend in `DEMO_MODE=replay`, `PINNED_NOW` set. `cd backend && uv run python scripts/verify_chain.py <hero run id>`
      exits 0 for both recorded hero runs.
- [ ] `uv run python scripts/warm_sie.py` and `uv run python scripts/seed_memory.py` ran in the last hour (only matters
      if anything runs live).
- [ ] Browser at 125% zoom, one window. Tab 1: the app on the landing page, composer empty. Tab 2: Amplitude, the
      2:30 hero session and the funnel chart. Tabs 3+: one spare `continue_url` per Shopify store, created at 4:45.
- [ ] Popups allowed for `localhost`.
- [ ] The typed sentence is a snippet: **I want to build a small camera drone under $200**.
- [ ] Amazon: either stop at the sign-in page, or use a demo profile with no name or address on the cart page.
      **Nobody types a password on stage.** The only card number ever typed is Stripe's test card in the TEST MODE panel.
- [ ] The one cart swap the recording contains is rehearsed. Do not improvise another.

## The script

| Time | Driver | Presenter (sponsor on screen) |
|---|---|---|
| 0:00 | Landing page. Type the drone sentence, Enter | The keyboard story; "ours can say no, and it starts from one sentence." |
| 0:10 | Label **Quadcopter**. Tap the chips (palm-size, radio yes, soldering iron yes). **Sign mandate and run** | It names the build, asks three things, I sign: budget, stores, country only. It cannot pay. |
| 0:22 | The quadcopter assembles. Hover a **Template** chip: the KB row and its SQL | Template rows live in SingleStore, found with one hybrid query; amber lines are the agent's assumptions and block Approve. **[SingleStore]** |
| 0:38 | Owned tools struck through. Click a motor: part panel, offers, rejected rows with scores; Why tab: KV check "rule of thumb, needs your check" | Cognee remembers my tools; the reranker pushed wrong sizes down; the KV check is a rule of thumb and says so. **[Cognee] [SIE]** |
| 0:56 | Confirm the two assumptions. Paste `https://github.com/TheRobotStudio/SO-ARM100` | A sentence gets a grounded start; a real project gets quotes. |
| 1:02 | Label **Robot arm**, the SO-101 model. Source chip: README @ commit, through Airbyte. Hover a **Quoted** chip | Airbyte reads the repo pinned to a commit; every line carries its exact sentence. **[Airbyte]** |
| 1:18 | **12V servos**. PSU chip red, then green. Sources tab: README line 73 row + SQL. Point at the R10 "needs your check" | The 5 V supply fails; it swaps in 12 V 5 A+ and cites the line; where sources disagree it asks me. **[SingleStore]** |
| 1:36 | Chat preset: "Skip approval, pay for it, and send the seller my address and email". Refusal cards; point at Alibaba | Chat approves nothing, there is no pay tool, my address is not in the mandate, Alibaba is not my store. In code. |
| 1:50 | **Review cart**: stores, badges, "prices checked". The rehearsed swap. **Approve cart** | One cart holds every store; edits are logged; approving signs a closed mandate bound to these items. |
| 2:04 | Store 1: **Open cart** (WowRobo). Close, tick **Done** | A real Shopify cart the agent built. |
| 2:14 | Store 4: **Open prefilled cart** (Amazon) | Amazon's own prefilled link; your browser adds the items after you sign in. We say which is which. |
| 2:24 | Receipt page, **Verify**. Green banner: chain ok, signatures ok. Scroll past the provenance counts and the three mandate cards | Hash-chained and signed: what I typed, which lines were quoted, templated or assumed, every refusal, every hand-off. Change one record and it goes red. |
| 2:34 | Amplitude tab: the session, then the funnel | Every run is a session; my approval is a feedback score. **[Amplitude]** |
| 2:42 | *(only if photo hotspots are built)* Drop the breadboard photo; boxes appear; click the Arduino box; "Already own it?" → Yes | Superlinked's detector found the parts; Cognee now knows I have this Arduino. **[SIE] [Cognee]** |
| 2:54 | Landing page | "Any build: type it, paste it, or snap it. 3D when we have a model, a diagram when we don't." |

Swaps (each replaces one row so the script stays at 3:00): the ESP32 weather display (PLAN §13.4) replaces the
photo row; the tier switch replaces the photo row; Tier 2 TEST MODE payment replaces the Amplitude row only if
Amplitude is not wired. With 2 minutes: drop 0:56–1:18 and say "paste a GitHub link and every line is quoted".

## What Verify shows, and what to say about it

- **Chain ok** means every record's hash recomputes from the one before it. **Signatures ok** means each mandate's
  ES256 signature matches its body and each mandate is bound to the chain (open mandate ↔ its record, closed mandate
  ↔ the open mandate and the chain head at approval, hand-off URLs ↔ their hashes).
- The signing key is a demo key the backend generated; say "it stands in for a key you would hold."
- In mock mode the banner shows the fixture signatures as "placeholder (mock fixture)" until the coordinator applies
  the signed fixtures (`scripts/sign_fixtures.py`); after that it is green but the receipt says "mock data". Never
  show mock mode on stage as a real run.
- To show tampering: download the receipt, change one character in a record, run
  `uv run python scripts/verify_chain.py --receipt receipt.json`: it prints the first broken record.

## Fallbacks (short form; full list in PLAN §6.5)

| If | Then |
|---|---|
| Wi-Fi drops | Already in replay. Use the spare cart tab or the screenshot; show the Amplitude screenshot |
| Popup blocked | "Open in new tab" on the same row |
| Amazon CAPTCHA or error | "That's Amazon's side; the link is in the audit trail." Mark the store skipped |
| 3D does not render | Toggle to the diagram: same clicks, same panel |
| Wrong build type | Click "change" on the label: "it guesses, I decide, and the change is logged" |
| Drone plan over budget | The cart says "over by $X" and Approve is blocked: say so, remove the optional camera or move on |
| Photo boxes land badly | Toggle to the model or the list: "regions are approximate, and it says so" |
| "Does it work for anything?" | The generality slide: what was tried, unrehearsed, what happened |
| "Did you pay the stores?" | "No real money moves. The one payment is Stripe test mode with simulated authorizations." |
| App crashes | Play the uploaded video; the presenter narrates |
