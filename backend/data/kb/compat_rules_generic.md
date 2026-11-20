---
doc_id: compat_rules_generic
title: Generic electrical rule pack (G1-G11): rule texts and sources
kind: rule_source
licence: written by the team (rule texts); sources cited per rule as kb:// rows
---

# Pack `generic_electrical`

Runs on every build (PLAN §3.8). Rules read attributes parsed from the listing description first, then the
title, then the template row. A missing attribute never passes: the result is "needs your check" with the
attribute named. Rule-of-thumb template rows only make a rule warn. Code: `backend/app/rules/generic_electrical.py`.

## chunk: g1
- rule: G1 SUPPLY_VOLTAGE (MVP)
- human_check: conditional (when the range comes only from a listing title, or a part states a voltage class and no range)
- on_failure: FAIL, then search a supply inside the range
- sources: kb://electrical_notes#arduino_uno_vin, kb://electrical_notes#esp32_devkitc_power, kb://electrical_notes#hcsr04_working, kb://electrical_notes#am2302_dht22

The supply or battery voltage must lie inside every powered part's stated input range. A battery is checked
from nominal (3.7 V per cell) to full charge (4.2 V per cell).

## chunk: g2
- rule: G2 CURRENT_BUDGET
- human_check: conditional (always when any load current is unknown: the sum is shown as "at least X A")
- on_failure: WARN with the sum and the limit
- sources: kb://electrical_notes#hcsr04_working, kb://electrical_notes#donkeycar_battery_pack

The sum of known load currents must stay at or under 80% of a supply's rating; for a battery, under its capacity
in amp-hours times its C rating.

## chunk: g3
- rule: G3 CELL_COUNT (MVP)
- human_check: never
- on_failure: FAIL, then pick a battery inside the range
- sources: kb://electrical_notes#lipo_cell_voltage, kb://electrical_notes#dfrobot_ph2_power, kb://electrical_notes#px4_f450_esc

The battery's cell count must lie inside the range the ESC, flight controller, driver or board states, such as
"3-4S".

## chunk: g4
- rule: G4 LOGIC_LEVEL
- human_check: always (we know board families, not every breakout)
- on_failure: WARN, and propose a logic level shifter line as an assumption until the user confirms it
- sources: kb://electrical_notes#espressif_esp32_input, kb://electrical_notes#espressif_gpio_faq, kb://electrical_notes#arduino_uno_ioref

A 5 V output must not drive a 3.3 V-only input without a level shifter or divider in the BOM.

## chunk: g5
- rule: G5 CONNECTOR_MATCH (MVP)
- human_check: conditional (when a listing shows the plug only in a photo: the connector is then unknown)
- on_failure: FAIL, then filter offers to the matching connector or add an adapter line
- sources: kb://electrical_notes#jst_ph_pitch, kb://electrical_notes#jst_xh_pitch, kb://electrical_notes#jst_sh_pitch, kb://electrical_notes#px4_x500_connectors, kb://electrical_notes#waveshare_barrel

Mating connectors must share family and pitch: JST-XH 2.5 mm, JST-PH 2.0 mm, JST-SH 1.0 mm; XT30 and XT60 are
different; a 5.5 x 2.1 mm barrel is not a 5.5 x 2.5 mm barrel.

## chunk: g6
- rule: G6 CONNECTOR_CURRENT
- human_check: conditional (always for XT30, whose figure is second-hand)
- on_failure: WARN
- sources: kb://electrical_notes#holybro_connector_table, kb://electrical_notes#amass_xt60_sheet, kb://electrical_notes#xt30_rating, kb://electrical_notes#jst_ratings

The expected continuous current must stay at or under the connector's rating: XT60 30 A (60 A burst), XT30 15 A
(30 A burst, unverified), JST-XH 3 A, PH 2 A, SH 1 A.

## chunk: g7
- rule: G7 KV_PROP_CELLS (MVP, WARN only)
- human_check: always (a rule of thumb; the chip says so)
- on_failure: WARN "outside the usual range"
- sources: kb://electrical_notes#oscarliang_motors_kv, kb://electrical_notes#px4_x500_motor_kv, kb://electrical_notes#holybro_x500_kv, kb://electrical_notes#no_3inch_source

Motor KV should suit the prop size and cell count: 5-inch props take about 2300-2800 KV on 4S or 1600-2100 KV on
6S; 10-inch (1045) props about 880-920 KV on 4S. No source was read for 3-inch props.

## chunk: g8
- rule: G8 ESC_CURRENT
- human_check: conditional (when the motor's maximum current is not in the listing, which is common)
- on_failure: FAIL when both numbers are known
- sources: kb://electrical_notes#px4_x500_esc

The ESC's continuous current must be at least the motor's maximum current; the ESC's cell range must include the
battery (checked by G3).

## chunk: g9
- rule: G9 DRIVER_CURRENT
- human_check: conditional (when the motor's stall current is not listed)
- on_failure: FAIL when both numbers are known
- sources: kb://electrical_notes#st_l298, kb://electrical_notes#toshiba_tb6612fng

A motor driver's current per channel must be at least the motor's stall current, and the driver's supply range
must include the battery voltage.

## chunk: g10
- rule: G10 SERVO_SUPPLY
- human_check: conditional (always for SG90-class numbers, which have no official sheet)
- on_failure: WARN, and propose a separate 5-6 V servo supply
- sources: kb://electrical_notes#donkeycar_servo_rail, kb://electrical_notes#sts3215_classes, kb://electrical_notes#sg90_range

The servo supply must lie inside the servo's range, and servos are powered from their own rail, not from the
controller's logic pin.

## chunk: g11
- rule: G11 PIN_CURRENT
- human_check: always (the 20 mA figure is from reseller copies of the spec table)
- on_failure: WARN
- sources: kb://electrical_notes#arduino_pin_current

No motor, servo or relay coil may be driven straight from a GPIO pin: use the driver in the BOM.

## chunk: g12
- rule: G12 STACK_MOUNT
- human_check: conditional (the pattern is read from the listing title; a listing that names none is not judged)
- on_failure: FAIL (the listing is rejected)
- sources: kb://electrical_notes#fpv_stack_mounting

Boards that share one stack (flight controller, ESC, VTX) share its mounting pattern: 20x20, 25.5x25.5 or 30x30 mm.
A listing for another pattern is rejected for that line.
