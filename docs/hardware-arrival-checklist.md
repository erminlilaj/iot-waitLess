# Hardware Arrival Checklist

Use this checklist when the boards and components arrive.

The goal is to make bring-up repeatable and avoid losing time on obvious setup mistakes.

## Before Powering Anything

- [ ] confirm both boards are the expected `Heltec WiFi LoRa 32 V3`
- [ ] confirm you have `4` ultrasonic sensors
- [ ] confirm you have `6` LEDs and `6` current-limiting resistors
- [ ] confirm jumper wires and breadboards are available
- [ ] confirm you have a safe `ECHO` level-shifting method if the ultrasonic sensors output `5V`
- [ ] confirm USB cables support data, not only charging

## Software Preparation

- [ ] install PlatformIO
- [ ] open the project and confirm `platformio.ini` is detected
- [ ] verify the selected board target is `heltec_wifi_lora_32_V3`
- [ ] verify LoRa frequency in `firmware/shared/ProjectConfig.h`
- [ ] recheck the pin map in `docs/hardware-map.md`

## First Flash

- [ ] build and flash `node_a`
- [ ] build and flash `node_b`
- [ ] open both serial monitors at `115200`
- [ ] confirm both nodes print their startup pin map
- [ ] confirm Node B runs the LED self-test

## Safety Check

- [ ] no ultrasonic `ECHO` pin is connected directly at `5V` into the ESP32
- [ ] no LED is connected without a resistor
- [ ] the board does not reset repeatedly after power-up
- [ ] the board does not get unusually hot

## Step-by-Step Bring-Up Order

1. `Node B` only
   - [ ] verify LED self-test
   - [ ] set `log summary`
   - [ ] verify local sensor logs
   - [ ] run `remote_queue 3`
   - [ ] verify controller logs change
   - [ ] run `report` and paste the output into `docs/test-results-log.md`

2. `Node A` only
   - [ ] run emulation mode
   - [ ] set `log summary`
   - [ ] verify summary lines contain `payload=A,...`
   - [ ] verify queue counts change as expected
   - [ ] run `report` and paste the output into `docs/test-results-log.md`

3. Two-node serial emulation
   - [ ] copy a Node A summary line containing `payload=A,...` into Node B
   - [ ] verify Node B accepts it

4. Real LoRa
   - [ ] verify Node A reports successful radio startup
   - [ ] verify Node B reports successful radio startup
   - [ ] verify Node B receives real packets
   - [ ] verify stale radio data becomes `LORA_STALE` after `3000 ms` without fresh packets

5. Emergency logic
   - [ ] verify `remote_ambulance_on`
   - [ ] verify `local_ambulance_on`
   - [ ] verify yellow occurs before priority green

## Quick Failure Checks

If Node B does not switch correctly:

- [ ] confirm local and remote queue values are changing
- [ ] confirm `minGreen`, `yellow`, and `maxGreen` values in the config
- [ ] confirm the correct side is receiving the telemetry

If LoRa does not work:

- [ ] confirm both nodes use the same frequency
- [ ] confirm both nodes boot with the same radio backend
- [ ] test again using serial emulation to isolate whether the bug is in radio or controller logic

If sensors do not react:

- [ ] confirm `TRIG` and `ECHO` are not swapped
- [ ] confirm the threshold values are still appropriate
- [ ] print raw distance values and compare them to the physical setup

## Core Files To Keep Open During Bring-Up

- `docs/hardware-map.md`
- `docs/node-a-telemetry-bench-test.md`
- `docs/node-b-standalone-bench-test.md`
- `docs/two-node-serial-emulation.md`
- `docs/fixed-test-scenarios.md`
- `docs/lora-integration.md`
- `docs/logging-and-results.md`
- `docs/test-results-log.md`
