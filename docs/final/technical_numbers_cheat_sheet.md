# Wait Less Technical Numbers Cheat Sheet

This page collects the numbers that are likely to come up during the final discussion. Values are split between configured firmware constants, measured CSV/INA219 results, and calculated LoRa airtime estimates.

## Sensing And Logging Timing

| Item | Value | Meaning |
| --- | ---: | --- |
| Main firmware loop interval | `200 ms` | Target control/sensing loop period on both nodes |
| Filtered ultrasonic update rate | about `5 Hz` per sensor | Each sensor gets one filtered occupancy result about every 200 ms |
| Raw ultrasonic pings per filtered reading | `3` | Median-of-3 filter |
| Raw pings per sensor per second | about `15` | 3 raw pings x 5 filtered reads per second |
| Delay between median samples | `5 ms` | Gap between raw ultrasonic pings inside the median filter |
| HC-SR04 echo timeout | `25,000 us = 25 ms` | No echo becomes `999 cm` |
| Serial status/log interval | `1,000 ms` | `A STATUS` / `B STATUS` evidence line printed once per second |
| Road CSV row interval | about `1 s` | Logger saves one row per status line |

Important distinction: the firmware senses faster than it logs. The controller can update around every `200 ms`, while the evidence CSV is normally `1 row/second`.

## Ultrasonic Thresholds And Reliability

| Item | Value |
| --- | ---: |
| Live demo threshold | `50 cm / 50 cm` |
| Road evaluation threshold | `100 cm / 100 cm` |
| Allowed threshold command range | `5 cm` to `400 cm` |
| Invalid/no-echo sentinel | `999 cm` |
| Valid distance check | `0 cm < distance < 900 cm` |
| Median filter | `3 samples` |
| Occupancy debounce | `2 consistent samples` |
| Sensor health `WARN` | `5` consecutive invalid readings |
| Sensor health `FAIL` | `15` consecutive invalid readings |

With a `200 ms` loop, the 2-sample debounce means a new occupied/free state usually needs about `400 ms` of consistent readings before it is accepted.

## LoRa Communication Timing

| Mode | Packet behavior |
| --- | --- |
| Active traffic | Full telemetry every `1 s` |
| Idle/no cars | Full telemetry only on state change; heartbeat every `10 s` |
| Peak low-communication mode | Heartbeat every `15 s`; Node B controls locally |
| Peak sleep | Node A sleeps for `15 s`, wakes, sends heartbeat, sleeps again |
| Command grace after wake | `5 s` |
| Active telemetry stale timeout | `3 s` |
| Heartbeat stale timeout | `25 s` |

Packet examples:

```text
Telemetry:
A,1,0,4,2,2,0,12345,42.0,999.0

Idle heartbeat:
H,A,I,12345

Peak heartbeat:
H,A,P,12345
```

## LoRa Radio Settings

| Setting | Value |
| --- | ---: |
| Radio | Heltec V3 onboard `SX1262` |
| Frequency | `868.0 MHz` |
| Bandwidth | `125 kHz` |
| Spreading factor | `SF7` |
| Coding rate | `4/5` |
| Sync word | `0x12` |
| Output power | `14 dBm` |
| Preamble length | `8 symbols` |

The firmware logs RSSI and SNR when packets are received. It does not currently measure synchronized round-trip latency.

## Estimated LoRa Airtime

Using `SF7`, `125 kHz`, `CR 4/5`, explicit header, CRC enabled, and preamble `8`:

| Payload type | Typical bytes | Estimated airtime |
| --- | ---: | ---: |
| Heartbeat `H,A,I,12345` | `11 bytes` | about `41 ms` |
| Full telemetry example | about `30 bytes` | about `72 ms` |
| Longer full telemetry | `36-40 bytes` | about `77-82 ms` |

Safe explanation: we measured LoRa freshness/stale behavior in the CSV; exact packet latency was not measured with synchronized clocks. Based on the configured LoRa settings, the radio airtime of each packet is on the order of tens of milliseconds, while the system update interval is dominated by the `1 s` telemetry interval and the `200 ms` control loop.

## Expected Reaction Time

| Case | Expected behavior |
| --- | --- |
| Local Side B car detected | Sensor read within about `200 ms`; controller updates lights in the same loop |
| Remote Side A car detected in active mode | Node A senses within about `200 ms`, sends telemetry at up to `1 s` interval, Node B processes on receive/next loop |
| Remote Side A change in idle mode | State change triggers full telemetry; heartbeat is only for "alive/no useful update" |
| Peak sleep mode | Node A intentionally does not do adaptive detection; Node B handles balanced local control and Node A wakes every `15 s` for heartbeat |
| Failure detection in active mode | Node B marks Node A stale after `3 s` without telemetry |
| Failure detection in heartbeat mode | Node B waits up to `25 s` before marking stale, because low communication is expected |

## Adaptive Controller Numbers

| Item | Value |
| --- | ---: |
| Minimum green time | `5 s` |
| Maximum green time | `20 s` |
| Yellow transition | `2 s` |
| Advantage margin | `4 demand points` |

Demand equation:

```text
demand = 3 x estimated_queue + 2 x far_occupied + 4 x near_occupied
```

Why near sensor has larger weight: it means a vehicle is already at the stop line.

## Emergency Button Timing

| Item | Value |
| --- | ---: |
| Button debounce | `35 ms` |
| Click window | `450 ms` |
| Long press clear | `1200 ms` |
| 1 click | Side B emergency |
| 2 clicks | Side A emergency |

Emergency requests still pass through the normal yellow transition; the controller does not jump directly from one green to the other.

## Peak Mode Windows

| Window | Time |
| --- | --- |
| Morning peak | `09:00-11:00` |
| Evening peak | `16:00-19:00` |

In the classroom/demo firmware these can be enabled manually with commands such as `peak_on`, `peak_sleep_on`, and `set_demo_hour <0-23>`.

## Road Evaluation Results

Main road dataset:

```text
data/data_readed/road_26-05-19_crossroads.csv
```

| Metric | Result |
| --- | ---: |
| Duration | `18.0 min` |
| Samples | `2160` |
| Thresholds | `100 cm / 100 cm` |
| TP / TN / FP / FN | `1269 / 817 / 59 / 15` |
| Accuracy | `96.6%` |
| False positive rate | `6.7%` |
| False negative rate | `1.2%` |
| LoRa stale rows | `65 / 2160 = 3.0%` |

## Sensor Improvement Results

Comparison data:

```text
data/data_readed/sensor_reliability_files/
```

| Metric | Before | After |
| --- | ---: | ---: |
| Duration | `600 s` | `600 s` |
| Samples | `600` | `600` |
| Filter | `median1_debounce1` | `median3_debounce2` |
| Accuracy | `94.17%` | `98.17%` |
| False positives | `27` | `9` |
| False negatives | `8` | `2` |
| Noise/ghost false positives | `13` | `0` |
| LoRa stale samples | `5` | `2` |
| Occupancy state changes | `46` | `28` |

Main explanation: median filtering reduced one-sample ultrasonic spikes, and debounce reduced unstable occupied/free switching.

## Energy Results

Baseline:

| Node | Average current | Average power |
| --- | ---: | ---: |
| Node A | `121.4 mA` | `609.4 mW` |
| Node B | `174.8 mA` | `875.7 mW` |

After optimization:

| Mode | Average current | Average power | Current reduction |
| --- | ---: | ---: | ---: |
| Node A active telemetry | `118.7 mA` | `595.9 mW` | `2.2%` |
| Node A idle heartbeat | `74.6 mA` | `375.2 mW` | `38.6%` |
| Node A peak sleep | `32.8 mA` | `164.3 mW` | `73.0%` |
| Node B telemetry receive | `172.9 mA` | `866.2 mW` | `1.1%` |
| Node B heartbeat receive | `158.4 mA` | `795.2 mW` | `9.4%` |

Node B improves less because it stays awake to control LEDs. Node A improves more because it can reduce repeated LoRa communication and sleep during peak mode.

## Useful Hardware Numbers

| Item | Pins |
| --- | --- |
| Node A far ultrasonic | TRIG `GPIO3`, ECHO `GPIO5` |
| Node A near ultrasonic | TRIG `GPIO6`, ECHO `GPIO7` |
| Node B far ultrasonic | TRIG `GPIO4`, ECHO `GPIO5` |
| Node B near ultrasonic | TRIG `GPIO6`, ECHO `GPIO7` |
| Node B emergency button | `GPIO3`, active LOW, button to GND |
| Node B Side A LEDs R/Y/G | `GPIO33 / GPIO34 / GPIO35` |
| Node B Side B LEDs R/Y/G | `GPIO38 / GPIO39 / GPIO40` |
| INA219 I2C | SDA `GPIO41`, SCL `GPIO42`, address `0x40` |
| INA219 shunt | `0.1 ohm` |

Node A and Node B are different boards, so repeated GPIO numbers across nodes are not conflicts.
