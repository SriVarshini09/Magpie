---
doc_id: template_sources
title: Reference designs behind the build-type templates
kind: reference
licence: mixed; per chunk
---

# Reference designs behind the build-type templates (PLAN Appendix B)

One chunk per reference a template cites. Quotes are short and exact, as read on Nov 19-20 and
recorded in PLAN Appendix B, §3.8 and §13.2. The descriptions are our own words. Rows marked
"rule of thumb" in a template are common practice, not a design: they cite a source for the
structure only and feed WARN-only rules. A human reads every template row once before G2.

## chunk: so_arm100_readme
- source: https://github.com/TheRobotStudio/SO-ARM100
- licence: Apache-2.0
- commit: a758567c3978dfeefe282ede0500085a48fe8f78
- used_by: tpl_robot_arm#servo, tpl_robot_arm#controller, tpl_robot_arm#psu, tpl_robot_arm#usb_cable, tpl_robot_arm#clamp, tpl_robot_arm#screwdriver, tpl_robot_arm#printed, tpl_claw_gripper#servo, tpl_claw_gripper#controller, tpl_claw_gripper#psu, tpl_claw_gripper#usb_cable, tpl_claw_gripper#printed, tpl_claw_gripper#clamp
- quote: "STS3215 Servo 7.4V, 1/345 gear (C001)"
- quote: "12V 5A+ power supply"
- quote: "The 12V version has a stall torque of 30kg.cm"
- quote: "5V power supply"
- quote: "Motor Control Board"
- quote: "USB-C Cable 2 pcs"
- quote: "Table Clamp 2pcs"
- quote: "phillips head screw driver sizes #0 and #1"
- quote: "Material: PLA+"
- checked: Nov 19 (every quote is an exact substring of the README in backend/fixtures/sources)

The README's parts table for one follower arm lists six 7.4V STS3215 servos with the 1/345 gear,
one motor control board, a 5V power supply, a USB-C cable pack, a table clamp pack and a
screwdriver set, with a stated total of $121.94. A note says the 12V servo version needs a 12V
supply of at least 5 A instead of the 5V one. The printing section gives PLA+ at 15% infill.
The gripper template derives single-gripper quantities from this arm list.

## chunk: lerobot_so101_docs
- source: https://huggingface.co/docs/lerobot/so101
- licence: [unverified]; cited, not copied
- used_by: tpl_claw_gripper#servo, tpl_claw_gripper#printed
- checked: Nov 20

The LeRobot SO-101 guide covers assembling the arm, including the gripper as motor ID 6 at the
end of the chain. The gripper is not sold or listed as a BOM of its own.

## chunk: px4_x500_v2
- source: https://docs.px4.io/v1.14/en/frames_multicopter/holybro_x500V2_pixhawk5x
- licence: CC BY 4.0
- used_by: tpl_quadcopter (structure of every row), tpl_quadcopter#esc, tpl_quadcopter#pdb, tpl_quadcopter#battery (x500 variant)
- quote: "XT60 plug for battery & XT30 plug for ESCs & peripherals"
- quote: "BLHeli S 20A"
- quote: "Holybro recommends a 4S 5000mAh"
- checked: Nov 20 (attribution of the "Holybro recommends" line to this page: confirm on the human read)

The PX4 build page for the Holybro X500 V2 lists the parts a quadcopter needs (frame, four 2216
motors with 1045 propellers, four ESCs, a Pixhawk flight controller, power distribution with a
power module, a 4S battery, GPS, telemetry radio and an RC receiver that is not in the kit). It
gives the motor KV as 880. It is the structural source for every quadcopter row; the 3-inch and
5-inch numbers do not come from it.

## chunk: holybro_x500v2_kit
- source: https://docs.holybro.com/drone-development-kit/px4-development-kit-x500v2
- licence: [unverified]; cited, not copied
- used_by: tpl_quadcopter#motor (x500 variant), tpl_quadcopter#battery (x500 variant)
- checked: Nov 20

Holybro's own kit page gives the same motors as KV920, which disagrees with the PX4 page's KV880;
the template cites both and the KV rule only warns. It gives a 4S battery range of 2000 to 5000 mAh.

## chunk: oscarliang_motors
- source: https://oscarliang.com/motors/
- licence: not an open licence; cited, short quote
- used_by: tpl_quadcopter#motor (5in variant)
- quote: "1600-2100KV is for 6S, while 2300-2800KV is for 4S"
- checked: Nov 20

A guide to FPV motors. Its KV guidance for 5-inch props per cell count is a rule of thumb, not a
design. No open-licence 5-inch or 3-inch FPV parts list was found, and no source was read for the
3-inch numbers.

## chunk: donkeycar_build_hardware
- source: https://docs.donkeycar.com/guide/build_hardware/
- licence: MIT (code); docs licence [unverified]
- used_by: tpl_rc_car#chassis, tpl_rc_car#sbc, tpl_rc_car#sd, tpl_rc_car#camera, tpl_rc_car#servo_driver, tpl_rc_car#usb_battery, tpl_rc_car#jumpers, tpl_rc_car#printed, tpl_rc_car#screws, tpl_rc_car#lipo
- quote: "Magnet Car or alternative"
- quote: "5v VIN should NOT be provided by the GPIO bus"
- quote: "Anker 10,000 maH"
- quote: "1800mAh 2S 20C"
- quote: "Raspberry Pi 5B 8GB"
- quote: "Wide Angle Raspberry Pi Camera"
- quote: "Female to Female"
- quote: "64GB"
- quote: "3D printed"
- quote: "M2x6"
- checked: Nov 20 (the last six strings are PLAN B.3's transcription of the parts list "as the docs state it"; confirm their exact wording on the page during the human read)

The Donkey Car hardware guide lists a 1/16 RC car, a Raspberry Pi, a microSD card, a wide-angle
camera, a PCA9685 servo driver wired over I2C (throttle on channel 0, steering on channel 1), a
USB power bank, jumper wires, a printed roll cage and top plate, and M2 and M3 screws. It warns
that the servo driver's 5 V must not come from the Pi's GPIO. The linked optional LiPo is a 2S pack.

## chunk: donkeycar_supported_cars
- source: https://docs.donkeycar.com/cars/supported_cars/
- licence: MIT (code); docs licence [unverified]
- used_by: tpl_rc_car#chassis
- checked: Nov 20

The supported-cars page names the Magnet and alternatives at 1/16 scale. It does not state the
chassis battery voltage, the ESC or the steering servo specs, so those template attributes are
null, never guessed.

## chunk: arduino_uno_r3_datasheet
- source: https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf
- licence: [unverified]; cited, short quote
- used_by: tpl_electronics_mcu#mcu
- quote: "7 – 12 V"
- checked: Nov 20

The Arduino Uno R3 datasheet gives the board's recommended VIN range and its 5 V logic level.

## chunk: kiwi_arduino_starter_kit
- source: https://www.kiwi-electronics.com/en/educational-kits-288/arduino-starter-kit-736
- licence: [unverified]; reseller listing, cited, not copied
- used_by: tpl_electronics_mcu#breadboard, tpl_electronics_mcu#jumpers, tpl_electronics_mcu#sensor, tpl_electronics_mcu#display, tpl_electronics_mcu#actuator, tpl_electronics_mcu#passives, tpl_electronics_mcu#battery
- checked: Nov 20 (unverified against Arduino's own page, which refused automated requests)

A reseller's listing of the Arduino Starter Kit K000007 contents: a breadboard, jumper wires,
sensors (TMP36, tilt, phototransistors), a 16×2 LCD, a small servo, a DC motor with an L293D
driver, LEDs, resistors, pushbuttons, potentiometers and a 9 V battery snap. The template uses it
as rule-of-thumb rows only.

## chunk: esp32_weather_epd_readme
- source: https://github.com/lmarzen/esp32-weather-epd
- licence: GPL-3.0 (parts list read; no code used)
- commit: c78ad15e7933684fb5af19168f6e2da003e08b84
- used_by: tpl_electronics_mcu#mcu, tpl_electronics_mcu#display, tpl_electronics_mcu#adapter, tpl_electronics_mcu#sensor, tpl_electronics_mcu#battery, tpl_electronics_mcu#jumpers (esp32_epaper variant)
- quote: "FireBeetle 2 ESP32-E"
- quote: "Waveshare 7.5in e-paper (v2)"
- quote: "DESPI-C02"
- quote: "BME280"
- quote: "3.7V LiPo w/ JST-PH2.0 connector"
- quote: "Wires ("Jumper Wires" if looking to minimize/avoid soldering)."
- checked: Nov 19 (README L56-L67 and L75; on a link run the README itself is fetched and quote-checked)

The project's parts table lists a FireBeetle 2 ESP32-E, a 7.5-inch Waveshare e-paper panel (from
its panel support table), a DESPI-C02 adapter, a BME280 sensor and a single-cell 3.7 V LiPo with a
JST-PH 2.0 plug, plus wires, a soldering iron and a computer. We read the parts list and use none
of the project's code.
