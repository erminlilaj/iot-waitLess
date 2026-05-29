---
title: Wait Less
---

# Wait Less: Making A Traffic Light React To Real Cars

We started Wait Less with a simple question: could a small IoT prototype make a traffic light react to what is actually happening on the road, instead of following a fixed timer?

The first version looked convincing in a demo. A sensor detected a nearby object, an ESP32 changed some LEDs, and the system seemed alive. But that is the easy part of an IoT project. The harder part is proving that the system still makes sense when the readings are noisy, the wireless link is imperfect, and the data comes from a real road instead of a controlled desk setup.

So we built the project around measurement. Wait Less became an ESP32 and LoRa traffic-light prototype with real ultrasonic sensors, CSV logs, labelled road data, energy measurements, and a simulator replay driven by the collected data.

The full loop looked like this:

```text
real sensors -> ESP32 firmware -> LoRa telemetry -> traffic-light control -> CSV evidence -> evaluation -> simulator replay
```

## The Prototype

The prototype models a small two-way crossroad. Each side of the road has two HC-SR04 ultrasonic sensors:

- a far sensor, used to notice approaching vehicles
- a near sensor, used to notice vehicles waiting close to the stop line

We used two Heltec ESP32 WiFi LoRa 32 V3 boards. Node A reads Side A and sends LoRa telemetry. Node B reads Side B, receives Side A, runs the traffic-light logic, and drives both sets of LEDs.

That split gave us a useful project shape. It was not just one board blinking LEDs from local sensor data. It had distributed sensing, wireless communication, stale-data handling, control logic, logging, and a visible output.

The main hardware was:

| Part | Use |
| --- | --- |
| 2 x ESP32 Heltec WiFi LoRa 32 V3 | road-side nodes |
| 4 x HC-SR04 ultrasonic sensors | vehicle presence detection |
| 6 x LEDs | two traffic-light heads |
| 1 x push button | emergency priority test |
| 1 x INA219 current sensor | energy measurements |

## The First Lesson: Detecting A Car Is Not The Same As Detecting Distance

The HC-SR04 does not know what a car is. It only reports distance. That sounds obvious, but it matters a lot once the sensor leaves the desk.

A pedestrian, a pole, a curb, a bad reflection, or the edge of the road can all look like a nearby object. On the other side, a real car can be missed if it crosses the cone too quickly, reflects poorly, or passes at the wrong angle.

The firmware therefore does not treat one distance reading as truth. It turns raw readings into a stable occupied/free state:

```text
HC-SR04 distance reading
-> median-of-3 filter
-> distance threshold
-> 2-sample debounce
-> stable occupied/free state
-> queue estimate
```

The loop runs every `200 ms`. With a 2-sample debounce, a change needs about `400 ms` to become stable. That number gave us a useful sanity check: at urban speeds, a normal car should remain in the detection zone long enough to be noticed.

Using a rough car length of `4.0 m` and a small extra beam width, the prototype is honest around `35-40 km/h` for normal urban queue detection. It is not a highway-speed vehicle detector, and we should not pretend that it is.

## The Threshold Was A Design Choice, Not A Magic Number

We used two threshold setups:

| Context | Threshold |
| --- | ---: |
| Live demo | `50 cm / 50 cm` |
| Road evaluation | `100 cm / 100 cm` |

The `50 cm` threshold made the indoor demo easier to control. The `100 cm` threshold gave the road test a wider detection zone for cars.

There is a tradeoff either way. A larger threshold catches more vehicles, but it also catches more things that are not vehicles. A smaller threshold reduces false positives, but it can miss cars if the mounting angle is not ideal.

In a real installation, we would not reuse one universal value. Each far and near sensor would need to be calibrated after mounting.

## Turning Sensor Events Into Traffic Demand

Once the firmware has stable occupancy states, it estimates queue pressure with simple counters:

```text
estimated_queue = incoming_count - passed_count
```

A far-sensor rising edge means a vehicle entered the measured lane. A near-sensor falling edge means a vehicle passed the stop-line area. If a car is sitting on the near sensor and the counters are still zero, the firmware still reports at least one queued vehicle so the controller can react.

The controller then computes demand:

```text
demand = 3 x estimated_queue + 2 x far_occupied + 4 x near_occupied
```

The near sensor gets the highest weight because a vehicle at the stop line is more urgent than a vehicle only approaching.

The traffic-light controller uses a `5 s` minimum green, a `20 s` maximum green, a `2 s` yellow transition, and a `4 point` advantage margin before switching sides. The margin is important because without it the system can become nervous when both roads have similar demand.

## LoRa Made The System Distributed

Node A sends compact CSV-style LoRa packets to Node B. A full telemetry packet looks like this:

```text
A,1,0,4,2,2,0,12345,42.0,999.0
```

We also added heartbeat packets:

```text
H,A,I,12345
H,A,P,12345
```

That small addition made the controller easier to reason about. A heartbeat lets Node B distinguish between "Node A is alive but has no useful traffic update" and "Node A is missing or stale."

With `868 MHz`, `125 kHz` bandwidth, `SF7`, coding rate `4/5`, and `14 dBm` output power, the estimated airtime was about `41 ms` for a heartbeat and about `72-82 ms` for full telemetry.

In practice, the control latency was dominated more by firmware scheduling than radio airtime. Node A senses every `200 ms` and normally sends active telemetry every `1 s`, so remote-side reaction is typically around `0.8-1.0 s`, with a conservative worst case around `1.5 s`.

## The Road Data Changed The Project

The most useful part of the project was taking it outside the demo mindset.

We collected and manually labelled an `18.0 minute` road session with `2160` samples using the `100 cm / 100 cm` thresholds. The result was:

| Metric | Result |
| --- | ---: |
| True positives | `1269` |
| True negatives | `817` |
| False positives | `59` |
| False negatives | `15` |
| Accuracy | `96.6%` |
| False positive rate | `6.7%` |
| False negative rate | `1.2%` |
| LoRa stale rows | `65 / 2160 = 3.0%` |

The numbers were good enough for a prototype, but they were also specific enough to show where the system was weak. False positives mostly came from the fact that an ultrasonic sensor detects physical objects, not object classes. False negatives happened when a car was outside the cone, reflected poorly, or appeared too briefly to survive filtering and debounce.

That evidence pushed us to improve the firmware. The first version used a simpler `median1_debounce1` sensor state. After field testing, we moved to `median3_debounce2`.

Using the same placement and thresholds, the comparison over a `600 s` session was:

| Metric | Before | After |
| --- | ---: | ---: |
| Accuracy | `94.2%` | `98.2%` |
| False positives | `27` | `9` |
| False negatives | `8` | `2` |
| Noise/ghost false positives | `13` | `0` |
| LoRa stale samples | `5` | `2` |
| Occupancy state changes | `46` | `28` |

This was the point where the project stopped being just a working demo. The data told us what to fix, and the next version was measurably better.

## Power Was Part Of The Story Too

Because this is an IoT system, we also measured energy with an INA219 current sensor.

The baseline measurements were:

| Node | Average current | Average power |
| --- | ---: | ---: |
| Node A | `121.4 mA` | `609.4 mW` |
| Node B | `174.8 mA` | `875.7 mW` |

After adding heartbeat and low-communication modes, Node A benefited the most:

| Mode | Average current | Average power | Reduction |
| --- | ---: | ---: | ---: |
| Node A active telemetry | `118.7 mA` | `595.9 mW` | `2.2%` |
| Node A idle heartbeat | `74.6 mA` | `375.2 mW` | `38.6%` |
| Node A peak sleep | `32.8 mA` | `164.3 mW` | `73.0%` |
| Node B telemetry receive | `172.9 mA` | `866.2 mW` | `1.1%` |
| Node B heartbeat receive | `158.4 mA` | `795.2 mW` | `9.4%` |

Node B has to stay mostly awake because it controls the lights. Node A has more room to save power because it can reduce repeated communication and sleep in selected modes.

## Replaying The Road As A Digital Twin

The simulator was not meant to replace the physical system. It was a way to make the logged data visible.

It can run random traffic, manual queue inputs, or replay the real CSV data:

```text
road CSV -> queue estimates -> visual cars -> traffic-light decisions
```

That replay helped connect the numbers back to behavior. Instead of only saying "the CSV has queue estimates," we could show how those estimates would affect the traffic light over time.

## What We Would Do Next

Wait Less is still a university prototype, not a production traffic controller. The next steps are clear:

- calibrate each far and near sensor after installation
- mount the sensors more rigidly and tune the angle for each lane
- add an upstream sensor for faster roads
- test radar or magnetometer sensing to reduce pedestrian false positives
- add synchronized timestamps to measure exact LoRa end-to-end latency
- collect a longer dataset across different traffic, weather, and lighting conditions
- learn thresholds and demand weights from labelled data instead of fixing them manually

## The Main Takeaway

The main lesson was that embedded logic is only half of the project. The other half is measurement.

The system became stronger when we stopped treating the demo as proof and started asking it to defend itself with data. Median filtering, debounce, stale-node handling, heartbeat packets, energy modes, and simulator replay all came from that shift.

The most satisfying part was not only that the LEDs changed. It was that the prototype could explain why it changed, show the data behind the decision, and reveal where the design still needed work.
