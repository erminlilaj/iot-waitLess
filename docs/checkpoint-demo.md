# April 10 Checkpoint Demo Plan

## Review Focus

The April 10 checkpoint should prove that the project is technically on the right track. The presentation should therefore be organized around:

1. quantified requirements based on the current implementation baseline
2. metrics that show whether the implementation meets those requirements
3. experiments, results, and what changed after each result
4. edge-side sensing, decision-making, and node interaction rather than cloud features

## Current Technical Baseline

These are the numbers already defined in the current codebase and should be used as the checkpoint baseline:

- control loop interval: `200 ms`
- telemetry transmission interval: `1000 ms`
- far ultrasonic threshold: `35 cm`
- near ultrasonic threshold: `18 cm`
- minimum green time: `5000 ms`
- yellow time: `2000 ms`
- maximum green time: `20000 ms`
- switching margin: `4` demand-score points
- demand score formula: `3 * queue + 2 * farOccupied + 4 * nearOccupied`
- example telemetry payload: `A,1,0,4,2,2,0,12345` which is `19 bytes`

## Checkpoint Requirements To Present

Use these as the current project requirements for the checkpoint, not as final-course claims:

- `R1`: each side is represented by two ultrasonic detections, one far and one near
- `R2`: the controller evaluates traffic demand every `200 ms`
- `R3`: Node A produces one telemetry update every `1000 ms`
- `R4`: the controller never switches before `5000 ms` of green time
- `R5`: every switch includes a `2000 ms` yellow safety interval
- `R6`: if the other side remains waiting, starvation is limited by a `20000 ms` maximum green time
- `R7`: switching depends on measured demand, not only on a fixed timer

## Checkpoint Metrics Table

Use this table directly in the presentation. It links each metric to its current value, where it comes from, and why it matters.

| Metric | Current value | Source | Why it matters |
| --- | --- | --- | --- |
| Control-loop period | `200 ms` | `firmware/shared/ProjectConfig.h` | Defines how often the controller can react to sensor changes |
| Telemetry update period | `1000 ms` | `firmware/shared/ProjectConfig.h` | Defines how fresh Node A data is when Node B makes decisions |
| Far ultrasonic threshold | `35 cm` | `firmware/shared/ProjectConfig.h` | Baseline for detecting approaching traffic |
| Near ultrasonic threshold | `18 cm` | `firmware/shared/ProjectConfig.h` | Baseline for detecting queue presence near the stop line |
| Minimum green time | `5000 ms` | `firmware/shared/ProjectConfig.h` | Prevents unstable rapid switching |
| Yellow transition time | `2000 ms` | `firmware/shared/ProjectConfig.h` | Enforces a safety interval before changing green side |
| Maximum green time | `20000 ms` | `firmware/shared/ProjectConfig.h` | Prevents starvation of the waiting side |
| Demand score formula | `3 * queue + 2 * farOccupied + 4 * nearOccupied` | `lib/traffic_control/TrafficTypes.h` and `simulation/traffic_logic.py` | Explains how the controller compares both sides |
| Example telemetry payload size | `19 bytes` for `A,1,0,4,2,2,0,12345` | `lib/traffic_control/NodeMessaging.cpp` | Shows that node-to-node communication is compact even with ambulance priority support |
| Response to busier opposing side | yellow at `12 s`, new green at `14 s` | `simulation/simulate_traffic.py` | Shows adaptive switching plus preserved yellow safety time |
| Response when current side becomes empty | yellow at `6 s`, new green at `8 s` | scripted controller experiment | Shows that empty-lane detection avoids wasting green time |
| Forced switch upper bound | yellow at `20 s`, new green at `22 s` | scripted controller experiment | Shows that one side cannot monopolize the green phase |

For the final delivery, add real-hardware metrics:

- false positives and false negatives of each ultrasonic sensor
- LoRa packet latency and packet-loss tolerance
- average waiting time versus a fixed-cycle baseline
- energy usage per node

## Experiments Already Executed On The Current Baseline

The following experiments are already supported by the current simulator and controller logic:

1. Equal demand should not trigger a switch.
   Setup: from `t = 6 s` to `t = 11 s`, both sides have queue `2`.
   Result: the controller keeps side `A` green during the full interval.
   Conclusion: equal pressure does not cause unnecessary switching.

2. The other side becoming clearly busier should trigger a switch after the minimum green is already satisfied.
   Setup: at `t = 12 s`, side `A` queue becomes `1` and side `B` queue becomes `4`.
   Result: yellow starts at `12 s` and side `B` becomes green at `14 s`.
   Conclusion: the controller reacts immediately at the decision level and preserves the `2000 ms` yellow interval.

3. If the current green side becomes empty while the other side has demand, the controller should yield at the first allowed instant.
   Setup: side `A` is busy until `t = 5 s`; at `t = 6 s`, side `A` becomes empty and side `B` queue becomes `2`.
   Result: yellow starts at `6 s` and side `B` becomes green at `8 s`.
   Conclusion: empty-lane detection works as intended.

4. The maximum green time should prevent starvation even when the current side still has demand.
   Setup: side `A` queue remains `3` and side `B` queue remains `1`.
   Result: yellow starts at `20 s` and side `B` becomes green at `22 s`.
   Conclusion: the `20000 ms` cap prevents one side from keeping green indefinitely.

Note: the scripted controller experiments above use `1 s` simulation steps, while the firmware target loop is `200 ms`. This is acceptable for the checkpoint because the purpose is to demonstrate the control policy and timing rules.

## Five-Minute Presentation Flow

1. Requirement slide
   Show the baseline numbers and state exactly what the current prototype is supposed to do.

2. Metric slide
   Show the metrics you use to verify the current baseline.

3. Experiment slide
   Show the four experiments above using short tables or screenshots.

4. Demo
   Run the simulator and narrate one switching event from measured demand to yellow to green.

5. Remaining work
   Explain what still needs real hardware validation: ultrasonic calibration, LoRa integration, and comparative evaluation against a fixed-cycle baseline.

## What To Upload

- a presentation centered on requirements, metrics, and experiments
- a public YouTube demo link
- source code and documentation in the same repository
- a README that links the video and summarizes the architecture

## What Not To Overemphasize

- cloud services
- fancy UI details that are not part of the core traffic-control problem
- unmeasured claims such as "much faster" or "much better"
