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
| Far sensor TRIG | `3` | `J3-14` | direct from ESP32 output |
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
| Side B red LED | `38` | `J3-11` | tested exposed output pin |
| Side B yellow LED | `39` | `J3-10` | tested exposed output pin |
| Side B green LED | `40` | `J3-9` | tested exposed output pin |

## Optional INA219 Energy Measurement Wiring

Use this only when measuring current consumption. It does not change the ultrasonic or LED wiring.

| INA219 Function | ESP32 GPIO / Header | Note |
| --- | --- | --- |
| VCC | `3V3` / `J3-2` or `J3-3` | use `3.3V` so I2C logic is ESP32-safe |
| GND | `GND` / `J3-1` or `J2-1` | common ground with the measured node |
| SDA | `GPIO41` / `J3-8` | optional INA219 I2C data |
| SCL | `GPIO42` / `J3-7` | optional INA219 I2C clock |
| VIN+ | power-source positive | high-side current input |
| VIN- | node `5V` input | output from INA219 to the measured node |

Current path:

```text
power bank +5V  -> INA219 VIN+
INA219 VIN-    -> measured node 5V
power bank GND -> measured node GND and INA219 GND
```

Do not connect `VIN+` and `VIN-` across `5V` and `GND`; the INA219 must be in series with the positive supply line. If the current is negative, swap `VIN+` and `VIN-`.

If the board is also connected to a normal USB cable, USB `5V` may power the board around the INA219. For a valid measurement, put the INA219 in series with the actual `5V` supply path or use a data-only USB connection while the `5V` supply passes through INA219.

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

- `GPIO3` is on `J3-14`
- `GPIO4` is on `J3-15`
- `GPIO5` is on `J3-16`
- `GPIO6` is on `J3-17`
- `GPIO7` is on `J3-18`
- `GPIO33` is on `J2-12`
- `GPIO34` is on `J2-11`
- `GPIO35` is on `J2-10`
- `GPIO38` is on `J3-11`
- `GPIO39` is on `J3-10`
- `GPIO40` is on `J3-9`
- `GPIO41` is on `J3-8`
- `GPIO42` is on `J3-7`

This means the current ultrasonic sensor mapping is physically accessible on `J3`, the side-A LED mapping is physically accessible on `J2`, and the side-B LED mapping is physically accessible on `J3`.

## Bench-Test Notes

- Because Node A and Node B are different boards, reusing the same GPIO numbers for the two sensor pairs is acceptable.
- Keep the LED resistors on Node B only, because Node B currently drives both traffic-light heads.
- Do not connect a `5V` ultrasonic echo pin directly to an ESP32 input.
- For each `HC-SR04 ECHO` line on `GPIO5` and `GPIO7`, use a voltage divider or a proper logic-level shifter if the sensor outputs `5V`.
- `TRIG` does not need a voltage divider because it is driven by the ESP32.
- The current firmware already maps LEDs to exposed `J2` header pins in [HardwareMap.h](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/firmware/shared/HardwareMap.h).
- The firmware can optionally print INA219 power readings when an INA219 is connected on `GPIO41/GPIO42`.

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
