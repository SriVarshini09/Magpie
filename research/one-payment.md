# One payment, many stores: research and build recommendation

Researched Thu Nov 19, 2026 for the Nov 20 build (11:00–16:30 PT). Read-only research: nothing was signed up for, installed, or called. Items I could not confirm from a primary source are marked **[unverified]**.

## Bottom line

- **No self-serve path exists today that lets our site take one real payment and pay real Shopify merchants.** Shopify's `complete_checkout` is granted case by case with no public application (Shopify staff, Sep 2 2026). Every aggregator that does it for real either needs production keys (Crossmint) or merchant onboarding (Violet, Stripe SPT).
- **What we can build tomorrow:** a real "Pay once" screen backed by a Stripe sandbox hold for the combined total, a per-store fan-out using Stripe Issuing virtual cards capped at each store's subtotal (simulated authorizations), and real merchant carts handed to the human through Shopify Checkout Kit popups over our page.
- **The demo must label the split honestly:** payment and settlement are test mode; carts are real; real payment stays with the human on the merchant's checkout.

## Recommended tiers

| Tier | Time | What it is | Real | Test / simulated | Keys |
|---|---|---|---|---|---|
| 1 | ~30 min | "Pay once" screen (combined total, per-store breakdown) + per-store hand-off using Checkout Kit for Web popup, plain link as fallback | Carts, totals, merchant checkout pages | Nothing is charged by us | None |
| 2 | ~60 min | Stripe sandbox: one PaymentIntent hold for the total, one Issuing virtual card per store with a spending limit equal to that store's subtotal, simulated authorization per store, then capture exactly what was approved | Stripe API objects, spending-limit enforcement, hold/capture logic | The card, the money, the merchant authorizations | Stripe sandbox `pk_test`/`sk_test`, Issuing activated in the sandbox |
| 3 | stretch | (a) 2–3 local UCP sample merchants complete checkout and return test order IDs, or (b) Stripe Shared Payment Tokens, one per store, each capped at the store subtotal | UCP wire protocol, order objects | Merchants, payment | (a) none; (b) Stripe sandbox, preview API version |

Build order: Tier 1 first and commit it. Tier 2 behind a "Test mode" toggle so Tier 1 still demos if Stripe misbehaves.

---

## Option A: Embedded merchant checkout inside our site

### Findings

- **UCP Embedded Checkout Protocol (ECP)** lets a host embed the business's checkout in an iframe or webview and exchange JSON-RPC 2.0 messages (`ec.ready`, `ec.start`, `ec.complete`, `ec.error`, `ec.totals.change`, plus delegation requests `ec.payment.credential_request`, `ec.payment.instruments_change_request`, `ec.fulfillment.address_change_request`, `ec.window.open_request`). The host appends `ec_version` (required), `ec_auth`, `ec_delegate`, `ec_color_scheme` to `continue_url`. Source: ucp.dev/specification/shopping/checkout/embedded/.
- **Shopify's ECP page** says the `continue_url` comes from a **UCP checkout response with status `requires_escalation`**, shows only iOS/Android webview examples, and its sample fetches an auth JWT for `ec_auth` (`fetchShopifyAuthenticationJWT()`). Checkout responses need the Checkout MCP, which is **not available at the anonymous tier**. Source: shopify.dev/docs/agents/checkout/ecp, shopify.dev/docs/agents/profiles/auth-and-rate-limiting.
- **Tier table (Shopify):** Anonymous = catalog + cart. Signed (RFC 9421 HTTP message signatures, ECDSA P-256, public key in our hosted agent profile) = adds checkout, no `complete_checkout`. Token (JWT via Dev Dashboard) = `complete_checkout` only if the token has purchase permission. The page does not state an approval step for Signed. **[unverified]** whether Signed works without any review.
- **`complete_checkout` access:** Shopify staff in the community thread (Aug 6 – Sep 2, 2026): "no public self-service application", granted "case by case", cannot be added from the Dev Dashboard scope picker, also needs the merchant to have the agent's channel enabled. A "Universal Cart access form" exists; a poster reported no response.
- **Checkout Kit for Web** (`@shopify/checkout-kit`, v4, transport is ECP): `<shopify-checkout>` element, `checkout.src = url; checkout.open()`. `target` is `auto`/`_blank` (new tab) or `popup` ("popup window centered over your page"). Docs state: "Checkout opens in a separate window on the checkout origin and communicates with your page through postMessage, so your page doesn't frame or fetch checkout." A `complete` DOM event carries `event.detail.checkout.order` (`order.id`). Shopify's agents page lists `create_cart` (Cart MCP) output as a valid input. A search summary of the docs says inline embedding requires JWT auth. Sources: shopify.dev/docs/storefronts/mobile/checkout-kit/web, shopify.dev/docs/agents/carts-and-checkout/checkout-kit.

### Verdict

- **Inline iframe/modal of the merchant checkout: not available to us tomorrow.** It needs at least Signed tier (hosted profile + request signing) to get a checkout object, and a JWT for inline rendering.
- **Popup over our page: available with no credentials.** The user stays on our site; each store's checkout opens in a centered popup; we get a `complete` event with the order. **[unverified]** that the `complete` event fires for an anonymous cart `continue_url` on an arbitrary merchant; test with one cart first, without paying.
- **Sequential flow:** browsers block popups not triggered by a click, so use one "Pay at <store>" button per store rather than auto-chaining.
- **Shop Pay:** Shop Pay recognises a returning buyer by email/SMS code across Shopify stores, which makes N checkouts fast. **[unverified]** in the popup context.

| | |
|---|---|
| One payment? | No. N payments, one per store, each on the merchant's own checkout |
| Real vs simulated | All real. On stage, stop before paying |
| Keys | None |
| Steps | `npm i @shopify/checkout-kit`; `import '@shopify/checkout-kit/shopify-checkout'`; render `<shopify-checkout target="popup">`; set `src` to the cart `continue_url`; listen for `complete`; keep an `<a href target="_blank">` fallback |
| Minutes | 20–30 |
| Demo moment | Click "Pay at WowRobo" and the real Shopify checkout with the 6 servos appears over our app |
| Production path | Merchant is merchant of record; we are a referrer. No licence needed. True single payment needs Shopify's Token tier with purchase permission plus the Shop Pay handler |
| Risks | Popup blockers; event may not fire for anonymous carts; CSP needs the checkout domain in `frame-src`/`connect-src` per docs |

---

## Option B: Stripe test mode "pay once, fan out"

### Findings

- **Manual capture hold:** `POST /v1/payment_intents` with `capture_method=manual`; after confirmation status is `requires_capture`. Capture with `POST /v1/payment_intents/{id}/capture`, optional `amount_to_capture` (partial capture releases the rest; only one capture per payment for most cards). Cancel releases the hold. Online card holds last 7 days (Visa merchant-initiated 5). Source: docs.stripe.com/payments/place-a-hold-on-a-payment-method.
- **Issuing in a sandbox is self-serve:** "You can activate Issuing in a sandbox in the Stripe Dashboard without contacting sales. Sandbox access is instant." and "In a sandbox, all card transactions are simulated. No real funds move." Source: docs.stripe.com/issuing/for-your-business.
- **Sandbox cards cannot pay real stores:** "You can only use these cards for testing within your Stripe account and not for external purchases." Source: docs.stripe.com/issuing/testing. So a test Issuing card will be declined at the real WowRobo checkout; do not try.
- **Test helpers:** `POST /v1/test_helpers/issuing/authorizations` (params `card`, `amount`, `merchant_data[name]`, `merchant_data[category]`, ...) and `POST /v1/test_helpers/issuing/authorizations/{id}/capture`, which creates an Issuing Transaction.
- **Funding:** the test Issuing balance must be funded first. US accounts use test top-ups (Dashboard or Top-ups API).
- **Spending limits:** `spending_controls[spending_limits][0][amount]=<cents>` with `interval=per_authorization` (shown in Stripe's agent guide). Single-use cards are also offered.

### How "one payment" works

1. Buyer pays the combined total once in a Stripe Payment Element on our page (test card `4242 4242 4242 4242`). We hold, not capture.
2. Backend creates one virtual card per store, limit = that store's subtotal, `metadata[mandate_id]`, `metadata[merchant]`.
3. For each store, simulate the merchant's authorization for its subtotal with `merchant_data[name]` set to the store name. Approved authorizations come back with IDs.
4. Capture the hold for the sum of approved amounts. If a store fails, `amount_to_capture` is lower and the buyer is never charged for it.

### Key calls

```
POST /v1/payment_intents            amount=<total> currency=usd capture_method=manual
                                    automatic_payment_methods[enabled]=true metadata[mandate_id]=...
POST /v1/issuing/cardholders        name, type=individual, billing[address][...]   (once)
POST /v1/issuing/cards              cardholder, type=virtual, currency=usd, status=active,
                                    spending_controls[spending_limits][0][amount]=<store cents>,
                                    spending_controls[spending_limits][0][interval]=per_authorization
POST /v1/test_helpers/issuing/authorizations   card, amount, merchant_data[name]=<store>
POST /v1/test_helpers/issuing/authorizations/{id}/capture
POST /v1/payment_intents/{id}/capture          amount_to_capture=<approved sum>
```

Frontend: `@stripe/stripe-js` + `@stripe/react-stripe-js`, `<Elements options={{clientSecret}}>`, `<PaymentElement/>`, `stripe.confirmPayment({elements, redirect: 'if_required'})`.

| | |
|---|---|
| Real vs simulated | Real Stripe objects and real limit enforcement; no real card, money, or merchant |
| Keys tonight | Stripe account (free, self-serve), a sandbox, Issuing activated in it, test balance topped up, one cardholder created. Do these tonight; they are the only steps that can surprise us |
| Minutes | 45–60 with keys ready (15 hold, 25 fan-out, 15 UI status) |
| Demo moment | One "Pay $X once" click, then three store rows flip to "Authorized $90.94 at WowRobo, card ••1234, limit $90.94". Bonus: try to authorize $1 over a store's limit and show the decline |
| Production path | Stripe Issuing lists "Reseller" and "On-demand services and fulfillment" as supported use cases, with a self-serve Standard program (limits: 25 cards/week, $5,000/week, $500/card/day, single-use virtual cards). Live mode needs an eligibility review. **We would be the merchant of record to the buyer**: sales tax, refunds, chargebacks, and each merchant's terms on resale are ours. Not legal advice; needs counsel before launch |
| Risks | Issuing activation in the sandbox may ask onboarding questions; cardholder may need terms-acceptance fields **[unverified]**; exact top-up parameters for the Issuing balance **[unverified]** (use the Dashboard); legacy "test mode" vs new sandboxes can behave differently |

**Connect transfers alternative:** separate charges and transfers to test connected accounts also demonstrate fan-out, but real merchants would each need to onboard to our Connect platform, which does not match buying from arbitrary Shopify stores. Issuing matches the story better.

---

## Option C: Universal / multi-merchant checkout APIs

| Provider | Sandbox | Self-serve tonight | Coverage | One-payment semantics | Verdict |
|---|---|---|---|---|---|
| **Jolly (docs still say Rye; docs.rye.com redirects to docs.commerce.jolly.dev)** | Staging `https://api.commerce.staging.jolly.dev/api/v1/` "no real orders or charges"; pay with `stripe_token` `tok_visa` | Key from the console Account page; separate staging account. Whether signup is instant is **[unverified]** | Shopify, Amazon, Best Buy, "thousands more"; US shipping, physical goods | **One product per checkout intent** (multi-product carts not supported). `POST /checkout-intents`, poll `GET /checkout-intents/{id}`, `POST /checkout-intents/{id}/confirm`. Intents expire in 45 min. 5 req/s, **50 req/day** | Stretch only. A 10-line parts list burns the daily quota in one run |
| **Stripe Shared Payment Tokens (SPT)** | Yes. `POST /v1/test_helpers/shared_payment/granted_tokens` (params `payment_method`, `usage_limits[currency|max_amount|expires_at]`); seller charges with `payment_method_data[shared_payment_granted_token]=spt_...`. Agent side: `POST /v1/shared_payment/issued_tokens` with sandbox test seller profile `profile_test_61TU90nIeGjU7NNVXA6TU90m7ISQWsBxpcx9lASWWXTk` | Needs a Stripe profile and agreeing to preview terms; docs use versions `2026-09-30.preview` and `2026-11-18.endive`. Whether a brand-new sandbox can call it without enablement is **[unverified]** | Only sellers on Stripe that accept SPT (ACP, or UCP `com.stripe.payments` handler). Not Shopify Payments merchants | Buyer enters card once; we issue one token per seller, each capped at that seller's amount and expiry; each seller charges directly | Best production story (we never hold funds, merchant stays merchant of record). Tier 3b |
| **Violet.io** | `sandbox-api.violet.io`; signup at channel.violet.io/signup per docs (search result; guide page now 404) **[unverified]** | App ID/secret appear self-serve | Only merchants that connect their store to our Violet app | True single cart with per-merchant "bags", one payment, orders submitted to each platform | Right model, wrong timeline: WowRobo etc. are not connected to us |
| **Crossmint Agent Checkouts** | **Production only**: staging keys get 403 "Agent Checkouts is only available in production" | Yes, but real orders | Broad | One API, real purchase | Excluded by the no-real-money rule |
| **Shopify Shop MCP / Universal Checkout** | None found | No API key needed for Shop MCP; in-agent completion requires Shop sign-in and Shopify's permission | Shopify merchants | Shop app reportedly has multi-merchant single checkout (secondary sources) **[unverified]** | The real long-term path on Shopify; not buildable tomorrow, and completing would move real money |
| **Skyfire** | Docs mention sandbox credentials on request **[unverified]** | Not confirmed | Participating sellers | Agent wallet/token | Skip |
| **Firmly** | No public docs found **[unverified]** | Appears sales-led | Unknown | Unknown | Skip |

Jolly merchant-of-record detail (from its payment providers page): `stripe_token` makes Rye/Jolly the merchant of record; `basis_theory_token` on Shopify forwards the card to Shopify's vault so the merchant stays merchant of record; `drawdown` (pre-funded balance) makes the developer the merchant of record.

---

## Option D: Local UCP sample merchants

### Findings (github.com/Universal-Commerce-Protocol/samples)

- **Python server** (`rest/python/server`, FastAPI, uv): 
  ```
  uv sync
  uv run import_csv.py --products_db_path=<dir>/products.db --transactions_db_path=<dir>/transactions.db --data_dir=../test_data/flower_shop
  uv run server.py --products_db_path=... --transactions_db_path=... --port=8182
  ```
  Advertises handlers `shop_pay`, `google_pay`, and `mock_payment_handler` (`dev.mock.payment_handler`). Has `POST /testing/simulate-shipping/{id}` guarded by a `Simulation-Secret` header. Flags: `--require_signatures`, `--allow_insecure_profile_urls`.
- **Client happy path** (`rest/python/client/flower_shop/simple_happy_path_client.py`): `GET /.well-known/ucp` → `POST /carts` → `POST /checkout-sessions {"cart_id"}` → three `PUT /checkout-sessions/{id}` (fulfillment method, destination, option) → `POST /checkout-sessions/{id}/complete` with
  ```json
  {"payment":{"instruments":[{"id":"instr_my_card","handler_id":"mock_payment_handler","type":"card",
   "credential":{"type":"token","token":"success_token"}, "billing_address":{...}}]}}
  ```
  Response has `status`, `order.id`, `order.permalink_url`. Headers: `UCP-Agent: profile="..."`, `idempotency-key`, `request-id`; unsigned mode sends `request-signature: test`.
- **Node server** (`rest/nodejs`, Hono, port 3000): `npm install`, `npm run dev`; README does not explain product seeding.
- **A2A sample** is marked unmaintained.
- **AP2 mandates:** UCP capability `dev.ucp.shopping.ap2_mandate`; business returns `ap2.merchant_authorization` (detached JWS) on every checkout response; platform sends `ap2.checkout_mandate` on complete; AP2 v0.2 requires ECDSA. Whether the sample server implements this is **[unverified]**.

### Windows notes

- README commands are POSIX (`/tmp`, `&`, `kill`, `mkdir -p`). On Windows use a local folder for the DBs and one terminal per server.
- Three merchants = three processes with different `--port` and DB paths. Only flower-shop test data ships; robot-parts CSVs must be written by hand (CSV schema **[unverified]**), or accept that the stand-in stores sell flowers.
- uv must be installed on each laptop; first `uv sync` downloads dependencies. Do it tonight, not at 11:00.

| | |
|---|---|
| One payment? | After the Stripe test hold, the agent calls `complete` at each local merchant with the mock token and gets an order ID per store |
| Real vs simulated | Real UCP protocol and order records; fake merchants, fake payment |
| Keys | None |
| Minutes | 60–90 on Windows from cold (clone, uv, seeding, three instances, client port). 30–40 if one teammate pre-stages it tonight |
| Demo moment | Three order IDs appear from three "stores" seconds after one payment |
| Production path | Same code against real UCP merchants once a tier that allows `complete_checkout` is granted, with a real handler (Shop Pay, or `com.stripe.payments` carrying an SPT) |
| Risks | Setup time on Windows; data mismatch with the real demo carts; adds three processes to keep alive on stage |

**Cheaper variant:** a single FastAPI router in our own backend that mimics the three UCP endpoints we use (`/.well-known/ucp`, `POST /checkout-sessions`, `POST /checkout-sessions/{id}/complete`) for N named merchants and returns order IDs. About 20 minutes, no extra processes. Label it "UCP-shaped mock merchant", not the reference server.

---

## Recommended build

### Tier 1 (30 min, no keys): Pay-once screen with real hand-off

- Screen shows combined total, per-store rows (store, item count, subtotal, shipping "calculated at store").
- Each row has "Pay at <store>" which opens the real cart in a Checkout Kit popup; fallback is an `<a target="_blank">` to `continue_url`.
- On `complete` event, row turns to "Paid, order <id>" **[unverified event]**; otherwise a manual "I've paid" tick.
- Audit trail: one cart mandate per store, state `handed_off` → `closed_by_user`.

### Tier 2 (60 min, Stripe sandbox): the "one payment" moment

- "Pay $X once" button with a visible **TEST MODE** badge. Payment Element inline, card 4242.
- Backend sequence: hold → card per store → simulated authorization per store → capture approved sum.
- Row states: `Queued` → `Card issued (limit $S)` → `Authorized at <store>` → `Settled`. Show the card's last4 and the authorization ID.
- Each row keeps the real hand-off link from Tier 1 under a "Real cart" label, so nobody thinks WowRobo was paid.
- Failure path worth showing: force one store over its limit, show the decline, and show the capture drop by that amount.

### Tier 3 (stretch, pick one)

- **3a:** mock or sample UCP merchants return order IDs after the authorization step (use the in-process variant unless the samples are pre-staged tonight).
- **3b:** replace the Issuing fan-out with one SPT per store (`usage_limits[max_amount]` = subtotal) and describe it as the production design where we never hold funds.
- **3c:** Jolly staging for one single-product order, only if a staging key is already in hand.

### UI flow for the Pay-once screen

1. **Header:** "Pay once for 3 stores", total in large type, TEST MODE pill.
2. **Breakdown card:** table of store, items, subtotal; footer row with combined total. Expandable line items.
3. **Consent line:** "You authorise up to $TOTAL, split as shown. Each store can charge at most its own subtotal." Checkbox gates the pay button.
4. **Payment Element** and "Pay $TOTAL once".
5. **Progress panel** after payment: one row per store with a stepper and live status (poll or SSE from FastAPI).
6. **Receipt:** hold ID, captured amount, released amount, per-store authorization or order ID, real-cart link, and "View mandate" opening the audit record JSON.

### Audit trail: closed mandate bound to the payment

Create the mandate **before** payment, hash it, and put the hash into Stripe metadata so each side points at the other.

```json
{
  "mandate_id": "mnd_...",
  "type": "payment",
  "status": "closed",
  "mode": "test",
  "user_consent": {"at": "2026-11-20T...", "text_shown": "You authorise up to ..."},
  "total": {"amount": 21450, "currency": "usd"},
  "allocations": [
    {"merchant": "shop.wowrobo.com", "cart_id": "...", "continue_url": "...",
     "cart_hash": "sha256:...", "limit": 9094,
     "instrument": {"kind": "issuing_card", "id": "ic_...", "last4": "1234"},
     "authorization_id": "iauth_...", "order_id": null, "status": "authorized"}
  ],
  "payment": {"provider": "stripe", "payment_intent": "pi_...",
              "authorized": 21450, "captured": 21450, "released": 0},
  "mandate_hash": "sha256:<canonical JSON without this field and without payment>",
  "signature": {"alg": "ES256", "kid": "demo-key-1", "value": "..."},
  "closed_at": "2026-11-20T..."
}
```

- States: `open` (created, consent recorded) → `funded` (hold placed) → `executing` → `closed` (captured or cancelled). A closed mandate is never edited; a change creates a new one.
- Set `metadata[mandate_id]` and `metadata[mandate_hash]` on the PaymentIntent and on each Issuing card.
- ES256 matches AP2 v0.2's ECDSA requirement, so the record can later become a real AP2 mandate. Signing is optional for the demo; the hash is not.

## Do tonight

1. Create the Stripe account and a sandbox, activate Issuing in it, top up the test Issuing balance, create one cardholder, and run one simulated authorization from the Dashboard. This is the single biggest de-risking step.
2. Put `STRIPE_SECRET_KEY` and `VITE_STRIPE_PUBLISHABLE_KEY` in a shared `.env`; confirm they are `sk_test`/`pk_test`.
3. Open one existing cart `continue_url` through a Checkout Kit popup and see whether the `complete`/lifecycle events arrive (do not pay).
4. Optional: install uv and pre-stage one UCP sample server if Tier 3a with the real samples is wanted.

## Biggest risks

1. **Misrepresentation on stage.** The fan-out pays nobody. If the UI does not say "test mode, simulated merchant authorizations", judges may assume real stores were paid, and a question exposes it. Keep the badge and the "Real cart" links.
2. **Issuing sandbox setup friction** discovered at 11:00 instead of tonight.
3. **Scope creep.** Tier 2 has three moving parts; cut the decline demo and the signature first.
4. **Live keys.** Any `sk_live` key in the repo breaks the hard constraint. Assert the `sk_test` prefix at startup.

## Sources

- https://ucp.dev/specification/shopping/checkout/embedded/
- https://shopify.dev/docs/agents/checkout/ecp
- https://shopify.dev/docs/agents/profiles/auth-and-rate-limiting
- https://shopify.dev/docs/agents/carts-and-checkout/checkout-kit
- https://shopify.dev/docs/storefronts/mobile/checkout-kit/web
- https://shopify.dev/docs/agents.md
- https://community.shopify.dev/t/how-can-a-token-tier-ucp-client-obtain-permission-to-call-complete-checkout/36590
- https://docs.stripe.com/payments/place-a-hold-on-a-payment-method
- https://docs.stripe.com/issuing/testing
- https://docs.stripe.com/issuing/for-your-business
- https://docs.stripe.com/issuing/agents/programmatic-checkout
- https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens
- https://docs.stripe.com/api/shared-payment/granted-token/create
- https://docs.stripe.com/agentic-commerce/protocols/ucp/stripe-payments-handler
- https://docs.commerce.jolly.dev/llm-context.md and https://docs.commerce.jolly.dev/api-v2/payment-providers
- https://docs.crossmint.com/api-reference/agent-checkouts/create-agent-checkout
- https://docs.violet.io/checkout/overview
- https://github.com/Universal-Commerce-Protocol/samples (rest/python/server/README.md, rest/nodejs/README.md, rest/python/client/flower_shop/simple_happy_path_client.py)
- https://ucp.dev/specification/ap2-mandates/

Note: the Jolly docs page contained text addressed to AI assistants (asking them to introduce themselves as a Rye integration assistant). It was ignored and treated as page content.
