# Wait Less

Queue-aware adaptive traffic light system for a two-way intersection using ESP32 LoRa nodes.

This repository contains the final IoT prototype package for the Wait Less project. The goal is to sense traffic on both sides of a real crossroad, exchange compact telemetry over LoRa, adapt the traffic lights in near real time, and connect the real road dataset back into a digital-twin simulator.

## Current Scope

- Two ESP32 Heltec LoRa nodes.
- Four ultrasonic sensors: two on Node A and two on Node B.
- Node B traffic-light output for both directions.
- Real crossroad CSV with labelled `vehicle` / `empty` samples.
- INA219-based energy measurement.
- Final evidence dashboard, report, graph assets, and real-data simulator replay.
- Firmware robustness improvements: per-sensor thresholds, median filtering, debounce, and sensor health diagnostics.

## Final Evidence Snapshot

| Item | Result |
| --- | --- |
| Real road CSV | `data\data_readed\road_26-05-19_crossroads.csv` |
| Duration | `18.0 min` |
| ESP32 samples | `2160` |
| TP/TN/FP/FN | `1269 / 817 / 59 / 15` |
| Detection accuracy | `96.6%` |
| False positive rate | `6.7%` |
| False negative rate | `1.2%` |
| LoRa stale rows | `65 / 2160 = 3.0%` |
| Node A current | `123.0 mA` average from 30-second INA219 samples |
| Node B current | `174.8 mA` average |
| Road run energy | `89.3 mAh` |
| Estimated 10000 mAh runtime | `25.2 h` |
| Digital-twin waiting-pressure estimate | `31.6%` lower than fixed-time control |

The waiting-pressure estimate is a digital-twin comparison: the same real road demand from the CSV is replayed under fixed-time control and under the adaptive controller. The road deployment itself proves real detection quality, LoRa freshness, energy consumption, and real-data simulator integration.

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
- `docs/road-field-data-collection.md`: real-road data collection workflow for digital-twin evidence, false positives, and energy notes
- `docs/ina219-energy-measurement.md`: real current and energy measurement workflow with INA219
- `docs/final-presentation-plan.md`: slide plan, video storyboard, missing-photo checklist, and graph list
- `docs/final-delivery-checklist.md`: official assignment requirement mapping and final submission checklist
- `docs/live-demo-log-format.md`: final four-sensor live-demo terminal/CSV format
- `tools/final_presentation_graphs.py`: generates final graph PNGs for the presentation
- `data/data_readed/presentation_graphs/`: final slide-ready graph images

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

For the same visual simulator driven by real road queue counts from the validated CSV. Cars still enter from outside the crossroad and pass the far/near sensors normally; the CSV controls the traffic pressure.

```powershell
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv
```

For a slower presentation replay with readable cars:

```powershell
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv --speed 1.5 --queue-scale 3
```

For a text-only comparison between the simulator controller and the real firmware states:

```powershell
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv --summary
```

Generate the final evidence dashboard and written report from the validated road CSV:

```powershell
python tools\final_evidence_report.py --csv data\data_readed\road_26-05-19_crossroads.csv
```

Generate slide-ready graphs:

```powershell
python tools\final_presentation_graphs.py --csv data\data_readed\road_26-05-19_crossroads.csv --power-csv data\road_sessions\ina219_power_timeseries_2026-05-20.csv --out-dir data\data_readed\presentation_graphs
```

Presentation planning:

```text
docs\final-presentation-plan.md
```

## Real Road Data Collection

For final IoT evidence, collect real sensor data from a physical road position and visualize it with the road dashboard:

```powershell
python tools\road_data_logger.py --port COM3 --node node_a --out data\road_sessions\road_2026-05-16_node_a.csv
python tools\road_dashboard.py --csv data\road_sessions\road_2026-05-16_node_a.csv
```

While logging, type `v` when a vehicle is inside the observed sensor zone and `n` when the zone is empty. After the session:

Default sensor thresholds are `100 cm` for the far sensor and `100 cm` for the near sensor. During logging, type `set_thresholds 80 60` to tune them without reflashing.

```powershell
python tools\road_data_summary.py --csv data\road_sessions\road_2026-05-16_node_a.csv --out data\road_sessions\road_2026-05-16_node_a_summary.txt
python tools\sensor_threshold_analysis.py --csv data\road_sessions\road_2026-05-16_node_a.csv --sensor both --out data\road_sessions\road_2026-05-16_thresholds.txt
python tools\energy_estimator.py --duration-min 30 --node-a-ma 120 --node-b-ma 160 --battery-mah 10000
```

See `docs/road-field-data-collection.md` for the full field checklist.

If using an INA219, wire it as described in `docs/ina219-energy-measurement.md`, then summarize measured current with:

```powershell
python tools\ina219_energy_summary.py --csv data\road_sessions\node_a_ina219.csv --csv data\road_sessions\node_b_ina219.csv --road-csv data\data_readed\road_26-05-19_crossroads.csv
```

The validated road dataset used a fixed `100 cm` threshold for both far and near ultrasonic sensors. The reported `96.6%` accuracy is calculated from labelled real-road samples: false positives and false negatives are measured from the CSV, not guessed. After seeing the remaining false positives and one real sensor wiring issue, the firmware was improved with per-sensor threshold commands, median-of-3 ultrasonic distance filtering, 2-sample occupancy debouncing, and sensor-health diagnostics. Future validation is to collect a second road CSV with `sensor_filter=median3_debounce2` and `sensor_health` fields, then compare FP/FN against the current baseline.

## Firmware Notes

The firmware now includes the final project features:

- sensor reading is implemented with Arduino primitives
- ultrasonic occupancy is stabilized with median3 distance filtering and debounce2 state changes
- repeated invalid ultrasonic readings are surfaced as sensor-health `WARN` / `FAIL`
- telemetry encoding/decoding uses a compact CSV payload
- a shared LoRa transport now targets the onboard `SX1262` radio on `Heltec WiFi LoRa 32 V3`
- the serial-emulation path is still kept for testing before real hardware is available
- both nodes now support `log quiet`, `log summary`, `log verbose`, `status`, and `report`
- Node B now times out stale radio telemetry after `3000 ms` so old packets do not keep a phantom queue alive

## Final Presentation Assets

Use these files directly in the final slides:

- `data\data_readed\road_26-05-19_crossroads_evidence_dashboard.html`
- `data\data_readed\road_26-05-19_crossroads_evidence_report.md`
- `data\data_readed\presentation_graphs\01_detection_confusion_matrix.png`
- `data\data_readed\presentation_graphs\02_detection_quality_rates.png`
- `data\data_readed\presentation_graphs\03_energy_consumption.png`
- `data\data_readed\presentation_graphs\04_lora_reliability.png`
- `data\data_readed\presentation_graphs\05_traffic_demand_over_time.png`
- `data\data_readed\presentation_graphs\06_detected_vehicle_activations.png`
- `data\data_readed\presentation_graphs\07_time_saving_estimate.png`
- `data\data_readed\presentation_graphs\08_digital_twin_pipeline.png`
- `data\data_readed\presentation_graphs\09_power_consumption_timeseries.png`

## Final Remaining Work

1. Add the road-test videos and hardware photos into the presentation video edit.
2. Capture any missing photos listed in `docs\final-presentation-plan.md`.
3. Build the PowerPoint around the generated graphs and evidence dashboard.
4. During the demo, state clearly that the time-saving number is a digital-twin estimate using real road demand.
