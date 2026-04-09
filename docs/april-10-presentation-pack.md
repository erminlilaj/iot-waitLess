# April 10 Presentation Pack

This file is the slide-ready content pack for the April 10 checkpoint.

It is intentionally aligned with the professor's review criteria:

- clear requirements with numbers
- explicit metrics
- experiments and results
- focus on edge-side sensing, communication, and control
- honest distinction between simulated evidence and real hardware evidence

## Presentation Goal

In 5 minutes, the presentation should prove that the project is technically on the right track.

The main message should be:

`We already validated the adaptive controller in software and validated node-to-node LoRa communication on real hardware. The remaining work is mainly sensor and actuator integration, not core logic invention.`

## Slide 1: Problem And Architecture

### Title

`Wait Less: Adaptive Traffic Light Control With ESP32 LoRa Nodes`

### What to show

- one sentence about the problem:
  `Fixed-cycle traffic lights waste time when one side is empty and the other side has a queue.`
- one sentence about the solution:
  `Our system uses two ESP32 LoRa nodes and ultrasonic sensing to adapt the light phase based on measured traffic demand.`
- architecture diagram or simulator screenshot
- explain the two-node split:
  - `Node A`: senses side A and sends telemetry
  - `Node B`: senses side B, receives side A telemetry, runs the controller, and drives the lights

### What to say

- the project is edge-focused, not cloud-focused
- each side is represented by far and near sensing
- the nodes exchange compact telemetry over LoRa
- the decision is local and real-time on the embedded side

## Slide 2: Requirements With Numbers

### Title

`Current Baseline Requirements`

### What to show

- `R1`: each side is monitored by two detections: far and near
- `R2`: controller evaluation period = `200 ms`
- `R3`: telemetry transmission period = `1000 ms`
- `R4`: minimum green time = `5000 ms`
- `R5`: yellow transition time = `2000 ms`
- `R6`: maximum green time = `20000 ms`
- `R7`: switching is demand-based, not purely timer-based
- demand score:
  `3 * queue + 2 * farOccupied + 4 * nearOccupied`

### What to say

- these are not vague claims, they are current implementation parameters from the code
- these numbers define the current technical baseline
- the checkpoint goal is to show that the system behaves consistently with these rules

## Slide 3: Metrics And How We Measure Them

### Title

`Metrics Used For Verification`

### What to show

Use a simple 3-column table:

| Metric | Current value | Why it matters |
| --- | --- | --- |
| Control loop | `200 ms` | reaction speed of controller |
| Telemetry period | `1000 ms` | freshness of remote traffic data |
| Min green | `5000 ms` | prevents oscillation |
| Yellow time | `2000 ms` | safety during switching |
| Max green | `20000 ms` | prevents starvation |
| Payload size | `19 bytes` | compact node-to-node communication |

Then add two real-hardware evidence bullets:

- `Node A`: `tx=RADIO_TX_OK`
- `Node B`: `source=LORA_RADIO | stale=OFF`

### What to say

- in software we measure timing and switching behavior
- in hardware we already measured that telemetry is really transmitted and received
- we also added stale-packet handling so old remote data is not trusted forever

## Slide 4: Experiments, Results, And Process

### Title

`Experiments And Current Results`

### What to show

Use four short experiments:

1. Equal demand
   - setup: both sides have equal queue
   - expected: no unnecessary switch
   - result: controller kept side A green

2. Empty-lane yield
   - setup: side A becomes empty, side B still has queue
   - expected: yield at first allowed instant
   - result: yellow at `6 s`, side B green at `8 s`

3. Busier-side priority
   - setup: side B becomes clearly busier
   - expected: switch after minimum green
   - result: yellow at `6 s`, side B green at `8 s`

4. Starvation prevention
   - setup: one side keeps demand for a long time
   - expected: forced switch at max green
   - result: yellow at `20 s`, side B green at `22 s`

Then add one hardware row:

5. Real LoRa A -> B communication
   - expected: Node B receives live packets from Node A
   - result: confirmed with `source=LORA_RADIO | stale=OFF` and `remoteQ=1`

### What to say

- the process was not only "we built something"
- we defined expected behavior first
- then we executed tests
- then we checked whether the results matched the hypothesis
- after testing, we improved the firmware by adding stale-telemetry timeout and clearer debug/report modes

## Slide 5: Current Status And Remaining Work

### Title

`What Is Done And What Remains`

### What to show

Done:

- adaptive controller validated in software
- real firmware builds on both boards
- firmware uploaded to both boards
- real LoRa communication validated between Node A and Node B
- metrics, experiments, and logs documented

Remaining:

- wire and validate real ultrasonic sensors
- wire and validate traffic-light LEDs
- validate emergency override on the real hardware path
- measure full end-to-end scenarios with physical sensing and actuation

### What to say

- the project is now beyond concept and beyond pure simulation
- the main risk is no longer the communication or controller logic
- the next stage is hardware integration and calibration

## Recommended Demo During The Talk

Use the demo in this order:

1. show the simulator for one normal adaptive-switching scenario
2. mention the software controller results
3. show one real-hardware log screenshot from Node A
4. show one real-hardware log screenshot from Node B
5. point out that the LoRa link was validated on real boards

## Screenshots To Capture Before Presenting

Capture these and keep them ready:

1. simulator screenshot showing the intersection and adaptive state
2. `Node A` log with:
   - `tx=RADIO_TX_OK`
   - payload changing from `A,1,0,...` to `A,0,1,...` to `A,0,0,...`
3. `Node B` log with:
   - `source=LORA_RADIO`
   - `stale=OFF`
   - `remoteQ=1`

## What Not To Say

Avoid these weak styles:

- `the system works very well`
- `the system is much better`
- `the system is fast`
- `the system is smart`

Replace them with measurable statements:

- `the controller evaluates traffic every 200 ms`
- `the telemetry period is 1000 ms`
- `the yellow interval is 2000 ms`
- `the max-green cap is 20000 ms`
- `Node B received live LoRa telemetry from Node A on real hardware`

## One-Sentence Closing

Use this as the final sentence:

`At this checkpoint, we validated the decision logic in software and the communication path on real hardware, so the remaining work is focused on physical sensing, actuation, and calibration rather than redesigning the system architecture.`
