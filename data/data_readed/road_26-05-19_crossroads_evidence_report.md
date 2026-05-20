# Wait Less Final Evidence Report

Source CSV: `data\data_readed\road_26-05-19_crossroads.csv`

## Data Collection

- First sample: 2026-05-19 18:02:10
- Last sample: 2026-05-19 18:20:09
- CSV duration: 18.0 min
- ESP32 node samples: 2160

## Detection Quality

- TP/TN/FP/FN: 1269/817/59/15
- Accuracy: 96.6%
- False positive rate: 6.7%
- False negative rate: 1.2%

## Sensor Reliability Explanation

- The road run used a fixed ultrasonic threshold of `100 cm` on the far sensors and `100 cm` on the near sensors.
- The reliability numbers are based on real road labels: `1284` samples were labelled as vehicle present and `876` samples were labelled as empty.
- False positives were measured from the CSV, not guessed: `59` empty-road samples were still detected as occupied.
- False negatives were also measured: `15` vehicle-present samples were missed by the sensors.
- Reliability response after the road test: the firmware now supports per-sensor threshold tuning, median-of-3 ultrasonic distance filtering, and 2-sample occupancy debouncing.
- Why this tackles the measured problem: median filtering rejects one-sample distance spikes, while debouncing prevents a single noisy reading from immediately changing the vehicle state.
- Hardware robustness response: the firmware now also reports sensor health, so repeated invalid ultrasonic readings become `WARN`/`FAIL` instead of silently looking like an empty road.
- Next validation step: collect a second road CSV with the new `sensor_filter=median3_debounce2` and `sensor_health` log fields, then compare FP/FN against this baseline.

## LoRa Reliability

- LORA_RADIO rows: 2095 (97.0%)
- LORA_STALE rows: 65 (3.0%)

## Energy Measurement / Estimate

- Node A average current: 123.0 mA
- Node B average current: 174.8 mA
- Total average current: 297.9 mA
- Energy used during this road run: 89.3 mAh (0.45 Wh at 5 V)
- Estimated 10000 mAh power-bank runtime: 25.2 h
- Current values were recalculated from 21 INA219 samples at 30-second intervals on 2026-05-20. Node A: 123.0 mA average, 104.2-147.8 mA range. Node B: 174.8 mA average, 142.5-213.6 mA range. Peak total power was 1812.0 mW at 210 s when ultrasonic polling, LoRa activity, and Node B LED load overlapped.

## Digital Twin Replay

The same real road CSV is used as the traffic source for the visual simulator. The simulator keeps normal car movement: cars enter from outside the crossroad, pass the far and near sensor zones, and then the visual detections are compared with the real detections shown in the panel.

```powershell
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv --speed 1.5 --queue-scale 3
```

- Paired replay frames: 2159
- Real firmware vs simulator green-side match: 36.3%
- Real firmware vs simulator phase match: 81.6%

## One-Sentence Evidence Claim

This project uses real ultrasonic sensors on a real crossroad, measures false positives and false negatives from labelled road data, estimates field energy use, and replays the collected CSV inside the digital-twin simulator.
