# Build-to-Cart: pre-hackathon research (tokens& Personal Agents Hackathon, Fri Nov 20, 2026)

Research date: Thu Nov 19, 2026. Read-only web research. I opened every link cited here, except where marked **[unverified]**. GitHub stars, last push and license come from the GitHub REST API (`api.github.com/repos/...`) on Nov 19–20, 2026 (UTC). "Last push" means the repo's latest push, not necessarily a release.

---

## TL;DR: the 10 resources that matter most

1. **Shopify UCP (Universal Commerce Protocol) CLI and MCP servers.** These give real product search and a real cart with no API key. Anonymous agents can use catalog search plus `create_cart`, and the cart comes back with a `continue_url` the human opens to pay. That is our "real action that stops before payment". Anonymous agents cannot call checkout tools.
   https://shopify.dev/docs/agents · https://shopify.dev/docs/agents/get-started/quickstart · https://shopify.dev/docs/agents/catalog/global-catalog · https://shopify.dev/docs/agents/carts-and-checkout/cart-mcp · https://shopify.dev/docs/agents/profiles/auth-and-rate-limiting · https://github.com/Shopify/ucp-cli (MIT)
2. **SO-101 robot arm (TheRobotStudio/SO-ARM100).** This is the recommended stage demo. The README has a priced BOM for US, EU, CN and JP. The repo also has a **URDF with per-link STL meshes**, so we get an assembled, articulated model in which every link is clickable. Apache-2.0. https://github.com/TheRobotStudio/SO-ARM100
3. **`urdf-loader` (gkjohnson/urdf-loaders).** Loads that URDF into three.js. Raycast clicks on each link's mesh and drive joints with `setJointValue`. This is the fastest route to the clickable 3D part map. Apache-2.0. https://github.com/gkjohnson/urdf-loaders/tree/master/javascript
4. **Senso API.** The "trusted context" layer. Calls: `POST /org/kb/raw` to ingest, `POST /org/search` for a grounded answer plus chunks with `kb_node_id`, and `POST /org/evals/text` with evaluator `kb_accuracy` to fact-check our "why" cards against the knowledge base. Base URL `https://apiv2.senso.ai/api/v1`, header `X-API-Key`. https://docs.senso.ai/docs/concepts · https://docs.senso.ai/specs/sdk-api.yaml
5. **Superlinked SIE Serverless.** Task-specific inference: GLiNER2 entity extraction for BOM lines from transcripts and READMEs, and Qwen3 reranking of store listings against the resolved spec. `pip install sie-sdk`; `api.superlinked.com/v1/{encode|score|extract}/{model}`. https://superlinked.com/serverless · https://superlinked.com/docs/quickstart.md · https://superlinked.com/docs/cloud/rate-limits
6. **Cognee 1.0 (`remember` / `recall`).** Memory of what the user already owns and their preferences. Works with Anthropic as the LLM plus `fastembed` embeddings, so no OpenAI key is needed. https://www.cognee.ai/blog/deep-dives/inside-cognee-1-0 · https://docs.cognee.ai/setup-configuration/overview.md
7. **Anthropic "Claude for commerce" blueprint (anthropics/commerce-agents).** Patterns to borrow, not code to fork:
   - Cart writes accept only product IDs that a tool returned in this session.
   - No tool places an order or moves money.
   - An approval typed in chat approves nothing.
   - UI components are exposed as tools.

   Apache-2.0, 3,492 stars. https://github.com/anthropics/commerce-agents · https://platform.claude.com/docs/en/about-claude/use-case-guides/commerce-agents.md
8. **AP2 (Agent Payments Protocol) v0.2 Checkout and Payment Mandates.** A ready-made data model for a verifiable intent trail. The open mandate has `checkout.allowed_merchants` and `checkout.line_items` with `acceptable_items` and `quantity`. The closed mandate binds a merchant-signed checkout. https://ap2-protocol.org/ · https://ap2-protocol.org/ap2/checkout_mandate/ · https://github.com/google-agentic-commerce/AP2 (Apache-2.0)
9. **SerpAPI `google_shopping` and `amazon` engines.** Multi-store price, shipping and review data in one key. The free tier is 250 searches per month at 50 per hour, so cache aggressively. https://serpapi.com/pricing · https://serpapi.com/google-shopping-api · https://serpapi.com/amazon-search-api
10. **PuLP or OR-Tools for whole-cart optimization.** A tiny MILP (mixed-integer linear program): choose an offer for each part, minimize price plus per-store shipping, with constraints on budget and arrival date. Change the weights to get the budget, fastest and fewest-stores tiers. https://github.com/coin-or/pulp · https://github.com/google/or-tools

---

## 1. Prior art and competitors

### 1a. Maker and electronics tools

| Product | What it does (verified) | What we borrow | How we differ |
|---|---|---|---|
| **Octopart / Nexar API** ([support: part limits](https://support.nexar.com/support/solutions/articles/101000476314-part-limits-and-how-they-work)) | Parts search API keyed on MPN (manufacturer part number). The Nexar support article says the evaluation app has a **lifetime part limit of 100** that does not reset monthly. Each part a supply query returns counts against it; design queries are free. Other Nexar and Altium pages cite different numbers (1,000 with a business email, or 100 per month) **[conflicting]**. | Offer model per MPN: distributor, stock, price breaks. | We start from a project link, not an MPN. The quota is too small to rely on; use it for 1–2 hero lookups at most. |
| **Kitspace + 1-click BOM** ([kitspace-v2](https://github.com/kitspace/kitspace-v2), [1clickBOM](https://www.github.com/kitspace/1clickBOM)) | Project hosting with BOMs. The browser extension fills carts at Digikey, Mouser, Farnell/Element14, Newark, RS and LCSC. **1clickBOM is archived** (last push Jan 2025). kitspace-v2 has 34 stars and was last pushed May 2026. kitspace.org **did not resolve** when I tried it on Nov 19. | The "buy everything for this project" button and multi-distributor cart filling. | Agentic resolution of vague parts, non-electronics stores (Amazon, Best Buy, Shopify), and the audit trail. |
| **InteractiveHtmlBom** ([repo](https://github.com/openscopeproject/InteractiveHtmlBom)) | Interactive HTML BOM plugin for KiCad, EasyEDA, Eagle, Fusion360 and Allegro (MIT, 4.7k stars, active). | **Two-way highlight UX**: hover or click a BOM row and the part lights up in the visual, and the reverse. Copy this for our part map and BOM list. | We apply the pattern to a 3D mechanical model, with shopping data attached. |
| **Flux.ai** ([site](https://www.flux.ai/)) | "AI hardware engineer": brief to schematic to layout. Shows each part's cost and lead time and exports a BoM. The homepage describes no BOM-to-cart feature. | Inline cost and lead time per part. | We are shopping-first for makers, not PCB design. |
| **Cirkit Designer** ([site](https://www.cirkitdesigner.com/)) | AI wiring and simulation for Arduino, ESP32 and Pico; generates wiring diagrams. The homepage mentions no BOM or shopping. | The idea of a wiring diagram as an output. | We buy the parts and check power and voltage. |
| **Wokwi** ([site](https://wokwi.com/)) | Browser simulator for Arduino, ESP32, STM32 and Pico. The homepage shows no BOM or buying features. | Nothing core; at most a "simulate before you buy" link for MCU projects. | — |
| **InvenTree** ([repo](https://github.com/inventree/InvenTree)) | Open-source inventory system (MIT, 7.9k stars, active). | The "what I own" concept and its schema (part, stock, location). | Too heavy for tomorrow; Cognee memory plays this role. |
| **PartsBox** ([site](https://partsbox.com/)) | Inventory and BOM pricing that handles price breaks, MOQ (minimum order quantity), order multiples and currency; turns shortages into purchase orders. It has a public API; the homepage does not say which plan includes it. | Put MOQ, price breaks and order multiples into our optimizer, e.g. Adafruit's 10+ tier at 10% off. | Consumer and maker focus, agentic. |
| **Bomist** ([site](https://bomist.com/)) | Desktop and cloud inventory plus BOM tool with Octopart, DigiKey, Mouser and TME pricing. Free for a single user, limited to 100 parts and 3 products. | Cost estimate per build quantity. | — |
| **PartGenie** ([Product Hunt](https://www.producthunt.com/products/partgenie)) | AI copilot for component sourcing. Claims 22M+ parts, with stock and pricing from DigiKey, Mouser and LCSC; launched 2025. The closest AI competitor for electronics. | Natural-language part requests and in-stock alternatives. | We take a project link and return a multi-category cart (servos, cables, clamps, tools), plus the 3D part map, memory of owned parts and the audit trail. |
| **Cofactr** (YC W22) ([YC page](https://ycombinator.com/companies/cofactr)) | Electronics supply chain from BOM to production for hardware companies. | — | Enterprise B2B; we are a personal agent. |
| **Instructables** | No official API. Third-party Apify scrapers expose `materials` and `tools` fields; the [lulzasaur actor](https://apify.com/lulzasaur/instructables-scraper) starts at $10 per 1,000 results. According to its listing snippet, another actor calls an undocumented internal search endpoint and notes that some projects have empty supplies sections ([jungle_synthesizer actor](https://apify.com/jungle_synthesizer/instructables-diy-project-tutorial-scraper), not opened **[unverified]**). | Parse the "Supplies" step. | Our parser: fetch the HTML, have Claude extract, and keep a source quote for each line. |
| **Hackaday.io** ([API docs](https://dev.hackaday.io/docs)) | API v2 at `https://hackaday.io/v2` with header `X-API-Key`, read-only, including **`GET /projects/:id/components`**, a structured components list. The response fields are not documented on that page. | A structured BOM source for Hackaday links. | — |
| **Printables / Thingiverse** | STL hosting. The Thingiverse API needs OAuth; one unofficial 2026 blog claims new developer applications aren't being approved **[unverified]**. | — | We use STLs hosted on GitHub (SO-101, AmazingHand), so no API is needed. |
| **e-NABLE** ([Phoenix hand](https://enablingthefuture.org/phoenix-hand)) | Body-powered 3D-printed hands. Files are on Thingiverse (Phoenix v2 is thing:1453190). An assembly materials kit is sold by 3D Universe. The materials are offered "as is" and "not intended … for commercial use". | The "materials kit" idea: screws, cord, elastic and Velcro as a hardware list. | A good second demo with no electronics, but sensitive (prosthetic). The screw counts differ between the guide and the kit. |
| **InMoov hand and forearm** ([build page](https://inmoov.fr/build-yours/hand-and-forarm)) | The tutorial uses **MG946R** finger servos instead of the out-of-stock HK15298, an **MG996** for the wrist, an Arduino Uno, 200 lb braided fishing line, springs, and a list of bolts. The author now recommends the newer i2 hand. | A perfect example of "vague, then substituted, then exact spec" resolution. | The BOM is scattered across forum posts and the page states no license, so it's not a stage demo. |

### 1b. Agentic-commerce efforts (status as of late 2026)

| Effort | What is real and current | Usable tomorrow? |
|---|---|---|
| **Universal Commerce Protocol (UCP)**, from Google and Shopify | Announced Jan 11, 2026 at NRF ([TechCrunch](https://www.techcrunch.com/2026/01/11/google-announces-a-new-protocol-to-facilitate-commerce-using-ai-agents/)). Shopify ships **Global Catalog**, **Storefront Catalog**, **Cart MCP**, **Checkout MCP** and **Order MCP**, plus `@shopify/ucp-cli` ([docs](https://shopify.dev/docs/agents)). Trust tiers: **Anonymous** gets catalog and cart tools (no checkout); **Signed** adds checkout without `complete_checkout`; **Token** (JWT) can complete checkout ([auth doc](https://shopify.dev/docs/agents/profiles/auth-and-rate-limiting)). Global Catalog defaults to 5 requests per second per API client. Unauthenticated traffic shares one global limit. | **Yes, this is the best real action.** Search, `create_cart`, then the `continue_url` goes to the human. |
| **Agentic Commerce Protocol (ACP)**, from OpenAI and Stripe ([repo](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol)) | Apache-2.0, 1.6k stars, beta. Latest spec version 2026-04-17, covering cart, feed, orders, authentication and MCP. ChatGPT **Instant Checkout was wound down**: Shopifreaks reported on Mar 12, 2026 that OpenAI is moving to retailer-built apps inside ChatGPT ([article](https://www.shopifreaks.com/openai-pivots-from-instant-checkout-to-an-app-based-shopping-model-inside-chatgpt/)). | The spec has no hosted sandbox. Stripe's **Shared Payment Tokens** (agent side) can be issued in a sandbox against the test seller profile `profile_test_61TU90nIeGjU7NNVXA6TU90m7ISQWsBxpcx9lASWWXTk`, with `usage_limits[max_amount]` and `[expires_at]`. Requires `Stripe-Version: 2026-09-30.preview` and agreeing to preview terms ([Stripe SPT doc](https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens.md?agent-seller=agent)). Optional stretch: a "spending mandate capped at the approved total". |
| **Agent Payments Protocol (AP2)**, from Google ([site](https://ap2-protocol.org/), [repo](https://github.com/google-agentic-commerce/AP2)) | v0.2, donated to FIDO Alliance working groups. Mandates are now **Checkout Mandate** and **Payment Mandate**, each **Open** (constraints, used for autonomous execution) or **Closed** (finalized). They are SD-JWT VDCs (selective-disclosure JWTs used as verifiable digital credentials) signed with ES256, and chained for an audit trail ([checkout mandate](https://ap2-protocol.org/ap2/checkout_mandate/)). The samples use ADK and Gemini. | **Borrow the data model**, not the stack. Emit an "AP2-inspired" open-mandate JSON when the intent is captured and a closed one at approval, and sign both. Label it "inspired by", not compliant. |
| **Visa Intelligent Commerce / Trusted Agent Protocol** ([TAP repo](https://github.com/visa/trusted-agent-protocol)) | TAP sample (223 stars): an agent that generates RFC 9421 HTTP message signatures, a merchant backend that verifies them, a CDN proxy, and an agent key registry. Visa's sandbox needs developer onboarding with mTLS **[not checked in depth]**. | No for payments. The concept is reusable (sign agent requests and log the key ID). |
| **Mastercard Agent Pay** ([press, Sept 2025](https://www.mastercard.com/us/en/news-and-trends/press/2025/september/mastercard-unveils-new-tools-and-collaborations-to-power-smarter.html): **the page returned 403 to my fetcher, so these facts come from search snippets [unverified]**) | Agent Toolkit: an MCP server that exposes Mastercard API documentation. One secondary source reports "Agent Pay for Machines" early access with a sandbox **[unverified]**. | No. |
| **Anthropic "Claude for commerce" blueprint** ([repo](https://github.com/anthropics/commerce-agents)) | Apache-2.0, 3,492 stars, pushed Nov 16, 2026. Shopping and merchant agents on the Messages API, the Agent SDK and Managed Agents; four verticals; a `StorefrontBackend` interface. The shopping agent "states products, prices, availability, and store terms only from tool results", and checkout is handed off to the host. | **Borrow patterns.** The rules say code must be written during the event, so don't fork it. |
| **Consumer shopping agents** | Google AI Mode checkout via UCP (US). Amazon **Alexa for Shopping** (May 13, 2026): price history, price tracking, and Buy for Me ([DC360](https://www.digitalcommerce360.com/2026/05/13/amazon-launches-ai-agent-alexa-for-shopping/)). Perplexity and PayPal **Instant Buy** (Nov 25, 2025) ([PayPal](https://newsroom.paypal-corp.com/2025-11-PayPal-and-Perplexity-Launch-Instant-Buy)). | These are generic single-store or single-item agents. **None I found turns a project link into a BOM and then into a multi-store optimized cart with compatibility checks and an audit trail.** An extended search found no direct competitor; that is "not found", not proof none exists. |
| **Persona "Know Your Agent"** | Persona frames its agent work as Know Your Agent (KYA): verify the human behind an agent. Its developer surface is the Embedded Flow (`npm install persona`, `new Persona.Client({templateId: "itmpl_…", environmentId: "env_…", onComplete})`) ([quickstart](https://docs.withpersona.com/quickstart-embedded-flow)). The KYA marketing pages returned 403 to my fetcher. | Yes, as a step-up check at approval, if the sponsor gives a sandbox template at the event **[unverified]**. |

**Positioning line for judges:** "Consumer agents buy one thing from one store. Build-to-Cart buys a whole project across stores. It proves each part fits, remembers what you own, and leaves a signed receipt of every decision."

---

## 2. Code and libraries

### 2a. Getting the BOM from a link

| Source type | Approach | Library / API | Time |
|---|---|---|---|
| YouTube | Get the description and chapters (often contains the parts list with affiliate links) plus the transcript. | [jdepoix/youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api): 8.6k stars, MIT, pushed 2026-11-09, needs no API key. [yt-dlp](https://github.com/yt-dlp/yt-dlp): 209k stars, Unlicense, pushed 2026-11-19; use `--dump-json --skip-download` for the description. | 20 min |
| GitHub README | Fetch `raw.githubusercontent.com/.../README.md` and parse the markdown tables (SO-101's BOM is a markdown table with links). | Plain HTTP. The Airbyte `github` agent connector is an alternative. | 10 min |
| Hackaday.io | `GET https://hackaday.io/v2/projects/:id/components` with `X-API-Key` ([docs](https://dev.hackaday.io/docs)). | REST | 15 min (key signup required) |
| Instructables | Fetch the HTML and extract the "Supplies" section. | Claude extraction, or Claude's server `web_fetch_20260209` tool | 20 min |
| Any page | Server-side web fetch through Claude. `web_fetch` only fetches URLs that already appear in the conversation, which is fine because the user pastes the link. | Anthropic `web_fetch_20260209` | 10 min |
| Entity pass | Extract `component`, `model number`, `quantity`, `voltage` and `connector` spans, with character offsets for audit quotes. | SIE `extract` with GLiNER2 (`fastino/gliner2-large-v1` is on Serverless). The result is `entities[]` with `text`, `label`, `score`, `start`, `end` ([SIE README](https://github.com/superlinked/sie)). | 20 min |
| Structured BOM | Claude structured outputs (`output_config.format`, or `client.messages.parse()`). Have it emit a `source_quote` for each line, then check the quote is an exact substring of the source document; this check is deterministic. | Anthropic SDK. Alternative with built-in source grounding: [google/langextract](https://github.com/google/langextract) (39k stars, Apache-2.0, pushed 2026-11-10). | 30 min |

**Warning from prior art:** one developer who extracted "tools used" from YouTube transcripts got plausible but often wrong results when they asked an LLM to *summarize*. For example, the model inferred PostgreSQL when the creator only said "SQL". The fix was verbatim *extraction* over transcript chunks ([dev.to](https://dev.to/wgeorgeassistantia/i-built-an-ai-tool-that-extracts-tech-stacks-from-youtube-videos-1520)). Prefer the description, README or BOM table. Use the transcript only to fill gaps, require verbatim spans, and flag transcript-only lines as low confidence.

### 2b. Product search and price APIs

| API | Can we get a key tonight? | Limits | What it returns | ToS risk | Verdict |
|---|---|---|---|---|---|
| **Shopify Global Catalog** (`https://catalog.shopify.com/api/ucp/mcp`, JSON-RPC `search_catalog`) | **No key needed.** The CLI's Shopify-managed profile works out of the box. Raw MCP needs a `meta.ucp-agent.profile` URL. | 5 rps per client; unauthenticated traffic shares one pool. Up to 50 results per page, 1,000 total. | `title`, `price_range`, `variants[].price`, `availability`, `checkout_url`, `seller.name` and `domain`. Price filters are in minor units. | Official | **Primary.** Whether it stocks STS3215 servos and other maker parts is **[unverified]**. Test tonight with `ucp catalog search --set /query='STS3215 servo' --set /context/address_country=US --format json`. |
| **Shopify Cart MCP** (`https://{shop}/api/ucp/mcp`: `create_cart`, `get_cart`, `update_cart`, `cancel_cart`) | No key needed (anonymous). | Lowest limits on the anonymous tier. | `cart.id` and `continue_url`, which the buyer opens on the storefront. | Official | **The action step.** |
| **SerpAPI** (`engine=google_shopping`, `engine=amazon`) | Self-serve signup **[instant key: unverified]**. | Free: 250 searches/month at 50/hour. Starter: $25 for 1,000. | Google Shopping: `title`, `extracted_price`, `source` (the merchant), `rating`, `reviews`, `delivery`, `product_link`. Amazon: `asin`, `extracted_price`, `rating`, `reviews`, `delivery`, `prime`. | SerpAPI does the scraping. Acceptable for a hack demo; cite it as "via SerpAPI". | **Secondary, broad coverage.** Cache every response. |
| **Adafruit product JSON** (`https://www.adafruit.com/api/product/{id}`) | No key needed. | Not documented. | `product_price`, `discount_pricing` tiers, `product_stock`, `product_url`, `products_coo` (country of origin), shipping weight. Example: product 155 is the TowerPro SG-5010 servo, $12.00, stock 0 on Nov 19. | Undocumented endpoint **[ToS unverified]** | Nice "real store, real stock" source for hobby parts. |
| **Best Buy Products API** ([docs](https://bestbuyapis.github.io/api-documentation/)) | Sign up with email and activate from the emailed link. | QPS (queries per second) and daily caps exist; the docs give no numbers. | `salePrice`, `onlineAvailability`, `shippingCost`, `customerReviewAverage`, **`addToCartUrl`** (expires in 7 days). | Official. The terms limit caching. | Good for cables and tools. Few hobby servos. |
| **Digi-Key Product Information v4** ([FAQ](https://developer.digikey.com/faq/products-plans-and-apis)) | Portal signup and OAuth2. Sandbox apps can call only sandbox endpoints. | Per-app daily cap via `X-RateLimit-Limit` (value not shown) **[unverified]** | Pricing, stock, specs | Official | Only if someone has time tonight. |
| **Mouser Search API** | Key requested from My Mouser; reportedly can sit in "pending authorization" **[unverified]**. | Third-party docs say 30 calls/min **[unverified]**. | Price breaks, stock | Official | Skip unless the key arrives tonight. |
| **Nexar / Octopart** | Signup | Evaluation app has 100 parts (lifetime, per the support article) | Multi-distributor offers | Official | Skip, or use for a single "hero" lookup. |
| **Amazon PA-API 5** | — | **Deprecated, replaced by the Creators API** (OAuth 2.0, new credentials, Associates account) ([notice](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/paapiv5-deprecation)). The old Add-to-Cart form docs now redirect to the deprecation notice. | — | — | **Skip.** Get Amazon prices through SerpAPI. |
| **Claude `web_search_20260209`** with `allowed_domains` | Uses our Anthropic key. | `max_uses` | Search results the model can read | Official | Long-tail fallback, e.g. Pololu or Seeed, then read the page with `web_fetch`. |
| eBay Browse API | Its docs returned 403 to my fetcher **[unverified]** | — | — | — | Skip. |

### 2c. Browser agents for add-to-cart (fallback only)

| Repo | Stars | Last push | License | Use | Time |
|---|---|---|---|---|---|
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | 121,528 | 2026-11-19 | MIT | Python agent; the cart flow at one non-Shopify store. | 45–60 min, flaky |
| [browserbase/stagehand](https://github.com/browserbase/stagehand) | 26,094 | 2026-11-20 | MIT | TypeScript `act()` / `extract()` primitives; more deterministic. | 45 min |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | 39,907 | 2026-11-18 | Apache-2.0 | Expose a browser to Claude as MCP tools. | 30 min |
| [Skyvern-AI/skyvern](https://github.com/Skyvern-AI/skyvern) | 23,474 | 2026-11-19 | **AGPL-3.0** | Avoid, because of the license. | — |

**Recommendation:** don't put a browser agent on the critical path. Large stores can detect and block automated browsers. Amazon's terms prohibit robots **[general knowledge; not re-checked tonight]**. Use Shopify Cart MCP for the real cart, Best Buy `addToCartUrl` and plain deep links for everything else. If you do a browser hop, pre-record it.

### 2d. Multi-store cart optimization

- **[coin-or/pulp](https://github.com/coin-or/pulp)**: 2,499 stars, pushed 2026-11-19. GitHub reports the license as NOASSERTION, so check the LICENSE file. It bundles the CBC solver, so `pip install pulp` is enough. **Pick this one.** 30–40 minutes.
- **[google/or-tools](https://github.com/google/or-tools)**: 14,410 stars, Apache-2.0, pushed 2026-11-19. The CP-SAT solver is an alternative.
- Model:
  - **Variables:** `x[i,o]` is 1 if part i is bought via offer o; `y[s]` is 1 if store s is used.
  - **Objective:** minimize Σ price·qty·x + Σ ship_s·y_s + w_time·late_days + w_stores·Σy.
  - **Constraints:**
    - Σ_o x[i,o] = 1 for every part not owned.
    - x[i,o] ≤ y[store(o)].
    - ETA(o) ≤ deadline (filter those offers out beforehand).
    - Total ≤ budget.
    - Free-shipping thresholds: optional binary per store.
  - **Tiers:** Budget (w_time=0), Fastest (large w_time), Fewest stores (large w_stores).
  - **Size:** about 10 parts × 5 stores solves in milliseconds, and brute force would also work.

### 2e. Compatibility checks and wiring diagrams

- **No off-the-shelf "hobby compatibility checker" exists that I could find.** Implement 6–10 rules in Python and store their text in Senso as trusted context:
  - Servo voltage matches the PSU.
  - PSU current ≥ servo count × per-servo current, times a factor.
  - Bus protocol matches the controller: Feetech TTL serial bus vs. PWM.
  - Connector and barrel size (5.5×2.1 mm, from the SO-101 PSU listing title **[verify]**).
  - The USB-C cable carries data.
  - The gear-ratio variant matches the joint.
- A real SO-101 rule from the README: the standard build uses **STS3215 7.4V** servos, "likely slightly less for a 5V power supply". The optional **12V STS3215** has 30 kg·cm stall torque and **needs a 12V, 5A+ supply**. This is a perfect demo of "flag and auto-fix": the user picks 12V servos, so the agent swaps in a 12V 5A PSU. The README does not give per-servo stall current **[verify from the Feetech datasheet before using numbers]**.
- **Wiring diagrams:**
  - [wireviz/WireViz](https://github.com/wireviz/WireViz): 5,342 stars, GPL-3.0, pushed 2026-10-25. Turns YAML into SVG via Graphviz; needs Graphviz installed. 30–45 min. GPL is fine as a separate tool.
  - [devbisme/skidl](https://github.com/devbisme/skidl): MIT. Overkill.
  - [fritzing/fritzing-app](https://github.com/fritzing/fritzing-app): desktop app, license "Other". Skip.
  - **Cheapest option:** a Mermaid or react-flow graph of power and data connections (PSU → bus board → 6 servos; USB → PC).
- [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy) (MIT, 1.7k stars, active): Claude Code skills for KiCad BOM work and Digikey/Mouser lookups. Useful reference prompts for PCB projects, not needed for the SO-101.

### 2f. The clickable breakdown UI

| Approach | Repo / demo | Stars, push, license | Buildable in ~1.5 h? | Notes |
|---|---|---|---|---|
| **A. URDF articulated model (recommended for SO-101)** | [gkjohnson/urdf-loaders](https://github.com/gkjohnson/urdf-loaders) ([simple demo](https://gkjohnson.github.io/urdf-loaders/javascript/example/bundle/simple.html), [drag-and-drop viewer](https://gkjohnson.github.io/urdf-loaders/javascript/example/bundle/index.html)) | 822, 2026-10-31, Apache-2.0 | **Yes, ~75–90 min** | npm package `urdf-loader`; `new URDFLoader(manager).load(url, robot => scene.add(robot))`; `robot.setJointValue(name, angle)`. The SO-101 URDF (`Simulation/SO101/so101_new_calib.urdf`) references meshes under `assets/`, so there is no `package://` path rewriting. Raycast to a mesh, read its STL filename, and map it to a BOM line. |
| **B. react-three-fiber + drei + outline** | [react-three-fiber](https://github.com/pmndrs/react-three-fiber), [drei](https://github.com/pmndrs/drei), [react-postprocessing Selection/Outline](https://react-postprocessing.docs.pmnd.rs/selection) | 33.8k, 2026-10-21, MIT / 10.2k, 2026-11-17, MIT | Yes, as a wrapper around A: `<primitive object={robot} onClick>` | Outline needs `EffectComposer autoClear={false}`. One forum report of infinite re-renders with `Select`; fall back to an emissive highlight. |
| **C. `<model-viewer>` with hotspots** | [google/model-viewer](https://github.com/google/model-viewer) ([annotations example](https://modelviewer.dev/examples/annotations/index.html)) | 8.3k, 2026-11-18, Apache-2.0 | **Yes, ~30–45 min** | Elements with `slot="hotspot-*"` use `data-position` and `data-normal`; the online editor gives positions by clicking. Needs one GLB, so the STL→GLB conversion is a prep step. Per-mesh picking isn't documented on that page. |
| **D. 2D photo part map** | Hand-rolled SVG `<polygon>` or `<rect>` hotspots over a product photo. Boxes from SIE Serverless `IDEA-Research/grounding-dino-base` (listed on Serverless; exact call shape **[verify]**) or [SAM 3](https://github.com/facebookresearch/sam3) (12.4k, 2026-11-17, license "Other") / [SAM 2](https://github.com/facebookresearch/sam2) (20.2k, Apache-2.0). | — | **Yes, ~45 min** with manual boxes; SAM needs a GPU. | The generic fallback for any project that has no 3D files. |
| **E. BOM graph** | [xyflow/xyflow](https://github.com/xyflow/xyflow) (React Flow) | 39.1k, 2026-11-19, MIT | **Yes, ~45 min** | Project → subassemblies → parts → chosen offer, colored by status (resolved, owned, warning). Doubles as the power and wiring graph. |
| F. GLTF to JSX | [pmndrs/gltfjsx](https://github.com/pmndrs/gltfjsx) | 5.9k, **last push 2024-11**, MIT | Optional | Stale but works for named-mesh GLBs. |
| G. AI-generated exploded-view image | Image model of your choice | — | ~20 min | **[unverified quality]** Fine as a "hero" illustration; can't be clicked accurately. |

**Exploded view on the URDF:** for each link, compute the bounding-box center and lerp the link's offset away from the model centroid by a slider value t. Also animate joints to a "display pose". Highlight: clone the material and set its emissive color. Label: drei `<Html>` anchored at the link center.

**Mesh-to-BOM mapping (from the SO-101 URDF):**

| URDF link | Meshes |
|---|---|
| `base_link` | `base_motor_holder_so101_v1`, `base_so101_v2`, `sts3215_03a_v1`, `waveshare_mounting_plate_so101_v2` |
| `shoulder_link` | `sts3215_03a_v1`, `motor_holder_so101_base_v1`, `rotation_pitch_so101_v1` |
| `upper_arm_link` | `sts3215_03a_v1`, `upper_arm_so101_v1` |
| `lower_arm_link` | `under_arm_so101_v1`, `motor_holder_so101_wrist_v1`, `sts3215_03a_v1` |
| `wrist_link` | `sts3215_03a_no_horn_v1`, `wrist_roll_pitch_so101_v2` |
| `gripper_link` | `sts3215_03a_v1`, `wrist_roll_follower_so101_v1` |
| `moving_jaw_so101_v1_link` | `moving_jaw_so101_v1` |

So every `sts3215_*` mesh maps to the servo BOM line, with one instance per joint: `shoulder_pan`, `shoulder_lift`, `elbow_flex`, `wrist_flex`, `wrist_roll`, `gripper`. `waveshare_mounting_plate` maps to the "Motor Control Board" line. Every other mesh maps to "3D-printed part (PLA+)" with a print-or-buy option.

**Risks:** STL units and scale in the URDF; check early. Large STLs can load slowly, so serve them from the app's public folder.

### 2g. Audit-trail and agent-trace UI

| Repo | Stars, push, license | Use | Time |
|---|---|---|---|
| [evilmartians/agent-prism](https://github.com/evilmartians/agent-prism) | 408, 2026-10-08, MIT | `TraceViewer` React components (trace list, span tree, details) for OpenTelemetry/Langfuse-shaped data. According to search snippets it needs React 19 + **Tailwind 3** **[verify against your template]**; components are copied in with degit. | 45 min as an "engineer view" tab |
| [langfuse/langfuse](https://github.com/langfuse/langfuse) | 37.6k, 2026-11-20, license "Other" | OpenTelemetry-based tracing backend (cloud or self-host); deep-link from each why card to a trace. | 30 min (cloud) |
| [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) | 12.4k, 2026-11-20, license "Other" | Alternative tracing UI. | 30 min |
| Custom (recommended for the main UI) | — | Per-part **"Why" card** plus a vertical **timeline** (shadcn/ui), with an expandable **receipt** at the bottom. Judges should see the trail without opening a separate tool. | 60 min |

---

## 3. Sponsor docs and choice

### Scorecard (5 = best)

| Sponsor | Prize value | Fit for Build-to-Cart | Integration time | Likely competition | Pick? |
|---|---|---|---|---|---|
| **Senso.ai** | 10k / 5k / 1k credits (cash value unclear) | **5**: the challenge text and Senso's prize text are nearly the same | 45–60 min | High (headline sponsor) | **YES (core)** |
| **Superlinked SIE Serverless** | 2 prizes × ($500 cash + $500 credits) | **4**: extraction and reranking are exactly "task-specific inference" | 40 min | Low to medium | **YES (core)** |
| **Cognee** | $1,000 / $500 / $250 in Cloud credits | **4**: "remembers what I own" | 40–50 min | Medium | **YES (core)** |
| **SingleStore** | $1,000 / $750 / $500 gift cards | **3.5**: real-time price observations and the decision log store | 35–45 min | Medium | **YES (4th; drop if behind)** |
| Amplitude + Statsig | $1,000 / $500 | 3: agent analytics wrapper plus a gate for the optimizer variant | **15–20 min** | High (easy to add) | Optional bonus |
| Persona | $250 Keychron gift card per member + swag | 3.5: verify the human before the cart handoff | 30–45 min if a sandbox template is provided | Low | Optional bonus |
| Firedrill | $500 Visa + 3 months Starter + 40k credits | 4: simulated shopping drills ("never checks out without approval") | 60–90 min; macOS/Linux only | Low to medium | Stretch |
| Airbyte | $1,000 Visa / $500 / $250 | 3: Gmail order receipts → owned inventory | 60–90 min (OAuth) | Medium | No |
| Guild AI | 100M / 50M / 25M tokens | 2 | Account "via sales" | — | No |
| Arcee AI | Credits + merch | 2 | 20 min | — | No |

### 3a. Senso.ai: the trusted-context layer (core)

**What we use it for**

The Senso knowledge base is the only source the agent treats as "trusted". It holds:
- the project's official BOM text (SO-101 README tables),
- spec notes for the STS3215 servo, the Waveshare bus board and the PSU,
- the compatibility rules (as text),
- the store shipping and return policies we choose to trust,
- a `/decisions` folder where the agent writes back a markdown decision record for each part. This mirrors Senso's own "Shared Context" use case: agents save decisions with an owner and a settled or unsettled status.

**Key API**

Base URL `https://apiv2.senso.ai/api/v1`, header `X-API-Key: tgr_…` ([concepts](https://docs.senso.ai/docs/concepts), [OpenAPI spec](https://docs.senso.ai/specs/sdk-api.yaml), [API keys](https://docs.senso.ai/docs/api-keys)).

- **Ingest:** `POST /org/kb/raw` with `{ "title", "text", "kb_folder_node_id"? }`. Returns **202**, and ingestion is asynchronous. Poll `GET /org/kb/nodes/{id}` until `content.processing_status == "complete"`; documents are unsearchable before that. Create folders with `POST /org/kb/folders`.
- **Search:** `POST /org/search` with `{ "query", "max_results": 5, "search_type": "hybrid" }`. Returns a grounded answer plus the matched chunks, each with a `kb_node_id`. Other variants:
  - `/org/search/context`: chunks only.
  - `/org/search/stream`: SSE events `token`, then `sources`, then `done`.
  - `/org/search/full`
  - `/org/search/content`

  **Every search consumes credits** (402 when the balance is empty). Send `X-Senso-Signals: off` on test searches to keep them out of the gap report.
- **Verify claims:** `POST /org/evals/text` with `{ "title", "text", "evaluator": "kb_accuracy", "label", "wait": true, "idempotency_key" }`. Judges each factual claim against the knowledge base. Returns 200 with an `EvalRunDetail` or 202 with a summary to poll. The Evals section says model cost "is not billed against your credit balance". Show a ✅/⚠️ per claim on the why card.
- **MCP alternative:** `https://apiv2.senso.ai/mcp` (Streamable HTTP; the MCP page documents OAuth. Bearer API-key access appears only in a search snippet of the setup page **[unverified]**) exposes `senso_search`, `senso_create_doc` and others ([MCP doc](https://docs.senso.ai/docs/mcp-server)). This is useful for the team's coding agent. In the app, use REST: deterministic and easy to log.

**Minimal code shape** (Python `httpx`):
```python
r = httpx.post(f"{BASE}/org/search", headers={"X-API-Key": KEY},
               json={"query": "STS3215 7.4V supply voltage and stall torque", "max_results": 5, "search_type": "hybrid"})
```

**Signup and free tier:** you need a Senso account and an organization. The docs mention no free tier, so **ask Senso at the event for hackathon credits**.

**Gotchas:**
- The docs site is partly JS-rendered, and the "hello world" example page shows a sign-in wall.
- Some features need specific Senso products (403 without them).
- Ingest everything by about 11:45 so processing is done before the first demo run.

**Integration time:** 45–60 min.

### 3b. Superlinked SIE Serverless: task-specific inference (core, two prizes)

**What we use it for**
1. **`extract`**: GLiNER2 picks parts out of a transcript, README or Supplies text, with spans that feed the audit quote.
2. **`score`**: a Qwen3 reranker ranks 20–40 store listings against the resolved spec string, e.g. "Feetech STS3215 7.4V 1/345 C001 serial bus servo". This catches wrong variants: 12V versions, other gear ratios, "compatible" knockoffs.
3. **`encode`**, optional: dedupe offers and match BOM lines to owned items.
4. Optional: `grounding-dino-base` boxes for the 2D photo part map.

The pitch for both prizes: "Our harness routes cheap, fast task-specific inference to SIE and only planning and explanation to Claude." Show a small cost and latency panel.

**Key API** ([serverless](https://superlinked.com/serverless), [quickstart](https://superlinked.com/docs/quickstart.md), [rate limits](https://superlinked.com/docs/cloud/rate-limits), [SIE README](https://github.com/superlinked/sie), repo 3,534 stars, Apache-2.0, pushed 2026-11-20):
- `pip install sie-sdk`
- `from sie_sdk import SIEClient` and `from sie_sdk.types import Item`
- `client = SIEClient(api_key=os.environ["SIE_API_KEY"])`
- `client.extract("fastino/gliner2-large-v1", Item(text=doc), labels=["component","model number","quantity","voltage","connector"])` returns `result["entities"]` with `text`, `label`, `score`, `start`, `end`.
- `client.score("Qwen/Qwen3-Reranker-4B", Item(text=spec), [Item(text=t) for t in listing_titles])` returns `scores["scores"]` with `item_id`, `score`, `rank`.
- REST equivalents: `POST https://api.superlinked.com/v1/{encode|score|extract}/{url-encoded model}` with `Authorization: Bearer sk-sie-…`.

**Signup:** console.superlinked.com; "no credit card required". Free credits are not stated **[ask at the event]**.

**Limits:** realtime endpoints allow 50 rps per key with 32 in flight. A 429 comes with `Retry-After`. A cold model returns **503**: wait `Retry-After` and retry, and warm the models at 11:15.

**Gotchas:**
- The quickstart examples use local model IDs (e.g. `urchade/gliner_multi-v2.1`). On Serverless, use the IDs in the catalog's "On Serverless" filter ([models](https://superlinked.com/models)).
- Whether the SDK's default base URL is the Serverless endpoint **[verify]**.

**Integration time:** 40 min.

### 3c. Cognee: agent memory (core)

**What we use it for**
- Persistent memory of **what the user owns**: "Precision screwdriver set; 2× USB-C cables; Prusa printer + PLA+".
- **Preferences**: "no AliExpress; prefers Prime; budget-sensitive".
- **Past builds.**

`recall` runs before search. Each removal is logged as "owned: matched memory X". Toggling "I already own this" in the UI calls `remember`.

**Key API** ([1.0 deep dive](https://www.cognee.ai/blog/deep-dives/inside-cognee-1-0), [installation](https://docs.cognee.ai/getting-started/installation.md), [config](https://docs.cognee.ai/setup-configuration/overview.md), [LLM providers](https://docs.cognee.ai/setup-configuration/llm-providers.md); repo [topoteretes/cognee](https://github.com/topoteretes/cognee) has 33.4k stars, Apache-2.0, pushed 2026-11-19; v1.6.8 dated Nov 12, 2026 according to a changelog search snippet **[unverified]**):
- Install: `uv pip install "cognee[anthropic]"`.
- `.env`:
  ```
  LLM_PROVIDER="anthropic"
  LLM_MODEL="anthropic/claude-sonnet-5"
  LLM_API_KEY="sk-ant-…"
  EMBEDDING_PROVIDER="fastembed"
  EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"
  EMBEDDING_DIMENSIONS=384
  TELEMETRY_DISABLED=true
  ```
  The docs' Anthropic example uses `claude-sonnet-5`; `claude-sonnet-5-5` should also work via LiteLLM **[verify]**.
- Code:
  - `await cognee.remember("User owns a precision screwdriver set …")`
  - `results = await cognee.recall("Which of these does the user already own: …")`
  - session-scoped memory: `session_id="user_42"`
  - reset: `await cognee.forget(everything=True)`
- Cloud: `await cognee.serve(url="https://your-instance.cognee.ai", api_key="ck_…")`. The blog mentions a "free Cloud key".

**Gotchas:**
- **If you configure only the LLM side, embeddings silently default to OpenAI**, and the preflight rejects a non-OpenAI LLM with untouched embedding settings. Set both.
- Python 3.10–3.14 is supported, but use **3.11+ on Windows**: 3.10 can cause a graph-DB error.
- `remember` builds the graph with LLM calls, which is slow. Pre-load memories at startup, not during the demo.
- The API is async.

**Integration time:** 40–50 min.

### 3d. SingleStore: real-time price and decision store (4th; drop first if behind)

**What we use it for**
- A `price_observations` table: every offer seen, with `seen_at`, source API and raw reference. This backs "prices seen and when" and the price sparkline.
- A `decisions` table: the JSON audit record plus its hash.
- An `events` table: the live trace that the UI polls or streams.
- Optional: a `VECTOR(384)` column with `DOT_PRODUCT` for semantic offer matching, and full-text search for MPNs.

**Key facts** ([Shared edition doc](https://docs.singlestore.com/cloud/getting-started-with-singlestore-helios/about-singlestore-helios/singlestore-helios-editions/shared-edition.md), [vector indexing](https://docs.singlestore.com/cloud/reference/sql-reference/vector-functions/vector-indexing.md)):
- The free **Shared** edition runs in AWS us-east-1.
- **One database, 10 tables**, 1 GB compressed, 100 connections.
- No rowstore or reference tables.
- No firewall config; the database is reachable from anywhere.
- `pip install singlestoredb`. Vector indexes support `DOT_PRODUCT` and `EUCLIDEAN_DISTANCE` on `VECTOR(N, F32)`.
- Whether vector indexes work on the Shared tier **[unverified]**. Brute-force `DOT_PRODUCT` over fewer than 10k rows is fine anyway.

**Integration time:** 35–45 min (the schema is below in §4).

### 3e. Optional bonus integrations

- **Amplitude Agent Analytics** ([SDK doc](https://amplitude.com/docs/sdks/agent-analytics/sdk)), about 15–20 min.
  - Install: `pip install amplitude-ai`.
  - Init: `ai = AmplitudeAI(api_key=os.environ["AMPLITUDE_AI_API_KEY"])`.
  - Wrap the client: `Anthropic(amplitude=ai, api_key=…)`. Requests, tokens, latency, cost and tool calls are then recorded.
  - Wrap each run in `with ai.agent("build-to-cart").session(user_id=…, session_id=run_id) as s:`. **LLM calls outside a session are silently dropped.**
  - Statsig: `statsig-python-core` (`check_gate`, `get_experiment`) to A/B the default cart tier ([Python Core docs](https://docs.statsig.com/server-core/python-core)). Statsig is now run by Amplitude after a May 2026 deal ([Amplitude blog](https://www.amplitude.com/blog/amplitude-and-statsig-partnership)).
- **Persona** ([embedded flow quickstart](https://docs.withpersona.com/quickstart-embedded-flow)): `npm install persona`, then `new Persona.Client({ templateId: "itmpl_…", environmentId: "env_…", onComplete: ({inquiryId, status}) => … }).open()`. Trigger it only when the cart exceeds a threshold or includes a new merchant. Store `inquiryId` in the closed mandate. The local page must be served, not opened as a file. Sandbox access without sales **[unverified; ask the Persona team at the event]**.
- **Firedrill** (stretch, 60–90 min) ([quickstart](https://docs.firedrill.run/quickstart.md), [custom tools](https://docs.firedrill.run/tools/custom-tools.md), [routing](https://docs.firedrill.run/connect/tools.md), [hacker page](https://firedrill.run/hacker-docs)):
  - Install and connect: `npm install --global firedrill-run`, `firedrill init`, `claude mcp add --transport http firedrill https://mcp.firedrill.run`. Event code **`TOKENSAND`** adds 500 credits (Billing → Event code).
  - Build a custom tool `parts-store` (`firedrill tools init parts-store`) with operations `search` (read), `add_to_cart` (write) and `checkout` (write).
  - Scenario: a servo goes out of stock mid-run, a price jumps, and the persona says "I own a screwdriver set".
  - Evaluations: **never calls `checkout`**; total ≤ budget; owned items removed; PSU mismatch flagged.
  - Routing is through env-var URLs on 127.0.0.1 (`dependency_env`); no proxies.
  - **Drills run on macOS/Linux only**, with specific Node versions (22.x ≥ 22.23.4, 24.x ≥ 24.11.1, 26.x ≥ 26.13.1). Built-in catalog includes Stripe (test mode) and a "Web Corpus" made-up web; there's no shop tool, hence the custom tool.

### 3f. Rejected (one line each)

- **Airbyte (Airbyte Agents / context layer):** The agent SDK (`airbyte-agent-sdk`; 52 connectors including `gmail`, `github`, `shopify`, `exa`, `google-drive`, `notion`) is real ([connectors folder](https://github.com/airbytehq/airbyte-agent-sdk/tree/main/connectors), [PyPI](https://pypi.org/project/airbyte-agent-sdk/)). But the "context layer" needs Airbyte Cloud on a paid plan or trial with a Snowflake or BigQuery warehouse ([context layer](https://airbyte.com/context-layer)), and the Gmail-receipts idea means Google OAuth setup. Too much setup for 5.5 hours.
- **Guild AI:** CLI `@guildai/cli` and SDK `@guildai/agents-sdk`, but an account requires "talking to sales" ([quickstart](https://docs.guild.ai/quickstart)). The prize is tokens.
- **Arcee AI:** Trinity open-weight models via API/OpenRouter; adds a second LLM vendor for little story value; credits and merch only.

---

## 4. Architecture and build plan

### 4a. Stack

- **Backend:** Python 3.11+ with FastAPI and SSE (server-sent events) for the live trace. Python because Cognee, `sie-sdk`, `singlestoredb`, PuLP and the Anthropic SDK are all first-class there.
- **Agent:** Anthropic Python SDK, **Messages API with the Tool Runner** (`@beta_tool` + `client.beta.messages.tool_runner`). We own the tools and the approval gates, and every tool call goes through our logger.
  - The Claude Agent SDK (`claude-agent-sdk`) is the alternative if the team prefers its built-in WebFetch/WebSearch and hooks.
  - Managed Agents exists too, but it's beta and bills session runtime on top of tokens; not needed here.
- **Models:**
  - `claude-sonnet-5-5` for extraction, tool calls and why-card text.
  - `claude-opus-5-5` for the one planning step (spec resolution of ambiguous lines and the final cart rationale).
- **Frontend:** Vite + React + TypeScript + Tailwind + shadcn/ui. three.js with `urdf-loader`, wrapped in `@react-three/fiber` + `@react-three/drei`. React Flow for the BOM graph fallback.
- **Search adapters:** the `ucp` CLI called as a subprocess with `--format json` (avoids hosting an agent profile), SerpAPI, the Adafruit JSON endpoint, and Best Buy.
- **Data:** Senso (trusted knowledge base), Cognee (memory), SingleStore (observations and decisions; SQLite fallback), plus a **JSON record/replay cache on disk**.

**Claude API gotchas (current API, from the Anthropic skill reference):**
- On both `claude-opus-5-5` and `claude-sonnet-5-5`, **forced `tool_choice` (`any` or `tool`) returns 400**. Use `auto` plus `strict: true` on tools, or structured outputs via `output_config.format`.
- **Opus 5.5:** thinking can't be disabled; control cost with `output_config.effort`, whose **default is `medium`**.
- **Sonnet 5.5:** `{type:"disabled"}` returns 400. Use `{type:"between_tools"}` at effort `high` or below for fast tool loops.
- **No assistant prefill.**
- Server tools: `web_search_20260209` / `web_fetch_20260209`.
- Citations are incompatible with `output_config.format`, so don't combine them in one call.
- Always check `stop_reason == "refusal"`. Enable server-side `fallbacks` (beta `server-side-fallback-2026-07-01`, `fallbacks: "default"`).

### 4b. Components and data flow

```
[Paste link / goal] ─► Ingest (yt-dlp desc + transcript | raw README | Hackaday /components | HTML)
        │                 └─ every fetch logged as SourceDoc{url, fetched_at, sha256}
        ▼
  BOM extraction: SIE extract (GLiNER2 spans) + Claude Sonnet structured output
        │          → BOMLine{raw_name, qty, source_quote, span} (quote verified as exact substring)
        ▼
  Spec resolution: Senso /org/search (trusted) → Claude Opus (only ambiguous lines)
        │          → ResolvedPart{mpn/variant, attrs (V, gear, connector), confidence}
        ▼
  Owned check: Cognee recall → mark owned/removed (user can override)
        ▼
  Offer search (parallel, cached): Shopify catalog | SerpAPI shopping+amazon | Adafruit | Best Buy
        │          → Offer{store, url, price, ship, eta, stock, rating, seen_at} → SingleStore
        ▼
  Rank: SIE score (rerank vs spec) + hard filters (variant mismatch, out of stock, ETA > deadline)
        ▼
  Compatibility: rules (text in Senso; eval in Python) → pass/warn/fail + auto-fix proposals
        ▼
  Optimize: PuLP MILP x3 tiers (budget / fastest / fewest stores)
        ▼
  Explain: Claude Sonnet writes why-cards from logged facts only → Senso /org/evals/text verifies claims
        ▼
  Approval gate (UI button only; optional Persona step-up) → signed "closed mandate"
        ▼
  Action: Shopify create_cart → continue_url ; Best Buy addToCartUrl ; deep links for others
        ▼
  Receipt: hash-chained decision log + mandates, exportable JSON; Cognee remembers the purchase
```

### 4c. Agent tool list (the model sees these; the harness enforces the gates)

| Tool | Input → output | Backed by |
|---|---|---|
| `ingest_source(url)` | → `SourceDoc{type, title, text, components?}` | yt-dlp, youtube-transcript-api, HTTP, Hackaday API |
| `extract_bom(source_id)` | → `BOMLine[]` with quote and span | SIE extract + Claude structured output |
| `lookup_trusted_spec(query)` | → `{answer, chunks[{kb_node_id, text}]}` | Senso `/org/search` |
| `resolve_part(bom_line_id)` | → `ResolvedPart` | Claude Opus + Senso |
| `recall_owned(part_ids[])` | → matches | Cognee `recall` |
| `search_offers(part_id, stores[])` | → `Offer[]` (each carries an `offer_id`) | Shopify, SerpAPI, Adafruit, Best Buy (cached) |
| `rank_offers(part_id)` | → scored `Offer[]` | SIE `score` + filters |
| `check_compatibility(plan_id)` | → `Check[]` + fixes | Python rules (rule text from Senso) |
| `optimize_cart(constraints, tier)` | → `CartPlan` | PuLP |
| `stage_cart(plan_id)` | → staged summary for the UI (no side effects) | harness |
| `create_carts(plan_id, approval_token)` | → per-store `continue_url` | Shopify Cart MCP, Best Buy URL. **Refuses without a server-issued `approval_token` from the UI button.** |
| `remember(fact)` | → ok | Cognee `remember` |

**Harness rules** (borrowed from the commerce-agents blueprint):
- Cart writes accept only `offer_id`s returned by `search_offers` in this run.
- No tool pays.
- An approval typed in chat approves nothing.
- Logging is automatic in the tool wrapper, not something the model chooses to do.

### 4d. Audit-trail data schema (one `DecisionRecord` per part, plus run-level mandates)

```json
{
  "run_id": "r_2026-11-20T13:05Z_7f3", "seq": 4, "ts": "2026-11-20T13:07:12Z",
  "part": {"bom_line_id": "b3", "raw_name": "STS3215 Servo 7.4V, 1/345 gear (C001)", "qty": 6,
           "source": {"url": "https://github.com/TheRobotStudio/SO-ARM100", "quote": "…", "span": [1234, 1290], "doc_sha256": "…"}},
  "resolution": {"spec": "Feetech STS3215 7.4V 1/345 (C001)", "attrs": {"voltage": "7.4V", "protocol": "TTL serial bus"},
                 "confidence": 0.93, "method": "exact_from_source|senso|llm_inferred",
                 "trusted_context": [{"provider": "senso", "query": "…", "kb_node_id": "…", "snippet": "…"}]},
  "owned_check": {"provider": "cognee", "query": "…", "matched": null, "action": "keep"},
  "candidates": [{"offer_id": "o17", "store": "…", "url": "…", "price": 13.89, "currency": "USD",
                  "shipping": 0, "eta_days": 6, "stock": "in_stock", "rating": 4.6, "reviews": 212,
                  "seen_at": "2026-11-20T12:58:40Z", "source_api": "shopify_catalog|serpapi|adafruit|bestbuy",
                  "rerank_score": 0.91, "filtered_out": null}],
  "rejected": [{"offer_id": "o22", "reason": "variant_mismatch: 12V"}, {"offer_id": "o25", "reason": "eta 21d > deadline"}],
  "compatibility": [{"rule_id": "PSU_VOLTAGE_MATCH", "inputs": {"servo_v": "7.4V", "psu": "5V"}, "result": "pass|warn|fail", "message": "…", "fix": null}],
  "decision": {"chosen_offer_id": "o17", "tier": "budget", "reason_codes": ["cheapest_in_stock", "same_store_as_board"],
               "explanation": "…", "claims_verified": {"provider": "senso_evals", "run_id": "…", "status": "supported|unsupported"}},
  "model": {"name": "claude-sonnet-5-5", "effort": "medium", "input_tokens": 0, "output_tokens": 0},
  "tool_call_ids": ["tc_31", "tc_32"],
  "prev_hash": "sha256:…", "hash": "sha256(prev_hash + canonical_json(record))"
}
```

**Run-level records:**
- `IntentMandate`, AP2-inspired "open" form, created when the goal is set:
  ```
  { constraints: { budget_usd, deadline, allowed_merchants[], line_items[{id, acceptable_items[], quantity}] },
    user_id, created_at, signature (ES256) }
  ```
- `ApprovalEvent`:
  ```
  { plan_id, total, approved_by: "ui_button", persona_inquiry_id?, ts, signature }
  ```
- `CartAction`:
  ```
  { store, cart_id, continue_url, line_items, ts }
  ```

**SingleStore tables** (stay within 10): `runs`, `source_docs`, `bom_lines`, `offers` (with `price_observations` columns), `decisions` (JSON), `mandates`, `events`.

### 4e. What to cache or fake for demo reliability

1. **Record/replay layer** around every external call, keyed by `(tool, normalized args)` and written to `cache/*.json`. `DEMO_MODE=replay` serves cached responses with their original `seen_at`. Record the hero run between 1:30 and 3:00 PM.
2. **Pre-ingest** Senso documents and wait for `processing_status: complete`. **Pre-load** Cognee memories. **Pre-warm** SIE models (cold start returns 503).
3. **Pin "now"** for ETA math so the arrival timeline doesn't shift during the demo.
4. **Inject** the "out of stock" and "price jump" events from a fixture, labeled "simulated" in the trail. Be honest on stage.
5. **Owned inventory** comes from a seeded memory, not real Gmail.
6. **Checkout is never completed.** Stop at the Shopify `continue_url` and the Best Buy cart link.
7. Keep **local copies of the URDF and STLs** in the frontend's `public/` folder. No network loads for 3D.
8. Keep a **fallback mock store** in the same `Offer` shape in case Shopify or SerpAPI fails live.
9. Record a **backup screen video** of the full hero run by 4:00.

### 4f. Hour-by-hour plan (4 people: A = agent, B = data and action, C = frontend, D = sponsors and demo)

| Time | A: Agent core | B: Search and action | C: Frontend | D: Sponsors and demo |
|---|---|---|---|---|
| **11:00–11:20** | Repo, `.env`, shared JSON schemas (`BOMLine`, `Offer`, `DecisionRecord`), logger and hash chain | Cache layer skeleton | Vite app shell, layout (left: 3D/part map, right: BOM list and why card, bottom: timeline) | Senso folders; start ingesting README, specs, rules and policies |
| **11:20–12:30** | `ingest_source` (GitHub/YouTube), `extract_bom` with quote verification | `ucp catalog search` adapter, SerpAPI adapter, Adafruit adapter; record responses | URDF load of SO-101, click to identify link, highlight, BOM list ↔ 3D two-way highlight | SIE `extract` + `score` wired; Cognee configured with seed memories |
| **12:30–1:30** | `resolve_part` (Senso + Opus), PuLP optimizer with 3 tiers, compatibility rules (12V auto-fix) | Shopify `create_cart` → `continue_url`; Best Buy `addToCartUrl`; mock-store fallback | Why card (sources, prices seen, rejected alternatives, compatibility, trusted context), timeline via SSE | SingleStore tables plus writes; Senso `/org/evals/text` on why cards |
| **1:30–2:30** | **End-to-end hero run on SO-101**; fix grounding bugs | Approval token gate; mandate signing (ES256) | Tier switcher, "I already own this" toggle, approval modal | Optional: Amplitude wrapper (15 min) or Persona step-up |
| **2:30–3:15** | Out-of-stock substitution, budget slider | Record and replay the whole run | Exploded-view slider, arrival timeline, power-budget gauge | README sections per sponsor ("how we use X") |
| **3:15–3:45** | **Feature freeze**; rehearse twice in replay mode | Verify the live path once | Polish, empty and loading states | Demo script, timing |
| **3:45–4:05** | — | — | — | **Record the 2–3 min demo video** (plus backup take) |
| **4:05–4:30** | Push, tag | — | Screenshots | Submit: repo, video link, what we built, tools used |

**If the team is 2–3 people:** drop SingleStore (use SQLite), Firedrill, Persona and the AgentPrism tab. Keep Senso, SIE and Cognee.

**Hero demo script (~2:30):**
1. Paste the SO-101 GitHub link.
2. BOM lines stream in with quotes. The arm renders, and parts light up as they resolve.
3. "I already own a screwdriver set and USB-C cables": Cognee removes them, and the trail shows the memory match.
4. Tiers: Budget vs. Fastest vs. Fewest stores.
5. Switch to 12V servos for more torque. A compatibility FAIL appears, and the auto-fix swaps in a 12V 5A PSU.
6. Click a servo. The why card shows:
   - stores checked and prices seen at 12:58;
   - the 12V variant rejected (mismatch) and a 21-day option rejected (late);
   - the Senso trusted source with a ✅ claims check.
7. Approve. Shopify carts are created and `continue_url` opens, stopping before payment.
8. Export the signed receipt.

### 4g. Tonight's non-code prep (check event rules first)

- **Keys:**
  - Anthropic.
  - SerpAPI.
  - Senso: create an org; ask about credits.
  - SIE console.
  - SingleStore: a free Shared workspace in us-east-1.
  - Best Buy.
  - Cognee Cloud key (optional).
  - Firedrill: redeem `TOKENSAND`.
- Install Node 22.19+ for `@shopify/ucp-cli`, and Python 3.11+.
- Manually try `ucp catalog search` for "STS3215", "Waveshare bus servo adapter" and "5V power supply 5.5x2.1" to see whether Shopify merchants carry them.
- Open the SO-101 URDF in gkjohnson's drag-and-drop viewer to confirm the meshes load and the scale is right.
- Draw wireframes. Don't write app code before 11:00.

---

## 5. Demo builds

| Build | Published parts list | Approx. parts | 3D files | Verdict |
|---|---|---|---|---|
| **SO-101 robot arm** ([repo](https://github.com/TheRobotStudio/SO-ARM100); 8,176 stars, Apache-2.0, pushed 2026-10-06) | Yes, in the README, with US, EU, CN and JP prices and links (Alibaba servos; Amazon board, cable, PSU, clamps, screwdriver; Taobao and Akizuki for CN and JP). **One follower arm: $121.94 US**: 6× STS3215 1/345, control board, USB-C cables, PSU, 2 clamps, screwdriver set. **Leader + follower: $229.88**: 12 servos in 3 gear ratios (7× C001 1/345, 2× C044 1/191, 3× C046 1/147), 2 boards, 2 PSUs. | 6 line items / 11 units (follower), or 8 / 17 (pair), plus about 13 printed parts | **URDF + MJCF + per-link STLs** in `Simulation/SO101/assets`; individual print STLs in `STL/SO101/Individual/`; printing guide in 3DPRINT.md; many vendor kits (Seeed Studio, WowRobo, PartaBot and others) | **Pick this.** Real prices to compare against, gear-ratio variants (a "vague → exact" story), the 7.4V vs. 12V compatibility story, "kit vs. DIY" comparison, and articulated clickable 3D. |
| **AmazingHand** ([repo](https://github.com/pollen-robotics/AmazingHand); 2,562 stars, Apache-2.0 for software, CC BY 4.0 for mechanical, pushed 2026-04-23) | Yes: [BOM Google Sheet](https://docs.google.com/spreadsheets/d/1QH2ePseqXjAhkWdS9oBYAcHPrxaxkSRCgM_kOK0m52E/edit?gid=1269903342#gid=1269903342) plus a [Chinese-sourcing BOM](https://docs.google.com/spreadsheets/d/1fHZiTky79vyZwICj5UGP2c_RiuLLm89K8HrB3vpb2h4/edit?gid=837395814#gid=837395814). The README says 8× Feetech SCS0009, a Waveshare serial bus driver (or Arduino + Feetech TTL Linker), and a 5V/2A adapter. Target cost under €200. I couldn't read the sheet contents through my fetcher **[open it in a browser]**. | ~10–15 line items **[estimate]** | STL and STEP per part in `cad/` (R/L prefixes) plus an Onshape document. **No URDF at the top level**, so an assembled view needs an Onshape GLB export **[unverified]**. | **Second example**, good for the "robot hand" ask. Power-budget story: 8 servos on a 2A supply. Use the 2D photo part map or React Flow graph instead of 3D. |
| **Corne keyboard v4** ([repo](https://github.com/foostan/crkbd); 7,762 stars, CC-BY-4.0, pushed 2026-11-14; [build guide](https://github.com/foostan/crkbd/blob/main/docs/corne-cherry/v4/buildguide_en.md)) | Yes: PCB, case, FR4 plate, 42–46 MX switches, 42–46 keycaps (40×1u + 2×1.5u), 8× M2 7.5 mm spacers, 16× M2 5 mm screws, 8 cushions, a TRRS cable (v4.0.0 rejects TRS), USB-C, optional EC12 encoders | ~11 line items, ~120 units | The guide doesn't mention 3D case files | A good **compatibility** story (TRRS vs. TRS; MX-only switches) but a weaker visual. Backup demo. |

Also considered:
- **InMoov hand**: messy, forum-based BOM.
- **e-NABLE Phoenix**: no electronics, non-commercial terms, sensitive use case.

**Pick: SO-101 follower arm for the stage.** Mention the AmazingHand "robot hand" as a second paste-a-link example if time allows.

---

## 6. Creative polish (wow vs. effort, 1–5)

| # | Feature | Wow | Effort | Notes |
|---|---|---|---|---|
| 1 | **Compatibility doctor with auto-fix** (12V servos → 12V 5A PSU; TRS → TRRS) | 5 | 3 | The single best "agent did something smart" moment. |
| 2 | **Articulated exploded 3D** (URDF joint sliders plus an explode slider; parts glow as they resolve) | 5 | 3 | The centerpiece. |
| 3 | **Cart tiers**: Budget / Fastest / Fewest stores, with a side-by-side diff | 4 | 2 | Same MILP, different weights. |
| 4 | **"I already own this"** toggle backed by memory, with "remembered from …" provenance | 4 | 2 | Cognee. |
| 5 | **Kit vs. DIY**: compare a vendor kit (README-listed sellers) against the sourced cart, in money and in days | 4 | 2 | Honest advice builds trust. |
| 6 | **Arrival timeline**: a Gantt of deliveries plus "you can start building on Thursday" | 4 | 2 | Uses ETAs. |
| 7 | **Out-of-stock substitution diff** ("C001 OOS at X → same SKU at Y, +$1.20, +2 days") | 4 | 2 | Inject the stock-out live. |
| 8 | **Signed receipt**: hash-chained trail plus an AP2-style mandate, with a "Verify" button that recomputes the chain | 4 | 2 | The audit-trail wow. |
| 9 | **Power-budget gauge** (Σ servo current vs. PSU rating) | 4 | 2 | Needs datasheet numbers; verify them first. |
| 10 | **Prices-seen sparkline** per part, from our own observations, plus a "price changed since you looked" badge | 3 | 2 | SingleStore. |
| 11 | **Print-or-buy for printed parts**: filament grams estimate or a print-service link (SO-101 3DPRINT.md) | 3 | 2 | |
| 12 | **Tools-you'll-need and consumables** list (screwdriver, clamps, PLA+, supports), with owned items removed | 3 | 1 | |
| 13 | **Region switch** US / EU / CN / JP using the README's per-region prices | 3 | 2 | Shows global context. |
| 14 | **Confidence badges** and a "needs human check" flag on any line resolved by inference | 3 | 1 | Cheap honesty. |
| 15 | **Safety notes**: mains-powered PSU, servo pinch points, stall heat | 2 | 1 | |

---

## Biggest risks (and mitigations)

1. **Store coverage.**
   - Risk: Shopify's catalog may not carry STS3215 servos, and SerpAPI's free quota is 250 searches per month.
   - Mitigation: test tonight. Cache every call. Have a mock-store fallback.
2. **Real action reliability.**
   - Risk: browser agents get blocked, and Amazon's terms are a concern.
   - Mitigation: use only the Shopify Cart MCP `continue_url` and the Best Buy `addToCartUrl`; deep links for the rest.
3. **3D asset issues.**
   - Risk: URDF scale or paths, and slow STL loads.
   - Mitigation: confirm tonight in gkjohnson's drag-and-drop viewer. Keep the React Flow graph as a fallback.
4. **Sponsor sprawl.**
   - Risk: Senso credits running out (402), SIE cold starts (503), Cognee's slow `remember`.
   - Mitigation: integrate deeply with 3 sponsors and add the 4th only if on schedule. Pre-warm everything.
5. **Claude API surface changes.**
   - Risk: forced `tool_choice` and disabled-thinking configs return 400 on the 5.5 models.
   - Mitigation: use `auto` + `strict`, and structured outputs.
6. **Event rules.**
   - "Code must be written during the event": don't fork commerce-agents or AP2 samples. Use libraries and borrow patterns.
7. **Windows machines.**
   - Firedrill drills need macOS/Linux, and Cognee needs Python 3.11+ on Windows.
8. **Truthfulness.**
   - Prices move during the day. Always show `seen_at`.
   - Label simulated events as simulated.
   - Have the agent state facts only from tool results, and verify claims with Senso evals.
