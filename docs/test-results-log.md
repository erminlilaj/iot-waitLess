# Wait Less Test Results Log

Use this file as the single place to record validation results.

The goal is to keep one organized document for both:

- software-only tests
- later hardware bring-up tests

For each executed test:

1. run the scenario
2. call `report` on the node you tested
3. paste the report block into the matching evidence section below
4. mark the result as `PASS`, `PARTIAL`, or `FAIL`

## Software Results

| ID | Date | Scenario | Input / setup | Expected result | Actual result | Status |
| --- | --- | --- | --- | --- | --- | --- |
| SW-01 | 2026-04-09 | Scripted simulation baseline | `python simulation/simulate_traffic.py` | controller keeps A green early, then switches to B when B becomes clearly busier | A stayed green through balanced demand, entered yellow at `t=12 s`, and B became green at `t=14 s` | PASS |
| SW-02 | 2026-04-09 | Empty-lane yield check | targeted Python controller test: A queue goes from `3` to `0`, B queue goes from `0` to `2` at `t=6 s` | yellow should begin at `t=6 s`, B should be green at `t=8 s` | yellow began at `t=6 s`, B became green at `t=8 s` | PASS |
| SW-03 | 2026-04-09 | Busier-side switch after minimum green | targeted Python controller test: A queue `2 -> 1`, B queue `1 -> 4` at `t=6 s` | yellow should begin at `t=6 s`, B should be green at `t=8 s` | yellow began at `t=6 s`, B became green at `t=8 s` | PASS |
| SW-04 | 2026-04-09 | Max-green enforcement | targeted Python controller test with both sides waiting continuously | controller should force yellow at `t=20 s` and switch to B at `t=22 s` | yellow began at `t=20 s`, B became green at `t=22 s` | PASS |
| SW-05 | 2026-05-20 | Remote ambulance priority | `remote_ambulance_on` on real firmware path | side A gets emergency priority through yellow | tested previously during firmware bring-up; remote emergency request forced side A priority after the safe yellow transition | PASS |
| SW-06 | 2026-05-20 | Local ambulance priority | `local_ambulance_on` on real firmware path | side B gets emergency priority through yellow | tested previously during firmware bring-up; local emergency request forced side B priority after the safe yellow transition | PASS |
| SW-07 | 2026-05-20 | Sensor robustness improvement | shared firmware sensor layer | ultrasonic noise should be reduced before occupancy reaches the queue estimator | implemented median-of-3 distance filtering and 2-sample occupancy debouncing; Node A and Node B firmware builds passed | PASS |
| SW-08 | 2026-05-20 | Sensor health diagnostics | repeated invalid ultrasonic readings | firmware should expose sensor timeout/wiring/angle problems instead of treating them only as empty road | added far/near sensor-health tracking with `OK`, `WARN`, and `FAIL` states in status/report/log output | PASS |

## Hardware Results

| ID | Date | Hardware item | Test | Expected result | Actual result | Status |
| --- | --- | --- | --- | --- | --- | --- |
| HW-01 | 2026-05-19 | Node B LEDs | startup self-test and Side B J3 remap | red, yellow, green sequence appears once and both traffic-light heads are controllable | Side B LEDs remapped to `J3-11/J3-10/J3-9`; Node B controller logs continued normally after upload | PASS |
| HW-02 | 2026-05-20 | Node B far sensor | distance / occupancy detection | object inside threshold shows `OCC` | final check showed `far=8.5cm/OCC` at `100 cm` threshold | PASS |
| HW-03 | 2026-05-20 | Node B near sensor | distance / occupancy detection | object inside threshold shows `OCC` | final check showed `near=7.1cm/OCC` at `100 cm` threshold | PASS |
| HW-04 | 2026-04-09 | Node A telemetry path | telemetry generation on real board using serial emulation inputs | queue estimator updates payload correctly on the board | `state 1 0 -> A,1,0,1,0,1,0,...`, `state 0 1 -> A,0,1,1,0,1,0,...`, `state 0 0 -> A,0,0,1,1,0,0,...`, all with `tx=RADIO_TX_OK` | PASS |
| HW-05 | 2026-05-20 | LoRa radio link | packet transfer A -> B | Node B receives telemetry over radio | final two-node check changed from `LORA_STALE` to `LORA_RADIO` and updated `remoteQ=1` from live Node A traffic | PASS |
| HW-06 | 2026-05-20 | Emergency behavior | ambulance override on real setup | emergency side gets priority after yellow | tested previously on the real setup; emergency override worked and the controller used yellow before changing priority | PASS |
| HW-07 | 2026-05-19 | Real road sensor data | log Node A and Node B at a real road using `tools/road_data_logger.py` | CSV contains real sensor readings and manual ground-truth labels | `data\data_readed\road_26-05-19_crossroads.csv` contains `2160` ESP32 samples from an `18.0 min` road run | PASS |
| HW-08 | 2026-05-20 | Sensor false positives / false negatives | summarize labeled road CSV with `tools/road_data_summary.py` | report includes TP, TN, FP, FN, accuracy, false-positive rate, and false-negative rate | TP/TN/FP/FN `1269/817/59/15`, accuracy `96.6%`, FP `6.7%`, FN `1.2%` | PASS |
| HW-09 | 2026-05-20 | Energy measurement | measure Node A and Node B current with INA219, then regenerate the evidence report | report includes measured average current, energy used, and estimated battery life | detailed 30-second samples: Node A `123.0 mA` avg (`104.2-147.8 mA`), Node B `174.8 mA` avg (`142.5-213.6 mA`), total `297.9 mA`; evidence report regenerated with measured values | PASS |
| HW-10 | 2026-05-20 | Threshold tuning | analyze labelled road CSV with `tools/sensor_threshold_analysis.py` | report recommends far/near thresholds based on FP/FN tradeoff | threshold-analysis file generated; final road run used fixed `100/100 cm` thresholds and achieved `96.6%` accuracy | PASS |
| HW-11 | 2026-05-20 | Node A near sensor | distance / occupancy detection | object inside threshold shows `OCC` | CSV check showed near sensor responding from about `30.4cm/OCC` down to `3.6cm/OCC` | PASS |
| HW-12 | 2026-05-20 | Node A far sensor | wiring fix and distance / occupancy detection | object inside threshold shows `OCC` | after rewiring, final check showed far sensor reading about `3 cm/OCC` at `100 cm` threshold | PASS |
| HW-13 | 2026-05-20 | Post-road sensor filtering | firmware build and logger format | logs should expose the active filter for future FP/FN comparison | summary logs now include `filter=median3_debounce2`, and future CSVs include `sensor_filter` | PASS |
| HW-14 | 2026-05-20 | Sensor health logging | future field CSV format | logger should capture whether each ultrasonic sensor is healthy during the run | future CSVs include `sensor_health`, for example `F:OK,N:OK`; repeated invalid readings become visible as `WARN`/`FAIL` | PASS |

## Evidence: Software Tests

### Scripted Simulation Baseline

```text
12s |      1 |      4 |     A | YELLOW |             9 |          18
13s |      1 |      4 |     A | YELLOW |             9 |          18
14s |      1 |      4 |     B |  GREEN |            18 |           9
```

### Targeted Controller Checks

```text
TEST1 empty-lane yield:
6s -> A, YELLOW
8s -> B, GREEN

TEST2 busier-side switch:
6s -> A, YELLOW
8s -> B, GREEN

TEST3 max-green enforcement:
20s -> A, YELLOW
22s -> B, GREEN
```

## Evidence: Node A Reports

Paste `Node A` output from the `report` command here.

```text
Node A ready.
[LoRa] backend: RadioLib SX1262
A STATUS | source=SERIAL_EMU | far=OCC | near=FREE | queue=1 | in=1 | out=0 | emergency=OFF | tx=RADIO_TX_OK | payload=A,1,0,1,0,1,0,62000
A STATUS | source=SERIAL_EMU | far=FREE | near=OCC | queue=1 | in=1 | out=0 | emergency=OFF | tx=RADIO_TX_OK | payload=A,0,1,1,0,1,0,70000
A STATUS | source=SERIAL_EMU | far=FREE | near=FREE | queue=0 | in=1 | out=1 | emergency=OFF | tx=RADIO_TX_OK | payload=A,0,0,1,1,0,0,79000
```

### Final Node A Sensor Checks, 2026-05-20

CSV evidence files:

- `data\road_sessions\node_a_sensor_check_now.csv`
- `data\road_sessions\node_a_far_check_now.csv`
- `data\road_sessions\node_a_other_sensor_check_now.csv`
- `data\road_sessions\node_a_far_recheck_now.csv`
- `data\road_sessions\node_a_far_last_check_now.csv`

Observed during serial checks:

```text
Node A open-space check:
far=999.0cm/FREE | near=999.0cm/FREE | thresholds=100.0/100.0 | tx=RADIO_TX_OK

Node A near sensor check:
far=999.0cm/FREE | near=30.4cm/OCC -> 3.6cm/OCC | thresholds=100.0/100.0 | tx=RADIO_TX_OK
```

Final wiring note:

```text
The Node A far sensor initially stayed at 999.0cm/FREE during CSV captures.
After rewiring, the final fixed check showed the far sensor reading about 3 cm/OCC at the 100 cm threshold.
```

## Evidence: Node B Reports

Paste `Node B` output from the `report` command here.

```text
Node B ready.
[LoRa] backend: RadioLib SX1262
B STATUS | far=999.0cm/FREE | near=999.0cm/FREE | localQ=0 | remoteQ=0 | source=LORA_STALE | stale=ON | green=A | phase=GREEN | emergency=OFF | priority=A | lights=A:GREEN B:RED
B STATUS | far=999.0cm/FREE | near=999.0cm/FREE | localQ=0 | remoteQ=1 | source=LORA_RADIO | stale=OFF | green=A | phase=GREEN | emergency=OFF | priority=A | lights=A:GREEN B:RED
```

## Evidence: Emergency Priority Tests

Emergency behavior was tested previously during firmware bring-up and was missed in the results table. The tested behavior was:

```text
Remote emergency:
command = remote_ambulance_on
expected = side A receives emergency priority after the safe yellow transition
result = PASS

Local emergency:
command = local_ambulance_on
expected = side B receives emergency priority after the safe yellow transition
result = PASS
```

Conclusion:

```text
The controller does not jump instantly from one green side to the other. It preserves the yellow transition, then gives priority to the emergency side.
```

### Final Node B And Two-Node Check, 2026-05-20

CSV evidence file:

- `data\road_sessions\two_nodes_final_check_now.csv`

Observed from Node B serial:

```text
1.75s  B far=8.5cm/OCC | near=7.1cm/OCC | localQ=1 | remoteQ=0 | A/GREEN | LORA_STALE
2.75s  B far=8.5cm/OCC | near=7.1cm/OCC | localQ=1 | remoteQ=1 | A/GREEN | LORA_RADIO
14.75s B far=8.5cm/OCC | near=7.1cm/OCC | localQ=1 | remoteQ=1 | A/GREEN | LORA_RADIO
```

Conclusion:

```text
Node B sensors worked, Node A telemetry was received over LoRa, and the final two-node communication path was live.
```

## Evidence: INA219 Energy Measurement

Measurement file:

- `data\road_sessions\ina219_energy_measurement_2026-05-20.txt`

Measured on 2026-05-20 by the prototype test team:

```text
Node A:
average current = 123.0 mA
current range = 104.2-147.8 mA
average bus voltage = 5.02 V
average power = 617.6 mW
role = 2 ultrasonic sensors + LoRa transmit

Node B:
average current = 174.8 mA
current range = 142.5-213.6 mA
average bus voltage = 5.01 V
average power = 875.9 mW
role = 2 ultrasonic sensors + LoRa receive + traffic LEDs

Two-node total:
average current = 297.9 mA
average power = 1493.5 mW
peak power = 1812.0 mW at 210 s
```

The final evidence dashboard/report and presentation graphs were regenerated with the detailed 30-second INA219 samples. The peak occurs when ultrasonic polling, LoRa activity, and Node B LED load overlap.

## Notes And Fixes

Use this section to record what changed after each failed or partial test.

- Example: "Near sensor threshold reduced from 18 cm to 15 cm because stop-line occupancy was detected too early."
- Example: "Kept log mode on summary and only switched to verbose while checking LoRa receive behavior."
- Real hardware note on 2026-04-09: a fallback-to-serial issue in the LoRa backend was fixed, after which both boards reported `RadioLib SX1262` and live A->B LoRa communication was confirmed.
- Terminal note on 2026-04-09: commands pasted too quickly into the monitor can concatenate into one line; sending one command per Enter works reliably.
- Final hardware note on 2026-05-20: Node A far sensor wiring was corrected after repeated `999.0cm/FREE` captures; final fixed check showed about `3 cm/OCC` after the fix.
- Final energy note on 2026-05-20: INA219 measurements replaced the earlier estimate in the evidence report.
