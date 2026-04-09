# Node A Telemetry Bench Test

This document explains how to use `Node A` as a telemetry sender before the real sensors and LoRa link are available.

## Goal

Use `Node A` to:

- read its two local ultrasonic sensors when hardware is available
- or emulate the far/near sensor states over the serial monitor
- generate the same telemetry payload format used by the full system

## Firmware File

- `firmware/node_a/main.cpp`

## Required Wiring Later

Use the pin map in:

- `docs/hardware-map.md`

For `Node A`, the planned sensor pins are:

- far ultrasonic sensor: `TRIG 4`, `ECHO 5`
- near ultrasonic sensor: `TRIG 6`, `ECHO 7`

## Serial Monitor Settings

- baud rate: `115200`
- line ending: `newline`

## Available Commands

- `help`
  Prints the command list.

- `emu_on`
  Switches Node A into serial-emulation mode.

- `emu_off`
  Switches Node A back to real-sensor mode.

- `reset_counts`
  Resets the queue estimator counters.

- `ambulance_on`
  Enables ambulance priority for side `A`.

- `ambulance_off`
  Clears ambulance priority for side `A`.

- `state 1 0`
  Sets emulated `farOccupied = 1`, `nearOccupied = 0`.

- `state 0 1`
  Sets emulated `farOccupied = 0`, `nearOccupied = 1`.

- `state 0 0`
  Clears both sensor states.

- `log quiet`, `log summary`, `log verbose`
  Controls how much periodic serial output is shown.

- `status`
  Prints a clean multi-line snapshot.

- `report`
  Prints a copy-friendly block for the results log.

## Emulation Example For One Vehicle

This sequence simulates one car moving through side `A`:

1. `emu_on`
2. `reset_counts`
3. `state 1 0`
   This simulates the car crossing the far sensor, so `incomingCount` increases.
4. `state 0 1`
   This simulates the car waiting near the stop line.
5. `state 0 0`
   This simulates the car leaving the near sensor, so `passedCount` increases.

## What To Observe

With `log summary`, every telemetry period Node A prints one compact status line with:

- whether the source is `SENSORS` or `SERIAL_EMU`
- far and near occupancy state
- `incomingCount`
- `passedCount`
- `estimatedQueue`
- the transmitted telemetry payload

With `status` and `report`, you can print a cleaner snapshot on demand instead of reading the scrolling log.

The payload still appears inside the summary and report output in a form such as:

- `payload=A,1,0,4,2,2,0,12345`

At this stage it may still be a LoRa stub, but it matches the messaging format used by the full project.

## Why This Step Matters

This lets the team exercise the telemetry and queue-estimation path without waiting for:

- physical ultrasonic sensors
- the final wiring
- the real LoRa integration

That means Step 4 can later focus on how both nodes interact, instead of first debugging the basic telemetry sender.
