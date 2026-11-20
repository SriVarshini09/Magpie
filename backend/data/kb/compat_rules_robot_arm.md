---
doc_id: compat_rules_robot_arm
title: Rule pack robot_arm (SO-101): rule texts and their sources
kind: rule_source
licence: our rule texts; sources cited per chunk
build_type: robot_arm
---

# Pack `robot_arm` (PLAN §3.8)

One chunk per rule. The code is A's `rules/robot_arm.py`; these rows are what each Check cites. "Human check"
means the rule never renders as a bare pass.

## chunk: r1
- rule: R1 PSU_VOLTAGE_MATCH
- sources: kb://so101_readme#L73, kb://sts3215#voltage_classes
- human_check: no
- fix: swap the PSU to the matching voltage

7.4V STS3215 servos run from a 5V supply (as the README's own BOM does); 12V STS3215 servos need a 12V supply.
Checked at BOM level, before any PSU offer is chosen, so the 12V choice fails here and the fix searches for a
12V supply.

## chunk: r2
- rule: R2 PSU_CURRENT_MIN
- sources: kb://so101_readme#L73
- human_check: no
- fix: search PSUs with amps >= 5

The 12V build needs a supply of at least 5 A ("12V 5A+"). For the 5V build the README states no rating, so no
stall-current arithmetic is done without a datasheet value.

## chunk: r3
- rule: R3 SERVO_VARIANT
- sources: kb://so101_readme#L96, kb://so101_readme#L79_81, kb://sts3215#leader_variants
- human_check: no
- fix: replace with C001 (or C018 for the 12V build)

The follower arm uses six C001 (1/345) servos. C044 and C046 are leader-arm variants and are rejected.

## chunk: r4
- rule: R4 SERVO_COUNT
- sources: kb://sts3215#follower_variant
- human_check: no
- fix: set the quantity to 6

The servo quantity equals the servo mesh instances in the URDF (6).

## chunk: r5
- rule: R5 BUS_PROTOCOL
- sources: kb://waveshare_adapter#bus_protocol, kb://sts3215#bus_not_pwm
- human_check: no
- fix: reject other boards

The controller must be a serial bus servo adapter for Feetech ST/SC servos, not a PWM driver or the Driver HAT.

## chunk: r6
- rule: R6 BARREL_PLUG
- sources: kb://waveshare_adapter#dc_jack
- human_check: when the plug is shown only in a photo
- fix: filter PSUs by plug size; otherwise warn

The PSU plug is 5.5×2.1 mm, matching the board's DC jack. An instance of G5 with this project's source.

## chunk: r7
- rule: R7 NO_MIXED_VOLTAGE
- sources: kb://sts3215#voltage_classes
- human_check: no
- fix: align all servos to the chosen class

All servos on one bus share a voltage class. Derived from R1.

## chunk: r8
- rule: R8 USB_DATA
- sources: kb://so101_readme#L98
- human_check: yes, unless the listing says it carries data
- fix: prefer listings that state data transfer

The USB-C cable must carry data, not only charge.

## chunk: r9
- rule: R9 PACK_COVERS_QTY
- sources: arithmetic
- human_check: no
- fix: add single units

The units in the chosen packs add up to at least the required quantity (a 5-pack plus a single covers 6).

## chunk: r10
- rule: R10 BOARD_INPUT_VOLTAGE
- sources: kb://so101_readme#L73, kb://waveshare_adapter#input_voltage
- human_check: always
- fix: none

The sources disagree: the README runs 7.4V servos from 5V; the Waveshare wiki says the adapter takes 9 to 12.6 V
and should match the servo voltage. WARN "needs your check", citing both rows. Shown honestly on stage.

## chunk: r11
- rule: R11 PLUG_AND_MAINS
- sources: kb://store_policies#us_only
- human_check: no
- fix: filter them out; log each rejection

The PSU has a US plug and 120 V input, and the seller ships from the US in USD. Catalog results include UK-plug,
220 V and Australian sellers. An instance of G1 for mains input.
