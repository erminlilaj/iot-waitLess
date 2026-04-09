# Wait Less

Queue-aware adaptive traffic light system for a two-way intersection using ESP32 LoRa nodes.

This repository now contains the first implementation scaffold for the project described in `hh.tex`. The goal is to sense traffic on both sides of an intersection, exchange compact telemetry over LoRa, and adapt the traffic lights in near real time.

## Current Scope

- Shared queue-aware traffic decision logic
- Arduino/ESP32 firmware skeleton for two nodes
- Local simulator for the second-delivery demo
- Documentation that aligns the technical story

## Repository Layout

- `platformio.ini`: PlatformIO environments for the two ESP32 nodes
- `lib/traffic_control/`: shared sensing, messaging, and adaptive-controller logic
- `firmware/node_a/`: sensing node for side A
- `firmware/node_b/`: sensing + controller node for side B
- `firmware/shared/`: common firmware configuration
- `firmware/shared/HardwareMap.h`: shared bench-test pin mapping
- `simulation/simulate_traffic.py`: local demo of the control algorithm
- `docs/checkpoint-demo.md`: suggested second-delivery presentation/demo flow
- `docs/april-10-readiness.md`: April 10 checklist and submission status
- `docs/april-10-slide-assets.pdf`: slide-ready tables, charts, technical numbers, and log snippets
- `docs/hardware-map.md`: current bench-test wiring plan
- `docs/bring-up-guide.md`: recommended order once hardware arrives
- `docs/hardware-arrival-checklist.md`: first-day hardware bring-up checklist
- `docs/fixed-test-scenarios.md`: fixed scenarios and expected serial evidence
- `docs/logging-and-results.md`: clean serial workflow using quiet, summary, verbose, status, and report
- `docs/test-results-log.md`: single results file for software and hardware validation
- `docs/node-a-telemetry-bench-test.md`: how to exercise Node A telemetry with or without sensors
- `docs/node-b-standalone-bench-test.md`: how to bench-test Node B before LoRa integration
- `docs/two-node-serial-emulation.md`: how the two nodes can interact before real LoRa is added
- `docs/lora-integration.md`: current RadioLib-based LoRa integration assumptions

## How The System Works

Each side of the intersection has:

- one far sensor for approaching traffic
- one near sensor for queue or stop-line presence

Node A reads side A and transmits a compact telemetry packet. Node B reads side B, receives side A telemetry, runs the adaptive controller, and drives the six traffic-light LEDs.

The current controller follows three simple rules:

1. Respect a minimum green time to avoid oscillation.
2. Switch if the current green side becomes empty and the other side has demand.
3. Switch after the minimum green if the other side is clearly busier, or after the maximum green if the other side is still waiting.

## Local Demo

You can already demo the logic without hardware:

```powershell
python simulation/simulate_traffic.py
```

This prints a time-based scenario showing when the controller keeps green, schedules yellow, and switches sides.

For repeatable software-only controller checks:

```powershell
python simulation/test_controller.py
```

This runs the current baseline assertions for balanced demand, empty-lane yield, busier-side switching, and max-green enforcement.

For a visual checkpoint demo with animated cars on a one-lane four-direction intersection:

```powershell
python simulation/visual_simulator.py
```

The visual simulator groups north/south as one adaptive phase and east/west as the other, which matches the current two-side controller design while giving you a much more presentation-friendly view of the traffic flow.

Inside the GUI you can now choose between:

- `Scenario`: the original scripted traffic pattern
- `Manual`: set the car frequency for north, south, east, and west yourself
- `Random`: let the simulator reshuffle traffic pressure automatically every few seconds

The latest visual version also replaces the old abstract sensor marks with ultrasonic-style modules, shows their capture zones, and pushes the far sensors farther from the intersection to better match the intended hardware story.

For a separate emergency-priority version that keeps the same base simulator but adds ambulance override behavior and shows the two ESP32 LoRa boards visually connected to their ultrasonic sensors and traffic lights:

```powershell
python simulation/visual_simulator_emergency.py
```

In this emergency version:

- the current green road still transitions through yellow before giving way
- an ambulance request overrides queue counts and gives priority to the ambulance axis
- Node A is shown handling the `North/South` sensors and lights
- Node B is shown handling the `East/West` sensors and lights

## Firmware Notes

The firmware is intentionally staged for bring-up:

- sensor reading is implemented with Arduino primitives
- telemetry encoding/decoding uses a compact CSV payload
- a shared LoRa transport now targets the onboard `SX1262` radio on `Heltec WiFi LoRa 32 V3`
- the serial-emulation path is still kept for testing before real hardware is available
- both nodes now support `log quiet`, `log summary`, `log verbose`, `status`, and `report`
- Node B now times out stale radio telemetry after `3000 ms` so old packets do not keep a phantom queue alive

Update the pin mappings in the node files before flashing to your boards.

## Recommended Next Steps

1. Finish the April 10 package using `docs/checkpoint-demo.md` and `docs/april-10-readiness.md`.
2. Use `docs/bring-up-guide.md` and `docs/hardware-arrival-checklist.md` when the hardware arrives.
3. Verify the LoRa radio assumptions and frequency on the real Heltec boards.
4. Wire real sensor pins, tune thresholds, and record telemetry logs from bench tests.
