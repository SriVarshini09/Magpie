---
doc_id: waveshare_adapter
title: Waveshare Bus Servo Adapter (A) wiki notes
kind: rule_source
source_url: https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
licence: Waveshare wiki; licence not stated [unverified]; short quotes, cited, no text copied
build_type: robot_arm
---

# Waveshare Bus Servo Adapter (A)

Read on the Waveshare wiki on Nov 19 (check C9). The exact URL path above is how the wiki names the page;
the path itself was not recorded that night [unverified]. Quotes are short and exact.

## chunk: input_voltage
- source: https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- licence: Waveshare wiki [unverified]; short quote
- rules: R10
- quote: "9~12.6V (should match servo voltage)"
- checked: Nov 19

The wiki gives the board's power input as 9 to 12.6 V and says it should match the servo voltage. This disagrees
with the SO-ARM100 README, which runs 7.4V servos from a 5V supply (kb://so101_readme#L73). R10 does not pick a
side: it warns "needs your check" and cites both rows.

## chunk: dc_jack
- source: https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- licence: Waveshare wiki [unverified]; facts only
- rules: R6, G5
- quote: "5.5×2.1"
- checked: Nov 19

Power enters through a 5.5×2.1 mm DC barrel jack, so the supply's plug must be 5.5×2.1 mm (a 5.5×2.5 mm plug is
the usual look-alike that fits loosely or not at all).

## chunk: bus_protocol
- source: https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- licence: Waveshare wiki [unverified]; facts only
- rules: R5
- checked: Nov 19

The adapter drives Feetech ST/SC serial bus servos over a daisy chain. Waveshare also sells a "Driver HAT (A)"
that appears in the same catalog searches; it is a different board and is rejected for this line (R5).
