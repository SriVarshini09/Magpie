---
doc_id: sts3215
title: Feetech STS3215 bus servo: variants and voltage classes
kind: doc
licence: our notes; facts cited to the SO-ARM100 README (Apache-2.0) and store listings read Nov 19
build_type: robot_arm
---

# Feetech STS3215 notes

What the robot-arm rules need to know about the STS3215, in our own words, each fact cited.
No Feetech datasheet was read; anything a listing alone states is marked as such.

## chunk: voltage_classes
- source: kb://so101_readme#L73
- rules: R1, R7
- checked: Nov 19 (README)

The STS3215 is sold in a 7.4V class and a 12V class. The README runs the 7.4V class from a 5V supply and says
the 12V class needs a 12V supply of at least 5 A. All servos on one bus should share a voltage class (R7,
derived from R1, not stated by Feetech in anything we read).

## chunk: follower_variant
- source: kb://so101_readme#L96
- rules: R3, R4
- checked: Nov 19 (README)

The follower arm uses six servos of variant C001 (7.4V, 1/345 gear). Six is also the servo count in the URDF's
mesh instances (R4).

## chunk: leader_variants
- source: kb://so101_readme#L79_81
- rules: R3
- checked: Nov 19 (README)

C044 (1/191) and C046 (1/147) are leader-arm gear variants. A listing for either is rejected for a follower line.

## chunk: c018_12v
- source: WowRobo store listing, read through Shopify UCP on Nov 19 (variant ids in PLAN Appendix A.2)
- licence: store listing; facts only, no quote
- rules: R1, R3
- checked: Nov 19 (listing; not a datasheet)

The 12V, 30 kg.cm class is sold as variant C018. That variant code comes from store listings (WowRobo's
variant table), not from the README, so a C018 match is a listing fact and the resolver records it as such.

## chunk: bus_not_pwm
- source: kb://waveshare_adapter#bus_protocol
- rules: R5
- checked: Nov 19

The STS3215 is a serial bus servo (Feetech ST series). It is driven by a serial bus servo adapter, not by a PWM
servo driver such as a PCA9685 board.
