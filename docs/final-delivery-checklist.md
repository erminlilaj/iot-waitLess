# Wait Less Final Delivery Checklist

This file maps the official final-delivery instructions to the exact Wait Less material we need to submit.

Important note: the assignment text appears to be a reused course template from `2022/2023`. The real deadline/date should be verified in Google Classroom. The current project package below is organized for the final exam delivery.

## Main Grading Message

The professor explicitly cares about process, not only final outcome. Our final story should therefore emphasize:

- how the project evolved from simulator to real IoT deployment
- which measurements were taken on a real crossroad
- which problems appeared during testing
- which fixes/improvements were added after observing those problems
- how every number was computed
- which parts remain future work and why

The strongest sentence for our project:

> We did not only build a traffic-light simulation. We built a two-node IoT prototype, collected labelled real-road ultrasonic data, measured detection errors, measured energy with INA219, and used the road CSV to drive a digital-twin replay.

## Requirement Mapping

| Official requirement | Our status | File / evidence | Remaining action |
| --- | --- | --- | --- |
| Final Concept document | Needs final clean version | History exists in `hh.tex`, `docs/project-stage-report.tex`, `docs/project-roadmap.md` | Create `docs/final-concept.md` |
| Final Design document | Needs final clean version | Hardware map, firmware, architecture docs exist | Create `docs/final-design.md` |
| Final Evaluation document | Mostly ready | `data\data_readed\road_26-05-19_crossroads_evidence_report.md`, graphs, CSV | Create `docs/final-evaluation.md` |
| Link to previous document history | Needs explicit links | Previous docs already in repo | Add "History" section to final concept/design/evaluation docs |
| Blog post on public site | Not uploaded yet | Can draft from README + final docs | Create LinkedIn/public blog post and link GitHub |
| 10-minute presentation video | Plan ready | `docs/final-presentation-plan.md` | Build slides, record, upload public YouTube |
| 5-minute demo video | Needs final storyboard | Road videos, live log, simulator, hardware photos | Create/record demo video, upload public YouTube |
| GitHub repository submission | Done | `https://github.com/hamzaabedlkadr-b/iot_project.git` | Add final docs/videos/blog links, then submit repo link |

## Documents To Create Next

### 1. `docs/final-concept.md`

Purpose: final project idea and motivation.

Must include:

- problem: fixed traffic-light timing wastes time when traffic is unbalanced
- core idea: sense vehicles on both roads and adapt green time
- IoT value: physical sensors, LoRa telemetry, real crossroad data, energy measurement
- offered service: local adaptive intersection controller and digital-twin replay
- final scope: prototype, not a city-scale deployment
- history links: `hh.tex`, `docs/project-roadmap.md`, `docs/project-stage-report.tex`

### 2. `docs/final-design.md`

Purpose: final architecture and implementation.

Must include:

- Node A role: two ultrasonic sensors + LoRa transmit
- Node B role: two ultrasonic sensors + LoRa receive + traffic-light LEDs
- hardware pin map and voltages
- network diagram: Node A -> LoRa -> Node B
- software components:
  - `firmware/node_a/main.cpp`
  - `firmware/node_b/main.cpp`
  - `lib/traffic_control/AdaptiveController.cpp`
  - `lib/traffic_control/SensorSupport.cpp`
  - `lib/traffic_control/LoRaTransport.cpp`
  - `tools/road_data_logger.py`
  - `simulation/visual_simulator_real_data.py`
- robustness additions:
  - `100 cm` threshold used in road CSV
  - runtime threshold commands
  - median3 filtering
  - debounce2 occupancy
  - sensor-health diagnostics
  - stale LoRa timeout
  - INA219 power logging

### 3. `docs/final-evaluation.md`

Purpose: final methodology, metrics, results, and honest discussion.

Must include:

- real road dataset path: `data\data_readed\road_26-05-19_crossroads.csv`
- duration: `18.0 min`
- samples: `2160`
- threshold: `100 cm / 100 cm`
- labels: vehicle / empty
- TP/TN/FP/FN: `1269 / 817 / 59 / 15`
- accuracy: `96.6%`
- false positive rate: `6.7%`
- false negative rate: `1.2%`
- LoRa stale rate: `65 / 2160 = 3.0%`
- energy source: `data\road_sessions\ina219_power_timeseries_2026-05-20.csv`
- Node A current: `123.0 mA`
- Node B current: `174.8 mA`
- total current: `297.9 mA`
- road-run energy: `89.3 mAh`
- peak total power: `1812.0 mW at 210 s`
- waiting-pressure reduction: `31.6%`, clearly labelled as digital-twin estimate, not direct field proof
- limitations:
  - manual truth labels
  - short road session
  - ultrasonic placement sensitivity
  - time-saving result is replay/simulation-based
  - filtering was added after the baseline CSV, so it needs a second road run

## Numbers And Justification Table

| Number | Value | Source | How to justify it |
| --- | --- | --- | --- |
| Road duration | `18.0 min` | CSV first/last timestamps | Computed from `elapsed_s` in road CSV |
| Samples | `2160` | road CSV | Count of ESP32 rows from Node A and Node B |
| Accuracy | `96.6%` | evidence report | `(TP + TN) / scored samples` |
| TP/TN/FP/FN | `1269/817/59/15` | labelled road CSV | Compared `truth_any_vehicle` to sensor occupancy |
| False positive rate | `6.7%` | evidence report | `FP / (FP + TN)` |
| False negative rate | `1.2%` | evidence report | `FN / (FN + TP)` |
| LoRa stale | `3.0%` | road CSV | Count `LORA_STALE` rows vs all node rows |
| Node A current | `123.0 mA` | INA219 time series | Average of 21 samples at 30 s intervals |
| Node B current | `174.8 mA` | INA219 time series | Average of 21 samples at 30 s intervals |
| Peak power | `1812.0 mW at 210 s` | INA219 time series | Sum of Node A + Node B power at each sample |
| Time saving estimate | `31.6%` | graph script | Real demand replay: fixed-time waiting pressure vs adaptive waiting pressure |

## Presentation Structure Required By Assignment

Maximum 10 minutes:

| Time | Topic | What we show |
| --- | --- | --- |
| 0:00-1:00 | Problem | Traffic lights waste time when demand is asymmetric |
| 1:00-2:00 | Existing approaches | Fixed-time lights, camera-based systems, loop detectors |
| 2:00-3:00 | Our solution | Two ESP32 LoRa nodes, ultrasonic sensing, adaptive controller |
| 3:00-4:00 | Hardware + network | Node A, Node B, sensors, LEDs, LoRa diagram |
| 4:00-7:00 | Architecture + algorithms | sensing, queue estimate, demand score, LoRa, stale handling, digital twin |
| 7:00-9:00 | Evaluation | accuracy, FP/FN, LoRa stale, energy, time-saving estimate |
| 9:00-10:00 | Discussion/future work | limitations, filtering after baseline, larger dataset, better mounting |

## Demo Video Structure Required By Assignment

Maximum 5 minutes:

| Time | Demo part | What to show |
| --- | --- | --- |
| 0:00-0:40 | Hardware overview | Node A, Node B, sensors, LEDs |
| 0:40-1:30 | Real road evidence | phone road video and live laptop log |
| 1:30-2:15 | IoT telemetry | Node A to Node B LoRa log, stale/live status |
| 2:15-3:00 | Energy | INA219 photo and power graph |
| 3:00-4:15 | Digital twin | real-data simulator replay |
| 4:15-5:00 | Results | evidence dashboard and graph summary |

## Blog Post Checklist

The blog post must be public and should include:

- project title: Wait Less
- short problem statement
- core IoT idea
- hardware components
- network diagram
- architecture / algorithms
- evaluation methodology
- main results
- limitations and future work
- GitHub repository link
- YouTube presentation video link
- YouTube demo video link

Suggested title:

```text
Wait Less: An IoT Digital Twin For Adaptive Traffic Lights Using ESP32 LoRa Nodes
```

## Evidence Assets Already Ready

- Final README: `README.md`
- Road CSV: `data\data_readed\road_26-05-19_crossroads.csv`
- Evidence report: `data\data_readed\road_26-05-19_crossroads_evidence_report.md`
- Evidence dashboard: `data\data_readed\road_26-05-19_crossroads_evidence_dashboard.html`
- Presentation plan: `docs\final-presentation-plan.md`
- Graphs: `data\data_readed\presentation_graphs\`
- Hardware map: `docs\hardware-map.md`
- Test results log: `docs\test-results-log.md`
- INA219 measurement docs: `docs\ina219-energy-measurement.md`

## Immediate Next Actions

1. Create final Concept / Design / Evaluation documents.
2. Insert photos and videos into the presentation plan.
3. Build the 10-minute presentation deck/video.
4. Build the 5-minute demo video.
5. Draft and publish the blog post.
6. Add public YouTube and blog links to README.
7. Push final repository.
8. Submit GitHub repository link through Google Classroom.
