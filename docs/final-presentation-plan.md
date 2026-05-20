# Wait Less Final Presentation Plan

This is the final story for the professor: we started with a simulation, connected it to real IoT hardware, collected real crossroad data, measured false positives/false negatives, measured energy, and used the real CSV as a digital-twin input.

## Core Claim

Wait Less is an IoT digital-twin traffic-light prototype. Four ultrasonic sensors measure real traffic presence, two ESP32 LoRa nodes exchange queue telemetry, Node B controls both traffic-light directions, and the final dashboard compares real road sensor data with the simulator replay.

Use this exact wording for the time-saving slide:

> The time-saving graph is a digital-twin estimate using the real road demand from our CSV. It compares the same demand under a fixed-time light and under our adaptive controller.

Do not say the road deployment already proved a real traffic delay reduction. The road deployment proves detection quality, communication freshness, energy, and real-data replay.

## Slide Outline

| Slide | Title | Main visual | Message |
| --- | --- | --- | --- |
| 1 | Wait Less | short road-test video frame or team setup photo | Real IoT traffic-light prototype, not only a simulator |
| 2 | Professor Feedback -> Our Response | before/after checklist | We moved from simulation to real sensors, real labels, energy, and digital twin |
| 3 | System Architecture | Node A/Node B photos + small diagram | Node A senses side A; Node B senses side B, receives LoRa, drives both lights |
| 4 | Hardware Roadmap | labelled Node A, Node B, sensor, LED photos | Four ultrasonic sensors, six LEDs, LoRa, INA219 energy measurement |
| 5 | Road Data Collection | road video + laptop live log screenshot | Real crossroad CSV with truth labels: vehicle / empty |
| 6 | Sensor Reliability | `01_detection_confusion_matrix.png` + `02_detection_quality_rates.png` | 96.6% accuracy; FP/FN measured from labels, not guessed |
| 7 | Robustness Improvements | log screenshot with `filter` and `health` | Per-sensor thresholds, median3, debounce2, sensor-health diagnostics |
| 8 | LoRa And Energy | `03_energy_consumption.png` + `04_lora_reliability.png` + `09_power_consumption_timeseries.png` | Two-node link freshness and measured INA219 consumption |
| 9 | Digital Twin Replay | simulator video + `05_traffic_demand_over_time.png` | Simulator cars are driven by real queue pressure from the road CSV |
| 10 | Waiting-Time Estimate | `07_time_saving_estimate.png` | Real demand replay estimates lower waiting pressure versus fixed-time control |
| 11 | Evidence Package | dashboard screenshot + graph thumbnails | CSV, dashboard, report, firmware, simulator, photos, videos |
| 12 | Future Work | clean bullet slide | Second road run with filtering enabled, better mounting, larger dataset, real deployment enclosure |

## Video Edit Plan

Make one polished video of about 60-90 seconds:

| Time | Visual | Text overlay |
| --- | --- | --- |
| 0-5 s | real crossroad establishing shot | Real crossroad test |
| 5-15 s | Node A and ultrasonic sensors | Node A: 2 ultrasonic sensors + LoRa transmit |
| 15-25 s | Node B, LEDs, LoRa | Node B: 2 sensors + LoRa receive + traffic lights |
| 25-35 s | laptop live log showing distance/car labels | Live ESP32 log and real labels |
| 35-45 s | road video with cars passing sensor area | Vehicle / empty truth labels |
| 45-55 s | INA219/current measurement photo | Measured energy, not guessed |
| 55-70 s | digital-twin simulator replay | Real CSV drives simulator traffic |
| 70-90 s | final dashboard/graphs montage | 96.6% accuracy, 3.0% stale LoRa, 31.6% estimated waiting-pressure reduction |

## Photos And Screenshots We Already Have

- Road-test videos from the real crossroad.
- Node A photo.
- Node B photo.
- Ultrasonic sensor photo.
- INA219 / consumption photo.
- Laptop log screenshot showing cars and distances from the road.
- Real CSV and dashboard/report.

## Extra Photos We Should Still Capture

- Wide crossroad photo with the sensor positions visible.
- One close-up of each ultrasonic sensor angle, especially showing where it points.
- Node A wiring close-up with labels for far/near trig/echo pins.
- Node B wiring close-up with labels for far/near sensors and both LED heads.
- Traffic-light LED photo showing both directions clearly.
- INA219 photo showing power path through `VIN+` and `VIN-`, not only the screen value.
- Laptop screenshot showing `filter=median3_debounce2` and `health=F:OK,N:OK`.
- Screenshot of the real-data simulator replay.
- Screenshot of the final evidence dashboard.
- Optional team/setup photo at the site, useful for credibility.

## Graph Assets

Generate all graph PNGs with:

```powershell
python tools\final_presentation_graphs.py --csv data\data_readed\road_26-05-19_crossroads.csv --power-csv data\road_sessions\ina219_power_timeseries_2026-05-20.csv --out-dir data\data_readed\presentation_graphs
```

| File | Use |
| --- | --- |
| `data\data_readed\presentation_graphs\01_detection_confusion_matrix.png` | TP/TN/FP/FN slide |
| `data\data_readed\presentation_graphs\02_detection_quality_rates.png` | Accuracy / FP / FN slide |
| `data\data_readed\presentation_graphs\03_energy_consumption.png` | INA219 measured current and power |
| `data\data_readed\presentation_graphs\04_lora_reliability.png` | LoRa live vs stale evidence |
| `data\data_readed\presentation_graphs\05_traffic_demand_over_time.png` | Road queue pressure over time |
| `data\data_readed\presentation_graphs\06_detected_vehicle_activations.png` | Vehicle activations by node/sensor |
| `data\data_readed\presentation_graphs\07_time_saving_estimate.png` | Fixed-time vs adaptive digital-twin estimate |
| `data\data_readed\presentation_graphs\08_digital_twin_pipeline.png` | Real data to simulator explanation |
| `data\data_readed\presentation_graphs\09_power_consumption_timeseries.png` | 30-second INA219 power-consumption trace |

## Key Numbers To Put On Slides

- Road run duration: `18.0 min`
- ESP32 samples: `2160`
- Detection TP/TN/FP/FN: `1269 / 817 / 59 / 15`
- Accuracy: `96.6%`
- False positive rate: `6.7%`
- False negative rate: `1.2%`
- LoRa stale rows: `65 / 2160 = 3.0%`
- Node A current: `123.0 mA`
- Node B current: `174.8 mA`
- Total current: `297.9 mA`
- Road run energy: `89.3 mAh`
- Estimated 10000 mAh runtime: `25.2 h`
- Peak total power: `1812.0 mW at 210 s`
- Digital-twin waiting-pressure reduction estimate: `31.6%`

Power graph explanation:

- The graph uses 21 INA219 samples taken every 30 seconds.
- The small change from the earlier Node A average (`121.4 mA` -> `123.0 mA`) is because the graph recalculates the average from the exact plotted samples.
- Node B stays higher because it is the receiver/controller node and drives the traffic LEDs.
- The largest peak at `210 s` happened while both nodes were active, with ultrasonic polling and LoRa running, and Node B also carrying the LED load.

## Final Demo Flow

1. Show the physical hardware photos first, so the professor immediately sees real IoT.
2. Show the live road log screenshot with distance, occupancy, and labels.
3. Show the accuracy graph and say FP/FN are measured from the labelled CSV.
4. Show the robustness log fields: `filter=median3_debounce2`, `health=F:OK,N:OK`.
5. Show INA219 energy graph.
6. Show simulator replay and explain it is driven by the real CSV queue pressure.
7. End with the evidence dashboard and future-work slide.

## Future Work Slide

- Collect a second road CSV after enabling the new filtering and health diagnostics.
- Tune thresholds per sensor and per mounting angle.
- Improve mounting stability and weather protection.
- Use a larger labelled dataset at different traffic densities.
- Replace manual labels with synchronized video annotation.
- Add low-power modes or adaptive sampling to reduce current.
- Add cloud upload / MQTT dashboard for a full IoT deployment.
