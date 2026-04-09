# Two-Node Serial Emulation Plan

This document describes the software-ready path for Step 4: exercise both nodes together before real LoRa is integrated.

## Goal

Use the existing firmware logic of both nodes while keeping communication serial-emulated:

- `Node A` generates telemetry payloads
- `Node B` accepts those payloads as if they were LoRa messages

## Current Status

The codebase is now prepared for this workflow:

- `Node A` prints a compact summary line that contains the payload, for example `payload=A,1,0,4,2,2,0,12345`
- `Node A` can also print a structured `report` block on demand
- `Node B` accepts both:
  - raw payload lines
  - longer lines that contain the payload as a substring

## Relevant Files

- `firmware/node_a/main.cpp`
- `firmware/node_b/main.cpp`
- `lib/traffic_control/NodeMessaging.cpp`

## Why This Step Exists

This isolates communication-format problems before the real LoRa driver is added.

If the two-node flow fails at this stage, the issue is likely in:

- payload format
- parsing
- controller integration

and not yet in radio configuration.

## Planned Usage Later

When hardware is available, there are two easy ways to use this setup:

1. Manual copy-paste path
   Read the summary line printed by `Node A` and paste it into the `Node B` serial monitor.

2. Temporary serial bridge path
   Connect a serial bridge in the lab setup so the line containing `payload=A,...` from `Node A` reaches `Node B`.

## Example Payload

`A,1,0,4,2,2,0,12345`

Meaning:

- side `A`
- far occupied = `1`
- near occupied = `0`
- incoming count = `4`
- passed count = `2`
- estimated queue = `2`
- ambulance request = `0`
- timestamp = `12345 ms`

## What Comes Next

After this step, the next software step is LoRa integration:

- replace the current transmit stub in `Node A`
- replace the serial-emulated receive path in `Node B`
- keep the same telemetry payload structure
