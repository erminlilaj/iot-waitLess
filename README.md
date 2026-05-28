# Wait Less

Wait Less is an IoT adaptive traffic-light prototype for a two-way crossroad. The system uses real ultrasonic sensors, two ESP32 Heltec LoRa nodes, real road data, INA219 energy measurements, and a simulator replay driven by collected CSV data.

The main goal is not only to show a simulation, but to show the full IoT path:

```text
real sensors -> ESP32 firmware -> LoRa telemetry -> traffic-light control -> CSV evidence -> evaluation -> simulator replay
```

## Final Package

| Item | Path |
| --- | --- |
| Final presentation | `docs/final/Wait_Less_final_presentation.pptx` |
| Real road dataset | `data/data_readed/road_26-05-19_crossroads.csv` |
| Road evidence report | `data/data_readed/road_26-05-19_crossroads_evidence_report.md` |
| Road dashboard | `data/data_readed/road_26-05-19_crossroads_evidence_dashboard.html` |
| Sensor reliability comparison | `data/data_readed/sensor_reliability_files/` |
| Presentation graphs | `data/data_readed/presentation_graphs/` |
| Firmware | `firmware/` and `lib/traffic_control/` |
| Simulator | `simulation/` |
| Data collection and analysis tools | `tools/` |
| Hardware wiring | `docs/hardware-map.md` |
| Code explanation | `docs/code-understanding-guide.md` |
| Technical numbers cheat sheet | `docs/final/technical_numbers_cheat_sheet.md` |

## System Architecture

The prototype uses two ESP32 Heltec LoRa boards.

| Node | Role |
| --- | --- |
| Node A | Reads Side A far/near ultrasonic sensors and sends Side A telemetry over LoRa |
| Node B | Reads Side B far/near ultrasonic sensors, receives Node A telemetry, runs the controller, and drives both traffic-light directions |

Each side has:

- one far ultrasonic sensor for approaching vehicles
- one near ultrasonic sensor for stop-line / queue detection

Node B combines local Side B data with remote Side A data and decides which side receives green.

## Hardware Summary

- 2 x ESP32 Heltec WiFi LoRa 32 V3 boards
- 4 x HC-SR04 ultrasonic sensors
- 6 x traffic-light LEDs: red/yellow/green for Side A and Side B
- 1 x push button for emergency priority testing
- INA219 current sensor for energy measurement
- LoRa link between Node A and Node B

Detailed pin mapping is in:

```text
docs/hardware-map.md
firmware/shared/HardwareMap.h
```

The live demo threshold is `50 cm / 50 cm`. The road-evaluation CSV used `100 cm / 100 cm`.

## Firmware Features

The final firmware includes:

- median-of-3 ultrasonic distance filtering
- 2-sample occupancy debounce
- per-sensor threshold command through serial
- sensor health status: `OK`, `WARN`, `FAIL`
- compact LoRa telemetry packets
- heartbeat packets for low-traffic and peak modes
- stale Node A detection and backup behavior on Node B
- emergency push-button logic
- INA219 support when the sensor is connected

The communication layer separates traffic data from node health:

```text
Telemetry packet:
A,1,0,4,2,2,0,12345,42.0,999.0

Heartbeat packet:
H,A,I,12345
H,A,P,12345
```

This avoids confusing "no useful traffic update" with "Node A failed".

## Build And Upload Firmware

Install PlatformIO, then build each node:

```powershell
platformio run -e node_a
platformio run -e node_b
```

Upload to the connected board:

```powershell
platformio run -e node_a --target upload --upload-port COM3
platformio run -e node_b --target upload --upload-port COM3
```

Open the serial monitor:

```powershell
platformio device monitor --port COM3 --baud 115200
```

Useful serial commands:

```text
status
report
log summary
log verbose
set_thresholds 50 50
set_thresholds 100 100
```

## Live Data Logging

Use the road logger to save Node B output into CSV:

```powershell
python tools/road_data_logger.py --port COM3 --node node_b --out data/road_sessions/final_demo_node_b.csv
```

During road collection, manual labels are used:

```text
v = vehicle present
n = empty road
```

This creates a CSV that can be evaluated for true positives, false positives, false negatives, LoRa stale status, thresholds, sensor health, distances, queues, and light states.

## Real Road Evaluation

The validated road dataset is:

```text
data/data_readed/road_26-05-19_crossroads.csv
```

Summary:

| Metric | Result |
| --- | --- |
| Duration | 18.0 minutes |
| Samples | 2160 |
| Thresholds | 100 cm / 100 cm |
| TP / TN / FP / FN | 1269 / 817 / 59 / 15 |
| Accuracy | 96.6% |
| False positive rate | 6.7% |
| False negative rate | 1.2% |
| LoRa stale rows | 65 / 2160 = 3.0% |

Generate the report and dashboard again with:

```powershell
python tools/final_evidence_report.py --csv data/data_readed/road_26-05-19_crossroads.csv
```

## Sensor Reliability Comparison

After the first road evaluation, the firmware was improved with median filtering and debounce. The before/after comparison data is in:

```text
data/data_readed/sensor_reliability_files/
```

Files:

```text
compare_no_filter_2026-05-27_node_b.csv
compare_median3_debounce2_2026-05-27_node_b.csv
compare_sensor_reliability_2026-05-27_notes.txt
```

Comparison summary:

| Metric | Before | After |
| --- | ---: | ---: |
| Samples | 600 | 600 |
| Accuracy | 94.17% | 98.17% |
| False positives | 27 | 9 |
| False negatives | 8 | 2 |
| Noise/ghost false positives | 13 | 0 |
| LoRa stale samples | 5 | 2 |
| Occupancy state changes | 46 | 28 |

Main result: median-of-3 filtering removed short ultrasonic spikes, and 2-sample debounce made the occupancy signal more stable. Pedestrian false positives can still happen because ultrasonic sensors detect physical objects, not vehicle type.

## Energy Measurements

INA219 measurements were taken before and after the communication/sleep improvements.

Baseline:

| Node | Average current | Average power |
| --- | ---: | ---: |
| Node A | 121.4 mA | 609.4 mW |
| Node B | 174.8 mA | 875.7 mW |

After optimization:

| Mode | Average current | Average power | Reduction |
| --- | ---: | ---: | ---: |
| Node A active telemetry | 118.7 mA | 595.9 mW | 2.2% |
| Node A idle heartbeat | 74.6 mA | 375.2 mW | 38.6% |
| Node A peak sleep | 32.8 mA | 164.3 mW | 73.0% |
| Node B telemetry receive | 172.9 mA | 866.2 mW | 1.1% |
| Node B heartbeat receive | 158.4 mA | 795.2 mW | 9.4% |

Node A improves the most because it can reduce repeated LoRa traffic and sleep during peak fixed-cycle mode. Node B remains mostly awake because it controls the LEDs.

Generate energy and presentation graphs with:

```powershell
python tools/final_presentation_graphs.py --csv data/data_readed/road_26-05-19_crossroads.csv --power-csv data/road_sessions/ina219_power_timeseries_2026-05-20.csv --out-dir data/data_readed/presentation_graphs
```

## Simulator

The simulator is used as a digital-twin replay. It can run random traffic, manual queues, or real CSV demand.

Basic simulator:

```powershell
python simulation/visual_simulator.py
```

Real-data replay:

```powershell
python simulation/visual_simulator_real_data.py --csv data/data_readed/road_26-05-19_crossroads.csv
```

Slower replay for presentation:

```powershell
python simulation/visual_simulator_real_data.py --csv data/data_readed/road_26-05-19_crossroads.csv --speed 1.5 --queue-scale 3
```

Text-only summary:

```powershell
python simulation/visual_simulator_real_data.py --csv data/data_readed/road_26-05-19_crossroads.csv --summary
```

## Repository Structure

```text
firmware/
  node_a/                 Node A firmware
  node_b/                 Node B firmware
  shared/                 shared config, pin map, INA219 support

lib/traffic_control/      shared controller, sensing, LoRa, packet logic
simulation/               visual simulator and real-data replay
tools/                    logger, report, graph, and analysis scripts
data/data_readed/         final road CSV, reports, graphs, reliability data
data/road_sessions/       live test CSV logs and INA219 time-series
docs/                     hardware map, code guide, diagrams, final slides
```

## Notes For The Demo

Recommended live-demo order:

1. Show Node A and Node B hardware.
2. Start Node B serial log and show distances, queues, stale status, and light states.
3. Trigger the emergency button once and twice to show Side B / Side A priority.
4. Show the saved CSV and explain the truth labels.
5. Show the evaluation numbers: accuracy, false positives, false negatives, LoRa stale percentage.
6. Show the energy improvement from heartbeat and peak sleep.
7. End with simulator replay from the real road CSV.

## Contributors

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/hamzaabedlkadr-b">
        <img src="https://github.com/hamzaabedlkadr-b.png" width="100px;"/>
        <br />
      </a>
      <br />
      <a href="https://www.linkedin.com/in/hamza-abdelkader/"> Hamza Abdel kader</a>
    </td>

<td align="center">
  <a href="https://github.com/erminlilaj">
    <img src="https://github.com/erminlilaj.png" width="100px;"/>
    <br />
  </a>
  <br />
  <a href="https://www.linkedin.com/in/ermin-lilaj-300057169/"> Ermin Lilaj</a>
</td>

<td align="center">
  <a href="https://github.com/darked0">
    <img src="https://github.com/darked0.png" width="100px;"/>
    <br />
    <sub><b>Nome Cognome 3</b></sub>
  </a>
  <br />
  <a href="www.linkedin.com/in/edoardo-severini"> Edoardo Severini</a>
</td>
  </tr>
</table>

---

## Demo / Presentation

<p align="center">
  📺 Watch the project presentation on YouTube
  <br /><br />

  <a href="https://www.youtube.com/watch?v=lq9b3uMraB4">
    <img 
      src="https://img.shields.io/badge/Watch%20on-YouTube-red?style=for-the-badge&logo=youtube" 
      alt="Watch on YouTube"
    />
  </a>
</p>
