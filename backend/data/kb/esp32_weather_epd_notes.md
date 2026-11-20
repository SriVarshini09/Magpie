---
doc_id: esp32_weather_epd
title: esp32-weather-epd README: parts-list excerpts with line numbers
kind: doc
source_url: https://github.com/lmarzen/esp32-weather-epd
commit_sha: c78ad15e7933684fb5af19168f6e2da003e08b84
licence: GPL-3.0 project; we read its README parts list and use none of its code; short quotes, cited
build_type: electronics_mcu
---

# esp32-weather-epd (README pinned to commit c78ad15)

Excerpts recorded in PLAN §13.2 and research/second-demo.md [checked Nov 19]. Line numbers are README lines at
the pinned commit. At run time the README itself is fetched and every `readme_quote` is checked against those
bytes; these rows are what the rule pack `mcu_battery` cites.

## chunk: l56_board
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L56
- readme_lines: 56
- quote: "FireBeetle 2 ESP32-E"
- rules: G1

Parts table row for the microcontroller board: a DFRobot FireBeetle 2 ESP32-E.

## chunk: l57_display
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L57
- readme_lines: 57
- quote: "See [Panel Support](#panel-support)."
- rules: R15

The display row points to the Panel Support section instead of naming a panel, so the display line carries two
quotes: this one and the recommended panel at L75.

## chunk: l58_adapter
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L58
- readme_lines: 58
- quote: "DESPI-C02"; "Waveshare HATs (rev 2.2/2.3) are not recommended."
- rules: R17

Adapter board row: the DESPI-C02, with a note that Waveshare HAT revisions 2.2 and 2.3 are not recommended.

## chunk: l59_sensor
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L59
- readme_lines: 59
- quote: "BME280"; "3.3V/5V compatible."
- rules: R16, G4

Sensor row: a BME280, which measures temperature, humidity and pressure.

## chunk: l60_battery
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L60
- readme_lines: 60
- quote: "3.7V LiPo w/ JST-PH2.0 connector"
- rules: R12, R13, R14

Battery row: a single-cell 3.7 V LiPo with a JST-PH 2.0 plug. The row's capacity note is an example, not a
requirement, so capacity is not filtered.

## chunk: l61_enclosure
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L61
- readme_lines: 61
- quote: "See [Enclosure Options](#enclosure-options)."
- rules: none

The enclosure row points to a list of options (wood, 3D prints, a picture frame). It is optional and not bought.

## chunk: l64_l67_other_items
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L63-L67
- readme_lines: 63-67
- quote: "Solder Iron + Solder"; "Linux, Windows, or MacOS computer"
- rules: none

"Other items needed" mixes parts (wires, an optional push button) with tools (a soldering iron, a computer).

## chunk: l75_panel_support
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L75
- readme_lines: 73-83 (table); 75 (recommended row)
- quote: "Waveshare 7.5in e-paper (v2)"
- rules: R15
- checked: Nov 19; only the L75 row is transcribed here [human check for the other rows]

The Panel Support table lists nine panels; the recommended one is the Waveshare 7.5-inch e-paper v2 (800 x 480,
black and white, raw panel). R15 matches exact models, not sizes.

## chunk: l136_polarity
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L136
- readme_lines: 136
- quote: "The polarity of JST-PH2.0 connectors is not standardized!"
- rules: R14

The README warns that JST-PH 2.0 polarity varies between batteries, and that the wires may need swapping.

## chunk: l138_l142_adapter_notes
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L138-L142
- readme_lines: 138, 140-142
- quote: none (paraphrased)
- rules: R17

Adapter setup notes: the rev 2.3 Waveshare HAT has an extra PWR pin that must go to 3.3 V, and the DESPI-C02 has a
RESE switch whose position must be set as the README describes.

## chunk: l120_l126_solder_free
- source: https://github.com/lmarzen/esp32-weather-epd/blob/c78ad15e7933684fb5af19168f6e2da003e08b84/README.md#L120-L126
- readme_lines: 120-126
- quote: none (paraphrased)
- rules: none

The solder-free section swaps in the FireBeetle with headers and a BME280 with factory-soldered headers.
