# Wait Less Final Presentation Speech

Target length: about 9 to 10 minutes.

Style: explain the story, evidence, and results. Do not explain code line by line. For code-heavy slides, say what the code proves at system level.

## Slide 1 - Opening

Good morning. We are presenting Wait Less, an IoT adaptive traffic-light prototype. The system uses two ESP32 LoRa nodes, four ultrasonic sensors, traffic-light LEDs, real road data, energy measurements, and a simulator replay. The goal is to make the light react to real vehicle demand instead of only following a fixed timer.

## Slide 2 - Problem And Motivation

The problem is wasted green time. In fixed-cycle traffic lights, one road can receive green while it is empty, and the other side keeps waiting. The TomTom number gives motivation: in Rome, traffic delay is significant, around 30 minutes per working day. Our project is a prototype, but it studies how local IoT sensing can reduce this kind of waste.

## Slide 3 - Project Process

Our first idea was mostly simulation. After feedback, we changed direction: we added real sensors, labelled road data, false positive and false negative measurement, LoRa freshness, and energy measurement. So the final project is not just a simulator. It is a measured IoT pipeline.

## Slide 4 - Existing Approaches

Fixed-time lights are simple, but they do not sense demand. Camera and loop systems are stronger, but they require heavier installation and calibration. Wait Less sits in the middle: a low-cost ESP32 LoRa prototype that shows sensing, communication, control, logging, and evaluation.

## Slide 5 - Network Architecture

This diagram shows the full system. Node A reads Side A sensors and sends telemetry to Node B over LoRa. Node B reads Side B sensors, receives Node A, runs the controller, and drives both traffic-light directions. The laptop is for evidence: it saves logs, CSVs, reports, and simulator replay. We also used INA219 for current measurement.

## Slide 6 - Road Placement

Here we show where the sensors are placed. Each side has a far sensor and a near sensor. The far sensor detects approaching vehicles, and the near sensor detects queue or stop-line presence. The live demo threshold is 50 cm, while the road evaluation used 100 cm.

## Slide 7 - Road Diagram

This road view makes the deployment clearer. The sensor cones show the physical detection zones. This matters because ultrasonic sensors are very dependent on position and angle. A good result is not only software; it also depends on mounting and calibration.

## Slide 8 - Software Pipeline

This is the complete software pipeline. Sensors become firmware states, firmware creates queue estimates and LoRa packets, Node B prints a live status line, the logger saves CSV, and the same CSV becomes metrics, graphs, and simulator replay. The important point is traceability from real sensing to final evidence.

## Slide 9 - Node Roles

Node A senses and transmits. Node B senses, receives, controls, and logs. Node B makes the final light decision locally using both local Side B data and remote Side A data. The live `B STATUS` line proves the roles are active during the demo.

## Slide 10 - Shared Logic

Both nodes use shared logic so they interpret sensors and packets consistently. The shared code handles pin mapping, filtering, queue estimation, packet format, controller logic, and optional energy measurement. We will not explain code details here; the key point is that both nodes use the same model.

## Slide 11 - Adaptive Algorithm

The controller scores demand with this equation: 3 times queue, plus 2 for far occupancy, plus 4 for near occupancy. Near occupancy has higher weight because a car at the stop line is more urgent. The controller also uses safe timing: 5 seconds minimum green, 20 seconds maximum green, and 2 seconds yellow.

## Slide 12 - Improvements

This slide shows what changed after problems appeared. We added threshold commands, median-of-3 filtering, 2-sample debounce, sensor health diagnostics, emergency button logic, and stale Node A backup. These were not decorative features; they came from issues seen during real testing.

## Slide 13 - Detection Results

This is a key result. We compared two 10-minute runs at the same crossroad position with 100 cm thresholds. Accuracy improved from 94.2 percent to 98.2 percent. False positives dropped from 27 to 9, false negatives from 8 to 2, and noise ghost detections from 13 to 0. This proves the reliability improvement with data.

## Slide 14 - Vehicle Speed

The system does not measure speed directly. It detects whether a car stays inside the ultrasonic beam long enough. With a 200 ms loop and 2-sample debounce, the safe detection time is about 0.4 seconds. For a normal car around 4 meters long, this gives a conservative reliable detection speed of about 35 to 40 km/h, suitable for urban crossroads and queues.

## Slide 15 - Occupancy Stability

Filtering also made the signal more stable. Occupied/free changes dropped from 46 to 28, a 39.1 percent reduction. False positive rate dropped from 7.69 percent to 2.59 percent, and false negative rate from 3.21 percent to 0.79 percent. This gives the controller a cleaner queue input.

## Slide 16 - LoRa Reliability

At first, sending a packet only proved connectivity. The final system makes packets meaningful: they include occupancy, queue, emergency state, timestamp, and distances. Node B also checks if data is fresh. If Node A becomes stale, Node B enters backup mode instead of trusting old data.

## Slide 17 - Communication Modes

We separated full telemetry from heartbeat to save energy. With active traffic, Node A sends full telemetry every second. With no cars, it sends heartbeat every 10 seconds. In peak low-communication mode, it sends heartbeat every 15 seconds and can sleep while Node B controls locally.

## Slide 18 - Communication Code Slide

This slide only supports the previous idea. We do not need to read the code. The important behavior is this: telemetry carries traffic state, heartbeat carries node health, and Node B changes timeout depending on packet type. Active timeout is 3 seconds, heartbeat timeout is 25 seconds.

## Slide 19 - Power Over Time

The power graph shows why the optimization matters. Combined baseline power was about 1485 mW. Idle heartbeat reduced it to about 1172 mW, and peak sleep reduced it to about 952 mW. The biggest saving is on Node A because Node A can reduce transmissions and sleep.

## Slide 20 - Current Over Time

The current graph tells the same story. In idle mode, communication drops from 60 full packets per minute to about 6 heartbeats per minute. Node A idle current reduces by 38.3 percent, and Node A peak sleep reduces by 73.1 percent. Node B saves less because it must keep controlling the lights.

## Slide 21 - Emergency Button

A real ambulance event is rare and cannot be controlled in class, so we used a button to simulate it. One click gives emergency priority to Side B. Two clicks gives priority to Side A. Long press clears the emergency. The controller still uses yellow transition, so it remains safe.

## Slide 22 - Simulator

The simulator is not the main result. It is a replay tool. It can still run random or manual traffic, but the important mode is CSV replay from the real road run. This connects the physical IoT data to a digital twin and helps visualize how real demand affects the light behavior.

## Slide 23 - Future Work

For future work, we would improve failover. Node B already handles stale Node A data. A future hardware design could allow Node A to take over the lights if Node B fails, using a tri-state buffer so only one controller drives the LED lines at a time. We would also add better sensors or wake-up detectors for real deployment.

## Closing

To conclude, Wait Less became a complete IoT evidence project: real sensors, LoRa communication, labelled road data, measured detection quality, measured energy, and simulator replay from real CSV demand. The most important part is the process: real testing showed problems, we improved the system, and the results became measurable.

## Short Backup Closing

If time is short:

Wait Less is not only a simulation. It is a measured IoT prototype with ESP32 LoRa nodes, four ultrasonic sensors, road labels, reliability metrics, energy measurements, and digital-twin replay. The project improved because real data showed us what needed to change.
