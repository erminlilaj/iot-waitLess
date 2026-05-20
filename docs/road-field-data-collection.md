# Road Field Data Collection Guide

Use this guide on Saturday, May 16, 2026, when collecting real crossroad data.

The goal is to answer the professor's comment directly:

- real sensor readings from a real road
- false-positive and false-negative evidence
- a digital-twin screen recording driven by logged IoT data
- energy measurements or at least a clearly labelled energy estimate

## What To Bring

- ESP32 LoRa Node A with the two ultrasonic sensors wired
- ESP32 LoRa Node B if you want the full two-node demo
- laptop with this repository
- USB cables and a power bank
- phone for road video
- tape, cardboard, tripod, or any stable mount for the sensors
- optional but strongly recommended: USB power meter

Safety: stay on the sidewalk or another safe area. Do not place hardware where it can distract drivers or enter the vehicle path.

## Best Setup For Tomorrow

Use two recordings:

1. Road video from your phone showing the real sensor placement and vehicles.
2. Screen video from the laptop showing live CSV logging and the digital twin dashboard.

For the professor, the most important evidence is not that LoRa sends packets. The important evidence is:

- when a real car is present, the sensor usually says `OCC`
- when no car is present, the sensor usually says `FREE`
- when it fails, we can quantify the failure instead of hiding it

## Before Leaving Home

From PowerShell in the project folder:

```powershell
cd C:\Users\Lenovo\Desktop\Sperenza\Spring_2026\iot\group_project
python -m pip install pyserial
python tools\road_data_logger.py --list-ports
```

If you see only Bluetooth ports, the ESP32 is not connected yet. After plugging in the board, choose the new USB/JTAG/serial port that appears, not the Bluetooth port.

Flash Node A:

```powershell
C:\Users\Lenovo\.platformio\penv\Scripts\platformio.exe run --environment node_a --target upload
```

If using Node B too, flash Node B:

```powershell
C:\Users\Lenovo\.platformio\penv\Scripts\platformio.exe run --environment node_b --target upload
```

## Simple Data Collection: Node A Sensor Evidence

This is the most important test if you only have time for one setup.

1. Connect Node A to the laptop by USB.
2. Put the sensors near the road, aimed at the observed lane.
3. Start logging:

```powershell
python tools\road_data_logger.py --port COM3 --node node_a --out data\road_sessions\road_2026-05-16_node_a.csv
```

Use the correct port if it is not `COM3`.

In a second PowerShell window, open the digital twin dashboard:

```powershell
python tools\road_dashboard.py --csv data\road_sessions\road_2026-05-16_node_a.csv
```

Start the laptop screen recording after both windows are visible.

## Quick Threshold Tuning Before Recording

The firmware lets you change sensor thresholds from the serial logger or monitor without editing code.

Useful commands:

```text
thresholds
filter
health
set_thresholds 80 60
set_far_threshold 90
set_near_threshold 50
```

The values are in centimeters. The default firmware threshold is:

- far sensor: `100 cm`
- near sensor: `100 cm`

A smaller threshold usually reduces false positives, but can increase false negatives if cars are farther away from the sensor.

Simple tuning method:

1. With no car in the target area, check that the sensor usually reports `FREE`.
2. With a car/object in the target area, check that the sensor reports `OCC`.
3. If the sensor reports `OCC` too often when empty, reduce the threshold.
4. If the sensor misses vehicles, increase the threshold or improve the sensor angle.

## Sensor Reliability Explanation

For the validated road dataset in `data\data_readed\road_26-05-19_crossroads.csv`, the firmware threshold was fixed at:

- far sensor: `100 cm`
- near sensor: `100 cm`

The `96.6%` detection accuracy is based on labelled real-road samples, not on a simulated assumption. During the road run, samples were marked as vehicle present or road empty, then the logged sensor state was compared against those labels.

The false positives were measured directly from the CSV: `59` empty-road samples were still detected as occupied. The false negatives were also measured directly: `15` vehicle-present samples were missed.

Reliability response added after this measured result:

- per-sensor threshold tuning commands, because each ultrasonic module and physical angle can behave differently
- median-of-3 distance filtering, so short ultrasonic spikes do not immediately create false detections
- 2-sample occupancy debouncing, so a vehicle state changes only after repeated consistent readings
- sensor-health diagnostics, so repeated invalid `999 cm` timeout readings are reported as `WARN` or `FAIL` instead of silently looking like an empty road

For the next road run, the CSV logger records the filter mode in `sensor_filter` and the diagnostic state in `sensor_health`. The expected filter value after this improvement is `median3_debounce2`, and the comparison target is whether FP/FN improve against the `96.6%` baseline run while the health field stays `F:OK,N:OK`.

## Label Ground Truth While Recording

The logger accepts simple keyboard labels. The label applies to the next samples until you change it.

- type `v` then Enter when a vehicle is inside the observed sensor zone
- type `n` then Enter when the observed sensor zone is empty
- type `u` then Enter when you are uncertain
- type `note text here` then Enter to mark a useful situation
- type `q` then Enter to stop logging

Example notes:

```text
note sensor angled toward parked cars
note pedestrian crossed
note bus passed close
note road empty for calibration
```

This is how we compute false positives and false negatives later.

## Suggested Road Session

Try to collect at least 15 minutes.

| Segment | Duration | What to do |
| --- | ---: | --- |
| Empty-road baseline | 3-5 min | Label mostly `n`; check false positives |
| Normal traffic | 8-10 min | Switch between `v` and `n` as cars enter/leave the sensor zone |
| Busy traffic / queue | 5 min | Capture real queue or repeated vehicles if available |
| Difficult cases | 2-3 min | Record pedestrians, parked cars, odd angles, or reflections if they happen |

Do not worry if the sensor is imperfect. Imperfection is useful data as long as it is recorded honestly.

## Full IoT Demo: Node B Dashboard

If both nodes are working:

1. Power Node A near side A sensors.
2. Connect Node B to the laptop by USB.
3. Power or wire Node B with side B sensors and LEDs.
4. Start logging Node B:

```powershell
python tools\road_data_logger.py --port COM3 --node node_b --out data\road_sessions\road_2026-05-16_node_b.csv
```

5. Start dashboard:

```powershell
python tools\road_dashboard.py --csv data\road_sessions\road_2026-05-16_node_b.csv
```

In the video, make sure the dashboard shows:

- live far/near sensor state
- local and remote queue values
- `source=LORA_RADIO` if LoRa is active
- green side and phase
- false-positive / false-negative metrics once labels exist

The terminal logger also prints a live table with:

- far and near distance in centimeters
- far and near `OCC` / `FREE`
- current threshold values
- queue values
- controller/network state
- manual truth label
- `TP`, `TN`, `FP`, or `FN` when ground truth is labelled

## After The Road Session

Generate a summary:

```powershell
python tools\road_data_summary.py --csv data\road_sessions\road_2026-05-16_node_a.csv --out data\road_sessions\road_2026-05-16_node_a_summary.txt
```

Analyze which threshold would have worked best for the labelled road data:

```powershell
python tools\sensor_threshold_analysis.py --csv data\road_sessions\road_2026-05-16_node_a.csv --sensor both --out data\road_sessions\road_2026-05-16_thresholds.txt
```

If you also recorded Node B:

```powershell
python tools\road_data_summary.py --csv data\road_sessions\road_2026-05-16_node_b.csv --out data\road_sessions\road_2026-05-16_node_b_summary.txt
```

Replay the collected CSV in the same visual simulator, using real road queue counts. Cars still enter from outside the crossroad and move through the far and near sensor zones normally; the CSV controls how much traffic pressure appears.

```powershell
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv
```

For a slower, cleaner presentation view:

```powershell
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv --speed 1.5 --queue-scale 3
```

Or print the simulator-vs-real-firmware comparison summary:

```powershell
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv --summary
```

Generate the final evidence dashboard and written report:

```powershell
python tools\final_evidence_report.py --csv data\data_readed\road_26-05-19_crossroads.csv
```

Keep these files:

- `.csv` file
- `.raw.log` file
- summary `.txt`
- threshold-analysis `.txt`
- evidence dashboard `.html`
- evidence report `.md`
- phone road video
- laptop screen video
- photos of sensor placement

## Energy Measurement

Energy considerations are mandatory.

Best option now: use the INA219 current sensor and record average current for each node.

Measure:

- Node A: sensing plus LoRa transmission
- Node B: sensing plus LoRa receive plus LEDs

INA219 wiring and logging steps are in:

```text
docs\ina219-energy-measurement.md
```

After you collect INA219 logs, summarize them:

```powershell
python tools\ina219_energy_summary.py --csv data\road_sessions\node_a_ina219.csv --csv data\road_sessions\node_b_ina219.csv --road-csv data\data_readed\road_26-05-19_crossroads.csv --out data\road_sessions\ina219_energy_summary.txt
```

Then regenerate the final evidence report using the measured current values printed by that summary:

```powershell
python tools\final_evidence_report.py --csv data\data_readed\road_26-05-19_crossroads.csv --node-a-ma <MEASURED_A_MA> --node-b-ma <MEASURED_B_MA> --energy-note "Current values were measured with an INA219 high-side current sensor."
```

If you only need a quick estimate, run:

```powershell
python tools\energy_estimator.py --duration-min 30 --node-a-ma 120 --node-b-ma 160 --battery-mah 10000
```

Replace `120` and `160` with your measured average current values.

If you do not complete the INA219 measurement, still run the estimator but write clearly in the report:

```text
Energy values are estimated, not directly measured.
```

## What To Say In The Final Report

Use wording like this:

```text
We used the simulator as a digital twin, but the data source was not only synthetic.
During the road session, the ESP32 ultrasonic node recorded real sensor states
from a physical road position. We labelled ground truth manually while recording,
then calculated false positives and false negatives from the CSV log.
```

That sentence directly addresses the professor's feedback.
