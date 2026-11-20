---
doc_id: so101_readme
title: SO-ARM100 README: SO-101 follower-arm excerpts with line numbers
kind: doc
source_url: https://github.com/TheRobotStudio/SO-ARM100
commit_sha: a758567c3978dfeefe282ede0500085a48fe8f78
licence: Apache-2.0 (LICENSE read); short quotes, cited
build_type: robot_arm
---

# SO-ARM100 README (pinned to commit a758567)

Line numbers are lines of README.md at the pinned commit, the same bytes as
`backend/fixtures/sources/SO-ARM100_README.md`. At run time the README is fetched live (through Airbyte)
and every `readme_quote` is checked against those bytes; these rows are what the rules and the
part panel cite. Quotes are short and exact; the sentences under them are our own words.

## chunk: L73
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L73
- readme_lines: 73
- quote: "you will also have to buy a 12V 5A+ power supply instead of a 5V one"
- quote: "The 12V version has a stall torque of 30kg.cm"
- rules: R1, R2, R7, R10
- checked: Nov 19

The follower arm's STS3215 servos come in a 7.4V class and a 12V class. The README says the 7.4V servos
were enough for its authors and are run from a 5V supply; anyone who picks the 12V servos must also buy a
12V supply rated 5 A or more instead of the 5V one. The leader arm is always 7.4V. The 12V link in this
line points at Alibaba, which is outside every preset mandate (a refusal, not an offer).

## chunk: L96
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L96
- readme_lines: 96
- quote: "STS3215 Servo 7.4V, 1/345 gear (C001)"
- rules: R3, R4
- checked: Nov 19

The one-follower-arm table lists six STS3215 7.4V servos with the 1/345 gear, variant C001, at $13.89 each.

## chunk: L79_81
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L79-L81
- readme_lines: 79-81
- quote: "STS3215 Servo 7.4V, 1/191 gear (C044)"
- quote: "STS3215 Servo 7.4V, 1/147 gear (C046)"
- rules: R3
- checked: Nov 19

The two-arm table adds the 1/191 (C044) and 1/147 (C046) gear variants. Those belong to the leader arm; the
follower arm uses only C001 (or the 12V C018 class). A C044 or C046 listing is a variant mismatch for the follower.

## chunk: L97
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L97
- readme_lines: 97
- quote: "Motor Control Board"
- rules: R5, R10
- checked: Nov 19

One motor control board per arm, $10.6 in the README; its link is the Waveshare bus servo adapter on Amazon.

## chunk: L98
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L98
- readme_lines: 98
- quote: "USB-C Cable 2 pcs"
- rules: R8
- checked: Nov 19

One pack of two USB-C cables per arm. Whether a listed cable carries data is not in the README: rule R8 asks
for a human check unless the listing says data.

## chunk: L99
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L99
- readme_lines: 99
- quote: "Power Supply"
- rules: R1, R6, R10
- checked: Nov 19

The follower table lists one power supply at $10. The table itself states no voltage or current; line 73 is
where the README says the 7.4V servos run from a 5V supply. The linked listing's URL names a 5.5x2.1 mm plug
(a hint only: the listing itself was not read, Amazon is never requested).

## chunk: L100
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L100
- readme_lines: 100
- quote: "Table Clamp 2pcs"
- checked: Nov 19

One pack of two table clamps per follower arm.

## chunk: L102
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L102
- readme_lines: 102
- quote: "$121.94"
- checked: Nov 19

The README's stated total for one follower arm, before shipping and tax, at its own (mostly Alibaba and Amazon) links.

## chunk: L104
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L104
- readme_lines: 104
- quote: "phillips head screw driver sizes #0 and #1"
- checked: Nov 19

A Phillips #0 and #1 screwdriver is recommended; the exact set does not matter. Usually already owned (memory).

## chunk: L112
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L112
- readme_lines: 112
- quote: "Material: PLA+"
- checked: Nov 19

Printing guidance for the arm's parts starts with PLA+ as the material.

## chunk: L136
- source: https://github.com/TheRobotStudio/SO-ARM100/blob/a758567c3978dfeefe282ede0500085a48fe8f78/README.md#L136
- readme_lines: 136
- quote: "contained in a **single file**"
- checked: Nov 19

All printed parts for the leader or the follower are in one print file, so the BOM carries them as one grouped
"3D-printed parts" line that is printed at home rather than bought.
