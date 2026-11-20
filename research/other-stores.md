# Non-Shopify stores for Build-to-Cart: what we can search and hand off tomorrow

Research and read-only checks run Thu Nov 19, 2026, about 8:00–8:45 PM PT. Nothing was signed up for, logged into, bought, or carted with cookies. No project code was written.

**Labels used below**
- **[checked]**: I ran the check tonight (curl, `ucp discover`, or a public JSON/GraphQL call) and saw the result.
- **[doc]**: the vendor's own docs or swagger say so (quoted).
- **[3rd-party]**: forum, blog, or search-result claim, not re-checked.
- **[unverified]**: not confirmed.

---

## 0. Headline findings

1. **None of the non-Shopify stores offer an agent-created cart that a human can open.** The only cart API is Mouser's, and that cart is bound to the API key owner's My Mouser account. I found no documented way to hand it to someone else.
2. **Four stores accept a prefilled multi-item cart URL with no API key. That is the best handoff available:**
   - **Digi-Key FastAdd** `https://www.digikey.com/classic/ordering/fastadd.aspx?part1=…&qty1=…&part2=…` **[checked]**: an anonymous GET returns `302 → /ordering/shoppingcart`.
   - **Best Buy click cart** `https://api.bestbuy.com/click/-/SKU1,SKU2/cart` **[checked]**: returns an "Adding to Cart…" page. Its script adds each SKU to the bestbuy.com cart, then redirects to `https://www.bestbuy.com/cart`. No API key needed; one unit per SKU.
   - **Amazon cart-add form** `https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=…&Quantity.1=…` **[checked]**: still works in 2026, but it now **redirects to Amazon sign-in** and then to `/associates/addtocart?ASIN.1=…` with the items kept.
   - **Walmart affiliate cart** `https://affil.walmart.com/cart/addToCart?items=ID|QTY` **[checked to the bot wall]**: returns `307 → https://www.walmart.com/affil/cart/addToCart?items=…`. Walmart's PerimeterX then sends curl to `/blocked`. A real browser should pass **[unverified]**.
3. **Three no-key search sources work tonight [checked]:**
   - **Adafruit**: the full catalog as JSON (5,592 products).
   - **SparkFun and Seeed Studio**: both run Magento 2, and anonymous GraphQL `products(search:…)` returns name, SKU, price, stock and URL key. One adapter covers both stores.
   - **DFRobot and Waveshare**: product pages carry schema.org JSON-LD with price and stock.
4. **Seeed Studio sells the hero servo**: "Feetech ST3215 C001 Servo 7.4V 1:345", **$20.00, IN_STOCK [checked]**. Waveshare sells the **Bus Servo Adapter (A) for $4.99, InStock [checked]**, which is less than half ArmDojo's $11.99. DFRobot sells the **FireBeetle 2 ESP32-E (DFR0654) for $8.90, InStock, rated 5.0 from 4 reviews [checked]**.
5. **Amazon, Walmart, eBay, Digi-Key, Mouser, Micro Center, RobotShop's www domain, Octopart and Best Buy's site all block curl or show a CAPTCHA [checked].** Search them only through an API or SerpAPI, never by scraping.
6. **Keys that are not realistic tonight:**
   - **Best Buy**: no longer issues keys to free email domains. Its blog says it "no longer takes new key requests if the email listed is from a free email service" **[doc, via Best Buy Developers blog on Medium; date not shown]**.
   - **eBay**: about 1 business day for approval, and many 2026 forum reports of automatic rejections **[3rd-party]**.
   - **Amazon Creators API**: "at least 10 qualifying sales within the past 30 days" **[doc]**.
   - **AliExpress affiliate API**: approval takes hours to days **[3rd-party]**.
   - **Arrow**: key goes through a sales rep, about 7+ days **[3rd-party]**.
   - **LCSC**: application plus an activation step **[doc + 3rd-party]**.
7. **Bonus Shopify UCP stores** (cart supported; usable with the CLI flow that already works): **The Pi Hut** (`thepihut.com`) and **Pimoroni** (`shop.pimoroni.com`) both return `dev.ucp.shopping.cart` **[checked]**. Both are UK stores that carry Waveshare e-paper panels, BME280 boards and LiPos. Check shipping to the US.

---

## 1. Checks run tonight (evidence)

| # | Check | Result |
|---|---|---|
| K1 | `ucp discover` on adafruit, sparkfun, pololu, seeedstudio, dfrobot, waveshare, makerfabs, good-display | All `HTTP 404 /.well-known/ucp`: **not Shopify UCP** |
| K2 | `ucp discover` on robotshop.com, microcenter.com, buyepaper.com | `HTTP 403` (Cloudflare). RobotShop is Shopify underneath (its myshopify domain already works). |
| K3 | `ucp discover` on lcsc.com, tindie.com, elecrow.com | Redirect or HTML instead of a profile: **not UCP** |
| K4 | `ucp discover` on thepihut.com, shop.pimoroni.com | **UCP profile with `dev.ucp.shopping.cart`** |
| K5 | Amazon `gp/aws/cart/add.html?ASIN.1=B087LY41PV&Quantity.1=1&ASIN.2=B0CTMM4LWK&Quantity.2=1` | `302 → /ap/signin?…openid.return_to=…/associates/addtocart?ASIN.1=…&Quantity.1=…&openid.assoc_handle=amzn_associates_add_to_cart_us&openid.pape.max_auth_age=3600`. The same happens with an `AssociateTag` (no tag is needed for the redirect). |
| K6 | Amazon `/dp/B0CTMM4LWK` and `/dp/B087LY41PV` | CAPTCHA page (3.7 KB) |
| K7 | Digi-Key FastAdd, 1 part, and 2 parts with `newcart=true` | `302 Location: /ordering/shoppingcart` and a session cookie, anonymously |
| K8 | Best Buy `api.bestbuy.com/click/-/6505727,6451330/cart` | 200 "Adding to Cart…". Its script calls `clickyAddToCart("https://www.bestbuy.com/cart?cmp=RMX", …, ["6505727","6451330"], …)` and posts `{skuId}` for each SKU to `/cart/api/v1/addToCart`. **There is no quantity field.** |
| K9 | Best Buy API with a dummy key | `{"errorCode":"403","errorMessage":"We were unable to validate your API Key."}`: the API is live. The docs still list `addToCartUrl: https://api.bestbuy.com/click/<id>/<sku>/cart` and "agree not to cache any content except on a temporary basis… response links will expire after seven days". |
| K10 | Walmart `affil.walmart.com/cart/addToCart?items=10450114|1` | `307 → www.walmart.com/affil/cart/addToCart?items=…`, then `/blocked` (PerimeterX) for curl. `/ip/<id>` is also blocked. |
| K11 | Adafruit `/api/product/2652` and `/api/products` | JSON with price, tiered `discount_pricing`, `product_stock`, URL and country of origin. Full catalog: 7.8 MB, 5,592 products. |
| K12 | Adafruit add-to-cart | A POST form to `/added` with a session-bound `securityToken`. GET `?action=add_product&pid=…` returns `302 → shopping_cart` with `cart_count=0`, so **no prefilled cart URL**. |
| K13 | SparkFun and Seeed `GET /graphql?query={products(search:"…"){…}}` | **200 with JSON**: name, SKU, `stock_status`, `final_price`, `url_key`. Deep link is `https://<host>/<url_key>.html` (200). |
| K14 | Waveshare product pages | Magento 1. JSON-LD Offer: Bus Servo Adapter (A) **$4.99 InStock**; 7.5" raw panel (WF0583CZ09) **$47.99 InStock**. The cart form needs `form_key`, so deep link only. |
| K15 | DFRobot product pages | JSON-LD Offer: FireBeetle 2 ESP32-E DFR0654 **$8.90 InStock**, rated 5.00 from 4 reviews; Gravity BME280 SEN0236 **$15 InStock**. Search URL pattern: `/search-{q}.html`. |
| K16 | Pololu product page | POST `/cart/add` with a `session_id` token, so deep link only |
| K17 | Mouser swagger `api.mouser.com/api/docs/v1` | Lists `POST /api/v{version}/cart/items/insert` ("Allows one or more part numbers to be added to the cart"; body `CartKey`, `CartItems[{MouserPartNumber, Quantity, CustomerPartNumber}]`; response has `CartKey`, `MerchandiseTotal`), plus `search/keyword` and `search/partnumber` (max 50 parts per call). mouser.com pages return "Access to this page has been denied" to curl. |
| K18 | Bot walls | 403 or challenge: digikey.com, robotshop.com, microcenter.com, ebay.com (home and search), octopart.com, buyepaper.com. Timeout: bestbuy.com, arrow.com. Redirect: aliexpress.us search. |

---

## 2. Store-by-store

### 2.1 SerpAPI (aggregator: Google Shopping, Immersive Product, Amazon, Walmart, eBay, Home Depot)
- **Search/price data:** One key covers these engines. Doc pages exist for `google_shopping`, `google_immersive_product`, `amazon`, `amazon-product`, `walmart`, `ebay`, `home_depot` and `google_shopping_light`. **There is no Best Buy or AliExpress engine** (404) **[checked]**.
  - `google_shopping` fields: `title`, `source` (merchant), `price`/`extracted_price`, `rating`, `reviews`, `delivery`, `product_link` (a google.com link in the sample), `immersive_product_page_token`, `multiple_sources` **[doc]**. Each request returns about 40 items; `start` is ignored **[doc]**.
  - `google_immersive_product` `stores[]` fields: `name`, `link` (the sample links straight to Walmart's product page), `price`, `shipping`/`shipping_extracted`, `total`/`extracted_total`, `rating`, `reviews`, `details_and_offers` (e.g., "In stock online") **[doc]**. This is the best fit for the "click a part → every store's offer" panel.
  - `amazon` fields: `asin`, `title`, `link`, `rating`, `reviews`, `price`/`extracted_price`, `delivery` **[doc]**.
  - `walmart` fields: `us_item_id`, `primary_offer.offer_price`, `rating`, `reviews`, `seller_name`, `free_shipping`/`two_day_shipping`, `out_of_stock`, `product_page_url` **[doc]**.
  - `ebay` fields: `link`, `product_id` (the item ID), `price.{from,to}.extracted`, `shipping`, `condition`, `seller.{username,reviews,positive_feedback_in_percentage}` **[doc]**.
- **Key tonight:** Yes, self-serve at serpapi.com/users/sign_up. Email and phone verification is likely **[3rd-party / unverified]**.
- **Free tier:** **250 searches/month, 50/hour**. Cached searches don't count. The free plan has no "U.S. Legal Shield" **[doc, pricing page]**.
- **Cart action:** deep links. **But SerpAPI hands us the IDs that the prefilled cart URLs need**: ASIN for Amazon, `us_item_id` for Walmart, and the Best Buy SKU from a bestbuy.com store link (`…/<sku>.p`) **[format unverified]**.
- **ToS/risk:** SerpAPI does the scraping, and the free plan has no legal shield. Label prices "via SerpAPI". Quota is the real risk: cache every response from the first call.
- **Coverage:** should find every demo part on Amazon, Walmart and eBay, and Google Shopping adds Best Buy, AliExpress and small shops **[unverified until the key exists]**.
- **Minutes:** 45–60 for all engines behind one `search(part, engines[])`.
- **Returns:** `Offer{store, title, price, shipping, total, delivery_text, rating, reviews, stock_text, url, ids:{asin|walmart_id|ebay_item|bestbuy_sku}, source_api:"serpapi:<engine>", seen_at}`.

### 2.2 Amazon
- **Search:** Creators API (it replaced PA-API 5) requires an approved Associates account and "at least 10 qualifying sales within the past 30 days" **[doc]**, so **no for tonight**. Product pages show curl a CAPTCHA **[checked]**. **Use SerpAPI `amazon`.**
- **Cart action: prefilled multi-item cart URL, gated by sign-in [checked].** Build `https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=<a>&Quantity.1=<n>&ASIN.2=…`. Amazon redirects to sign-in with `max_auth_age=3600`, so a user who hasn't signed in within the last hour is likely asked to sign in **[inference]**. Amazon then continues to `/associates/addtocart?…`. Whether that page adds silently or shows a confirm button is **[unverified]** because it needs a login. The Creators API docs list no cart operation **[doc]**.
- **ToS/risk:** Amazon's terms forbid robots and scraping **[general knowledge]**, which the CAPTCHA reinforces. An affiliate tag is **not required** for the cart URL; I saw the same redirect without one **[checked]**. Never invent a tag.
- **Coverage:** the SO-101 README sources the board (B0CTMM4LWK), PSU (B087LY41PV), USB-C cables, clamps and screwdriver from Amazon. Servos, FireBeetle, e-paper, DESPI-C02, BME280 and LiPo are all likely listed **[unverified]**.
- **Minutes:** 10 for the URL builder on top of the SerpAPI adapter.
- **Returns:** `{merchant:"amazon.com", kind:"prefilled_cart_url", url, caveat:"Amazon asks you to sign in first"}`.

### 2.3 Digi-Key
- **Search:** Product Information v4 (KeywordSearch, ProductDetails), OAuth2. A Digi-Key forum post (Oct 2025) says "anyone can register and start immediately at a rate limit of 1000 calls per day without any additional approvals" **[3rd-party; author's role not stated]**. Developer docs: 120/min and 1,000/day for Product Information **[doc via search]**. Sandbox apps can only call sandbox endpoints, so register a **production** app **[doc]**.
- **Key tonight:** Yes, but a person must create a DigiKey account and app.
- **Fields:** price breaks, quantity available, lead time, Digi-Key part number, product URL **[doc]**.
- **Cart action: prefilled multi-item cart URL (FastAdd) [checked].** `https://www.digikey.com/classic/ordering/fastadd.aspx?part1=1738-DFR0654-ND&qty1=1&part2=…&qty2=…&newcart=true&utm_source=build-to-cart`. Per the post: "max safe character count of the URL is around 1700 characters". `cref1..n` sets line notes. POST is also accepted. There is **no direct Cart API**. The MyLists API (OAuth) and a keyless "MyLists Third Party API" that returns a `singleUseUrl` exist **[3rd-party; the post now 404s]**.
- **ToS/risk:** Low. FastAdd is meant for third-party tools. The site blocks curl (Cloudflare); the API does not.
- **Coverage:** ESP32 demo strong:
  - FireBeetle **1738-DFR0654-ND** and 1738-DFR0654-F-ND **[3rd-party search results; US stock unverified]**.
  - BME280 and LiPo breakouts from the Adafruit and SparkFun lines **[unverified PNs]**.
  - PSUs, cables and screwdrivers **[unverified]**.

  SO-101 weak: no STS3215 or Waveshare adapter found. Digi-Key carries Seeed's *XIAO Bus Servo Adapter* 114993612, which is a different board.
- **Minutes:** 60–90, of which the OAuth2 client-credentials token is about 20.
- **Returns:** Offers with `DigiKeyProductNumber`, `UnitPrice` breaks, `QuantityAvailable`, `ProductUrl`, plus one FastAdd URL per plan.

### 2.4 Adafruit
- **Search:** `https://www.adafruit.com/api/products` (all products) and `/api/product/{id}` **[checked]**. No key. Undocumented; the ToS was not checked.
- **Fields:** `product_price`, `discount_pricing` (1–9, 10–99, 100+ tiers), `product_stock` ("in stock", a count, 0 or a negative number), `product_url`, `product_mpn`, shipping weight, `products_coo`. No rating, shipping cost or ETA.
- **Cart action: deep link only [checked].** The form POSTs to `/added` with a session `securityToken`, and the GET variant adds nothing.
- **Coverage [checked]:**
  - In stock: BME280 2652 $14.95; LiPo 1578 500 mAh $7.95 and 2011 2000 mAh $12.50; 5V 4A PSU 1466 $14.95; 38 USB-C cables.
  - Out of stock (stock 0): 12V 5A PSU 352 $24.95; 7.5" 800×480 bare e-paper 6396 $59.95; eInk Breakout Friend 4224 $8.50, a possible substitute for DESPI-C02.
  - Not carried: STS3215 and Waveshare adapter.
- **Minutes:** 20–30. Download once, cache, and fuzzy-match locally.
- **Returns:** Offers with tier prices and stock; deep links.

### 2.5 Seeed Studio
- **Search:** Magento 2 GraphQL `https://www.seeedstudio.com/graphql` **[checked]**. No key. Fields: name, sku, `stock_status`, `price_range.minimum_price.final_price`, `url_key`. You can also request `rating_summary` **[unverified]**.
- **Cart action: deep link** `https://www.seeedstudio.com/<url_key>.html` **[checked 200]**. Magento guest carts made through GraphQL live on our server and can't be handed to the user's browser.
- **Coverage [checked]:**
  - In stock: **Feetech ST3215 C001 7.4V 1:345 $20 (SKU 108090023)**; C047 12V $22; SO-ARM101 kits; Grove BME280 $18.70; 12V 2A US PSU $7 (too weak, a good reject).
  - Wrong board for the demo: its own XIAO bus servo boards.
  - Not found: FireBeetle.
  - Mostly out of stock: LiPo and screwdrivers.
- **Minutes:** 30–40, shared with SparkFun.

### 2.6 SparkFun
- **Search:** same Magento 2 GraphQL at `https://www.sparkfun.com/graphql` **[checked]**.
- **Cart action:** deep link `https://www.sparkfun.com/<url_key>.html` **[checked 200]**. The Magento cart needs `form_key`.
- **Coverage [checked]:**
  - BME280: SEN-15440 Qwiic $16.95; SEN-13676 $25.50.
  - LiPo: PRT-13854 850 mAh $13.61, JST-PH on SparkFun LiPos **[unverified per item]**.
  - USB-C cable: CAB-29262 1 m $10.95.
  - Screwdrivers: TOL-25565 iFixit Marlin set $21.95; TOL-12891 pocket set $5.50.
  - PSUs: only TOL-15312 5V 2A and TOL-15313 12V 600 mA, both too weak, which makes good reject moments.
  - Not found: STS3215, FireBeetle.
  - Only e-ink item: TRMNL.
- **Minutes:** included in 2.5.

### 2.7 Best Buy
- **Search:** Products API, but **new keys need a company email** **[doc, via the Best Buy Developers blog]**. Fields if you have a key: `salePrice`, `onlineAvailability`, `shippingCost`, `customerReviewAverage`, `addToCartUrl` **[doc]**. Otherwise get Best Buy offers from SerpAPI Google Shopping or Immersive Product.
- **Cart action: prefilled multi-SKU cart URL with no key [checked]:** `https://api.bestbuy.com/click/-/<sku1>,<sku2>/cart`. Each SKU is added once. Repeating a SKU might add a second unit **[unverified]**. It must run in the user's browser; the cart is on bestbuy.com, the same site as api.bestbuy.com.
- **ToS/risk:** The API terms forbid caching beyond temporary use and links expire after 7 days **[doc]**. The keyless `-` form is undocumented and could stop working **[risk]**.
- **Coverage:** USB-C cables, screwdriver kits and maybe PSUs. No servos, e-paper or sensors **[unverified]**.
- **Minutes:** 10 for the URL; SKU extraction rides on SerpAPI.

### 2.8 Walmart
- **Search:** the affiliate Content Provider API is gated and selective, and read-only **[3rd-party]**. **Use SerpAPI `walmart`.**
- **Cart action: prefilled cart URL, partly checked.** `https://affil.walmart.com/cart/addToCart?items=<id>|<qty>` redirects to `www.walmart.com/affil/cart/addToCart`. A multi-item comma form (`items=ID|1,ID2|2`) keeps its parameters through the redirect **[checked]**, but what the cart does with it is **[unverified]**. Walmart blocks curl.
- **ToS/risk:** heavy bot detection (PerimeterX). Deep links and cart links are fine in a real browser.
- **Coverage:** PSUs, cables, screwdrivers, clamps; marketplace sellers for servos and e-paper **[unverified]**.
- **Minutes:** 10 on top of SerpAPI.

### 2.9 DFRobot store
- **Search:** HTML `https://www.dfrobot.com/search-{q}.html` lists `/product-NNNN.html` links. Product pages carry a JSON-LD Offer with `price`, `availability`, `aggregateRating`, `sku` and `shippingDetails.weight` **[checked]**. No API.
- **Cart action:** deep link.
- **Coverage [checked]:** FireBeetle 2 ESP32-E DFR0654 $8.90 InStock, rated 5.0 (4); Gravity BME280 SEN0236 $15 InStock. No 7.5" e-paper; its e-ink displays are 2.13" and 4.7". LiPo with PH2.0 not found in search **[unverified]**.
- **Minutes:** 30–40 (search page, then product page, then JSON-LD).

### 2.10 Waveshare store
- **Search:** HTML `https://www.waveshare.com/catalogsearch/result/?q=…` (`h2.product-name a`), then the product page's JSON-LD Offer **[checked]**. Pages with many variants (ST3215) have no JSON-LD offer; their prices show only in HTML ($16.99–$21.99).
- **Cart action:** deep link. The cart needs `form_key`.
- **Coverage [checked]:**
  - **Bus Servo Adapter (A) $4.99 InStock.**
  - **7.5" 800×480 raw panel $47.99 InStock**, with tiers $46.39, $45.59 and $45.27.
  - ST3215 servo: Waveshare's branding; how it maps to Feetech C001 needs a human check.
  - BME280 module; USB-C cables.
  - None found: 12V 5A PSU, screwdriver, FireBeetle.
- **Minutes:** 30–40. You can share a "JSON-LD product page" helper with DFRobot.

### 2.11 eBay
- **Search:** Browse API, 5,000 calls/day **[doc]**. Account approval takes "approximately 1 business day" **[doc]**, and many 2026 forum threads report automatic rejections **[3rd-party]**. **Use SerpAPI `ebay`.**
- **Cart action:** deep link `https://www.ebay.com/itm/<id>`. I found no cart URL. An eBay Partner Network tag is optional.
- **Coverage:** probably every part, including STS3215 and DESPI-C02 **[unverified]**.
- **Minutes:** 0 extra (comes with the SerpAPI adapter).

### 2.12 Mouser
- **Search:** Search API (keyword and part number, max 50 results per call). Up to 30 calls/minute and 1,000/day **[doc via search]**. The key requires a My Mouser account and a request form. Reports differ on whether it arrives instantly or in 1–2 business days **[3rd-party]**.
- **Cart action: agent-created cart via API, but not one a human can be handed [checked swagger].** `POST /api/v1/cart/items/insert` with an empty `CartKey` creates a cart and returns `CartKey` and `MerchandiseTotal`. Every call needs an `apiKey` tied to a My Mouser account. I found **no documented browser URL** for an API cart, and community projects list "does it show in the website basket after login?" as an open question **[3rd-party]**. The fallback is Mouser's Price & Availability Assistant, which accepts pasted `PN|qty` lines **[doc]**.
- **Coverage:** FireBeetle (426-DFR0654 and -F) **[3rd-party]**, Adafruit and SparkFun breakouts **[unverified]**. No STS3215 or Waveshare.
- **Minutes:** 60–90. **Skip for the demo.** At most, show the cart total from the API next to a deep link.

### 2.13 Nexar / Octopart
- **Search:** GraphQL `supSearch` / `supSearchMpn` returns many distributors per part number. The free Evaluation plan is "up to 1,000 matched parts" (business email) or 100 (personal email), lifetime, not monthly **[doc, but the numbers conflict across Nexar pages]**. octopart.com blocks curl **[checked]**.
- **Cart action:** deep links (Octopart click URLs) to each distributor.
- **Coverage:** good for the ESP32 demo's MPNs (DFR0654, ADA2652); poor for generic SO-101 items.
- **Minutes:** 45–60. **Use for one "hero" lookup at most.**

### 2.14 AliExpress
- **Search:** affiliate API (`aliexpress.affiliate.product.query`, HMAC-signed) after Open Platform and affiliate approval, which takes hours to days **[3rd-party]**. SerpAPI has no AliExpress engine **[checked 404]**. Google Shopping sometimes lists AliExpress. Search redirects for curl **[checked]**.
- **Cart action:** deep link `https://www.aliexpress.us/item/<id>.html`.
- **Coverage:** probably everything, including STS3215, DESPI-C02 and generic BME280 or LiPo **[unverified]**. Shipping time is the catch.
- **Recommendation:** skip.

### 2.15 LCSC
- **Search:** partner API (key plus nonce plus timestamp) after an application at lcsc.com/agent. New keys may only work on the test API until LCSC activates them **[doc + 3rd-party]**. No prefilled cart URL found; BOM upload only.
- **Coverage:** weak. Waveshare BME280 module C431940 is out of stock **[3rd-party]**; no FireBeetle or 7.5" panel found.
- **Recommendation:** skip.

### 2.16 Newark / Farnell (element14)
- **Search:** Product Search API. "Register on our Partner Portal and then apply for an API key" **[doc, checked page]**. Rate limits **[unverified]**.
- **Cart action:** deep link; BOM upload **[unverified]**.
- **Coverage:** weak for these demos **[unverified]**.
- **Recommendation:** skip.

### 2.17 Arrow
- **Search:** the Pricing & Availability API key goes through a sales rep, about 7+ days. Its terms forbid caching beyond 48 hours **[3rd-party + doc terms]**.
- **Recommendation:** skip.

### 2.18 Micro Center
- No API. Cloudflare returns 403 **[checked]**. In-store pickup is the draw.
- **Cart action:** deep link only.
- **Recommendation:** skip.

### 2.19 Pololu
- No public API. The cart form carries a session token **[checked]**.
- **Coverage:** little overlap with these demos **[mostly unverified]**.
- **Recommendation:** skip.

### 2.20 RobotShop (non-Shopify parts)
- None worth building. www.robotshop.com is Shopify behind Cloudflare: `.well-known/ucp`, product `.js` and `/cart/<v>:<q>` all return 403 to curl **[checked]**.
- Keep using the myshopify domain through UCP. It lists the Waveshare 7.5" raw panel and FeeTech STS3215 (12V C018) **[3rd-party search results]**.

### 2.21 Google Shopping alternatives (if SerpAPI signup fails)
- **Serper.dev** `/shopping`: about 2,500 free queries one time, no card **[3rd-party]**.
- **SearchApi.io**: `google_shopping` and `google_product_offers` engines, about 100 free requests **[3rd-party]**.
- **DataForSEO** Merchant API: $1 free credit **[doc via search]**.

Serper is the best backup: a single POST with an `X-API-KEY` header, about 30 minutes.

---

## 3. Ranked table

| # | Store | Search source | Key tonight? | Cart action | Demo-part coverage (SO-101 / ESP32) | Min | Risk | Recommendation |
|---|---|---|---|---|---|---|---|---|
| 1 | **SerpAPI** (Google Shopping, Immersive, Amazon, Walmart, eBay, Home Depot) | Official SerpAPI JSON | **Yes**, self-serve; phone verification likely [unverified] | Deep links, plus the IDs for rows 2, 6 and 7 | Broad (all parts likely) [unverified until key] | 45–60 | 250/mo, 50/hr quota; scraping-based; no legal shield on free plan | **Build first.** Cache everything. |
| 2 | **Amazon** | SerpAPI `amazon` (Creators API needs 10 sales/30 days) | Via SerpAPI | **Prefilled cart URL** (sign-in first) [checked] | README sources 6 of 7 SO-101 lines; ESP32 likely | +10 | Robots banned (CAPTCHA seen); no tag needed | **Build** (URL builder) |
| 3 | **Digi-Key** | Product Info v4 API | **Yes**, needs a DigiKey account; 1,000/day | **Prefilled cart URL (FastAdd)** [checked 302 to cart] | SO-101 weak (PSU, cable, tools); ESP32 strong (FireBeetle 1738-DFR0654-ND) | 60–90 | Low | **Build** if someone registers tonight |
| 4 | **Adafruit** | Public catalog JSON | **No key** | Deep link | SO-101: 5V 4A PSU, cables (12V 5A out of stock); ESP32: BME280, LiPo (e-paper out of stock) | 20–30 | Undocumented endpoint | **Build** (cheap, real stock) |
| 5 | **Seeed Studio** | Magento GraphQL [checked] | **No key** | Deep link | **STS3215 C001 $20 in stock**, SO-ARM101 kits; Grove BME280 | 30–40 (with #6) | Unofficial use of storefront API | **Build** (one adapter for #5 and #6) |
| 6 | **SparkFun** | Magento GraphQL [checked] | **No key** | Deep link | Cables, screwdrivers, weak PSUs (rejects); BME280, LiPo | (shared) | Same as #5 | **Build** with #5 |
| 7 | **Best Buy** | SerpAPI (API key needs company email) | No (API); **not needed for cart** | **Prefilled multi-SKU cart URL, no key** [checked] | Cables, screwdriver kits; no maker parts | +10 | Undocumented keyless form; quantity 1 per SKU | **Build** (URL builder, SKUs via SerpAPI) |
| 8 | **Walmart** | SerpAPI `walmart` | Via SerpAPI | **Prefilled cart URL** (redirect checked; final page unverified) | PSUs, cables, tools, clamps | +10 | PerimeterX; format partly unverified | **Build** (URL builder), test in a browser at 11:00 |
| 9 | **DFRobot** | JSON-LD on product pages [checked] | **No key** | Deep link | ESP32: **FireBeetle $8.90**, BME280 $15 | 30–40 | HTML scraping, low volume | **Stretch** (brand-direct price) |
| 10 | **Waveshare** | Search HTML + JSON-LD [checked] | **No key** | Deep link | **Bus Servo Adapter (A) $4.99**, ST3215; **7.5" panel $47.99**, BME280 | 30–40 (shared helper with #9) | HTML scraping | **Stretch** with #9 |
| 11 | eBay | SerpAPI `ebay` (Browse API: ~1 business day approval, auto-rejections) | Via SerpAPI | Deep link | Likely all [unverified] | 0 | Used/auction listings | Comes free with #1 |
| 12 | Mouser | Search API | Maybe (form; instant or 1–2 days) | Agent cart via API, **account-bound, no handoff URL** | ESP32 partial (426-DFR0654) | 60–90 | Cart can't be handed to user | Skip |
| 13 | Nexar/Octopart | GraphQL | Yes (account); 100–1,000 parts lifetime | Deep links | ESP32 MPNs only | 45–60 | Tiny quota | Skip (one hero lookup at most) |
| 14 | AliExpress | Affiliate API (approval) | No | Deep link | Likely all [unverified] | 60+ | Approval; slow shipping | Skip |
| 15 | LCSC | Partner API (apply plus activate) | No | BOM upload | Weak | 60+ | Approval | Skip |
| 16 | Newark/Farnell | element14 API (apply) | Unknown | Deep link | Weak [unverified] | 60 | Approval | Skip |
| 17 | Micro Center | None (403) | — | Deep link | Cables, tools [unverified] | — | Bot wall | Skip |
| 18 | Pololu | None | — | Deep link | Little overlap | — | — | Skip |
| 19 | Arrow | API via sales rep (7+ days) | No | Deep link | Weak | — | 48 h cache limit | Skip |
| — | RobotShop www | (Shopify; use myshopify UCP) | — | UCP cart (existing) | — | 0 | Cloudflare on www | Already covered |
| — | The Pi Hut, Pimoroni | **Shopify UCP** [checked] | No key | **Agent cart (UCP)** | e-paper panels, BME280, LiPo (UK shipping) | 5 | Ships from UK | Add to UCP merchant list if useful |

---

## 4. Recommended non-Shopify adapter set for a team of 4 (in build order)

All adapters return the same `Offer` shape already in the plan (`store, title, price, shipping, total, stock, rating, reviews, url, ids, source_api, seen_at`). Handoffs return `{merchant, kind: "agent_cart" | "prefilled_cart_url" | "deep_link", url, caveat}`.

| Order | Adapter | Owner | Min | Why |
|---|---|---|---|---|
| 1 | **SerpAPI** (`google_shopping`, `google_immersive_product`, `amazon`, `walmart`, `ebay`; `home_depot` for the table clamp) | Stores person (B) | 60 | One key reaches Amazon, Walmart, eBay, Best Buy and many small shops. Immersive Product fills the per-part "every store" panel. |
| 2 | **Cart-link builder**: Amazon `cart/add.html`, Best Buy `click/-/SKUs/cart`, Walmart `affil…/addToCart?items=`, Digi-Key FastAdd | B | 30–40 | Turns the cart for non-Shopify stores from deep links into prefilled carts. No keys. Test each in a real browser at 11:00 and fall back to deep links per store. |
| 3 | **Adafruit catalog JSON** | Any free person | 25 | No key, real stock and price tiers. Covers BME280, LiPo, PSUs and cables, and gives out-of-stock rejects. |
| 4 | **Magento GraphQL** for **Seeed and SparkFun** | Same person | 35 | No key. Seeed is a second real source for the hero servo ($20 vs WowRobo's $15.99). SparkFun supplies "too weak PSU" rejects for the rules engine. |
| 5 | **Digi-Key v4 + FastAdd** | B, after 1–2 | 75 | Only if someone registers the app tonight. Gives the ESP32 demo a real distributor cart URL. |
| 6 | **Brand-direct JSON-LD** for **DFRobot and Waveshare** | Stretch | 45 | Cheapest prices for the FireBeetle ($8.90) and Bus Servo Adapter (A) ($4.99). Each brand's own listing confirms the part identity. |

**Skip:** Mouser, eBay API, AliExpress API, Best Buy API, Amazon Creators API, Nexar (beyond one lookup), LCSC, Arrow, Newark, Micro Center, Pololu.

**Do tonight (a person, not the app):**
- **SerpAPI:** sign up and spend at most 10 test searches.
- **Digi-Key:** register a production app (client ID and secret).
- **Optional: Serper.dev** backup key.

Don't bother with Best Buy (free email refused), eBay (approval), Amazon Creators (sales threshold), Arrow or LCSC.

**Quota math for SerpAPI:** 12 BOM lines × 2 engines = 24 searches, plus about 10 Immersive lookups for hero parts, comes to about 35 of the 250 per month. Record every response to disk on the first call and replay from cache during development and the demo.

**Compatibility "reject" moments found tonight** (good audit-trail material):
- SparkFun 12V 600 mA and 5V 2A supplies, and Seeed 12V 2A: under the 5A spec.
- Adafruit 5V 4A: 4A, not 5A, so WARN.
- Adafruit 12V 5A and 7.5" bare panel: out of stock.
- Seeed's own bus servo boards: not the Waveshare (A) board.
- Waveshare's "ST3215" naming vs Feetech "STS3215 C001": needs a human check.
- Waveshare (A) board input is 9–12.6 V (from an earlier check).
- JST-PH LiPo polarity differs between vendors: WARN.

---

## 5. Where each demo part can be bought

Codes:
- **V**: price and stock verified tonight.
- **L**: listed in a doc or search result; price or stock not re-checked.
- **U**: Shopify UCP result from the Nov 19 checks.
- **?**: probably carried; confirm with SerpAPI tomorrow.
- **X**: searched, not found, or the wrong spec.
- **—**: not checked or not relevant.

### 5.1 SO-101 arm

| Part | Shopify UCP (existing) | Seeed | Waveshare | Adafruit | SparkFun | Digi-Key | Mouser | Amazon | Walmart / eBay / AliExpress | Best Buy |
|---|---|---|---|---|---|---|---|---|---|---|
| Feetech STS3215 C001 7.4V (×6) | **U** WowRobo $15.99 (5-pack $74.95); RobotShop $22.69; OpenELAB $26.39 | **V $20.00 in stock** (108090023) | L ST3215 $16.99–$21.99 (variant needs a check) | X | X | X | X | ? | ? / ? / ? | X |
| Waveshare Bus Servo Adapter (A) | **U** ArmDojo $11.99 | X (own XIAO boards only) | **V $4.99 InStock** | X | X | X (Seeed XIAO adapter only) | — | L B0CTMM4LWK (README; CAPTCHA blocked price) | ? | X |
| 5V PSU 5.5×2.1 (5A) | **U** Robot Italy 5V 4A $16.74 (WARN 4A) | — | — | **V** 1466 5V 4A $14.95 (WARN 4A) | **V** TOL-15312 5V 2A $9.50 (X too weak) | ? | ? | L B087LY41PV (README) | ? | ? |
| 12V 5A PSU 5.5×2.1 | **U** Geekworm $17.00; LEDUpdates $19.99 | **V** 12V 2A $7 (X too weak) | X | **V** 352 $24.95, **out of stock** | **V** TOL-15313 12V 0.6A (X) | ? | ? | ? | ? | ? |
| USB-C data cable | **U** ÜCable $11.00; OdeMobile $11.99 | **V** (several) | **V** (several) | **V** 38 listings, e.g., 6370 $6.95 | **V** CAB-29262 1 m $10.95 | ? | ? | L (README) | ? | ? |
| Table clamp | U junk results only | — | — | **V** 2456 toggle clamp $3.95 (likely X: not a bench clamp) | — | — | — | L (README) | ? (Home Depot via SerpAPI too) | X |
| Precision screwdriver set | **U** $9.99–$12.99 | V (mostly out of stock) | X | V (singles, mostly out of stock) | **V** TOL-25565 iFixit $21.95; TOL-12891 $5.50 | ? | ? | L (README) | ? | ? |

### 5.2 ESP32 weather display

| Part | Shopify UCP | DFRobot | Waveshare | Adafruit | SparkFun | Seeed | Digi-Key | Mouser | Amazon / AliExpress / eBay |
|---|---|---|---|---|---|---|---|---|---|
| DFRobot FireBeetle 2 ESP32-E | ? (RobotShop likely) | **V DFR0654 $8.90 InStock, 5.0 (4)** | X | X | X | X | **L 1738-DFR0654-ND** (US stock unverified) | L 426-DFR0654-F | ? |
| Waveshare 7.5" 800×480 e-paper panel | L RobotShop raw panel; L OpenELAB; L The Pi Hut (UCP store) | X | **V $47.99 InStock** (WF0583CZ09) | **V** 6396 $59.95, **out of stock** | X (TRMNL only) | X (only 7.3"/7.5" kits) | X | X | ? |
| DESPI-C02 adapter | **L OpenELAB $10.00** (UCP store; run a catalog search) | X | X (substitute: e-Paper Driver HAT) | substitute: 4224 eInk Breakout Friend, out of stock | X | X | X | X | ? (Good Display sells on its own site; buyepaper.com blocked) |
| BME280 sensor | ? | **V SEN0236 $15 InStock** | L module (price not read) | **V 2652 $14.95 in stock** (10+ $13.46) | **V SEN-15440 $16.95** / SEN-13676 $25.50 | **V Grove $18.70** | ? (Adafruit/SparkFun lines) | ? | ? (generic GY-BME280; check 3.3V vs 5V) |
| 3.7V LiPo with JST-PH 2.0 | ? (The Pi Hut, Pimoroni likely) | ? (not found in search) | — | **V 1578 500 mAh $7.95; 2011 2000 mAh $12.50** | **V PRT-13854 850 mAh $13.61** | V (mostly out of stock) | ? | ? | ? (WARN: polarity varies) |

**Cheapest real multi-store cart from tonight's numbers, without SerpAPI:**

| Demo | Store and items | Price |
|---|---|---|
| ESP32 | DFRobot: FireBeetle | $8.90 |
| | Waveshare: 7.5" panel | $47.99 |
| | OpenELAB (UCP): DESPI-C02 | $10.00 |
| | Adafruit: BME280 and 500 mAh LiPo | $14.95 + $7.95 |
| | **Total** | **≈ $89.79 + shipping** |
| SO-101 | WowRobo (UCP): servos | |
| | Waveshare: adapter | $4.99 (vs ArmDojo $11.99) |
| | Adafruit or Geekworm: PSUs | |
| | SparkFun: cable and screwdriver | |

Only the UCP stores give an agent cart; the others are deep links.

---

## Sources

- Digi-Key FastAdd guide (forum, Oct 2025): https://forum.digikey.com/t/digikey-fastadd-bulk-add-parts-into-a-digikey-cart-via-third-party-tooling-and-urls/61356 (raw text read at `/raw/61356`)
- Digi-Key developer FAQ: https://developer.digikey.com/faq/products-plans-and-apis
- Mouser API swagger: https://api.mouser.com/api/docs/v1 · Cart API page: https://www.mouser.com/api-cart/ · Search API page: https://www.mouser.com/api-search/
- Mouser Cart API handoff question: https://github.com/TimsenDK/retro-recaps/issues/11
- Best Buy API docs: https://bestbuyapis.github.io/api-documentation/ · Key policy change: https://medium.com/best-buy-developers/announcing-a-change-to-best-buy-s-api-access-b09afc4bc27a
- SerpAPI pricing: https://serpapi.com/pricing · Engines: https://serpapi.com/google-shopping-api, https://serpapi.com/google-immersive-product-api, https://serpapi.com/amazon-search-api, https://serpapi.com/walmart-search-api, https://serpapi.com/ebay-search-api
- Amazon Creators API intro: https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction
- eBay API call limits: https://developer.ebay.com/develop/api/buy/api_call_limits · Getting started: https://developer.ebay.com/develop/guides/get-started-with-ebay-apis
- Nexar part limits: https://support.nexar.com/support/solutions/articles/101000476314-part-limits-and-how-they-work
- LCSC API: https://www.lcsc.com/docs/openapi/index.html · https://www.lcsc.com/agent
- element14 Partner Portal: https://partner.element14.com/
- Arrow API terms: https://developers.arrow.com/api/index.php/site/page?view=terms
- Walmart (3rd-party summary of the affiliate API): https://www.zinc.com/blog/walmart-api
- DESPI-C02 at OpenELAB: https://openelab.io/products/24-pin-serial-e-paper-screen-hat-adapter-board
- DFR0654 at Digi-Key: https://www.digikey.com/en/products/detail/dfrobot/DFR0654/13978504

Raw check outputs (temporary, may be cleared): `C:\Users\ptula\AppData\Local\Temp\claude\fe68aa92e0ea2987\80ff7711-1f2f-4184-b887-c493cf3cb5c4\scratchpad\stores\` and `…\scratchpad\ucp-check\discover\`.
