# Code Understanding Guide

This document explains the code structure of the Wait Less IoT traffic-light prototype.
It is written for a reader who wants to understand how the firmware, logger, simulator, and evaluation scripts work together.

## Big Picture

The project has two real ESP32 LoRa nodes:

- `Node A`: reads Side A ultrasonic sensors and transmits queue telemetry.
- `Node B`: reads Side B ultrasonic sensors, receives Node A telemetry, runs the controller, drives the traffic lights, logs status, handles emergency button input, and detects stale Node A data.

The real-road CSV and simulator are not replacements for the hardware. They are used to evaluate and replay what the hardware measured.

## Main Data Flow

```text
Side A sensors -> Node A -> LoRa telemetry -> Node B
Side B sensors -----------------------------> Node B
Node B adaptive controller -----------------> Side A / Side B traffic LEDs
Node B serial log --------------------------> laptop CSV logger
Saved CSV ----------------------------------> evidence dashboard + simulator replay
```

## Firmware Structure

### `firmware/node_a/main.cpp`

Node A is the sensing and telemetry node.

Important responsibilities:

- reads Side A far and near ultrasonic sensors;
- applies median filtering and occupancy debounce through `SensorSupport`;
- estimates Side A queue with `LaneEstimator`;
- sends compact LoRa payloads using `encodeTelemetry`;
- prints `A STATUS` lines for testing and CSV logging;
- supports serial commands for threshold tuning, emulation, and reports.

Professor-facing summary:

> Node A is not a simulation. It converts physical ultrasonic readings into a queue estimate and sends that measurement to Node B over LoRa.

### `firmware/node_b/main.cpp`

Node B is the controller and actuator node.

Important responsibilities:

- reads Side B far and near ultrasonic sensors;
- receives Side A telemetry over LoRa;
- runs the adaptive controller;
- drives both traffic-light heads;
- logs one complete `B STATUS` line with all four sensor distances;
- handles the physical emergency button;
- enters backup mode when Node A telemetry becomes stale.

Key log fields:

- `A_queue`, `B_queue`: estimated queue on each side;
- `A_far`, `A_near`, `B_far`, `B_near`: four real ultrasonic readings;
- `source=LORA_RADIO`: Node A data is live;
- `stale=ON`: Node A data is missing or old;
- `backup=ON`: Node B is using fail-safe assumptions for Side A;
- `emergency_target=A/B`: physical emergency priority target;
- `lights=A:... B:...`: current LED output state.

### `firmware/shared/HardwareMap.h`

This is the source of truth for pins.

Examples:

- Node A far sensor: `TRIG GPIO3 / J3-14`, `ECHO GPIO5 / J3-16`;
- Node B emergency button: `GPIO3 / J3-14` to `GND`;
- Node B Side B LEDs: `GPIO38/GPIO39/GPIO40`.

Changing hardware pins should happen here first, then the documents should be updated.

### `firmware/shared/ProjectConfig.h`

This file contains shared constants:

- loop period;
- telemetry period;
- stale timeout;
- ultrasonic thresholds;
- median/debounce values;
- traffic-light timing;
- LoRa radio settings;
- INA219 energy measurement settings.

The live demo threshold is `50 cm / 50 cm`. The validated road CSV used `100 cm / 100 cm`, which is why evaluation numbers must be described separately from the demo threshold.

### `firmware/shared/Ina219Support.*`

This optional module reads INA219 current and power measurements.

If INA219 is not connected, the firmware continues normally and prints `INA219_NA`.
That keeps the traffic-light demo independent from the energy measurement hardware.

## Shared Firmware Library

### `lib/traffic_control/TrafficTypes.h`

Defines the common data structures:

- `SideTelemetry`: one side's sensor state, counters, queue, emergency flag, and distances;
- `TrafficDecision`: controller output, active green side, phase, emergency priority, and lights;
- `demandScore`: converts queue and sensor state into a simple priority number.

### `lib/traffic_control/TrafficSensing.*`

Implements `LaneEstimator`.

Logic:

- far sensor rising edge means a vehicle is approaching;
- near sensor falling edge means a vehicle passed the stop line;
- queue estimate is `incomingCount - passedCount`;
- if near sensor is occupied but queue is zero, report queue as at least one.

This is simple, explainable, and suitable for a classroom prototype.

### `lib/traffic_control/SensorSupport.*`

Implements ultrasonic measurement reliability:

- sends the HC-SR04 trigger pulse;
- converts echo duration to distance;
- uses `999 cm` as timeout/no echo;
- applies median-of-3 filtering;
- applies occupancy debounce;
- tracks sensor health as `OK`, `WARN`, or `FAIL`.

This directly addresses the professor's concern about false positives and sensor reliability.

### `lib/traffic_control/NodeMessaging.*`

Encodes and decodes the LoRa packet.

Current payload format:

```text
side,far,near,in,out,queue,emergency,timestamp,far_cm,near_cm
```

The decoder also accepts older shorter payloads so old test logs and older firmware formats remain understandable.

### `lib/traffic_control/AdaptiveController.*`

Implements the two-phase adaptive light controller.

Rules:

- keep a minimum green time to avoid rapid oscillation;
- switch when the current side is empty and the other side has demand;
- switch when the other side is clearly busier;
- switch after maximum green if the other side is waiting;
- emergency requests override normal demand, but still pass through yellow first.

### `lib/traffic_control/LoRaTransport.*`

Wraps the Heltec V3 SX1262 LoRa radio.

Node A uses transmit mode.
Node B uses receive mode.

The wrapper keeps radio setup in one place and still allows the firmware to build with serial-emulation fallback if RadioLib is not enabled.

### `lib/traffic_control/DebugSupport.h`

Small helpers for readable serial logs:

- log mode labels;
- `ON/OFF` formatting;
- common `status` and `report` commands.

## Python Tools

### `tools/road_data_logger.py`

This is the field logger used during the demo and road tests.

It:

- opens the ESP32 serial port;
- parses `A STATUS` and `B STATUS` lines;
- displays a clean live table;
- saves a CSV with sensor, queue, LoRa, emergency, backup, and power fields;
- lets the user type manual labels such as `v`, `n`, `far 1`, `near 0`, and `note ...`.

### `tools/final_evidence_report.py`

Builds the final dashboard and report from the validated road CSV.

It summarizes:

- duration;
- sample count;
- TP/TN/FP/FN;
- accuracy;
- false positive and false negative rates;
- LoRa stale percentage;
- energy estimate;
- simulator comparison link.

### `tools/final_presentation_graphs.py`

Generates slide-ready graphs:

- confusion matrix;
- detection quality rates;
- energy consumption;
- LoRa reliability;
- traffic demand over time;
- detected activations;
- time-saving estimate;
- digital-twin pipeline;
- INA219 power time series.

### Other Tools

- `road_data_summary.py`: summarizes one road CSV.
- `sensor_threshold_analysis.py`: explores threshold choices from labelled data.
- `ina219_energy_summary.py`: summarizes measured current and energy.
- `energy_estimator.py`: quick current/battery estimate.
- `road_dashboard.py`: lightweight live CSV dashboard.

## Simulation Code

### `simulation/traffic_logic.py`

Pure-Python controller equivalent used for simulator and graph scripts.
It mirrors the demand-score and adaptive switching rules used in firmware.

### `simulation/visual_simulator_real_data.py`

Replays the validated road CSV inside the visual simulator.
Cars still enter from outside the crossroad, but real CSV queue pressure controls the replay.

### Other Simulators

- `simulate_traffic.py`: text-based controller demo.
- `visual_simulator.py`: visual traffic demo.
- `visual_simulator_emergency.py`: visual demo with emergency behavior.
- `test_controller.py`: repeatable software checks for controller rules.

## Reliability Features To Explain

### False Positive Control

The firmware reduces false positives with:

- configurable per-sensor thresholds;
- median-of-3 distance filtering;
- 2-sample occupancy debounce;
- manual road labels for measured TP/TN/FP/FN.

### Sensor Health

Repeated invalid ultrasonic readings are reported as:

```text
health=F:OK,N:OK
health=F:WARN,N:OK
health=F:FAIL,N:OK
```

This helps distinguish "no car" from "sensor probably disconnected or badly aimed."

### Node A Failure

Node B detects stale Node A telemetry after the stale timeout.

Expected log:

```text
source=LORA_STALE | stale=ON | backup=ON | recovery=WAITING_FOR_LORA
```

Node B then uses conservative Side A demand instead of pretending that Side A is empty.
When Node A returns, Node B logs recovery and resumes live LoRa data.

### Node B Failure

Node B currently controls the physical LEDs, so a true Node B failure requires hardware redundancy.
The proposed solution is a tri-state buffer or failover selector so Node A can safely drive the lights only when Node B is disconnected from the LED lines.

Do not connect two ESP32 GPIOs directly to the same LED line.

## How To Read The Live Demo Log

Example:

```text
B STATUS | A_queue=1 | B_queue=0 | A_far=169.2cm/FREE | A_near=165.6cm/FREE | B_far=14.9cm/OCC | B_near=142.6cm/FREE | thresholds=50.0/50.0 | source=LORA_RADIO | stale=OFF | backup=OFF | recovery=LIVE | green=B | phase=GREEN | emergency=OFF | lights=A:RED B:GREEN
```

Meaning:

- Node B is receiving Node A data over LoRa.
- Side A queue is `1`; Side B queue is `0`.
- B far sensor detects an object at `14.9 cm`.
- Backup is off because LoRa is live.
- B side currently has green.

## What To Say In The Presentation

Use this short explanation:

> The project is organized around two ESP32 LoRa nodes. Node A senses one road side and sends compact telemetry. Node B senses the second road side, receives Node A data, runs the adaptive controller, and drives the LEDs. The logger stores real sensor distances, queue estimates, LoRa freshness, emergency state, backup state, and power values. The simulator is then used as a digital twin to replay the measured road demand and compare adaptive behavior against fixed timing.

The most important point is that the evaluation is based on real sensor data and manual labels, not only simulated cars.
