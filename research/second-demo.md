# Second demo: electronics-only project

Researched Thu Nov 19, 2026 (evening, the day before the hackathon). Everything below was fetched or run today unless it is marked **[unverified]**. Prices are from the Shopify global catalog via `npx ucp` 0.9.1 and will drift.

## 1. Chosen project and why

**Chosen: ESP32 E-Paper Weather Display, `lmarzen/esp32-weather-epd`**
- Repo: https://github.com/lmarzen/esp32-weather-epd. 6,359 stars, 487 forks. GPL-3.0. Last push and last README commit Jul 22, 2026 (`c78ad15`, "Added support for the GDEP073E01 7 color spectra 6 panel. (#230)").
- It is a battery-powered Wi-Fi e-paper weather station made only of off-the-shelf electronics: an ESP32 dev board, a 7.5" e-paper panel, an adapter board, a BME280 sensor, a LiPo battery and jumper wires. The enclosure is optional (DIY wood, picture frame or community 3D prints), so no 3D model is needed.
- The parts list is a markdown table in the README (6 rows, L54–L61), plus an "Other items needed" list (L63–L67). That gives 8 buyable lines, 2 tools the user owns, and 1 optional enclosure.
- Its rules differ from the arm's servo-voltage rule. The best one for the stage is the battery: a single-cell 3.7–4.2 V Li-ion with a **JST-PH 2.0 mm** 2-pin plug. Today's catalog has cheap, well-ranked batteries that fail it: 1.25 mm plugs, 3-pin PH plugs, 2S 7.4 V packs, and a listing whose title says "JST" while its description says PH1.25. Some of these come from the same stores that sell the correct battery.
- Every part has at least one USD offer from a US-origin Shopify store. The cart covers 3 stores, all confirmed UCP stores.

**Runner-up: Corne Cherry v4 keyboard, `foostan/crkbd`**, build guide `docs/corne-cherry/v4/buildguide_en.md`
- 7,763 stars. CC-BY-4.0 for hardware (the repo also has a LICENSE_MIT file). Last push Nov 14, 2026.
- It has the best table: a `Count` column, 10 required lines and 1 optional line.
- Its rules come from the doc itself: the TRRS (4-pole) vs TRS (3-pole) cable depends on the revision, and switches must be Cherry MX compatible only.
- Shopify coverage is excellent, because keyboard stores are almost all on Shopify. KEEBD (UCP) sells an assembled v4.1.1 that includes the TRRS cable and 8 rubber feet.

**Why it lost:**
- 5 of its 10 lines are mechanical (case, plate, spacers, screws, rubber cushions), so it does not read as "electronics only".
- "PCB / Case / Switch plate, 1 set each" are sold as one kit, which forces bundle de-duplication on stage. No v4 FR4 plate is sold on its own.
- Every v4 listing found is v4.1.x, where a TRS cable is also compatible, so the TRRS rule would pass on real offers rather than fire.

**Other candidates checked and rejected:**

| Candidate | What I found | Verdict |
|---|---|---|
| `wled/WLED` (19.1k stars, EUPL-1.2) | README (110 lines) has no parts list; it links to the wiki's compatible-hardware page | No BOM |
| `wled/WLED-Docs` (MIT) `docs/basics/getting-started.md` | Wiring steps, no parts list with quantities. Useful rule sources: `top5_mistakes.md` L21 (default current limiter 850 mA), level-shifter pages | Rule source, not a BOM |
| AirGradient (`airgradienthq/arduino` now redirects to `Open-Air-Foundation/firmware-one-openair`, 389 stars, CC-BY-SA-4.0) | README lists supported sensors only; kits use AirGradient's own PCB | No BOM |
| ESPHome projects (`ajfriesen/ESPHome-AirGradient` 205 stars; `Madelena/esphome-weatherman-dashboard` 1.3k stars, no license) | No parts list, or 2 bullets | Too thin |
| Raspberry Pi Pico projects (GitHub code search for parts tables) | Only small or stale repos (for example `pjgpetecodes/pico-streamdeck`, 230 stars, last push 2021) | Not popular or not maintained |
| `BlueAndi/Pixelix` (448 stars, MIT) | README L102–L104 lists 3 bullets (ESP32 DevKitV1, 8x32 WS2812B matrix, "Power supply 5 V / 4 A"); L112 warns about LED current | Good LED-current rule, but only 3 lines |
| `scottlawsonbc/audio-reactive-led-strip` (3.0k stars, MIT) | 4 bullets, no quantities, PSU amps unspecified, also needs a computer | Too thin, dormant |

## 2. Parts list with source line references

**URL to paste in the demo:** `https://github.com/lmarzen/esp32-weather-epd`

The README is at the repo root.
- If the app needs a file URL: `https://raw.githubusercontent.com/lmarzen/esp32-weather-epd/main/README.md`
- Pinned to a SHA so the demo cannot change under you (verified byte-identical to `main` today): `https://raw.githubusercontent.com/lmarzen/esp32-weather-epd/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md`
- Human-readable line view: `https://github.com/lmarzen/esp32-weather-epd/blob/main/README.md?plain=1#L54-L67`

The file uses LF line endings. Line numbers come from `cat -n` on the raw file and match GitHub's.

**Raw table (README L54–L67), verbatim:**
```
54	  | Component Type  | Component                                    | Notes                                                     | Link                                                                         |
55	  |-----------------|----------------------------------------------|-----------------------------------------------------------|------------------------------------------------------------------------------|
56	  | ESP32           | FireBeetle 2 ESP32-E                         | Features low-power design, USB-C, and battery management. | Available [here](https://www.dfrobot.com/product-2195.html?tracking=PfSxQ8). |
57	  | E-Paper Display | See [Panel Support](#panel-support).         | See [Panel Support](#panel-support).                      | See [Panel Support](#panel-support).                                         |
58	  | Adapter Board   | DESPI-C02                                    | Waveshare HATs (rev 2.2/2.3) are not recommended.         | Available [here](https://www.aliexpress.us/item/3256804446769469.html).      |
59	  | Sensor          | BME280                                       | Temperature, humidity, and pressure. 3.3V/5V compatible.  | Available from multiple vendors.                                             |
60	  | Battery         | 3.7V LiPo w/ JST-PH2.0 connector             | Any capacity (e.g., 5000mAh for 6+ months runtime)        | Available from multiple vendors.                                             |
61	  | Enclosure       | See [Enclosure Options](#enclosure-options). | See [Enclosure Options](#enclosure-options).              | See [Enclosure Options](#enclosure-options).                                 |
63	Other items needed:
64	- Wires ("Jumper Wires" if looking to minimize/avoid soldering).
65	- Solder Iron + Solder (unless following [Solder-Free Component Selection](#solder-free-component-selection-optional)).
66	- Linux, Windows, or MacOS computer (used to configure and install ESP32 firmware).
67	- Push Button (optional, if you want a reset button mounted on your enslosure, else you can use the on-board reset button).
```
Also used: L75 (recommended panel), L120–L126 (solder-free variants), L136 (polarity warning), L138 and L140–L142 (adapter notes).

| # | Line (qty) | Exact source quote (substring check) | Source lines | Resolved spec | Status in demo |
|---|---|---|---|---|---|
| 1 | ESP32 board (1, implicit) | `FireBeetle 2 ESP32-E` | L56; L124 "Buy the [FireBeetle 2 ESP32-E w/ Headers]" | DFRobot DFR0654-F (with headers) if solder-free, else DFR0654 | Buy |
| 2 | E-paper display (1, implicit) | `See [Panel Support](#panel-support).` then `Waveshare 7.5in e-paper (v2)` / `(recommended)` | L57, then L75 | 7.5", 800x480, black/white, raw panel (24-pin FPC) | Buy |
| 3 | Adapter board (1, implicit) | `DESPI-C02` | L58 | Good Display DESPI-C02. Negative constraint: "Waveshare HATs (rev 2.2/2.3) are not recommended." | Buy |
| 4 | Sensor (1, implicit) | `BME280` | L59 | BME280 breakout, I2C, "Temperature, humidity, and pressure. 3.3V/5V compatible."; pre-soldered headers if solder-free (L125) | Buy |
| 5 | Battery (1, implicit) | `3.7V LiPo w/ JST-PH2.0 connector` | L60 | 1S LiPo, 3.7 V nominal, JST-PH 2.0 mm 2-pin; "Any capacity (e.g., 5000mAh for 6+ months runtime)" | Buy (rule target) |
| 6 | Enclosure (optional) | `See [Enclosure Options](#enclosure-options).` | L61, then L87–L118 | DIY wood / 3D printable (community links) / picture frame | Excluded: optional, no 3D model |
| 7 | Wires (1 pack, unspecified) | `Wires ("Jumper Wires" if looking to minimize/avoid soldering).` | L64 | Female-female Dupont jumper wires | Owned (seed in owned.json) or buy |
| 8 | Solder iron + solder | `Solder Iron + Solder` | L65 | Tool | Owned / tool, not bought |
| 9 | Computer | `Linux, Windows, or MacOS computer` | L66 | Tool | Owned / tool, not bought |
| 10 | Push button (optional, 1) | `Push Button (optional, if you want a reset button mounted on your enslosure` | L67 (typo "enslosure" is in the source; quote it verbatim) | Momentary tactile switch, jumper-wire compatible (L126) | Optional, skip |

Lines for the demo: **5 to buy** (rows 1–5), **3 owned or tools removed** (rows 7–9), **2 optional skipped** (rows 6 and 10). That is 10 extracted lines, within the 5–12 target.

## 3. Shopify coverage table

**Method:**
- Each query was run from the ucp-check folder in the exact form requested: `npx ucp catalog search --input '{"query":"<part>","context":{"address_country":"US"}}' --format json`.
- Each query was then run a second time with `"filters":{"ships_from":[{"country":"US"}]}` added.
- Where a store was the target, I used `"filters":{"shops":["gid://shopify/Shop/<id>"]}`.
- Prices are `variants[0].price.amount / 100`, all single-variant listings.

**What I found about the catalog** (this matters for the app):
- `context.address_country:"US"` does **not** restrict currency or origin. The requested form returned GBP (The Pi Hut), EUR (OpenELAB Technology Ltd., Robot Italy), ZAR, INR and JPY sellers mixed in with US ones.
- `filters.ships_to` made no visible difference.
- `filters.ships_from:[{"country":"US"}]` did fix it: almost all results were USD from US stores, with one EUR listing slipping through.
- So: add `ships_from` US **and** keep only `currency == "USD"` on the client side.
- JPY is zero-decimal: Yushakobo's `amount: 16000, currency: JPY` is ¥16,000, not ¥160.
- `pagination.total_count` is about 800–950 for almost any query (including "DESPI-C02"), so it says nothing about relevance.

**Weather display coverage** (all USD unless noted; "US" means it appeared with `ships_from` US):

| Part (qty) | Top 3 good matches (price, merchant) | Obviously wrong matches seen |
|---|---|---|
| FireBeetle 2 ESP32-E (1) | **$19.29 OpenELAB Inc.** "FireBeetle 2 ESP32-E IoT Microcontroller with Header" (US; matches solder-free L124). $14.95 Vetco Electronics "FireBeetle 2 ESP32-E Battery Ready ... (D74)" (US; header status [unverified]). $9.88 / $10.62 Shenzhen Mingsheng Weiye "DFR0654" / "DFR0654-F" (requested form only; ships-from unknown [unverified]). Non-USD: The Pi Hut £8.33 | "Terminal Block Board for FireBeetle 2 ESP32-E" (RobotShop $20.94, Pi Hut £14.92; accessory, not the board). "FireBeetle ESP32 IoT Microcontroller", the older v1 board (RobotShop $9.49, OpenELAB $16.59). FireBeetle 2 ESP32-C6 / -S3 / -P4 boards (different MCU). "FireBeetle 2 ESP32 Expansion Shield" (Vetco $12.95) |
| 7.5" e-paper, 800x480 B/W (1) | **$56.55 RobotShop USA** "Waveshare 800×480, 7.5" E-Ink Raw Display" (US; description: "Display Color: Black/White", 170.20 x 111.20 mm, 3.3 V, no driver board, so this is the v2 raw panel). $64.39 RobotShop "Waveshare 7.5" E-Paper E-Ink Display Module for Raspberry Pi Pico, 800×480, Black/White" (panel plus Pico driver board). $66.88 RobotShop "800x480, 7.5-inch E-Ink display HAT for Raspberry Pi" (panel plus Waveshare HAT). Also $89.00 Buy2fix (B/W module for Raspberry Pi) | OpenELAB "Waveshare 7.5 inch E-Ink Display 800x480 E-Paper with Hat" **$128.49**: title says 7.5" 800x480, but the description describes a seven-color ACeP photo frame. OpenELAB "Waveshare 7.5inch 4 Color e-Paper display (H)" $93.49 (not in the README's Panel Support list). "7.5" E-Paper (B) Red/Black/White" $56.55 (supported by L77, but not the recommended B/W panel and slower). OurLum "Waveshare E Paper Display" $466.44. 4.26" 800x480 panels (wrong size). 7.3" color panels are off-spec for the recommended B/W build, but some 7.3" 7-color panels are in the README allowlist (L79–L81), so R15 must match exact models, not "7.3 inch" |
| DESPI-C02 adapter (1) | **$10.00 OpenELAB Inc.** "GooDisplay DESPI-C02 24-Pin Serial E-Paper HAT Adapter" (the only USD match). €9.14 OpenELAB Technology Ltd. (EU sister store). Fallback: the Waveshare HAT inside the $66.88 RobotShop bundle (README says "not recommended") | "DESPI-C02-CV0097" 0.97-inch variant $12.79. "DESPI-C102" $8.29 and "DESPI-C579" $8.39 (other panel sizes). Querying "DESPI-C02" alone also returned unrelated non-electronics: a Gundam-hobby sponge, Alo Yoga, SKIMS, Béis bags |
| BME280 (1) | **$11.99 OpenELAB Inc.** "Waveshare BME280 Environmental Sensor" (US; "Onboard voltage level translator, compatible with 3.3V/5V"). $10.99 ShillehTek "BME280 Pre-Soldered ..." (US; matches L125). $13.99 Axiometa. Also $9.00 Zaitronics, $11.63 RobotShop Waveshare BME280 | "Grove - Barometer Sensor (BMP280)" RobotShop $10.19 (no humidity). LILYGO T-Echo "with BME280" $107.37 (a whole LoRa device). Enviro+ $62.55. Gadget Zone BME280 $35.61 (price outlier). Grove BME280 $18.75 / $22.50 (works, but needs a Grove-to-Dupont cable) |
| 3.7V LiPo, JST-PH 2.0 (1) | **$12.97 Rokland** "PKCELL Flat 3.7V 2000mAh ... 803860 Battery with JST Type PH 2.0 Plug" (US; listing says "Check polarity match"). $13.99 RC Battery Depot "3.7V 2000mAh 103450 LiPo with JST-PH2.0 2-Pin Connector" (US). $15.97 Rokland "MakerFocus Flat 3.7V 3000 mAh ... JST Type PH 2.0 Plug". Also $23.99 Xain-USA 4400 mAh 1S2P JST-PH 2.0 | **ameriDroid $7.95** "3.7V 2000mAh 103450 LiPo Battery w/ JST 1.25 Connector" (description: "Micro JST 1.25mm 2-pin (SH1.25)"). **Rokland $9.97** "... 1S 1C LiPo Battery with Micro JST 1.25 Plug". MakerNova $7.99 (JST 1.25). **HaruTech $13.00** 5000 mAh: title says "with JST Connector", description says "2P PH1.25mm Pitch". Rokland $12.97 "Specialty **3-pin** JST PH" (its own listing: "will not work with other boards that require a 2-pin connection"). RC Battery Depot $13.99 "**7.4V** 450mAh ... with JST PH 2" (2S). Atlavox $13.99 / $17.99 "JST-PH 2-pin **reverse polarity** connector". RadioMaster 7.4 V 2S XT30. Rage RC drone packs. Rokland $8.97 "RAK ... Battery Cable with Power Switch" (a cable, not a battery) |
| Jumper wires F/F (1 pack) | $1.95 RobotShop "Jumper Wires Premium 6" F / F Pack of 20" (US). $3.25 Electronix Express 5-pc 12" F/F. $5.00 Arduino Online Shop 50 F/F (US). Also Vetco $4.69 | "Grove to 4 Pin 2.54 Female Jumper Wire" (Grove). "M5Stack Grove2Dupont" (OpenELAB). Male-male sets |
| Push button (optional) | $0.75 RobotShop "12mm Push Button Switch". $0.69 Vetco "SPST Tactile Dome Push Button". $1.00 Alpha 3D Lab | "12mm Square Push Button ... with Red LED ... 50mA @ 12VDC" (needs 12 V for the LED). 250 V panel-mount metal buttons |
| Enclosure | Not searched: excluded by design (optional; DIY or 3D print) | n/a |

**Coverage:** 5/5 required parts plus wires plus the optional button all have USD offers from US Shopify stores. The weak spot is DESPI-C02, which has one US seller.

**Proposed cart** (mandate stores: OpenELAB, RobotShop USA, Rokland; wires owned, button skipped):

| Store | Items | Subtotal |
|---|---|---|
| OpenELAB Inc. (openelab.com) | FireBeetle 2 ESP32-E w/ Header $19.29 + DESPI-C02 $10.00 + Waveshare BME280 $11.99 | $41.28 |
| RobotShop USA (robotshop-us.myshopify.com) | Waveshare 7.5" 800x480 B/W raw panel | $56.55 |
| Rokland (store.rokland.com) | PKCELL 3.7V 2000 mAh JST PH 2.0 | $12.97 |
| **Total before shipping and tax** | | **$110.80** |

With the RC Battery Depot battery instead, the total is $111.82. An optimizer without a store penalty might move the board to Vetco ($14.95) or the sensor to ShillehTek ($10.99), which adds stores. Pin the mandate to the 3 stores above.

**UCP discover** (`npx ucp discover --business <url> --format json`; no carts created):

| Business URL | Result | Endpoint | Cart / checkout |
|---|---|---|---|
| https://openelab.com | success, UCP 2026-08-25 | `https://9irjdt-u1.myshopify.com/api/ucp/mcp` | yes / yes (also catalog search and lookup, fulfillment, discount, order) |
| https://www.robotshop.com | **PROFILE_FETCH_FAILED: HTTP 403** on `/.well-known/ucp` | n/a | n/a |
| https://robotshop-us.myshopify.com (the `seller.domain`) | success, UCP 2026-08-25 | `https://robotshop-us.myshopify.com/api/ucp/mcp` | yes / yes |
| https://store.rokland.com | success | `https://rokland.myshopify.com/api/ucp/mcp` | yes / yes |
| https://rcbatterydepot.com | success | `https://z54q35-kc.myshopify.com/api/ucp/mcp` | yes / yes |
| https://vetco.net | success | `https://8da295-18.myshopify.com/api/ucp/mcp` | yes / yes |
| https://ameridroid.com | success | `https://ameridroid.myshopify.com/api/ucp/mcp` | yes / yes |

**Lesson:** always pass `variants[].seller.domain` (the myshopify domain) to `--business`, not `seller.url`. RobotShop's public domain blocks the profile fetch.

## 4. Compatibility rules (numbers, sources, auto-fix)

Proposed IDs continue PLAN.md §3.8. They are deterministic Python over attributes parsed from the listing **description first, then the title**. The HaruTech listing shows why: its title says "JST", its description says PH1.25.

| ID | Rule | Numbers | Source | On failure |
|---|---|---|---|---|
| **R12 `BATTERY_CONNECTOR`** (stage rule) | Battery plug must be JST **PH**, **2.0 mm** pitch, **2-pin** | Board needs 2.0 mm. Failing offers: 1.25 mm (ameriDroid, Rokland, MakerNova, HaruTech), 3-pin (Rokland "Specialty") | README L60 "3.7V LiPo w/ JST-PH2.0 connector". DFRobot wiki DFR0654 power table: "PH2.0 Connector: 3.7~4.2V Li-ion" (https://wiki.dfrobot.com/FireBeetle_Board_ESP32_E_SKU_DFR0654, fetched today). JST PH series page: the connector "features a pitch of 2.0 mm" (https://www.jst-mfg.com/product/index.php?series=199&lang=en, fetched today) | FAIL, then auto-fix |
| **R13 `BATTERY_CELLS`** | Single cell only: 3.7 V nominal, at most 4.2 V full | 2S pack = 7.4 V nominal, 8.4 V full (2 x 4.2), which is above the board's 4.2 V | DFRobot wiki: "PH2.0 Connector: 3.7~4.2V Li-ion"; board overview row 4 "Li-ion Battery Port: Support 3.7V-4.2V" | FAIL, then auto-fix (RC Battery Depot "7.4V 450mAh ... JST PH 2" passes R12 and fails here) |
| **R14 `BATTERY_POLARITY`** | Polarity is not standardized | none | README L136: "The polarity of JST-PH2.0 connectors is not standardized! You may need to swap the order of the wires in the connector." Listings saying "reverse polarity" (Atlavox) or "Check polarity match" (Rokland) | WARN "needs human check". Never auto-pass; reject listings that say "reverse polarity" |
| R15 `PANEL_SUPPORTED` | Panel must be one of the 9 rows in README Panel Support | Allowlist L75–L83. The 4-color (H) panel is not listed | README L73–L83 | FAIL, then swap to the L75 "(recommended)" panel |
| R16 `SENSOR_HUMIDITY` | The sensor must measure humidity, so a BMP280 is rejected | BME280: relative humidity ±3%, VDD 1.71–3.6 V (Bosch page). The BMP280 listing only gives pressure and temperature specs | README L59. Bosch BME280 page (https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/, fetched today). RobotShop BMP280 listing text. The Bosch BMP280 PDF downloaded but is encrypted and was not parsed **[partially verified]** | FAIL, then swap to a BME280 |
| R17 `EPD_ADAPTER` | Prefer DESPI-C02. A Waveshare HAT gets a warning | rev 2.3 HAT has an extra `PWR` pin that goes to 3.3 V. DESPI-C02 "RESE" switch must be at 0.47 | README L58, L138, L140–L142 | WARN, plus a setup note on the why-card |

**Battery runtime (why-card only, not a rule):** the README example is "5000mAh for 6+ months runtime" (L60). Scaling that linearly, about 833 mAh per month, so 2000 mAh is roughly 2.4 months. This is a linear extrapolation of the README's example, not a measurement **[unverified]**.

**Charge-current rule (not used):** I could not find a charge-current spec for the FireBeetle 2 ESP32-E on DFRobot's wiki or product page, so a "capacity ≥ charge current x 1h" rule would be **[unverified]**. Leave it out.

**Auto-fix for R12/R13:**
1. Filter the battery offers to `connector_family == PH && pitch_mm == 2.0 && pins == 2 && cells == 1`. Drop anything whose description says "reverse polarity".
2. Restrict to stores allowed by the mandate.
3. Pick the cheapest available offer and attach the R14 WARN.

With a 3-store mandate (OpenELAB, RobotShop, Rokland), the flow inside Rokland is:
- The cheapest battery is $9.97 "Micro JST 1.25 Plug". It fails R12 (1.25 mm ≠ 2.0 mm).
- R12 also rejects the 3-pin "Specialty" listing.
- The RAK cable is rejected as "not a battery".
- The auto-fix picks **PKCELL 2000 mAh JST PH 2.0, $12.97** (+$3.00).

If ameriDroid is allowed instead, the failing pick is $7.95 (JST 1.25) and the swap is +$5.02.

## 5. Tricky extraction cases

1. **Indirect row:** L57 "E-Paper Display | See [Panel Support](#panel-support)." The extractor must follow the anchor to a second table (L73–L83) with 9 options and choose L75 "(recommended)". The source quote spans two places, so the quote check needs to accept a pair of spans.
2. **Indirect optional row:** L61 "Enclosure | See [Enclosure Options]". It leads to a bullet list (DIY wood with measurements, 3D printable links table, picture frame). Classify it as optional and non-electronic, and do not buy it. This is also the honest "no 3D model needed" moment.
3. **No quantity column:** quantity is implicitly 1 for every table row. Wires have no quantity (treat as 1 pack). Do not invent numbers.
4. **Indented table:** every table line starts with two spaces (`  | ESP32 ...`). Markdown parsers handle this. A naive `^\|` regex misses the whole table.
5. **Parts mixed with tools:** "Other items needed" (L63–L67) mixes parts (wires, push button) with tools (solder iron) and a computer. Classify each line as part, tool or owned.
6. **Optional flag and a typo inside the quote:** L67 "Push Button (optional, ... enslosure ...)". Keep `optional=true` and quote the typo verbatim, or the substring check fails.
7. **Constraints in the Notes column:**
   - L58 "Waveshare HATs (rev 2.2/2.3) are not recommended." is a negative constraint.
   - L59 "3.3V/5V compatible" is an attribute.
   - L60 "Any capacity (e.g., 5000mAh ...)" is an example, not a requirement. Do not filter for 5000 mAh.
8. **Conditional variants from another section:** the Solder-Free list (L120–L126) changes SKUs. Use the FireBeetle "w/ Headers" (DFR0654-F) and a BME280 with factory-soldered headers.
9. **Links that are not offers:** the Link column points to affiliate DFRobot and AliExpress URLs (L52 says some are affiliate). They must not become offers. The AliExpress link would be refused by the mandate, like Alibaba in the main demo.
10. **Attributes packed into a name:** "3.7V LiPo w/ JST-PH2.0 connector" holds voltage, chemistry, connector family and pitch. "JST-PH2.0", "JST PH 2.0", "PH2.0mm" and "JST Type PH 2.0" must all normalize to the same thing. "JST 1.25", "Micro JST 1.25", "SH1.25" and "PH1.25" must not match.
11. **Listings whose title contradicts the description:**
    - OpenELAB "Waveshare 7.5 inch ... with Hat" $128.49 describes a 7-color ACeP photo frame.
    - HaruTech "with JST Connector" turns out to be PH1.25.
    - Rokland's JST 1.25 listing names 5 capacities in the title but exposes 1 variant at $9.97.
    - Treat these as low confidence.

## 6. The 20-second demo segment

**Setup before going on stage:**
- Preset mandate for this run: budget $130, stores OpenELAB + RobotShop USA + Rokland, share country only, ship to US.
- Seed owned.json / Cognee with "soldering iron" and "jumper wires" (the computer is classed as a tool automatically).
- Run it once tonight and keep the replay (M10), because live prices and rankings drift.

| t | Driver clicks | Presenter says |
|---|---|---|
| 0:00 | Paste `https://github.com/lmarzen/esp32-weather-epd`, click **Sign mandate and run** | "Second project, no robot: a battery-powered e-paper weather display. Electronics only." |
| 0:04 | BOM graph appears (5 to buy, 2 struck through as owned, enclosure and button marked optional). Hover the Battery node to show the L60 quote | "Same pipeline. Every part is quoted from the README, and the tools I already own are gone." |
| 0:09 | The Battery node turns red: **R12 FAIL, JST 1.25 mm ≠ JST-PH 2.0 mm** ($9.97). It flips green to **PKCELL 2000 mAh JST-PH 2.0, $12.97**, with a yellow "check polarity" chip | "The cheapest battery wouldn't even plug in. DFRobot's spec says this board takes a single-cell JST-PH 2.0, so the agent swapped it, and flags polarity for me to check." |
| 0:16 | Click **Approve cart**. Three cart links appear (OpenELAB $41.28, RobotShop $56.55, Rokland $12.97) | "Three stores, $110.80, one approval." |

## 7. Risks

1. **DESPI-C02 has one US seller** (OpenELAB Inc., $10.00). If it sells out tonight, use the RobotShop $66.88 panel-plus-HAT bundle, let R17 WARN, and drop the separate panel line.
2. **The catalog changes overnight.** If Rokland's $9.97 JST 1.25 listing stops ranking, the red moment disappears.
   - Mitigation: run tonight and replay. The JSON snapshots are in the ucp-check `s2` folder (see Appendix).
   - Second option: allow ameriDroid, whose $7.95 JST 1.25 cell fails the same way.
3. **Title-only matching picks wrong, expensive items.** One example is the $128.49 OpenELAB "7.5 inch with Hat" photo frame. The resolver must read descriptions, and R15 must use the README allowlist.
4. **The indirect "See Panel Support" row.** If extraction does not follow the anchor, the display line is empty or wrong, and the source-quote check needs two spans. Keep a hard-coded README table parser as the fallback (PLAN G1 already allows that).
5. **Polarity cannot be decided from listings.** Show it as WARN, never as PASS, and do not claim the agent verified it.
6. **Lithium shipping.** Rokland's listing says batteries ship by ground only, and expedited options disappear at checkout. Delivery dates may be longer **[unverified delivery estimate]**.
7. **RobotShop's public domain returns 403 on `/.well-known/ucp`.** Use `seller.domain` (`robotshop-us.myshopify.com`) for `--business`.
8. **Currency mixing and JPY.** `address_country` does not filter currency. Add `ships_from` US, keep only USD, and handle zero-decimal currencies.
9. **Windows CLI crash.** One parallel `npx ucp discover` run printed `Assertion failed: !(handle->flags & UV_HANDLE_CLOSING), file src\win\async.c, line 76` to stderr; its JSON output was still written. Run `ucp` calls one at a time from the backend.
10. **License.** The project is GPL-3.0 (copyleft, not permissive). We only read its README, so this is fine, but say "open source", not "MIT", if asked. The Corne runner-up is CC-BY-4.0 / MIT.
11. **Cheap "GY-BME280" boards are sometimes mislabeled BMP280s [unverified, general maker lore].** The proposed cart uses the Waveshare BME280 from OpenELAB, whose description lists humidity.

## Appendix A: Runner-up details (Corne Cherry v4)

- Doc URL: `https://github.com/foostan/crkbd/blob/main/docs/corne-cherry/v4/buildguide_en.md`
- Raw, pinned to its last commit `d69ffb4` (Mar 23, 2025), byte-identical to `main`: `https://raw.githubusercontent.com/foostan/crkbd/d69ffb4efeab27492e24deb529429461cb99e1ef/docs/corne-cherry/v4/buildguide_en.md`

Parts table, verbatim:
```
10	| Name                 | Count   | Remarks                                                                                     |
12	| PCB                  | 1 set   |                                                                                             |
13	| Case                 | 1 set   |                                                                                             |
14	| Switch plate         | 1 set   | FR4 1.6mm thick                                                                             |
15	| Key switches         | 42 - 46 | Only Cherry MX compatible                                                                   |
16	| Keycaps              | 42 - 46 | 1u 40 pcs, 1.5u 2 pcs                                                                       |
17	| Spacer M2            | 8       | 7.5 mm For Case assembly                                                                    |
18	| Screw M2             | 16      | 5 mm For Case assembly                                                                      |
19	| Rubber cushion       | 8       |                                                                                             |
20	| TRRS (4 poles) cable | 1       | v4.0.0: TRS (3 poles) cable is not compatible<br/>v4.1.0: TRS (3 poles) cable is compatible |
21	| Type-C cable         | 1       |                                                                                             |
27	| Rotary Encoder | 0 - 4 pieces | compatible product of the rotary encoder EC12 |
```
Also: L57–L58 warn against plugging or unplugging the TRRS cable while USB is connected.

| Part | Top good matches (USD unless noted) | Wrong matches |
|---|---|---|
| PCB + case + plate (1 set each) | KEEBD "Corne v4 MX Keyboard" $150.00 ("Version v4.1.1 ... comes assembled ... Includes 1 x Corne v4 MX Keyboard 1 x TRRS Cable 8 x Rubber Feet"). Case Zones "Corne V4.1 ... MX ... Wired" $111.38 (PLA 3D-printed shell, ships a TRS cable). Yushakobo "Corne V4 Cherry" ¥16,000 (JPY) | "Corne V4 Chocolate" (Choc switches, fails MX). "Corne MX Hotswap v3.0.1 PCB Kit" (v3). Boardsource "Corne Wireless SMT PCB" (different design). Little Keyboards "Corne Carry Case" $19.99 (a carrying case, not an enclosure). No standalone v4 FR4 plate found |
| Key switches 42–46 (MX) | Mechanical Keyboards Cherry MX Red $0.28/ea, MX Brown $0.40/ea. Momokai Cherry MX $1.40. KEEBD Gateron (per-pack pricing [unverified]) | "CHERRY MX SWITCH for Pushbuttons" (arcade). Low-profile and Choc keycaps or switches |
| Keycaps (1u x40, 1.5u x2) | MoErgo 72-pack 1U $53.00. HIP 20-pack XDA 1U MX $9.66. KEEBD CFX set $30.00 | "Kailh Low Profile Pudding" (Choc). Novelty keycaps |
| Spacer M2 7.5 mm x8 | WREKD M2 knurled standoff $0.80/ea. Keebio "M2 Screws/Standoffs" $3.49. Pyrodrone 5-pc $4.99 | M3 spacers (SpeedyFPV) |
| Screw M2 5 mm x16 | Specialty Parts 100-pc M2x5 button head $7.95. Palm Beach Bots 10-pk $1.99. Boxy Pixel Ti $2.70 | "M2 X 5mm set screws, cup point". 4,000-pack $68.79 |
| Rubber cushion x8 | Keebio SKUF feet $2.99. PrimeKB Bumpons $4.00. CannonKeys Bumpons $5.00 (also included in the KEEBD kit) | Sorbothane 1" $287.95 |
| TRRS cable x1 | Keebio $2.49. holykeebs $5.00. KEEBD 24 cm dual-90° $6.00 | TRRS male-to-female extensions. TRS-to-TRRS adapters |
| Type-C cable x1 | UGREEN $13.99. Satechi $16.78. KEEBD $14.00 | Charge-only or "power" cables (needs R8) |
| Rotary encoder EC12 (0–4) | 773 GROUP EC12E24204A8 $2.23. Saber Keebs EC12 low profile $2.00 | EC11 listings (Keebio $1.99, KEEBD $3.00); footprint compatibility with EC12 [unverified] |

UCP discover for keyboard stores:
- `https://keebd.com` succeeded (endpoint `keebd.myshopify.com`, cart and checkout).
- `https://keebio.com` failed to fetch; `https://keebio.myshopify.com` succeeded. Keebio's real storefront is keeb.io.

## Appendix B: Reproduction

- Catalog JSON (≈80 files): `C:\Users\ptula\AppData\Local\Temp\claude\fe68aa92e0ea2987\80ff7711-1f2f-4184-b887-c493cf3cb5c4\scratchpad\ucp-check\s2\`
  - `epd_*.json`: requested form.
  - `epd_*__us.json`: with `ships_from` US.
  - `oe_*`, `rs_*`, `vt_*`, `rok_*`, `amd_*`, `rcb_*`: store-restricted searches.
  - `cr_*`, `kd_*`: Corne.
  - `disc_*.json`: discover output.
- Fetched docs: `C:\Users\ptula\AppData\Local\Temp\claude\fe68aa92e0ea2987\80ff7711-1f2f-4184-b887-c493cf3cb5c4\scratchpad\docs\` and `...\scratchpad\web\` (README copies, DFRobot wiki, JST and Bosch pages).
- Shop GIDs for `filters.shops`:

| Store | GID |
|---|---|
| OpenELAB Inc. | `gid://shopify/Shop/93537272132` |
| RobotShop USA | `gid://shopify/Shop/57390268577` |
| Rokland | `gid://shopify/Shop/713772` |
| RC Battery Depot | `gid://shopify/Shop/62651695173` |
| ameriDroid | `gid://shopify/Shop/18842123` |
| Vetco | `gid://shopify/Shop/64692912265` |
| KEEBD | `gid://shopify/Shop/57731907736` |

- Nothing was created: no carts, no accounts, no git operations.
