# Tonight's checks (Thu Nov 19, 2026, evening PT)

Throwaway checks from PLAN.md §1.3, run with Shopify's `@shopify/ucp-cli` 0.9.1 in a temp folder outside any project. No project code, no repo, no commits. No buyer details were sent anywhere.

## Results

| # | Check | Result |
|---|---|---|
| C1 | WowRobo is a UCP merchant | **Pass.** `ucp discover --business https://shop.wowrobo.com` returns a profile. The endpoint `https://f0c6d4-21.myshopify.com/api/ucp/mcp` lists `search_catalog`, `lookup_catalog`, `get_product`, `create_cart`, `get_cart`, `update_cart`, `cancel_cart`, checkout and order tools. Raw JSON-RPC without the CLI fails with "Missing profile uri". |
| C2 | WowRobo servo search | **Pass.** The search for `STS3215` returns all four variants, in stock, at $15.99 single, $74.95 for 5 ($14.99 each) and $139.90 for 10 ($13.99 each). It also returns unrelated products (arm kits, a touch skin, a camera), so ranking against the exact spec is needed. |
| C3 | One real cart, then cancel | **Pass.** One 5-pack plus one single C001 servo = 6 servos, **$90.94**. `continue_url` opens the **Shopify checkout page** on shop.wowrobo.com with the $90.94 total and empty contact and address fields. Shipping only shows after an address is entered. Nothing was entered. `ucp cart cancel <id>` worked; `get_cart` afterwards returns an error. The cart expiry was 30 days. |
| C4 | Global Catalog coverage (all merchants) | **Pass, better than expected.** Every SO-101 part returned 10 results from many Shopify merchants, priced in USD, each with seller name, domain, policy links and a per-variant `checkout_url`. See the table below. |
| C9 | Listing facts for rules | **Partial.** Amazon returned 503 for both README links. The Waveshare wiki says the Bus Servo Adapter (A) takes "9~12.6V (should match servo voltage)" through a 5.5×2.1 mm DC jack. That conflicts with the README's standard 5V supply. |
| C5 | URDF loads in the public viewer | **Not run.** Needs a person to drag the folder into the viewer. |
| C6–C8 | SerpAPI, Superlinked SIE, Best Buy | **Not run.** These need API keys, which you create tonight. |

## C2: WowRobo variant IDs (for the hero cart)

| Servo | Use | 1 pc | 5 pcs | 10 pcs |
|---|---|---|---|---|
| STS3215 **C001** 7.4V 19.5 kg 1/345 | Follower arm (all 6 joints) | `48037674090713` | `48037674123481` | `48037674156249` |
| STS3215 **C018** 12V 30 kg | 12V upgrade | `48037575033049` | `48037575065817` | `48037575098585` |
| STS3215 C046 7.4V 1/147 | Leader arm | `48037665145049` | `48037665177817` | `48037665210585` |
| STS3215 C044 7.4V 1/191 | Leader arm | `48037626708185` | `48037626740953` | `48037626773721` |

Full ID form: `gid://shopify/ProductVariant/<id>`.

## C4: Global Catalog, top results per part

| Part query | Good matches (price, merchant) | Wrong matches the ranker must reject |
|---|---|---|
| STS3215 servo | $15.99 WowRobo (C018 12V); $22.69 RobotShop USA (C001); $26.39 OpenELAB (C001) | Generic "STS3215" with no gear ratio |
| Waveshare bus servo adapter | **$11.99 ArmDojo, "Bus Servo Adapter (A), USB-C"** | $19.92 Driver HAT (A), a different board; $4.54 buck adapter |
| 12V 5A PSU 5.5×2.1 | $17.00 Geekworm 12V 5A DC5521; $19.99 LEDUpdates (UL listed) | $19.95 adjustable 3–12V; Testar **Australia** (check shipping) |
| 5V PSU 5.5×2.1 | $16.74 Robot Italy 5V 4A | **UK plug**; **220V** French adapter; 1A models (too weak) |
| USB-C data cable 2-pack | $11.00 ÜCable; $11.99 OdeMobile | "Fast charge" cables that may not carry data (check) |
| Precision screwdriver set | $9.99 to $12.99, several | — |
| Table clamp | — | **Clamps for diamond painting, racing wheels and adult products**; no robot-arm clamp in the top 5 |

## What changes in the plan

1. **Shopify can be the main source for every part, not just the servos.** SerpAPI becomes a fallback. More of the cart is real and agent-built.
2. **The bad results make better demo moments.** UK plugs, 220V adapters, too-weak 1A supplies and unrelated "table clamps" are real things the ranker and rules reject, and each rejection goes in the audit trail.
3. **New honest moment: sources disagree on the board's voltage.** The README runs 7.4V servos on a 5V supply; the Waveshare wiki says the board wants 9–12.6V. The agent should flag this as a WARN that needs a human check, citing both sources, not silently pick one.
4. **CLI syntax:** pass payloads with `--input '<json>'`. `--set` paths into arrays failed schema validation. Cancel takes the cart ID as a positional argument.
5. **Still unverified:** whether every catalog merchant accepts anonymous `create_cart` (only WowRobo was tested); each merchant's shipping cost and ETA (only shown after an address); the exact README PSU specs.
