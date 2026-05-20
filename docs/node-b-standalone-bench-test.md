# Node B Standalone Bench Test

This document explains how to test the current real firmware on one ESP32 board before LoRa is integrated.

## Goal

Use `Node B` as a standalone bench prototype that:

- reads its two local ultrasonic sensors
- runs the adaptive controller
- drives the six traffic-light LEDs
- accepts serial commands that emulate `Node A`

## Firmware File

- `firmware/node_b/main.cpp`

## Required Wiring

Use the pin map in:

- `docs/hardware-map.md`

For `Node B`, wire:

- far ultrasonic sensor: `TRIG GPIO4 = J3-15`, `ECHO GPIO5 = J3-16`
- near ultrasonic sensor: `TRIG GPIO6 = J3-17`, `ECHO GPIO7 = J3-18`
- side A LEDs: `R/Y/G = GPIO33/GPIO34/GPIO35 = J2-12/J2-11/J2-10`
- side B LEDs: `R/Y/G = GPIO38/GPIO39/GPIO40 = J3-11/J3-10/J3-9`

Important:

- if the ultrasonic `ECHO` output is `5V`, use a voltage divider or level shifter before the ESP32 input
- keep LED resistors in series with each LED
- according to [esp_datasheet.png](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/esp_datasheet.png), the current tested LED mapping now uses exposed `J2` header pins, so the LEDs can be wired directly to the pins listed above

## What Happens At Startup

When `Node B` boots:

- all LEDs are turned off
- a short light self-test runs: red, then yellow, then green
- the serial monitor prints the pin map
- the serial monitor prints the available bench commands

## Serial Monitor Settings

- baud rate: `115200`
- line ending: `newline`

## Bench Commands

These commands simulate the remote side `A`:

- `help`
  Prints the command list again.

- `remote_clear`
  Sets side `A` to empty.

- `remote_queue 3`
  Sets side `A` queue to `3` and marks the remote side as occupied.

- `remote_state 1 0 2`
  Sets remote `farOccupied = 1`, `nearOccupied = 0`, `queue = 2`.

- `thresholds`
  Prints the current local far and near distance thresholds plus the active sensor filter.

- `filter`
  Prints the active robustness filter. The current implementation is median3 distance filtering plus debounce2 occupancy.

- `health`
  Prints far/near sensor health. Repeated invalid ultrasonic readings become `WARN` or `FAIL`.

- `set_thresholds <far_cm> <near_cm>`
  Updates both local occupancy thresholds without reflashing.

- `set_far_threshold <cm>` / `set_near_threshold <cm>`
  Updates only one local threshold.

- `remote_ambulance_on`
  Enables ambulance priority for side `A`.

- `remote_ambulance_off`
  Clears ambulance priority for side `A`.

- `local_ambulance_on`
  Enables ambulance priority for side `B`.

- `local_ambulance_off`
  Clears ambulance priority for side `B`.

- `A,1,0,4,2,2,0,12345`
  Sends a raw telemetry payload in the same format used by the firmware messaging layer.

- `log quiet`, `log summary`, `log verbose`
  Controls how much periodic serial output is shown.

- `status`
  Prints a clean multi-line controller snapshot.

- `report`
  Prints a copy-friendly block for the results log.

## What To Observe

With `log summary`, every second the serial monitor prints one compact controller line with:

- local far and near distances in centimeters
- current far/near thresholds
- local occupancy state
- local queue estimate
- remote queue estimate
- whether the remote side is idle or serial-emulated
- whether remote radio data is stale
- controller state: green side, phase, elapsed phase time, and LED state
- whether emergency override is active and which side has priority

If you need more detail, switch to `log verbose`. If you want a clean snapshot to paste into documentation, use `status` or `report`.

## Simple Test Sequence

1. Power `Node B` and open the serial monitor.
2. Confirm the red-yellow-green self-test runs once.
3. Place an object in front of the `Node B` far sensor and near sensor.
4. Check that the serial monitor shows `OCC` and that `localQueue` increases.
5. Wait at least `5 s` and confirm the controller can give green to side `B`.
6. Type `remote_queue 3`.
7. Check that side `A` is now treated as having demand.
8. Remove the object from side `B` or wait for the controller timing rules to react.
9. Confirm the controller uses yellow before switching.
10. Type `remote_ambulance_on` and confirm the controller gives priority to side `A` through a yellow transition.

## Why This Step Matters

This bench test isolates three things before LoRa is added:

- sensor reading
- local controller behavior
- LED output correctness

That makes the next communication step easier because the local hardware path is already tested.
