Wait Less - ESP32 Node Commands (Windows / PlatformIO)

Project folder:
  C:\Users\Lenovo\Desktop\Sperenza\Spring_2026\iot\group_project

Use the exact commands below in PowerShell.


1) Build + Upload:
C:\Users\Lenovo\.platformio\penv\Scripts\platformio.exe run --environment node_a --target upload

2) Serial Monitor (115200 baud, enable send-on-enter):
C:\Users\Lenovo\.platformio\penv\Scripts\platformio.exe device monitor --port COM3 --baud 115200 --filter send_on_enter

3) Commands you can type in the monitor:
help
log summary
emu_on
emu_off
reset_counts
thresholds
filter
health
set_thresholds 50 50
state 1 0        (far=OCC, near=FREE)
state 0 1        (far=FREE, near=OCC)
state 0 0        (far=FREE, near=FREE)
ambulance_on
ambulance_off
status
report

Expected indicators:
  - "Node A ready."
  - "tx=RADIO_TX_OK" in STATUS lines

---
NODE B (USB connected to PC)

1) Build + Upload:
C:\Users\Lenovo\.platformio\penv\Scripts\platformio.exe run --environment node_b --target upload

2) Serial Monitor (115200 baud, enable send-on-enter):
C:\Users\Lenovo\.platformio\penv\Scripts\platformio.exe device monitor --port COM3 --baud 115200 --filter send_on_enter

3) Commands you can type in the monitor:
help
log summary
remote_queue 3
remote_state 1 0 2   (far=OCC, near=FREE, queue=2 for remote side A)
remote_clear
remote_ambulance_on
remote_ambulance_off
local_ambulance_on
local_ambulance_off
thresholds
filter
health
set_thresholds 50 50
status
report

Expected indicators:
  - "Node B ready."
  - "source=LORA_RADIO" and "stale=OFF" when A->B telemetry is received

---
TWO-NODE TESTING (A is USB, B is external power)

1) Flash Node A and leave it running on COM3.
2) Power Node B from external power.
3) Use Node A emulation commands to generate traffic:
   emu_on
   reset_counts
   state 1 0
   state 0 1
   state 0 0
4) If Node B is connected instead, use:
   remote_state 1 0 2
   remote_queue 3
5) Confirm B shows:
   source=LORA_RADIO
   stale=OFF

Notes:
  - If only one USB port is available, you can monitor A or B one at a time.
  - Change COM port if needed (e.g., COM4, COM5).

---
REAL ROAD DATA COLLECTION (digital twin + false-positive evidence)

1) Find the ESP32 COM port:
python tools\road_data_logger.py --list-ports

2) Start Node A road logger:
python tools\road_data_logger.py --port COM3 --node node_a --out data\road_sessions\road_2026-05-16_node_a.csv

3) In a second PowerShell window, open the live dashboard:
python tools\road_dashboard.py --csv data\road_sessions\road_2026-05-16_node_a.csv

4) While recording, type labels into the logger:
v      vehicle inside observed sensor zone
n      observed sensor zone empty
u      uncertain / do not score
note pedestrian crossed
thresholds
filter
health
set_thresholds 50 50
q      stop logging

Default sensor thresholds in current demo firmware:
  far  = 50 cm
  near = 50 cm

Validated road CSV threshold:
  far  = 100 cm
  near = 100 cm

5) Summarize detection quality:
python tools\road_data_summary.py --csv data\road_sessions\road_2026-05-16_node_a.csv --out data\road_sessions\road_2026-05-16_node_a_summary.txt

6) Find better sensor thresholds from the labelled data:
python tools\sensor_threshold_analysis.py --csv data\road_sessions\road_2026-05-16_node_a.csv --sensor both --out data\road_sessions\road_2026-05-16_thresholds.txt

7) Estimate/report energy:
python tools\energy_estimator.py --duration-min 30 --node-a-ma 120 --node-b-ma 160 --battery-mah 10000

7b) If using INA219, log each node and summarize measured current:
python tools\road_data_logger.py --port COM3 --node node_a --out data\road_sessions\node_a_ina219.csv
python tools\road_data_logger.py --port COM4 --node node_b --out data\road_sessions\node_b_ina219.csv
python tools\ina219_energy_summary.py --csv data\road_sessions\node_a_ina219.csv --csv data\road_sessions\node_b_ina219.csv --road-csv data\data_readed\road_26-05-19_crossroads.csv --out data\road_sessions\ina219_energy_summary.txt

Replace COM3 and current values with your real values.
Full guide: docs\road-field-data-collection.md
INA219 guide: docs\ina219-energy-measurement.md
Final four-sensor demo log format: docs\live-demo-log-format.md

---
FINAL LIVE DEMO LOG (4 physical ultrasonic sensors)

1) Power Node A normally so it transmits Side A queue and distances over LoRa.
2) Connect Node B to the laptop, because Node B sees both sides.
3) Start the final demo logger:
python tools\road_data_logger.py --port COM3 --node node_b --out data\road_sessions\final_demo_node_b.csv

The final demo firmware starts with:
  thresholds=50.0/50.0

Emergency push button on Node B:
  wire GPIO3 / J3-14 to one side of the push button
  wire the other side of the push button to GND
  1 click  = emergency priority for Node B / Side B
  2 clicks = emergency priority for Node A / Side A
  long press = clear emergency override

If needed during the demo, type:
  set_thresholds 50 50

Expected live table columns:
  A_Q B_Q A_far A_near B_far B_near health control

Expected raw Node B line:
  B STATUS | A_queue=... | B_queue=... | A_far=...cm/... | A_near=...cm/... | B_far=...cm/... | B_near=...cm/... | thresholds=50.0/50.0 | source=LORA_RADIO | stale=OFF | backup=OFF | recovery=LIVE | emergency=... | emergency_target=... | button_override=... | lights=A:... B:...

Backup/recovery test for professor:
  1) Keep Node B logger running.
  2) Power off Node A or move it out of range.
  3) After the stale timeout, Node B should show:
       source=LORA_STALE | stale=ON | backup=ON | recovery=WAITING_FOR_LORA
  4) Power Node A again.
  5) Node B should print recovery and return to:
       source=LORA_RADIO | stale=OFF | backup=OFF | recovery=LIVE

This is the terminal view to record for the final demo video.

---
REAL ROAD VISUAL SIMULATOR REPLAY

Recommended final-demo command:
python simulation\visual_simulator.py

Inside the simulator choose:
- CSV replay + Use Default: replay the validated road CSV inside the main simulator
- Load CSV: choose another saved road file
- Direct queues: manually set Side A / Side B queue counts
- Random: generate automatic synthetic traffic pressure

Run the normal visual simulator with car counts from the validated crossroad dataset.
Cars enter from outside the crossroad and pass the far/near sensors normally; the CSV controls traffic pressure:
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv

Slower presentation replay:
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv --speed 1.5 --queue-scale 3

Print simulator-vs-real-firmware summary only:
python simulation\visual_simulator_real_data.py --csv data\data_readed\road_26-05-19_crossroads.csv --summary

---
FINAL EVIDENCE DASHBOARD / REPORT

Generate the presentation dashboard and written evidence report from the validated road CSV:
python tools\final_evidence_report.py --csv data\data_readed\road_26-05-19_crossroads.csv

Output files:
data\data_readed\road_26-05-19_crossroads_evidence_dashboard.html
data\data_readed\road_26-05-19_crossroads_evidence_report.md
