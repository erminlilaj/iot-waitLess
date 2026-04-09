# Fixed Test Scenarios And Expected Outputs

This document defines a fixed set of test scenarios for later hardware validation.

The goal is to avoid improvising during bring-up. Each scenario has:

- setup
- action
- expected controller behavior
- expected serial evidence

## Reading The Logs

The firmware currently prints these useful serial patterns:

- `A STATUS | ...`
- `B STATUS | ...`
- `REPORT NODE_A`
- `REPORT NODE_B`
- `[LoRa RX] ...` in verbose mode

These strings are the main evidence to look for during tests.

## Scenario 1: Node B Startup Self-Test

### Setup

- flash `Node B`
- wire the six LEDs
- power the board

### Expected Behavior

- all LEDs start off
- both heads show red briefly
- both heads show yellow briefly
- both heads show green briefly
- normal controller logs begin after the self-test

### Expected Serial Evidence

- `Node B ready.`
- `Standalone bench mode is enabled.`
- `Node B side-A LEDs R/Y/G: ...`
- `Node B side-B LEDs R/Y/G: ...`

## Scenario 2: Node A Telemetry In Emulation Mode

### Setup

- flash `Node A`
- open serial monitor

### Action

1. send `emu_on`
2. send `reset_counts`
3. send `state 1 0`
4. send `state 0 1`
5. send `state 0 0`

### Expected Behavior

- `incomingCount` increases after `state 1 0`
- `estimatedQueue` becomes non-zero while the near state is occupied
- `passedCount` increases after `state 0 0`
- payload lines are printed every telemetry interval

### Expected Serial Evidence

- `Node A switched to emulation mode.`
- `Node A estimator counters reset.`
- `Node A emulated state updated | far=1 near=0`
- `Node A emulated state updated | far=0 near=1`
- `Node A emulated state updated | far=0 near=0`
- `A STATUS | ... payload=A,...`

## Scenario 3: Node B Local Sensing Only

### Setup

- flash `Node B`
- wire only Node B sensors and LEDs

### Action

- place an object in front of the far sensor
- then near sensor
- then remove it

### Expected Behavior

- `localQueue` increases as the vehicle is detected
- side `B` is allowed to hold green when it has demand
- no remote side demand is present

### Expected Serial Evidence

- `B STATUS | far=.../OCC`
- `B STATUS | ... green=B ...` may appear depending on the phase history

## Scenario 4: Remote Queue Via Serial Emulation

### Setup

- flash `Node B`
- open serial monitor

### Action

1. send `remote_clear`
2. send `remote_queue 3`

### Expected Behavior

- side `A` is treated as waiting
- after the local timing rules allow it, side `A` should receive priority if side `B` is weaker
- the controller must still use yellow before a side change

### Expected Serial Evidence

- `Remote side reset to empty.`
- `Remote queue set to 3`
- `B STATUS | ... phase=YELLOW ...`
- later `B STATUS | ... green=A | phase=GREEN ...`

## Scenario 5: Two-Node Serial Emulation

### Setup

- flash both nodes
- use Node A in emulation mode
- use Node B in normal bench mode

### Action

1. on Node A, send `emu_on`
2. on Node A, simulate traffic and copy one summary line that contains `payload=A,...`
3. paste that line into Node B

### Expected Behavior

- Node B accepts the payload as remote telemetry
- remote queue appears in the controller logs
- switching decisions use that queue information

### Expected Serial Evidence

On Node A:

- summary line containing `payload=A,1,0,1,0,1,0,12345`

On Node B:

- `Remote telemetry payload accepted.`
- `B STATUS | ... remoteQ=...`

## Scenario 6: Real LoRa Packet Reception

### Setup

- flash both nodes with LoRa-enabled firmware
- both boards use the same frequency

### Action

- allow Node A to transmit telemetry
- keep Node B in receive mode

### Expected Behavior

- Node B receives live packets without manual paste
- remote telemetry updates the controller

### Expected Serial Evidence

On Node A:

- `A STATUS | ... tx=RADIO_TX_OK ...`

On Node B:

- `[LoRa RX] A,...`
- `B STATUS | ... source=LORA_RADIO ...`

## Scenario 7: Ambulance Priority On Remote Side

### Setup

- Node B running

### Action

1. send `remote_queue 2`
2. send `remote_ambulance_on`

### Expected Behavior

- if side `B` is currently green, the controller should move through yellow
- side `A` then becomes green with emergency priority

### Expected Serial Evidence

- `Remote ambulance override enabled.`
- `B STATUS | ... emergency=ON | priority=A ...`
- a yellow phase before the new green side

## Scenario 8: Ambulance Priority On Local Side

### Setup

- Node B running

### Action

1. send `local_ambulance_on`

### Expected Behavior

- if side `A` was green, the controller should move through yellow
- side `B` then becomes green with emergency priority

### Expected Serial Evidence

- `Local ambulance override enabled.`
- `B STATUS | ... emergency=ON | priority=B ...`

## Scenario 9: Ambulance Priority Through Node A Telemetry

### Setup

- Node A and Node B running in serial emulation or real LoRa mode

### Action

1. on Node A, send `ambulance_on`
2. forward or transmit the telemetry to Node B

### Expected Behavior

- Node B sees remote telemetry with `emergencyRequested = 1`
- side `A` becomes the priority side after yellow

### Expected Serial Evidence

On Node A:

- payload field for ambulance becomes `1`
- example: `A,1,1,1,0,1,1,12345`

On Node B:

- `B STATUS | ... emergency=ON | priority=A ...`

## Scenario 10: Emergency Clear And Return To Normal Logic

### Setup

- any scenario where emergency priority is active

### Action

- clear the ambulance request:
  - `ambulance_off`
  - `remote_ambulance_off`
  - `local_ambulance_off`

### Expected Behavior

- controller returns to normal queue-based logic
- future switches again depend on demand and timing rules

### Expected Serial Evidence

- `B STATUS | ... emergency=OFF ...`
- normal queue-based controller behavior in the next summary or report

## Scenario 11: Stale Radio Telemetry Timeout

### Setup

- Node B running with real LoRa enabled
- Node A sends at least one packet successfully

### Action

1. turn off Node A or stop its transmissions
2. wait more than `3000 ms`

### Expected Behavior

- Node B should stop trusting the old remote queue
- remote traffic should be treated as empty until a fresh packet arrives
- the status should clearly show that the radio data is stale

### Expected Serial Evidence

- `B STATUS | ... source=LORA_STALE | stale=ON ...`
- `remoteQ=0` in the summary line or report output
