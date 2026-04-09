# Bench-Test Hardware Map

This file freezes the current bench-test wiring plan for the real ESP32 implementation.

It is the source of truth for Step 1: choose one wiring map and keep the code and the physical setup aligned.

## Hardware Assumption

- Board: `Heltec WiFi LoRa 32 V3 (ESP32-S3)`
- Sensors: `HC-SR04`
- Traffic lights: `6 LEDs`
- Communication: LoRa uses the board's onboard `SX1262` radio in the current software design
- Header reference used here: [esp_datasheet.png](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/esp_datasheet.png)

## Current Firmware Roles

- `Node A`: reads side A far/near ultrasonic sensors and sends telemetry
- `Node B`: reads side B far/near ultrasonic sensors, receives Node A telemetry, and drives both traffic-light heads

This matches the current firmware design.

## Node A Wiring

Side A sensing node:

| Function | GPIO | Header | Note |
| --- | --- | --- | --- |
| Far sensor TRIG | `4` | `J3-15` | direct from ESP32 output |
| Far sensor ECHO | `5` | `J3-16` | use voltage divider or level shifter if sensor ECHO is `5V` |
| Near sensor TRIG | `6` | `J3-17` | direct from ESP32 output |
| Near sensor ECHO | `7` | `J3-18` | use voltage divider or level shifter if sensor ECHO is `5V` |

## Node B Wiring

Side B sensing + controller node:

| Function | GPIO | Header | Note |
| --- | --- | --- | --- |
| Far sensor TRIG | `4` | `J3-15` | direct from ESP32 output |
| Far sensor ECHO | `5` | `J3-16` | use voltage divider or level shifter if sensor ECHO is `5V` |
| Near sensor TRIG | `6` | `J3-17` | direct from ESP32 output |
| Near sensor ECHO | `7` | `J3-18` | use voltage divider or level shifter if sensor ECHO is `5V` |
| Side A red LED | `33` | `J2-12` | tested exposed output pin |
| Side A yellow LED | `34` | `J2-11` | tested exposed output pin |
| Side A green LED | `35` | `J2-10` | tested exposed output pin |
| Side B red LED | `36` | `J2-9` | tested exposed output pin |
| Side B yellow LED | `47` | `J2-13` | tested exposed output pin |
| Side B green LED | `48` | `J2-14` | tested exposed output pin |

## Source In Code

These pins are now defined in:

- `firmware/shared/HardwareMap.h`

The node firmware reads from that file instead of using hard-coded pins in each `main.cpp`.

## Onboard LoRa Radio Pins

The shared LoRa transport is configured for the Heltec V3 onboard radio:

| Function | GPIO |
| --- | --- |
| LoRa CS | `8` |
| LoRa SCK | `9` |
| LoRa MOSI | `10` |
| LoRa MISO | `11` |
| LoRa RESET | `12` |
| LoRa BUSY | `13` |
| LoRa DIO1 / IRQ | `14` |

## J2 And J3 Notes From The Datasheet

From [esp_datasheet.png](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/esp_datasheet.png):

- `GPIO4` is on `J3-15`
- `GPIO5` is on `J3-16`
- `GPIO6` is on `J3-17`
- `GPIO7` is on `J3-18`
- `GPIO33` is on `J2-12`
- `GPIO34` is on `J2-11`
- `GPIO35` is on `J2-10`
- `GPIO36` is on `J2-9`
- `GPIO47` is on `J2-13`
- `GPIO48` is on `J2-14`

This means the current ultrasonic sensor mapping is physically accessible on `J3`, and the current tested LED mapping is physically accessible on `J2`.

## Bench-Test Notes

- Because Node A and Node B are different boards, reusing the same GPIO numbers for the two sensor pairs is acceptable.
- Keep the LED resistors on Node B only, because Node B currently drives both traffic-light heads.
- Do not connect a `5V` ultrasonic echo pin directly to an ESP32 input.
- For each `HC-SR04 ECHO` line on `GPIO5` and `GPIO7`, use a voltage divider or a proper logic-level shifter if the sensor outputs `5V`.
- `TRIG` does not need a voltage divider because it is driven by the ESP32.
- The current firmware already maps LEDs to exposed `J2` header pins in [HardwareMap.h](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/firmware/shared/HardwareMap.h).

## What This Step Solves

After this step:

- the code and wiring plan use the same pin map
- the team can wire the prototype consistently
- future changes to pins are made in one place only

## Next Step

Step 2 is to make `Node B` work as a standalone real bench test:

- read its two local sensors
- print the measured distances and occupancy states
- drive the six LEDs according to the controller output
