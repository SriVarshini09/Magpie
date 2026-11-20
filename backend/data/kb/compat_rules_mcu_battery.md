---
doc_id: compat_rules_mcu_battery
title: Rule pack mcu_battery (R12-R17): rule texts and sources
kind: rule_source
licence: written by the team (rule texts); sources cited per rule as kb:// rows
---

# Pack `mcu_battery`

The electronics rules of the second demo (PLAN §13.3), for the ESP32 e-paper weather display. R12 and R13 are G5
and G3 with this project's sources. Listing descriptions are read before titles. Code:
`backend/app/rules/mcu_battery.py`.

## chunk: r12
- rule: R12 BATTERY_CONNECTOR (stage rule)
- human_check: never (a missing pin count is "needs your check", not a pass)
- on_failure: FAIL, then filter battery offers to JST-PH, 2.0 mm, 2-pin, 1S
- sources: kb://esp32_weather_epd#l60_battery, kb://electrical_notes#dfrobot_ph2_power, kb://electrical_notes#jst_ph_pitch

The battery plug must be JST PH with a 2.0 mm pitch and 2 pins. A "JST 1.25", "Micro JST 1.25", "SH1.25" or
"PH1.25" plug does not fit, and neither does a 3-pin PH plug. A cable or accessory listing is not a battery.

## chunk: r13
- rule: R13 BATTERY_CELLS
- human_check: never
- on_failure: FAIL, then the same filter as R12
- sources: kb://electrical_notes#dfrobot_ph2_power, kb://electrical_notes#lipo_cell_voltage

The battery must be a single cell: 3.7 V nominal and at most 4.2 V full. A 2S 7.4 V pack is 8.4 V full and fails.

## chunk: r14
- rule: R14 BATTERY_POLARITY
- human_check: always
- on_failure: WARN "check polarity" on every battery; a listing that says "reverse polarity" is rejected
- sources: kb://esp32_weather_epd#l136_polarity

JST-PH polarity is not standardized, so the agent never says it verified polarity. The user checks it.

## chunk: r15
- rule: R15 PANEL_SUPPORTED
- human_check: conditional (only the L75 recommended panel is transcribed; the other Panel Support rows need a human)
- on_failure: FAIL, then swap to the README's recommended panel
- sources: kb://esp32_weather_epd#l57_display, kb://esp32_weather_epd#l75_panel_support

The panel must match a model in the README's Panel Support table by exact model, not by size: a 7.5-inch colour
photo frame or a three-colour (B) panel is not the recommended black-and-white v2 panel.

## chunk: r16
- rule: R16 SENSOR_HUMIDITY
- human_check: never
- on_failure: FAIL, then swap to a BME280
- sources: kb://esp32_weather_epd#l59_sensor, kb://electrical_notes#bosch_bme280

The sensor must measure humidity. A BMP280 measures only pressure and temperature, so it is rejected.

## chunk: r17
- rule: R17 EPD_ADAPTER
- human_check: conditional (a Waveshare HAT needs a setup check)
- on_failure: WARN, plus a setup note
- sources: kb://esp32_weather_epd#l58_adapter, kb://esp32_weather_epd#l138_l142_adapter_notes

Prefer the DESPI-C02 adapter. A Waveshare HAT gets a warning, because the README does not recommend rev 2.2 and
2.3 HATs, and a note on its extra PWR pin.
