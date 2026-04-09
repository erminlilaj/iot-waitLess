# LoRa Integration Notes

This document records the current Step 5 software integration of LoRa in the project.

## Current Goal

Replace the previous serial-only LoRa stubs with a real radio transport layer in code, while keeping serial emulation available until hardware testing is possible.

## What Was Added

- a shared LoRa transport wrapper in `lib/traffic_control/LoRaTransport.h`
- the RadioLib-based implementation in `lib/traffic_control/LoRaTransport.cpp`
- board radio pin mapping in `firmware/shared/HardwareMap.h`
- LoRa configuration values in `firmware/shared/ProjectConfig.h`
- firmware integration in:
  - `firmware/node_a/main.cpp`
  - `firmware/node_b/main.cpp`

## Current Library Choice

- LoRa library: `RadioLib`
- radio chip: `SX1262`
- board target in PlatformIO: `heltec_wifi_lora_32_V3`
- onboard radio GPIO mapping: implemented as the current software assumption and must be verified against the board pin map during hardware bring-up

## Current Behavior

### Node A

- initializes the LoRa transport at startup
- attempts real radio transmission through the shared wrapper
- still prints the payload to serial for debugging and manual forwarding

### Node B

- initializes the LoRa transport in receive mode
- polls for received packets through the shared wrapper
- still accepts serial-emulated payloads and bench commands
- automatically times out stale radio telemetry after `3000 ms`
- reports whether the remote side is `LORA_RADIO`, `SERIAL_EMU`, `IDLE`, or `LORA_STALE`

## Important Assumption

The current default LoRa frequency is:

- `868.0 MHz`

This matches the expected regional setup for Italy/Europe. If your board variant or test setup is for another LoRa region, update:

- `firmware/shared/ProjectConfig.h`

before flashing.

## Why The Serial Path Is Still Kept

Because hardware testing is postponed, the serial path is still useful for:

- validating the telemetry format
- manually injecting packets
- debugging controller behavior without the radio
- exercising ambulance-priority messages before the real radio is available

## What Still Needs Real Testing Later

- radio initialization success on the real boards
- packet transmission from Node A to Node B
- RSSI and SNR logging validity
- remote telemetry timeout behavior after packet loss
- correct frequency for the actual hardware SKU
- stability under repeated packet traffic

## Next Stage After Hardware Is Available

When you have the boards and materials:

1. flash Node A and Node B
2. verify that both report `RadioLib SX1262` at startup
3. verify Node A can transmit real packets
4. verify Node B receives them without manual serial forwarding
5. only after that, remove reliance on the serial-emulation path during normal tests
