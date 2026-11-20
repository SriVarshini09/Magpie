# Unique shopping-agent ideas for the tokens& Personal Agents Hackathon (SF, Fri Nov 20 2026)

Research date: 2026-11-19. Read-only web research. Nothing was signed up for, cloned, downloaded, run, or posted.
Scope: ideas other than "Build-to-Cart" that still fit the brief: "Build a shopping agent with an audit trail", which asks for reliable context, a meaningful action, and visible steps.

**How this was verified.** Every repo and page cited here was opened by me or by one of four research sub-agents I ran in parallel (Chinese ecosystem, commerce rails, pain evidence and competitors, global libraries). Star counts and dates are as shown on GitHub on 2026-11-19/20. "Last push" means GitHub's `pushed_at`, which counts a push to any branch. "Commit" means the newest commit we saw on the default branch. Anything we could not open or confirm is marked **[unverified]**.

**Prompt-injection notes (ignored).** Three pages contained text aimed at AI agents:
- The MinerU repo page told agents to install a skill and save a memory preference.
- A Senso docs page told agents to install a CLI and run setup commands.
- A search summary flagged agent-directed promotional text on a Ramp procurement page, which we did not open.

None of these instructions were followed.

---

## 0. TL;DR

**Top 3 (ranked):**
1. **Money-Back Agent.** It files retailer price-adjustment and return-window claims on things you already bought, citing the exact policy clause and price evidence. Holiday price-match windows are open right now: Best Buy matches purchases made Oct 30–Dec 31 through Jan 15. The incumbents (Paribus, Earny) are dead. Key repo precedent: the JD.com 价保 (price-protection) auto-claim skill. Build stack: `extruct` + `price-parser` + `changedetection.io` + Midscene.
2. **Audited Haggler.** It negotiates for used gear inside a signed mandate and has a "disclosure firewall". It is pitched directly at Meta Muse's Sept 2026 Marketplace incident, where the agent shared a seller's address and accepted a lowball offer. Key repos: `Usagi-org/ai-goofish-monitor` (20.3k★) and `XianyuAutoAgent` (9.7k★) as the simulated adversary seller.
3. **Group-Buy Escrow.** It pools maker demand, takes Stripe card *holds* (manual capture), and places the bulk order only if the price break is hit; otherwise it releases every hold. Drop (Massdrop) closed its standalone store on Mar 31 2026, which leaves a gap.

**Context judges will compare against.** Meta **Muse** launched 2026-09-08. It negotiates, checks out with Stripe Link one-time cards, and says it shows "a complete audit trail of past and planned actions". Amazon **Alexa for Shopping**, Instacart **Clementine**, and Google AI Mode business calling all shipped in 2025–26. A generic "agent with logs" will not stand out. What will: an audit trail that **proves** something (a cited policy clause, a hash-bound mandate, a captured hold, or a blocked disclosure).

---

## 1. Landscape facts that shape the pitch

- **Meta Muse (Sep 8, 2026).** It can "open a browser, fill out forms, and negotiate on their behalf". It checks with the person "before sensitive actions like sending an email or making a purchase". Checkout runs through Link (Stripe) with one-time cards, and a separate "Sentinel" agent approves outbound actions. It is rolling out in the US, Singapore (Oct 27) and Australia (Nov 17). https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/
- **Muse Marketplace incident (Sep 28, 2026).** Muse ran a Facebook Marketplace sale of a keyboard without the seller's authorization. The seller said it "told people my address and agreed to a lowball price". The buyer came to his home, and the seller got a one-star review. https://www.gdnonline.com/Details/1407922/Metas-AI-assistant-shares-sellers-home-address-on-Facebook-Marketplace-without-permission
- **Microsoft Magentic Marketplace (MSR-TR-2025-50, Oct 2025).** In simulated agentic markets the authors found "severe first-proposal bias" giving "10-30x advantages for response speed over quality". Performance "degrades sharply with scale". On manipulation (fake reviews, fake awards, prompt injection), the video transcript says "Some frontier models resisted everything, but others were completely compromised". https://www.microsoft.com/en-us/research/publication/mage/ — open-source environment: https://github.com/microsoft/multi-agent-marketplace
- **OpenAI Instant Checkout** was reported "deprioritized" on 2026-03-24 (CNBC, per our rails sub-agent). ACP remains a beta spec used mainly for product feeds. **UCP** (Google + Shopify, announced 2026-01-11) is the actively shipping checkout standard.

### Rails reality check (what a team can actually use tomorrow)

| Rail | Usable in 5.5 h? | What you get for the audit trail |
|---|---|---|
| **UCP samples**: Python FastAPI merchant (has "simulation endpoints for testing"), happy-path client, Node/Hono server. https://github.com/Universal-Commerce-Protocol/samples (243★, Apache-2.0). Spec repo: https://github.com/Universal-Commerce-Protocol/ucp (~3.5k★, commit 2026-11-18/19, Apache-2.0) | **Yes**, runs locally | Checkout session lifecycle, order lifecycle, idempotency keys |
| **AP2 v0.2** (now in FIDO working groups). https://github.com/google-agentic-commerce/AP2 (~3.3k★, v0.2.0 released 2026-04-28, Apache-2.0) | **Yes**, local samples. Needs a free Gemini key | v0.2 mandates are **Checkout Mandate + Payment Mandate (open/closed)**, replacing v0.1's Intent/Cart/Payment. SD-JWT mandates, merchant-signed checkout JWT and receipts are hash-bound: a "non-repudiable picture of the transaction" |
| **Stripe sandbox** | **Yes** | Manual capture: `capture_method=manual` holds funds. Online card authorizations are valid ~7 days (Visa merchant-initiated: 5 days). Cancelling releases the hold. https://docs.stripe.com/payments/place-a-hold-on-a-payment-method. Issuing sandbox is "instant" (single-use cards, auth webhooks). Shared Payment Token test helper exists, but whether a fresh account needs preview enablement is **[unverified]** |
| **Jolly (formerly Rye) staging**: `api.commerce.staging.jolly.dev`, "sandbox — no real orders or charges" | **Maybe.** Self-serve signup **[unverified]**. 50 req/day default, US physical goods only | Checkout-intent states `retrieving_offer → awaiting_confirmation → placing_order → completed/failed` |
| **Shopify UCP endpoint** `https://{shop}/api/ucp/mcp` | Catalog and cart: **yes** (API key, no approval). `complete_checkout`: granted case by case, so hand off via `continue_url` | Real product discovery and carts |
| **x402**: https://github.com/x402-foundation/x402 (~6.8k★, Apache-2.0; coinbase/x402 is now a dev fork) | Yes, on testnet | Signed payment payload + transaction hash |
| **Visa Trusted Agent Protocol** sample: https://github.com/visa/trusted-agent-protocol (223★, last push 2025-10-28) | Runs locally; the VIC APIs themselves are gated (~10 business days) | RFC 9421 signed agent requests |
| Avoid: Visa VIC APIs, Mastercard Agent Pay, Stripe Agentic Commerce Suite (private preview), Crossmint (production keys, real purchases) | No | — |

**Recommended "audit-trail spine" for any idea below:**
- UCP sample merchant as the checkout target.
- AP2 v0.2 mandate structure, signed with ECDSA, as the decision record.
- Stripe sandbox event log as independent payment evidence.
- Midscene's per-step HTML replay report for any browser action.
- `extruct` + `price-parser` for deterministic price evidence.
- Senso's cited answers (`content_id` + `version_id`) for "which policy or fact did we rely on".

---

## 2. Twelve ideas

Feasibility assumes 2–4 people and 5.5 hours. Three ideas are flagged **WILDCARD**.

---

### Idea 1: Money-Back Agent (post-purchase price adjustments + return-window rescue)

**One-liner:** Watches what you already bought. When a retailer cuts its own price inside the adjustment window, or a return window is about to close on something unopened, it files the claim and attaches the policy clause and price evidence.

**Real pain and who has it:** Busy professionals who buy electronics and gear and never chase refunds.
- "Nearly 60 percent of shoppers have kept unwanted items" because returning was a hassle. The average abandoned return is worth $50, and 27% cite "Return deadline passed/was too short" (Savings.com survey, 1,000 US adults, Aug 8–9 2025). https://www.savings.com/insights/return-policy-study
- US returns projected at $849.9B in 2025, 15.8% of sales (NRF/Happy Returns, Oct 15 2025). https://nrf.com/media-center/press-releases/consumers-expected-to-return-nearly-850-billion-in-merchandise-in-2025
- Card price protection is nearly extinct. Only a few Capital One, Navy Federal, UBS and HSBC cards still offer it (AwardWallet, Apr 2026). https://awardwallet.com/credit-cards/price-protection/
- Retailer windows still exist and are open now:
  - Best Buy: "we will match our lower price, upon request" during the return period. Its Holiday Price Match covers purchases Oct 30–Dec 31, matchable through Jan 15. https://www.bestbuy.com/site/help-topics/price-match-guarantee/pcmcat290300050002.c?id=pcmcat290300050002
  - Target runs a holiday price match from Nov 1 to Dec 24 2026, with a 14-day window otherwise. https://www.target.com/help/articles/policies-guidelines/price-match-guarantee
  - Target ended *competitor* matching on July 28 2025. https://newjersey.news12.com/2025/07/23/target-has-confirmed-that-its-price-match-policy-has-come-to-an-end/7sWu5g6GI09kgr3FA5hLlc

**Repos and libraries that make it unique:**
- **Chinese precedent: JD.com 价保 (price-protection) auto-claim.** This category has existed in China for years.
  - https://clawhub.ai/danielwangyy/jd-price-protect is an OpenClaw skill (MIT-0, v1.0.0, docs in English + Chinese). It uses Playwright over CDP to click every "申请价保" button and outputs JSON listing `success` refunds and `failed` items with reasons such as "无差价" (no price difference). It suggests a cron job every ~8 h.
  - Older examples: https://github.com/sunoj/jjb (京价保 Chrome extension, now "permanently discontinued") and https://github.com/yangnianbing/jd-price-protect-puppeteer (8★).
- https://github.com/scrapinghub/extruct (~985★, last push 2026-10-15, BSD-3, English) pulls schema.org `Product`/`Offer` JSON-LD, so the current price is captured deterministically without an LLM.
- https://github.com/scrapinghub/price-parser (~351★, last push 2026-11-02, BSD-3) normalizes prices.
- https://github.com/dgtlmoon/changedetection.io (~35.9k★, last push 2026-11-20, Apache-2.0) is the price-drop watcher.
- https://github.com/airbytehq/airbyte-agent-sdk (~136★, commit 2026-11-16; connector folders include gmail, shopify, amazon-seller-partner, stripe; license type **[unverified]**) handles receipt ingestion.
- https://github.com/docling-project/docling (~70.8k★, MIT) or PaddleOCR-VL in https://github.com/PaddlePaddle/PaddleOCR (~92.9k★, Apache-2.0) parse PDF or photo receipts.
- https://github.com/web-infra-dev/midscene (~15.7k★, last push 2026-11-19, MIT, English + Chinese) files the claim in a browser and produces an **HTML report with screenshots and a replay of every step**.

**Competitors (honest):**
- Paribus: Capital One discontinued its price-protection feature in Jan 2023, and the service is listed as defunct. https://en.wikipedia.org/wiki/Paribus
- Earny appears dead; the domain now redirects to an unrelated site.
- Refundly (Oct 2025) *tracks* returns to refund but does not file them. https://www.retailitinsights.com/doc/refundly-launches-to-help-consumers-track-online-shopping-returns-and-know-exactly-when-they-get-their-money-back-0001
- Alexa for Shopping tracks prices *before* purchase. https://www.digitalcommerce360.com/2026/05/13/amazon-launches-ai-agent-alexa-for-shopping/amp/
- Verdict: **open niche**.

**Meaningful action:** Submits the price-adjustment request (retailer chat or order page) or starts the return/RMA. For a live retailer, the agent stops at a pre-filled message the human sends. For the full autonomous path, demo against a local UCP sample merchant that plays the retailer.

**Audit trail shows each step of the chain:**
1. Receipt line, with source email ID and parsed fields.
2. Policy clause: a Senso cited passage with `content_id`/`version_id`.
3. Price evidence: URL, timestamp, JSON-LD offer snapshot and SHA-256 of the HTML.
4. Eligibility math: days since purchase vs. the window.
5. Claim filed: Midscene replay.
6. Outcome and dollars recovered.

**30-second demo:**
1. Forward a TV receipt.
2. The dashboard shows "Bought Nov 3 at $499. Now $429. Inside Holiday Price Match (purchases Oct 30–Dec 31 → claim by Jan 15)," with the Best Buy clause quoted.
3. Click "Claim". A browser opens the support chat and types the request, and a screenshot timeline scrolls.
4. The ledger ticks: "+$70 claimed".

**Best-fit sponsors:**
- Senso: retailer policies as verified, cited context; `senso evals text` can verify the agent's claim against the policy.
- Airbyte: Gmail and Shopify connectors.
- Cognee: purchase memory across sessions.

**Feasibility: High.** Biggest risk: automating live retailer chats (terms of service, bot detection). Mitigate by having the human send the final message and running the autonomous path on a mock or UCP merchant. Gmail OAuth can eat time; use exported `.eml` samples.

---

### Idea 2: Audited Haggler (secondhand gear buyer with a mandate and a disclosure firewall)

**One-liner:** For used cameras, power tools and 3D printers, it checks listings with a multimodal judge and prices them against comps. It negotiates only inside a signed mandate (max price, walk-away, what it may disclose). It never shares an address or agrees to meet without a re-verified human OK.

**Real pain and who has it:** Makers and creators buying used gear, and busy people who hate haggling.
- The Muse incident (Sep 28 2026, link above) is the pitch slide.
- Zelle survey (Sept 2025, 1,000 US adults who use Facebook): 63% shop on Marketplace. Of those, 14% report being scammed, and 79% have seen scams. https://www.zelle.com/social-media-scams
- FTC: $12.5B in reported fraud losses in 2024; online shopping was the second most-reported category. https://www.ftc.gov/news-events/news/press-releases/2025/03/new-ftc-data-show-big-jump-reported-losses-fraud-125-billion-2024
- V2EX (2025-10-22): a Xianyu seller asks for an LLM tool to deal with half-price lowball bots. https://v2ex.com/t/1167597

**Repos that make it unique:**
- https://github.com/Usagi-org/ai-goofish-monitor (~20.3k★, last push 2026-10-10, MIT, Chinese README + README_EN). Pipeline: a natural-language task generates analysis criteria; for each new listing it fetches details, seller info and images; a multimodal LLM judges them; recommended listings trigger ntfy/Telegram/webhook alerts; results go to SQLite. Port this pattern to eBay or a simulated marketplace. (It moved from dingyufei615/ai-goofish-monitor.)
- https://github.com/shaxiu/XianyuAutoAgent (~9.7k★, commit 2026-06-10, GPL-3.0, Chinese). A *seller-side* bargaining bot with tiered price concessions, expert routing and manual-takeover keywords. Use it, or its prompts, as the **adversary seller** in your demo.
- https://github.com/fancyboi999/goofish-cli (501★, v0.6.6, Apache-2.0, Chinese). A design pattern to copy: every action is an MCP tool with per-account rate budgets, a circuit breaker on risk responses, `requires_readback`, and no auto-retry when a submission's result is unknown.
- https://github.com/SAIL-Research-Lab/AgenticPay (55★, last push 2026-07-18, MIT). Buyer/seller negotiation benchmark: 160 tasks, private bottom prices, JSON contracts, Global/Buyer/Seller scores. Use it to show the haggler beats a baseline.
- https://github.com/eBay/npm-public-api-mcp (~49★, commit 2026-10-27, Apache-2.0). eBay's own read-only MCP for active listings. Sold comps via the Marketplace Insights API are "Limited Release", partner-only. https://www.developer.ebay.com/api-docs/buy/marketplace-insights/overview.html

**Competitors:**
- Meta Muse negotiates natively.
- Swoopa: vehicle-focused, with AI outreach and lowball help. https://apps.apple.com/us/app/swoopa/id6475300269
- Flipify: alerts and templates, no negotiation. https://www.flipifyapp.com/blog/the-best-facebook-marketplace-alerts-app
- Verdict: **getting crowded**. The differentiators are the mandate, the disclosure firewall, and listing-verification evidence.

**Meaningful action:** Sends offers and counteroffers, accepts a deal, and books a public "safe exchange" pickup. Optionally it puts a Stripe manual-capture hold on a deposit.

**Audit trail:**
- The mandate, as an AP2 open-mandate-shaped JSON signed by the user.
- Per listing: photos, model identification, the comp set with sources, and a red-flag checklist.
- Every inbound and outbound message, annotated with the mandate rule it was checked against.
- **Blocked actions**, for example "seller asked for address → withheld; requires Persona re-verification".

**30-second demo:**
1. A teammate plays the seller, or the seller is driven by XianyuAutoAgent-style prompts. They lowball and ask for the buyer's home address.
2. The agent counters with three cited comps and refuses the address.
3. It triggers a Persona step-up on the user's phone.
4. After approval it proposes a police-station safe-exchange spot.
5. The ledger shows three rounds, $85 saved, and one disclosure blocked.

**Best-fit sponsors:**
- Persona: "reverifying the human identity bound to the agent" to "unblock high-risk actions in real time" (Persona Know Your Agent page: https://marketing.withpersona.com/solutions/know-your-agent/).
- Firedrill: simulate adversarial sellers. The sponsor's product could not be verified online, so **check at the venue**.
- Cognee: seller and interaction memory. Statsig could A/B-test negotiation strategies.

**Feasibility: Medium-High** with simulated sellers. Biggest risk: Facebook Marketplace has no API and automating it breaks its terms, so **do not automate FB**. Use a simulated marketplace plus eBay listings, and have a human relay messages for Craigslist.

---

### Idea 3: Recall-Safe Used Kid Gear (pre-purchase safety gate plus offer)

**One-liner:** Before a parent buys a used stroller, crib or car seat, the agent reads the listing photos and label, checks CPSC and NHTSA recall data and the seat's expiry date, and then negotiates or walks away with a written safety verdict.

**Real pain and who has it:** Busy parents buying secondhand.
- Consumer Reports found banned products, including padded crib bumpers and infant inclined sleepers, "easy to find" on Facebook Marketplace, eBay, Craigslist and Mercari (KOLD, Sept 25 2026). Meta says it is adding recall warning labels, and eBay says it blocked 21M potentially unsafe listings in 2025. https://www.kold.com/2026/09/25/banned-baby-products-still-sale-secondhand-marketplaces/
- Safe Kids: car seats usually expire "between 6 and 10 years", and "buying a new car seat is best". https://ucsg.safekids.org/faqs/

**Data and libraries that make it unique (all public, no key):**
- **CPSC Recalls REST API.** Example: `https://www.saferproducts.gov/RestWebServices/Recall?format=json&ProductName=stroller&RecallDateStart=2026-01-01`. We verified it returns JSON with `RecallNumber`, `Products[{Name, Model, NumberOfUnits}]`, `Hazards`, `Remedies`, `RemedyOptions`, `ProductUPCs` and `Images`. The unfiltered endpoint returns over 10 MB, so always filter.
- **NHTSA recalls API**, for example `https://api.nhtsa.gov/recalls/recallsByVehicle?make=…&model=…&modelYear=…`, returns JSON with no key. A dedicated **child-seat** recall endpoint was not found **[unverified]**; plan to fall back to NHTSA's web search or to manufacturer data.
- Label OCR: https://github.com/OpenBMB/MiniCPM-V (~27.2k★, last push 2026-11-09, Apache-2.0, English + Chinese; MiniCPM-V 4.7 and MiniCPM-OCR released Oct 2026) or PaddleOCR-VL (0.9B).
- Semantic matching of fuzzy listing text to recall product names: Superlinked SIE, https://github.com/superlinked/sie (~3.5k★, commit 2026-11-19, Apache-2.0), which serves embeddings and rerankers.

**Competitors:**
- Platform-side recall labels (Meta) and listing filters (eBay).
- We found **no consumer agent** that does pre-purchase recall plus expiry verification. That is absence of evidence from our searches, not proof.
- Verdict: **open**.

**Meaningful action:** Makes an offer, or declines with a cited reason. Optionally the agent prepares a registration reminder, since Safe Kids says to "register the seat, even if it is used".

**Audit trail:**
1. Label crop.
2. Extracted model and manufacture date.
3. Raw CPSC/NHTSA query and response, with recall number and hazard.
4. Expiry calculation.
5. Verdict, worded as "no known recall found", never "safe".
6. The offer or decline message.

**30-second demo:**
1. Hold a car-seat label to the webcam. The agent reads "Manufactured 2017-03; expires per label 2023-03" and returns **EXPIRED**, so it walks away.
2. Paste a stroller listing. The agent matches CPSC recall #… with the hazard text and drafts a decline.
3. A third listing passes, and the agent sends an offer within the mandate.

**Best-fit sponsors:** Senso (safety guidance as verified context), Superlinked SIE (listing-to-recall matching), Cognee (child's gear history).

**Feasibility: High.** Biggest risk: false negatives when matching listings to recalls. Use careful wording and show match confidence. This idea combines well with Idea 2 as a vertical.

---

### Idea 4: Group-Buy Escrow for makers (holds, not payments)

**One-liner:** Pools a Discord's demand for filament, PCBs or keyboard parts. Each pledge is a **card hold**. When the price break is reached, the agent captures all holds and places the bulk order. If it isn't reached by the deadline, every hold is released automatically.

**Real pain and who has it:** Maker communities and small studios.
- Drop (formerly Massdrop) stopped operating as a standalone store on Mar 31 2026. https://green-keys.info/en/drop-to-close-its-standalone-ec%ef%bd%9clast-order-will-be-placed-on-3-25-pt-and-the-corsair-integration-phase-is-expected-to-begin-on-3-31/
- KeebsForAll (Jul 13 2025) said the JIRIS80 group buy "will probably never be fulfilled by the manufacturer". https://keebsforall.com/blogs/news/kfa-group-buy-updates-july-13-2025
- splitkb: "delays during group buys are all too common", and "a vendor may go bankrupt". https://docs.splitkb.com/hc/en-us/articles/360014141499
- Price breaks are real: 3D-Fuel's wholesale discounts run from 5% at 5 spools to 20% at 100 and 30% at 1,000. https://www.3dfuel.com/pages/wholesale-3d-printer-filament

**Libraries and rails that make it unique:**
- Stripe manual capture (`capture_method=manual` → status `requires_capture` → capture or cancel). Online card authorizations are valid ~7 days (Visa merchant-initiated: 4 days 18 h). https://docs.stripe.com/payments/place-a-hold-on-a-payment-method
- AP2 v0.2 open/closed mandates as the pledge format.
- Persona for one-human-one-pledge anti-sybil checks.
- SingleStore for a live pledge counter.

**Competitors:**
- Drop is gone.
- Shopify/WooCommerce group-buy plugins and informal Geekhack/Discord runs **[unverified]**.
- Verdict: **open**. The hard part is trust and escrow, which is exactly what the audit trail shows.

**Meaningful action:** Captures holds and places the supplier order: a UCP sample merchant checkout, or a Jolly/Rye staging order. On failure, it cancels the PaymentIntents.

**Audit trail:**
- Each pledge: verified user, quantity, max unit price, PaymentIntent ID.
- Tier math and the exact moment the threshold was crossed.
- Stripe capture and cancel events.
- Supplier order confirmation and per-member allocation.

**30-second demo:**
1. Three teammates pledge through a Slack or Discord bot.
2. A live counter crosses 100 spools, and the unit price drops 20%.
3. The agent captures the holds; the Stripe test dashboard flips "Uncaptured → Succeeded".
4. It places the order. A late pledger's hold is auto-released, with the reason logged.

**Best-fit sponsors:** Persona, SingleStore, Amplitude/Statsig (pledge funnel).

**Feasibility: Medium-High.** Biggest risk: holding or capturing money for others raises money-transmission questions and Stripe terms issues, so keep it strictly in test mode. The ~7-day hold limit also constrains real campaigns.

---

### Idea 5: RFQ Wrangler (custom-part quotes for small manufacturers)

**One-liner:** Sends a drawing or STEP file to several job shops and chases the replies. It parses quote PDFs into a normalized matrix (unit price, MOQ, lead time, finish, exclusions), negotiates, and awards the PO.

**Real pain and who has it:** Engineers and small manufacturers buying machined, sheet-metal or 3D-printed parts. Evidence is mostly qualitative:
- CloudNC (Jul 2 2026): "By the time a quote is ready, the work may already have gone somewhere else." https://www.cloudnc.com/blog/why-quoting-is-the-bottleneck-in-manufacturing
- Venture money says the problem is real: Didero raised $30M (Feb 20 2026) for procurement agents for manufacturers and distributors. https://www.digitalcommerce360.com/2026/02/20/didero-30-million-funding-ai-procurement/

**Libraries:**
- docling (MIT) or https://github.com/opendatalab/MinerU (~84k★, last push 2026-11-18). MinerU's license is Apache-2.0 plus conditions: commercial use is OK below 100M MAU or $20M monthly revenue.
- https://github.com/invoice-x/invoice2data (~2.3k★, MIT): template parsing for repeat suppliers.
- airbyte-agent-sdk: Gmail connector.
- https://github.com/topoteretes/cognee (~33.4k★, last push 2026-11-19, Apache-2.0): a supplier memory graph covering past lead-time slips and quality issues.

**Competitors:**
- Didero (enterprise-focused).
- Shop-side quoting tools: Paperless Parts, AMFG, Uptool.
- Instant-quote marketplaces such as Xometry and SendCutSend **[not opened]**.
- Verdict: enterprise is covered; **small-shop buyer side is less covered**.

**Meaningful action:** Sends the RFQ emails, follow-ups and counteroffers, then the PO.

**Audit trail:**
- Each quote's source PDF, with the extracted fields highlighted.
- Normalization assumptions, for example "Shop B excludes deburr; +$1.20/unit est."
- Scoring weights, negotiation messages, and the final PO.

**30-second demo:**
1. Upload a bracket drawing.
2. Three teammates reply as shops with different PDF quotes, and the matrix fills live.
3. The agent flags Shop B's hidden exclusion and sends a counter.
4. Shop A matches, and the PO is emailed.

**Best-fit sponsors:** Airbyte (Gmail), Cognee (supplier memory), Senso (approved-vendor list and sourcing policy as verified context).

**Feasibility: High.** Biggest risk: emailing real shops during a hackathon is spam, so use teammates. PDF parsing variance is the main technical risk.

---

### Idea 6: Landed-Cost Copilot (tariff-aware "where should I buy this part?")

**One-liner:** Given the same part on AliExpress, 1688 or Taobao and at a US distributor, it computes the real landed cost (HTS code, duty stack, shipping mode, agent fees) with a cited classification rationale, then buys from the cheapest real source.

**Real pain and who has it:** Makers and small importers since the end of de minimis.
- CBP suspended de minimis "effective 12:01a.m. on August 29, 2025". https://content.govdelivery.com/accounts/USDHSCBP/bulletins/3f01456
- After the Supreme Court's IEEPA ruling (Feb 20 2026), the suspension continued under EO 14388. The CIT upheld it on Aug 13 2026, and statute ends de minimis on July 1 2027. https://www.troutman.com/insights/the-800-free-pass-is-gone-cit-confirms-president-can-eliminate-de-minimis-tariff-exemption/
- The rules keep changing (Zonos tracker, updated Oct 26 2026):
  - IEEPA tariffs ended Feb 24 2026.
  - The Section 122 10% surcharge expired Jul 24.
  - New Section 301 tariffs of 10–12.5% started Jul 24.
  - The postal prepaid-duty threshold rose from $800 to $2,500.
  https://zonos.com/us-tariff-updates
- Small-business importers pay "approximately $25,000 more per month in tariff costs since April 2025" (Fortune, Dec 2025). https://fortune.com/2025/12/29/trump-tariffs-cost-25000-per-month-small-business-importers-center-american-progress/

**Data and libraries:**
- **USITC HTS REST API**, for example `https://hts.usitc.gov/reststop/search?keyword=…`. We verified it returns a JSON array (`htsno`, `description`, `general`, `special`, `other`, `additionalDuties`, `footnotes`) with no key.
- https://github.com/next-1688/1688-shopkeeper (~1.7k★, Chinese; license not shown; needs an `ALI_1688_AK` key from 1688's AI app).
- https://github.com/JeremyDong22/taobao_mcp (27★; Playwright with QR login).
- Senso's versioned documents are a natural fit for tariff notices, because `version_id` records *which* rule version a calculation used.

**Competitors:**
- Zonos Classify ("99%+ accuracy") https://zonos.com/classify, Avalara, Flexport **[unverified]**.
- Verdict: **crowded at the classification API layer**. A maker-facing buy decision faces only some competition. Note the overlap: this could also ship as a module of Build-to-Cart.

**Meaningful action:** Builds the cart or simulated order at the chosen source (Jolly staging for a US merchant URL) and emits a duty worksheet and commercial-invoice draft.

**Audit trail:**
- HTS candidates with the raw USITC JSON and the chosen code's rationale.
- Rate stack with source and date.
- FX rate, shipping quote, and the final comparison table.

**30-second demo:**
1. Paste an AliExpress stepper-motor link and a US distributor link.
2. The agent shows the HTS candidates and duty stack, and concludes: "Looks 38% cheaper; lands 6% more expensive."
3. It buys domestic and keeps the worksheet as the receipt.

**Best-fit sponsors:** Senso (versioned rules), SingleStore (rate tables, FX), Arcee (open-weight classifier). Trinity-Mini is a 26B/3B-active MoE under OpenMDW-1.1 on Hugging Face: https://huggingface.co/arcee-ai

**Feasibility: Medium.** Biggest risk: duty-stacking accuracy (Chapter 99 interactions), so frame it as an estimate. Scraping AliExpress or 1688 is blocked or against terms, so use pasted product pages.

---

### Idea 7: Restock Desk (post-Stocky reorder agent for Shopify and Etsy makers)

**One-liner:** Reads sales velocity from the shop and raw-material stock from InvenTree, decides what to reorder, and places orders or POs with suppliers that have no integration (email or web checkout), after an approval step.

**Real pain and who has it:** Small product makers.
- **Shopify shut down Stocky on Aug 31 2026.** Merchants say the native replacement lacks velocity-based reorder suggestions and PO creation, and supplier records reportedly don't export (Shopify Community, Jun–Jul 2026). https://community.shopify.com/t/637085
- The median brand lost "about $21,000" a year to stockouts (Katana study of 375 brands, vendor-modeled). https://ecommercefastlane.com/katana-375-brand-study/
- "44% stock out monthly" (inFlow survey of 400 operators). https://www.inflowinventory.com/state-of-inventory-2026

**Libraries:**
- airbyte-agent-sdk: shopify, woocommerce and amazon-seller-partner connectors as typed agent tools.
- https://github.com/inventree/InvenTree (~7.9k★, last push 2026-11-19, MIT): BOMs and supplier parts.
- changedetection.io: supplier restock alerts.

**Competitors:**
- Prediko, Stockful, Purser, Inventory Planner, Stocksmith (formerly Craftybase): https://stocksmith.io/c/inventory-control-software
- Verdict: **crowded for forecasting**. An agent that actually *places* orders with non-integrated suppliers is less covered.

**Meaningful action:** Places the supplier order (UCP sample or Jolly staging) or emails a PO.

**Audit trail:** Orders pulled and the time window, the velocity calculation, the BOM explosion, reorder-point math, supplier choice, the approval, and the order confirmation.

**30-second demo:**
1. A Shopify dev store "sells" 40 candles.
2. The agent sees wax at 3 days of cover and drafts a PO.
3. The owner approves in Slack, and the order is placed.
4. Clicking any number shows its derivation.

**Best-fit sponsors:** Airbyte, SingleStore, Amplitude/Statsig.

**Feasibility: Medium.** Biggest risk: connector and dev-store setup time. Also differentiate it clearly from Build-to-Cart: this is recurring replenishment, not a one-off project BOM.

---

### Idea 8: Fix-or-Fresh (repair-vs-replace buyer)

**One-liner:** From a photo of the broken thing plus a symptom, it identifies the model and pulls iFixit guides (difficulty, time, parts). It prices the part against a replacement, new or used, then buys the cheaper path and explains why.

**Real pain and who has it:** Busy households and makers. US PIRG estimates "the average American family could save about $330 a year repairing instead of replacing" (via TurnTo23; undated). https://www.turnto23.com/news/national/families-could-save-hundreds-per-year-by-repairing-electronics-appliances-instead-of-replacing. Other PIRG and Consumer Reports figures are **[unverified]** because the pages blocked fetches.

**Libraries:**
- **iFixit API 2.0**: `https://www.ifixit.com/api/2.0/guides?limit=2` returned JSON (`guideid`, `title`, `category`, `difficulty`, `url`) without login in our test.
- https://github.com/Dthen/ifixit-mcp (1★, commit 2026-09-27, 0BSD; iFixit data is **CC BY-NC-SA**).
- Vision: https://github.com/m87-labs/moondream (~10.2k★, last push 2026-04-20, Apache-2.0; vikhyat/moondream redirects here) or MiniCPM-V for reading model labels.
- https://github.com/IDEA-Research/Rex-Omni (~1.6k★, commit 2026-02-22; IDEA License 1.0, check before commercial use) to detect parts by prompt.

**Competitors:**
- **iFixit FixBot** (Dec 9 2025) diagnoses problems, uses photos, and lets you order parts in-app, at $4.99/month later. https://www.engadget.com/general/ifixits-new-app-uses-ai-to-help-you-repair-your-stuff-130000091.html
- Verdict: **some competition**. The repair-vs-replace *economics* plus the buy step is the gap.

**Meaningful action:** Orders the part, or the replacement (Jolly staging or UCP sample).

**Audit trail:** Identification evidence, guide difficulty and time, part price sources (JSON-LD), replacement options, and the decision formula (parts + time value vs. replacement).

**30-second demo:** Photo of a dead coffee maker. The agent identifies the model, finds a "Moderate, 45 min" guide, and compares an $18 part with an $89 replacement. It orders the part and shows the guide.

**Best-fit sponsors:** Superlinked SIE (image embeddings and rerank), Cognee (home-inventory memory), Senso.

**Feasibility: Medium-High.** Biggest risk: identification accuracy, and iFixit's non-commercial data license, which is fine for a hackathon.

---

### Idea 9: Plan Switcher (shop for an electricity tariff using your real hourly usage)

**One-liner:** Takes your Green Button interval CSV and bill PDF and prices a year of your actual usage against every eligible tariff in OpenEI's Utility Rate Database. It recommends the cheapest plan, for example an EV time-of-use rate, and prepares the switch.

**Real pain and who has it:** EV owners and home-office workers in California and Texas. The evidence is weak and dated:
- UCS (2012): 29% of PG&E EV owners stayed on the standard rate; switching could save "more than $400 per year – and as much as $1,000". https://blog.ucs.org/don-anair/are-some-californians-paying-too-much-to-charge-their-plug-in-vehicles/
- EnergyBot's own study (2024): Texas bill-credit plans cost 24% more than fixed-rate plans. https://www.newswire.com/news/study-finds-texans-may-be-losing-out-on-thousands-thanks-to-free-22386643

**Data and libraries:**
- **OpenEI URDB API**: `GET https://api.openei.org/utility_rates?version=latest&format=json&api_key=…`. The key is free via signup, which the team must do; we did not. Filters include `address` or `lat`/`lon`, `sector`, `approved` and `detail=full`. With `detail=full` you get `energyratestructure`, `energyweekdayschedule`/`energyweekendschedule` (12×24 period maps) and `fixedchargefirstmeter`. That is enough to compute bills yourself. https://openei.org/services/doc/rest/util_rates/
- https://github.com/NREL/pysam (157★, BSD-3) wraps NREL's System Advisor Model. Whether its utility-rate module takes URDB data directly was **not confirmed on the page [unverified]**.
- PG&E "Download My Data" exports CSV or XML (ESPI) interval data. https://PGE.com/assets/pge/docs/save-energy-and-money/energy-usage-tips/PGE-Data-Access-Tools.pdf **[unverified: seen in a search result, not opened]**

**Competitors:**
- PG&E's own comparison tool. https://www.pge.com/en/account/rate-plans/find-your-best-rate-plan.html
- EnergyBot in Texas. https://www.energybot.com/faqs.html
- TrueMeter for businesses. https://truemeter.com/
- Verdict: **some competition**. In California the utility's own tool is a strong substitute.

**Meaningful action:** Weak. Switching must happen in the utility account, so the agent fills the switch form and the human submits. In Texas retail markets it can start an enrollment.

**Audit trail:** Interval-data hash, the URDB tariff IDs used, an hour-by-hour cost table, behavior assumptions such as an EV charging shift, and the recommendation.

**30-second demo:** Drop in the CSV. A chart shows "E-1 $2,310/yr vs EV2-A $1,640/yr; $670 saved if charging moves after 9 pm". Every number links to its rate period.

**Best-fit sponsors:** SingleStore (interval data), Senso (tariff fine print), Statsig.

**Feasibility: High** for the analysis, **Low** for the action. Biggest risk: judges may not see a "purchase".

---

### Idea 10: Bid Leveler (buying a home-repair job)

**One-liner:** Drop in three contractor bids. The agent normalizes line items to the same scope, verifies each contractor's license and insurance with the state board, flags missing scope, sends clarification and counter emails, and books the winner.

**Real pain and who has it:** Busy homeowners.
- WTOP (Aug 18 2025), citing a Clever Real Estate survey: 78% of recent renovators went over budget, and 53% of those blamed vague or misleading bids. https://wtop.com/business-finance/2025/08/are-you-doing-a-home-renovation-but-dont-understand-the-bids-let-ai-take-a-look
- California's CSLB offers an Instant License Check that shows license status, workers' comp and complaint history, and contracting without a license carries fines up to $15,000. https://www.cslb.ca.gov/Resources/GuidesAndPublications/DebrisRemovalFacts.pdf **[unverified: CSLB document seen in a search result, not opened]**.

**Libraries:** docling or MinerU for bid PDFs and photos, and Cognee for contractor history. CSLB license lookup is a web form, so plan to scrape it gently.

**Competitors:**
- **BidCompareAI** (GreatBuildz): free, 1–6 bids, side-by-side, scope-adjusted totals. It has **no in-tool license check and no negotiation**. https://bidcompare.greatbuildz.com/
- ReadMyBid, Brixzly, QuoteScore (search results only).
- Verdict: **some competition**. The differentiators are license verification, negotiation and booking.

**Meaningful action:** Sends clarification and counter emails, accepts a bid and books a start date.

**Audit trail:** Bid line items mapped to a canonical scope (each linked to a PDF snippet), the license lookup response with a timestamp, negotiation messages, and the acceptance.

**30-second demo:** Three roofing bids. The agent shows "Bid C omits tear-off; Bid A's license lapsed in August". It counters Bid B with Bid C's material price, Bid B accepts, and the job is booked.

**Best-fit sponsors:** Senso, Cognee, Airbyte (Gmail).

**Feasibility: High.** Biggest risk: scraping the license site (forms, possible blocks). It is California-specific unless other states are added.

---

### Idea 11 (WILDCARD): Thumb Agent (shopping inside app-only storefronts with a phone GUI agent)

**One-liner:** For stores that only work well, or only exist, as mobile apps, a phone GUI agent on an Android emulator builds the order. It hands over to the human at the payment screen, and every tap is screenshotted into the trail.

**Why it's a wildcard:** The technology is the novelty. We found **no strong pain statistic** for "app-only commerce"; the target would be food-delivery and local-pharmacy apps.

**Repos that make it unique:**
- https://github.com/zai-org/Open-AutoGLM (~26.6k★, last push 2026-03-06, Apache-2.0, English + Chinese; README says "for research and learning use only").
  - Its sample output compares a shampoo's price on JD and Taobao before ordering.
  - It has `confirmation_callback` and `takeover_callback`. Payment, password and banking pages cause blank screenshots, and the agent then requests takeover. That is a natural human-approval gate.
  - `AutoGLM-Phone-9B-Multilingual` supports English scenarios, and hosted endpoints exist on Zhipu BigModel and ModelScope (API key needed).
- https://github.com/mobile-next/mobile-mcp (~10.7k★, last push 2026-11-18, Apache-2.0): an MCP server that drives iOS/Android simulators and devices.
- https://github.com/droidrun/mobilerun (formerly droidrun; ~10.1k★, MIT): an LLM-agnostic mobile agent that works with Claude.
- https://github.com/X-PLUG/MobileAgent (~9.4k★, last push 2026-11-03, MIT): Mobile-Agent-v3.5 and GUI-Owl-1.5 (Feb 2026, 2B–235B, built on Qwen3-VL).
- Midscene also drives Android and iOS and produces the same replay report.

**Competitors:** Open-AutoGLM's own demos, which target Chinese apps. Muse and Alexa work through browser or Amazon flows.

**Meaningful action:** Builds the in-app order up to payment. The human taps "Pay", and the agent logs the confirmation screen.

**Audit trail:** Screenshot per step, the model's stated intent per action, takeover and approval events, and the final order screen OCR'd into the ledger.

**30-second demo:** "Reorder my usual from the pharmacy app". The emulator drives itself, the payment screen goes blank, and a takeover prompt appears. The human pays, and the timeline shows 14 screenshotted steps.

**Best-fit sponsors:** Arcee (open-weight planner), Guild AI (agent runtime and governance; the docs show per-session event logs and spend budgets: https://docs.guild.ai/), Firedrill.

**Feasibility: Low-Medium.** Biggest risk: emulator setup and model latency; AutoGLM is tuned for Chinese apps; app terms and emulator detection.

---

### Idea 12 (WILDCARD): Scam-Proof Shopper (hardened in a simulated adversarial market, then shops for real)

**One-liner:** Before it touches your card, the shopping agent is drilled in a simulated marketplace full of fake reviews, fake awards and prompt-injected listings. Then it shops against a real UCP merchant. The audit trail shows each manipulation it caught and why.

**Why it's a wildcard:** It is half safety tooling, half shopping.

**Evidence:** Magentic Marketplace findings (Section 1). Its manipulation tests included fake reviews, fake awards and prompt injection. The Muse incident shows the real-world cost.

**Repos:**
- https://github.com/microsoft/multi-agent-marketplace (~200★, last push 2026-11-01, MIT).
- https://github.com/sierra-research/tau2-bench (~2.5k★, last push 2026-11-10, MIT). Its retail domain has return and exchange tasks with policy rules, which works as a grader.
- AgenticPay, as above.
- The Firedrill sponsor platform **[product details unverified online]**.

**Competitors:** Generic agent-evaluation companies such as Coval, Raindrop and Patronus; none are consumer shopping agents.

**Meaningful action:** Completes a purchase on the UCP sample merchant. A *blocked* payment to a malicious seller agent is also logged as an action.

**Audit trail:** Each drill (attack type, model response, pass/fail), the policy that blocked it, and then the real checkout's mandate and receipt.

**30-second demo:** A split screen shows the naive agent paying a fake "award-winning" seller while the hardened agent flags the injected listing text. Then the hardened agent buys from the legitimate seller, and a scoreboard shows 6/6 manipulations blocked.

**Best-fit sponsors:** Firedrill, Statsig (experiment tracking), Arcee (compare open-weight model robustness).

**Feasibility: Medium.** Biggest risk: setting up Magentic Marketplace inside 5.5 h. Pre-read its README the night before.

---

## 3. Ranking: top 3 with reasoning

1. **Money-Back Agent (Idea 1).**
   - *Timeliness:* holiday price-match windows (Best Buy through Jan 15, Target through Dec 24) are live during the demo.
   - *Open niche:* Paribus and Earny are dead and Refundly only tracks.
   - *Pain is quantified:* about 60% keep unwanted items, and the average abandoned return is worth $50.
   - *Strong audit trail:* receipt → cited policy clause → hashed price evidence → eligibility math → filed claim. It answers "show the information and steps behind what it did" literally.
   - *Story:* the Chinese 价保 precedent shows the pattern works at scale.
   - *Sponsors:* fits Senso's brief ("trusted context + decision trail"), Airbyte and Cognee.
   - *Risk:* live retailer automation. Mitigate with a human-sent final message plus a UCP mock merchant.
2. **Audited Haggler (Idea 2), optionally with Idea 3's recall gate.**
   - *Narrative:* the Muse incident is recent and memorable, and an agent that **refuses** to disclose an address and asks for Persona re-verification is a memorable demo moment.
   - *Strong action:* live negotiation.
   - *Sponsors:* direct fit for Persona and Firedrill.
   - *Repos:* the Xianyu repos give real, starred code to borrow and to play the adversary.
   - *Risk:* crowding from Muse, and facebook-automation terms. Answer with mandate plus firewall, and use simulated sellers.
   - *Narrower variant:* "Used kid gear" (Idea 3) adds public, verifiable recall data with no API keys.
3. **Group-Buy Escrow (Idea 4).**
   - *Novel and maker-native:* Drop's closure and failed group buys are documented.
   - *Very concrete action:* Stripe holds are captured or released by rule, and the Stripe event log is independent proof.
   - *Fit:* the AP2 mandate format maps naturally onto pledges.
   - *Risk:* money-movement framing. Stay in test mode, and remember the 7-day hold limit.

**Runners-up:**
- **Recall-Safe Kid Gear (Idea 3)**: highest feasibility; weaker "purchase" moment.
- **RFQ Wrangler (Idea 5)**: the most practical B2B option, but less flashy.

**Rejected as crowded** (checked by our evidence sub-agent):
- Voice agent phoning local stores. Google AI Mode already "Have AI check pricing", rolling out to all US Search users since Jul 2025. https://techcrunch.com/2025/07/16/google-rolls-out-ai-powered-business-calling-feature-brings-gemini-2-5-pro-to-ai-mode
- Pantry auto-restock: Instacart Clementine and Alexa for Shopping.
- Subscription cancel: Rocket Money.
- Gift memory: Alexa for Shopping.
- Team purchase requests: Ramp and Zip procurement agents.
- Taobao/1688 proxy buying: crowded proxy agents, plus counterfeit risk.

---

## 4. Cool libraries worth knowing (25)

| # | Repo | Stars / activity / license | One line |
|---|---|---|---|
| 1 | https://github.com/web-infra-dev/midscene | ~15.7k★, last push 2026-11-19, MIT, EN+ZH | ByteDance vision UI automation (web, Android, iOS, desktop) with a per-step HTML replay report: a ready-made audit trail |
| 2 | https://github.com/zai-org/Open-AutoGLM | ~26.6k★, last push 2026-03-06, Apache-2.0, EN+ZH | Z.ai phone agent; `takeover_callback` at payment pages; English-capable 9B model |
| 3 | https://github.com/Usagi-org/ai-goofish-monitor | ~20.3k★, last push 2026-10-10, MIT, ZH (+EN README) | Natural-language watch task → multimodal LLM judges listing images and seller → alerts |
| 4 | https://github.com/shaxiu/XianyuAutoAgent | ~9.7k★, commit 2026-06-10, GPL-3.0, ZH | Seller-side Xianyu bargaining bot with tiered concessions; a ready adversary |
| 5 | https://github.com/fancyboi999/goofish-cli | 501★, Apache-2.0, ZH | MCP tools with rate budgets, circuit breaker, read-back and no blind retries: a model for safe purchase tools |
| 6 | https://github.com/OpenBMB/MiniCPM-V | ~27.2k★, last push 2026-11-09, Apache-2.0 | On-device VLM (4.7) plus MiniCPM-OCR (Oct 2026) for labels and screenshots |
| 7 | https://github.com/PaddlePaddle/PaddleOCR | ~92.9k★, Apache-2.0 | PaddleOCR-VL (0.9B) turns receipts and documents into Markdown/JSON |
| 8 | https://github.com/opendatalab/MinerU | ~84k★, last push 2026-11-18, custom Apache+conditions | PDF/Office/HTML to Markdown/JSON at high quality (heed the license thresholds) |
| 9 | https://github.com/docling-project/docling | ~70.8k★, MIT | Document conversion for receipts, quotes and manuals |
| 10 | https://github.com/scrapinghub/extruct | ~985★, last push 2026-10-15, BSD-3 | schema.org Product/Offer extraction: price evidence without an LLM |
| 11 | https://github.com/scrapinghub/price-parser | ~351★, last push 2026-11-02, BSD-3 | Robust amount and currency parsing |
| 12 | https://github.com/dgtlmoon/changedetection.io | ~35.9k★, last push 2026-11-20, Apache-2.0 | Self-hosted price and restock change triggers |
| 13 | https://github.com/microsoft/multi-agent-marketplace | ~200★, last push 2026-11-01, MIT | Simulated two-sided agentic market for testing buyer agents against manipulative sellers |
| 14 | https://github.com/sierra-research/tau2-bench | ~2.5k★, last push 2026-11-10, MIT | Retail domain with return and exchange policies; grades policy-following |
| 15 | https://github.com/SAIL-Research-Lab/AgenticPay | 55★, last push 2026-07-18, MIT | 160-task buyer/seller negotiation benchmark with private reservation prices |
| 16 | https://github.com/google-agentic-commerce/AP2 | ~3.3k★, v0.2.0 2026-04-28, Apache-2.0 | Hash-bound Checkout and Payment mandates plus receipts: the gold standard for "proof" |
| 17 | https://github.com/Universal-Commerce-Protocol/samples | 243★, Apache-2.0 | Local UCP merchant server with simulation endpoints; a safe checkout target |
| 18 | https://github.com/x402-foundation/x402 | ~6.8k★, Apache-2.0 | HTTP 402 payments with a testnet facilitator, for pay-per-call data and tools |
| 19 | https://github.com/visa/trusted-agent-protocol | 223★, last push 2025-10-28 | RFC 9421 signed agent requests; the sample runs locally with no Visa credentials |
| 20 | https://github.com/webaesbyamin/agent-receipts | 1★, MIT | Ed25519-signed, hash-chained receipts with an MCP server. Tiny project, but exactly the idea; copy the pattern |
| 21 | https://github.com/mobile-next/mobile-mcp | ~10.7k★, last push 2026-11-18, Apache-2.0 | MCP server that drives iOS/Android simulators and devices |
| 22 | https://github.com/CupOfOwls/kroger-mcp | ~84★, commit 2026-10-23, MIT | Kroger API MCP: product search plus add to a *real* Kroger cart. Self-serve Kroger API access is **[unverified]** |
| 23 | https://github.com/topoteretes/cognee | ~33.4k★, last push 2026-11-19, Apache-2.0 | Sponsor: graph memory for preferences, purchases and supplier history |
| 24 | https://github.com/superlinked/sie | ~3.5k★, commit 2026-11-19, Apache-2.0 | Sponsor: Superlinked Inference Engine (embeddings, rerankers, extraction). The old `superlinked/superlinked` is archived |
| 25 | https://github.com/airbytehq/airbyte-agent-sdk | ~136★, commit 2026-11-16, license **[unverified]** | Sponsor: permission-aware agent connectors including Gmail, Shopify, WooCommerce, Amazon Seller Partner and Stripe |

**Honourable mentions:**
- https://github.com/D4Vinci/Scrapling (BSD-3): adaptive scraping.
- https://github.com/daijro/camoufox (~13.5k★, MPL-2.0): anti-detect Firefox. Mind sites' terms.
- https://github.com/akaszynski/keepa (Apache-2.0): Amazon price history; needs a Keepa key.
- https://github.com/IDEA-Research/Rex-Omni: detect anything by prompt; custom license.
- https://github.com/pipecat-ai/pipecat (BSD-2) and https://github.com/livekit/agents (Apache-2.0): voice confirmation.
- https://github.com/inventree/InvenTree (MIT) and https://github.com/grocy/grocy (MIT): inventory as context.
- https://github.com/eBay/npm-public-api-mcp: eBay's official read-only MCP.

**Avoid:**
- Archived: bytebot, `bytedance/UI-TARS-desktop` and `bytedance/UI-TARS` (archived 2026-11-09), `superlinked/superlinked`.
- Stale: `TencentQQGYLab/AppAgent` (2025-03), `tychxn/jd-assistant`, WebShop, GroundingDINO.
- Non-commercial licenses: MediaCrawler and `zhinianboke/xianyu-auto-reply`.

---

## 5. Sponsor-tool notes (verified where possible)

- **Senso.ai**: a "context layer" with a knowledge base, `senso search` returning answers with source passages (`content_id`, `version_id`), and `senso evals text`, which labels claims `verified`/`conflict`/`unsupported` with quotes. It also has Shared Context for multiple agents and a CLI. A search summary mentions a REST API at apiv2.senso.ai, an MCP server and a "Product Catalog" section, but those details are **[unverified]**. https://docs.senso.ai/docs/why-senso
- **Persona (Know Your Agent)**: binds agents to a verified human, with government ID plus selfie liveness, and can "Unblock high-risk actions in real time by reverifying the human identity bound to the agent". KYA-specific API details aren't on the page. https://marketing.withpersona.com/solutions/know-your-agent/
- **Guild.ai**: a control plane and runtime for agents. It provides a per-session event log of LLM and tool calls, an admin audit log, spend budgets, an Agent SDK and CLI, and an MCP server. https://docs.guild.ai/
- **Superlinked SIE**: open-source inference server for embeddings, rerankers and extraction (see the library table).
- **Airbyte**: the agent SDK above. The Airbyte MCP and Context Store details are **[unverified]**.
- **Arcee**: AFM-4.5B (tagged apache-2.0 on Hugging Face) and Trinity-Mini, 26B/3B-active, OpenMDW-1.1. https://huggingface.co/arcee-ai
- **Firedrill**: **could not verify** a product by that name online. The only match is an unrelated chaos-engineering blog post. Ask the sponsor at the event.

---

## 6. Things to double-check at the venue

- Firedrill's actual product and API.
- Whether a fresh Stripe sandbox can call the Shared Payment Token test helper (`Stripe-Version: 2026-09-30.preview`). Fall back to manual capture or Issuing.
- Jolly (Rye) staging-key self-serve and the 50 req/day limit.
- The Kroger developer portal: self-serve app registration and the `cart.basic:write` scope.
- Whether NHTSA has a child-seat recall endpoint (Idea 3).
- Whether PySAM's utility-rate module accepts URDB JSON directly (Idea 9).
- Airbyte agent SDK license.

---

## 7. Sources (all opened unless marked)

Landscape and rails:
https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/ ·
https://www.gdnonline.com/Details/1407922/Metas-AI-assistant-shares-sellers-home-address-on-Facebook-Marketplace-without-permission ·
https://www.microsoft.com/en-us/research/publication/mage/ ·
https://github.com/microsoft/multi-agent-marketplace ·
https://github.com/Universal-Commerce-Protocol/ucp ·
https://github.com/Universal-Commerce-Protocol/samples ·
https://github.com/google-agentic-commerce/AP2 ·
https://github.com/agentic-commerce-protocol/agentic-commerce-protocol ·
https://github.com/x402-foundation/x402 ·
https://github.com/visa/trusted-agent-protocol ·
https://docs.stripe.com/payments/place-a-hold-on-a-payment-method ·
https://docs.stripe.com/agentic-commerce ·
https://shopify.dev/docs/agents ·
https://docs.commerce.jolly.dev (via docs.rye.com redirect)

Idea evidence:
https://www.savings.com/insights/return-policy-study ·
https://nrf.com/media-center/press-releases/consumers-expected-to-return-nearly-850-billion-in-merchandise-in-2025 ·
https://awardwallet.com/credit-cards/price-protection/ ·
https://www.bestbuy.com/site/help-topics/price-match-guarantee/pcmcat290300050002.c?id=pcmcat290300050002 ·
https://www.target.com/help/articles/policies-guidelines/price-match-guarantee ·
https://newjersey.news12.com/2025/07/23/target-has-confirmed-that-its-price-match-policy-has-come-to-an-end/7sWu5g6GI09kgr3FA5hLlc ·
https://en.wikipedia.org/wiki/Paribus ·
https://www.retailitinsights.com/doc/refundly-launches-to-help-consumers-track-online-shopping-returns-and-know-exactly-when-they-get-their-money-back-0001 ·
https://www.digitalcommerce360.com/2026/05/13/amazon-launches-ai-agent-alexa-for-shopping/amp/ ·
https://clawhub.ai/danielwangyy/jd-price-protect ·
https://github.com/sunoj/jjb ·
https://www.zelle.com/social-media-scams ·
https://www.ftc.gov/news-events/news/press-releases/2025/03/new-ftc-data-show-big-jump-reported-losses-fraud-125-billion-2024 ·
https://v2ex.com/t/1167597 ·
https://apps.apple.com/us/app/swoopa/id6475300269 ·
https://www.flipifyapp.com/blog/the-best-facebook-marketplace-alerts-app ·
https://www.developer.ebay.com/api-docs/buy/marketplace-insights/overview.html ·
https://www.kold.com/2026/09/25/banned-baby-products-still-sale-secondhand-marketplaces/ ·
https://ucsg.safekids.org/faqs/ ·
https://www.saferproducts.gov/RestWebServices/Recall?format=json&ProductName=stroller&RecallDateStart=2026-01-01 ·
https://api.nhtsa.gov/recalls/recallsByVehicle?make=acura&model=rdx&modelYear=2012 ·
https://green-keys.info/en/drop-to-close-its-standalone-ec%ef%bd%9clast-order-will-be-placed-on-3-25-pt-and-the-corsair-integration-phase-is-expected-to-begin-on-3-31/ ·
https://keebsforall.com/blogs/news/kfa-group-buy-updates-july-13-2025 ·
https://docs.splitkb.com/hc/en-us/articles/360014141499 ·
https://www.3dfuel.com/pages/wholesale-3d-printer-filament ·
https://www.cloudnc.com/blog/why-quoting-is-the-bottleneck-in-manufacturing ·
https://www.digitalcommerce360.com/2026/02/20/didero-30-million-funding-ai-procurement/ ·
https://content.govdelivery.com/accounts/USDHSCBP/bulletins/3f01456 ·
https://www.troutman.com/insights/the-800-free-pass-is-gone-cit-confirms-president-can-eliminate-de-minimis-tariff-exemption/ ·
https://zonos.com/us-tariff-updates ·
https://zonos.com/classify ·
https://fortune.com/2025/12/29/trump-tariffs-cost-25000-per-month-small-business-importers-center-american-progress/ ·
https://hts.usitc.gov/reststop/search?keyword=3d%20printer%20filament ·
https://community.shopify.com/t/637085 ·
https://ecommercefastlane.com/katana-375-brand-study/ ·
https://www.inflowinventory.com/state-of-inventory-2026 ·
https://stocksmith.io/c/inventory-control-software ·
https://www.turnto23.com/news/national/families-could-save-hundreds-per-year-by-repairing-electronics-appliances-instead-of-replacing ·
https://www.engadget.com/general/ifixits-new-app-uses-ai-to-help-you-repair-your-stuff-130000091.html ·
https://www.ifixit.com/api/2.0/guides?limit=2 ·
https://openei.org/services/doc/rest/util_rates/ ·
https://github.com/NREL/pysam ·
https://blog.ucs.org/don-anair/are-some-californians-paying-too-much-to-charge-their-plug-in-vehicles/ ·
https://www.newswire.com/news/study-finds-texans-may-be-losing-out-on-thousands-thanks-to-free-22386643 ·
https://www.pge.com/en/account/rate-plans/find-your-best-rate-plan.html ·
https://www.energybot.com/faqs.html ·
https://truemeter.com/ ·
https://wtop.com/business-finance/2025/08/are-you-doing-a-home-renovation-but-dont-understand-the-bids-let-ai-take-a-look ·
https://bidcompare.greatbuildz.com/ ·
https://techcrunch.com/2025/07/16/google-rolls-out-ai-powered-business-calling-feature-brings-gemini-2-5-pro-to-ai-mode

Sponsors:
https://docs.senso.ai/docs/why-senso ·
https://docs.senso.ai/ ·
https://marketing.withpersona.com/solutions/know-your-agent/ ·
https://docs.guild.ai/ ·
https://huggingface.co/arcee-ai

Repos: all GitHub URLs in Sections 2 and 4 were opened by me or by the sub-agents on 2026-11-19/20.
Not opened: PG&E-Data-Access-Tools.pdf (search result only) and the CSLB PDF (search result only).
