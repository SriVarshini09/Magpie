---
doc_id: electrical_notes
title: Electrical notes: datasheet lines behind the generic rule pack
kind: rule_source
licence: mixed; per chunk (short quotes, cited; no text copied beyond the quote)
---

# Electrical notes

One chunk per source line in PLAN §3.8 (pack `generic_electrical`) and §13.3 (pack `mcu_battery`).
Quotes are the short excerpts PLAN records; "unverified" means the figure or the exact URL was not
read by us and the rule that uses it asks for a human check.

## chunk: arduino_uno_vin
- source: https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf
- licence: Arduino datasheet; short quote, cited
- rules: G1
- quote: "7 – 12 V"
- checked: Nov 20

The Arduino Uno R3 datasheet gives the VIN input range as 7 to 12 volts. A supply or battery outside that
window fails G1 for the Uno.

## chunk: esp32_devkitc_power
- source: https://docs.espressif.com/projects/esp-idf/en/stable/esp32/hw-reference/esp32/get-started-devkitc.html
- licence: Espressif documentation; short quote, cited
- rules: G1
- quote: "one and only one of the options"
- checked: unverified (exact URL not recorded in PLAN)

The ESP32-DevKitC guide lists three ways to power the board (micro-USB, the 5V pin, the 3V3 pin) and says to
use exactly one of them at a time.

## chunk: hcsr04_working
- source: https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf
- licence: module datasheet; short quote, cited
- rules: G1, G2
- quote: "Working Voltage DC 5 V"; "Working Current 15mA"
- checked: unverified (exact URL not recorded in PLAN)

The HC-SR04 ultrasonic module works at 5 volts and draws about 15 milliamps. G1 reads the voltage, G2 adds the
current to the load budget.

## chunk: am2302_dht22
- source: https://cdn-shop.adafruit.com/datasheets/Digital+humidity+and+temperature+sensor+AM2302.pdf
- licence: sensor datasheet; short quote, cited
- rules: G1
- quote: "3.3-5.5V DC"
- checked: unverified (exact URL not recorded in PLAN)

The AM2302 (DHT22) humidity and temperature sensor accepts 3.3 to 5.5 volts.

## chunk: donkeycar_battery_pack
- source: https://docs.donkeycar.com/guide/build_hardware/
- licence: Donkey Car docs; licence unverified (code is MIT); short quote, cited
- rules: G2, G3
- quote: "1800mAh 2S 20C"
- checked: Nov 20

The battery pack the Donkey Car build guide links is a two-cell LiPo of 1800 mAh rated 20C, so its
discharge limit is about 1.8 Ah x 20 = 36 A.

## chunk: dfrobot_ph2_power
- source: https://wiki.dfrobot.com/FireBeetle_Board_ESP32_E_SKU_DFR0654
- licence: DFRobot wiki; short quote, cited
- rules: G3, R12, R13
- quote: "PH2.0 Connector: 3.7~4.2V Li-ion"
- checked: Nov 19

The FireBeetle 2 ESP32-E power table names a JST-PH 2.0 battery connector for a single Li-ion cell
(3.7 V nominal, 4.2 V full). A 2S pack or a different plug does not fit this board.

## chunk: px4_f450_esc
- source: https://docs.px4.io/
- licence: PX4 user guide, CC BY 4.0; short quote, cited
- rules: G3
- quote: none (PLAN gives the excerpt "20A … 3-4S", not an exact line)
- checked: unverified (PLAN cites "the PX4 F450 page"; the exact page URL is not recorded)

The ESC lines on the PX4 F450 build page state a 20 A ESC for 3S to 4S batteries: the ESC's cell range is what
G3 checks the battery against.

## chunk: lipo_cell_voltage
- source: https://oscarliang.com/lipo-battery-guide/
- licence: not an open licence; fact cited, no text copied
- rules: G3, R13
- quote: none
- checked: Nov 20

One LiPo cell is 3.7 V nominal and 4.2 V when full, so an nS pack spans about 3.7n to 4.2n volts. The rules
convert "14.8V" to 4 cells only when no explicit S count is given.

## chunk: espressif_esp32_input
- source: https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf
- licence: Espressif datasheet; short quote, cited
- rules: G4
- quote: "–0.3 … 3.6 V"
- checked: unverified (exact URL not recorded in PLAN)

The ESP32 datasheet gives the input voltage on a pin as -0.3 to 3.6 volts. A 5 V signal is outside that.

## chunk: espressif_gpio_faq
- source: https://docs.espressif.com/projects/esp-faq/en/latest/
- licence: Espressif FAQ; short quote, cited
- rules: G4
- quote: "The voltage tolerance of GPIO is 3.6 V."
- checked: unverified (exact URL not recorded in PLAN)

Espressif's FAQ confirms the GPIO pins are not 5 V tolerant, so a 5 V output needs a level shifter or divider.

## chunk: arduino_uno_ioref
- source: https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf
- licence: Arduino datasheet; fact cited
- rules: G4
- quote: none
- checked: Nov 20

The Uno's IOREF pin is tied to 5 V: its outputs are 5 V logic.

## chunk: jst_ph_pitch
- source: https://www.jst-mfg.com/product/index.php?series=199&lang=en
- licence: JST product page; short quote, cited
- rules: G5, R12
- quote: "features a pitch of 2.0 mm"
- checked: Nov 19

The JST PH series has a 2.0 mm pitch. "JST 1.25", "Micro JST 1.25", "SH1.25" and "PH1.25" listings are a
1.25 mm pitch and do not mate with a PH 2.0 socket.

## chunk: jst_xh_pitch
- source: https://www.jst-mfg.com/
- licence: JST product pages; fact cited
- rules: G5
- quote: none
- checked: unverified (series page URL not recorded in PLAN)

The JST XH series has a 2.5 mm pitch (often listed as 2.54 mm; same connector).

## chunk: jst_sh_pitch
- source: https://www.jst-mfg.com/
- licence: JST product pages; fact cited
- rules: G5
- quote: none
- checked: unverified (series page URL not recorded in PLAN)

The JST SH series has a 1.0 mm pitch. Sellers' "SH1.25" is not an SH part: it is a 1.25 mm connector.

## chunk: px4_x500_connectors
- source: https://docs.px4.io/v1.14/en/frames_multicopter/holybro_x500V2_pixhawk5x
- licence: PX4 user guide, CC BY 4.0; short quote, cited
- rules: G5
- quote: "XT60 plug for battery & XT30 plug for ESCs & peripherals"
- checked: Nov 20

On the Holybro X500 V2 the power distribution board takes the battery on an XT60 and feeds the ESCs and
peripherals through XT30 plugs. An XT30 does not mate with an XT60.

## chunk: waveshare_barrel
- source: https://www.waveshare.com/wiki/Bus_Servo_Adapter_(A)
- licence: Waveshare wiki; fact cited
- rules: G5
- quote: none
- checked: Nov 19 (page read; exact URL form unverified)

The Waveshare Bus Servo Adapter (A) DC jack takes a 5.5 x 2.1 mm barrel plug. A 5.5 x 2.5 mm plug is a
different size.

## chunk: holybro_connector_table
- source: https://docs.holybro.com/
- licence: Holybro docs; licence unverified; short quote, cited
- rules: G6
- quote: "XT60 | 12 AWG | 30A | 60A"
- checked: Nov 20 (exact page URL not recorded in PLAN)

Holybro's connector table rates the XT60 at 30 A continuous and 60 A burst.

## chunk: amass_xt60_sheet
- source: https://www.amass.com.cn/
- licence: manufacturer sheet; short quote, cited
- rules: G6
- quote: "Current rating 35A"
- checked: Nov 20 (exact sheet URL not recorded in PLAN)

Amass's 2025 XT60 sheet gives 35 A. The rule uses the lower 30 A figure.

## chunk: xt30_rating
- source: none (second-hand figure)
- licence: n/a
- rules: G6
- quote: none
- checked: unverified

XT30 is commonly given as 15 A continuous and 30 A burst. We have not read a primary source for this figure,
so G6 always asks for a human check on an XT30.

## chunk: jst_ratings
- source: https://www.jst-mfg.com/
- licence: JST product pages; fact cited
- rules: G6
- quote: none
- checked: unverified (series page URLs not recorded in PLAN)

Current ratings used by G6: JST-XH 3 A, JST-PH 2 A, JST-SH 1 A per contact.

## chunk: oscarliang_motors_kv
- source: https://oscarliang.com/motors/
- licence: not an open licence; one short quote, cited
- rules: G7
- quote: "1600-2100KV is for 6S, while 2300-2800KV is for 4S"
- checked: Nov 20

For 5-inch props the usual motor KV is 2300 to 2800 on 4S and 1600 to 2100 on 6S. This is a rule of thumb,
not a design: G7 only warns.

## chunk: px4_x500_motor_kv
- source: https://docs.px4.io/v1.14/en/frames_multicopter/holybro_x500V2_pixhawk5x
- licence: PX4 user guide, CC BY 4.0; fact cited
- rules: G7
- quote: "KV880"
- checked: Nov 20

The PX4 X500 V2 page lists 2216 motors at KV880 with 1045 (10-inch) props on 4S.

## chunk: holybro_x500_kv
- source: https://docs.holybro.com/drone-development-kit/px4-development-kit-x500v2
- licence: Holybro docs; licence unverified; fact cited
- rules: G7
- quote: "KV920"
- checked: Nov 20

Holybro's own kit page lists the same motors at KV920. The two sources disagree; both are cited and G7 uses
880-920 KV for 10-inch props on 4S.

## chunk: no_3inch_source
- source: none
- licence: n/a
- rules: G7
- quote: none
- checked: unverified

No source was read for 3-inch props. G7 returns "needs your check" for a 3-inch build instead of a range.

## chunk: px4_x500_esc
- source: https://docs.px4.io/v1.14/en/frames_multicopter/holybro_x500V2_pixhawk5x
- licence: PX4 user guide, CC BY 4.0; short quote, cited
- rules: G8
- quote: "BLHeli S 20A"
- checked: Nov 20

The X500 V2 pairs 2216 motors with 20 A BLHeli S ESCs. G8 checks the ESC's continuous current against the
motor's maximum current when both are stated.

## chunk: st_l298
- source: https://www.st.com/resource/en/datasheet/l298.pdf
- licence: ST datasheet; short quotes, cited
- rules: G9
- quote: "TOTAL DC CURRENT UP TO 4 A"; "SUPPLY VOLTAGE UP TO 46 V"
- checked: unverified (exact URL not recorded in PLAN)

The L298 dual H-bridge handles 2 A DC per channel, 4 A total, on a supply up to 46 V.

## chunk: toshiba_tb6612fng
- source: https://toshiba.semicon-storage.com/
- licence: Toshiba datasheet; short quotes, cited
- rules: G9
- quote: "Iout=1.2A(ave) / 3.2A (peak)"; "VM=15VMax."
- checked: unverified (exact URL not recorded in PLAN)

The TB6612FNG gives 1.2 A average and 3.2 A peak per channel, with a motor supply of at most 15 V.

## chunk: donkeycar_servo_rail
- source: https://docs.donkeycar.com/guide/build_hardware/
- licence: Donkey Car docs; licence unverified (code is MIT); short quote, cited
- rules: G10
- quote: "5v VIN should NOT be provided by the GPIO bus"
- checked: Nov 20

The Donkey Car build guide says the servo driver's 5 V supply must not come from the Raspberry Pi's GPIO
header: servos need their own rail.

## chunk: sts3215_classes
- source: https://github.com/TheRobotStudio/SO-ARM100
- licence: Apache-2.0; short quote, cited
- rules: G10
- quote: "STS3215 Servo 7.4V"
- checked: Nov 19

The SO-ARM100 README lists STS3215 bus servos in a 7.4 V class and a 12 V class. These are voltage classes,
not input ranges, so G1 and G10 ask for a human check when the supply differs from the class.

## chunk: sg90_range
- source: none (no official SG90 sheet found)
- licence: n/a
- rules: G10
- quote: none
- checked: unverified

SG90-class micro servos are commonly given as 4.8 to 6 V. No official sheet was found, so G10 always asks for a
human check on these numbers.

## chunk: arduino_pin_current
- source: https://docs.arduino.cc/hardware/uno-rev3/
- licence: fact cited
- rules: G11
- quote: none
- checked: unverified (reseller copies of the spec table only)

An Arduino Uno I/O pin supplies about 20 mA. That is not enough for a motor, servo or relay coil: use the
driver in the BOM.

## chunk: bosch_bme280
- source: https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/
- licence: Bosch product page; facts cited
- rules: R16
- quote: none
- checked: Nov 19

The Bosch BME280 measures humidity (about ±3% relative humidity), pressure and temperature on a 1.71 to 3.6 V
supply. The BMP280 measures only pressure and temperature.

## chunk: fpv_stack_mounting
- source: listing titles in the mock catalog and the quadcopter template's flight controller row (kb://tpl_quadcopter#fc)
- licence: our own note; no external source was read for this rule
- rules: G12
- checked: Nov 20

FPV flight controllers, ESCs and video transmitters are sold for a stack mounting pattern that the listing names:
commonly 20x20 mm, 25.5x25.5 mm (whoop all-in-one boards) and 30x30 mm (30.5 mm hole spacing). Boards in one
stack share the pattern; a board for another pattern needs an adapter plate. This is a rule of thumb, read from
listing titles.
