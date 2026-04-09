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
| SW-05 |  | Remote ambulance priority | `remote_ambulance_on` on real firmware path | side A gets emergency priority through yellow | not executed yet in this environment | PENDING |
| SW-06 |  | Local ambulance priority | `local_ambulance_on` on real firmware path | side B gets emergency priority through yellow | not executed yet in this environment | PENDING |

## Hardware Results

| ID | Date | Hardware item | Test | Expected result | Actual result | Status |
| --- | --- | --- | --- | --- | --- | --- |
| HW-01 |  | Node B LEDs | startup self-test | red, yellow, green sequence appears once |  |  |
| HW-02 |  | Node B far sensor | distance / occupancy detection | object inside threshold shows `OCC` |  |  |
| HW-03 |  | Node B near sensor | distance / occupancy detection | object inside threshold shows `OCC` |  |  |
| HW-04 | 2026-04-09 | Node A telemetry path | telemetry generation on real board using serial emulation inputs | queue estimator updates payload correctly on the board | `state 1 0 -> A,1,0,1,0,1,0,...`, `state 0 1 -> A,0,1,1,0,1,0,...`, `state 0 0 -> A,0,0,1,1,0,0,...`, all with `tx=RADIO_TX_OK` | PASS |
| HW-05 | 2026-04-09 | LoRa radio link | packet transfer A -> B | Node B receives telemetry over radio | Node B changed from `source=LORA_STALE | stale=ON` to `source=LORA_RADIO | stale=OFF` and updated `remoteQ=1` from live Node A traffic | PASS |
| HW-06 |  | Emergency behavior | ambulance override on real setup | emergency side gets priority after yellow |  |  |

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

## Evidence: Node B Reports

Paste `Node B` output from the `report` command here.

```text
Node B ready.
[LoRa] backend: RadioLib SX1262
B STATUS | far=999.0cm/FREE | near=999.0cm/FREE | localQ=0 | remoteQ=0 | source=LORA_STALE | stale=ON | green=A | phase=GREEN | emergency=OFF | priority=A | lights=A:GREEN B:RED
B STATUS | far=999.0cm/FREE | near=999.0cm/FREE | localQ=0 | remoteQ=1 | source=LORA_RADIO | stale=OFF | green=A | phase=GREEN | emergency=OFF | priority=A | lights=A:GREEN B:RED
```

## Notes And Fixes

Use this section to record what changed after each failed or partial test.

- Example: "Near sensor threshold reduced from 18 cm to 15 cm because stop-line occupancy was detected too early."
- Example: "Kept log mode on summary and only switched to verbose while checking LoRa receive behavior."
- Real hardware note on 2026-04-09: a fallback-to-serial issue in the LoRa backend was fixed, after which both boards reported `RadioLib SX1262` and live A->B LoRa communication was confirmed.
- Terminal note on 2026-04-09: commands pasted too quickly into the monitor can concatenate into one line; sending one command per Enter works reliably.
