---
doc_id: store_policies
title: Store policies: action levels, what each hand-off can and cannot do
kind: doc
licence: our notes, from the store registry (backend/data/stores.json) and PLAN §3.16 / §12
---

# Store policies

What the agent may say about each store and each hand-off. The store registry (`data/stores.json`, owner B)
is the source of truth for levels and caveats; these rows are the citable wording.

## chunk: action_levels
- rules: none
- checked: Nov 19-20

Agent cart: the agent created a real cart at a Shopify store through its UCP API; it opens as the store's own
checkout. Prefilled cart: a link in the store's own published format; when the user opens it, the store adds
the items to the user's cart and may ask them to sign in. Product link: a link to the product page; the user
adds the item. Our Universal Cart is the cart of record for every item from every store. We never pay and no
real money moves.

## chunk: amazon_prefilled
- rules: none
- checked: Nov 19 (redirect to sign-in keeps the items); after sign-in [unverified]

Amazon's cart-add link asks the user to sign in first; the store, not us, adds the items. Our code never
requests amazon.com: the link is a string the user's browser opens. Prices for Amazon come only through SerpAPI.

## chunk: never_request
- rules: none
- checked: Nov 19

Never requested by our code or by any fetcher or search provider on our behalf: amazon.com, digikey.com (the
website; api.digikey.com is allowed), ebay.com, walmart.com, bestbuy.com, microcenter.com, octopart.com,
robotshop.com (main domain) and their regional sites. The list and its tests live in `stores/http.py`.

## chunk: us_only
- rules: R11, G1
- checked: Nov 19

Shopify results keep `ships_from` US and USD only. Listings in GBP, EUR or JPY, and power supplies with UK, EU or
AU plugs or 220-240 V-only input, are rejected and logged, never silently converted.

## chunk: no_affiliate_no_buyer_data
- rules: none

Cart links carry item ids and quantities only: no affiliate tag, no buyer name, email, phone or address. Buyer
fields are stripped from every agent action unless the mandate's `data_sharing` allows them, and each strip is a
refusal record.

## chunk: links_are_hints
- rules: none

Links inside a project's README (for example the SO-ARM100 README's Alibaba links) are hints, not offers. A store
outside the mandate's allowed merchants produces a refusal record; its listing is kept as evidence only.

## chunk: mock_and_test
- rules: none

Mock data carries `source_api: "mock"` and `simulated: true` and is shown with the "Mock data" badge. Stripe runs in
TEST MODE only: keys must start with sk_test_ / pk_test_, every Stripe object is checked for livemode false, and
the test payment is a person's UI action, never an agent tool.
