# Live Demo Log Format

For the final live demo, use Node B as the main terminal because Node B has the complete controller view:

- Side A data received from Node A over LoRa
- Side B data measured locally
- traffic-light state for both sides
- stale/live LoRa status
- optional INA219 power data

## Hardware Scope For The Demo

The final hardware demo uses four ultrasonic sensors:

| Side | Sensor | Meaning |
| --- | --- | --- |
| Side A / first queue | far sensor | approaching vehicle detection |
| Side A / first queue | near sensor | stop-line / queue detection |
| Side B / second queue | far sensor | approaching vehicle detection |
| Side B / second queue | near sensor | stop-line / queue detection |

The older visual simulator can draw more sensor zones for presentation, but the real IoT demo uses these four physical ultrasonic sensors.

## New Node B Summary Line

Node B now prints one live summary line with both queues and all four sensor distances:

```text
B STATUS | A_queue=2 | B_queue=1 | A_far=42.0cm/OCC | A_near=999.0cm/FREE | B_far=88.4cm/OCC | B_near=31.2cm/OCC | thresholds=100.0/100.0 | filter=median3_debounce2 | health=F:OK,N:OK | localQ=1 | remoteQ=2 | source=LORA_RADIO | stale=OFF | green=A | phase=GREEN | emergency=OFF | priority=A | lights=A:GREEN B:RED | power=5.012V/178.4mA/894.1mW
```

Use this explanation in the demo:

- `A_queue`: number of cars estimated in the first queue, received from Node A.
- `B_queue`: number of cars estimated in the second queue, measured by Node B.
- `A_far` / `A_near`: distances from Node A's two ultrasonic sensors.
- `B_far` / `B_near`: distances from Node B's two ultrasonic sensors.
- `OCC`: object detected inside the active threshold.
- `FREE`: no object detected inside the active threshold.
- `thresholds=100.0/100.0`: far/near detection threshold in centimeters.
- `filter=median3_debounce2`: median filtering and debouncing enabled.
- `health=F:OK,N:OK`: Node B local sensor health.
- `source=LORA_RADIO` and `stale=OFF`: Node A data is live.
- `lights=A:GREEN B:RED`: current traffic-light output.

## Logger Table

When running:

```powershell
python tools\road_data_logger.py --port COM3 --node node_b --out data\road_sessions\final_demo_node_b.csv
```

the live table now shows:

```text
 time(s) node A_Q B_Q A_far       A_near      B_far       B_near      mA      health      control             truth result
```

This is the line to show in the screen recording, because it proves that the controller is using four real ultrasonic sensors, two queues, LoRa freshness, and traffic-light state.

## CSV Fields Added For The Demo

The logger now stores these extra columns:

- `a_queue`
- `b_queue`
- `a_far_cm`
- `a_far_occupied`
- `a_near_cm`
- `a_near_occupied`
- `b_far_cm`
- `b_far_occupied`
- `b_near_cm`
- `b_near_occupied`

The older `far_cm` and `near_cm` columns are still kept for compatibility; for Node B rows they represent the local Side B sensors.
