# Code Understanding Guide

This document explains the code structure of the Wait Less IoT traffic-light prototype.
It is written for a reader who wants to understand how the firmware, logger, simulator, and evaluation scripts work together.

## Big Picture

The project has two real ESP32 LoRa nodes:

- `Node A`: reads Side A ultrasonic sensors and transmits queue telemetry.
- `Node B`: reads Side B ultrasonic sensors, receives Node A telemetry, runs the controller, drives the traffic lights, logs status, handles emergency button input, and detects stale Node A data.

The real-road CSV and simulator are not replacements for the hardware. They are used to evaluate and replay what the hardware measured.

## Main Data Flow

```text
Side A sensors -> Node A -> LoRa telemetry -> Node B
Side B sensors -----------------------------> Node B
Node B adaptive controller -----------------> Side A / Side B traffic LEDs
Node B serial log --------------------------> laptop CSV logger
Saved CSV ----------------------------------> evidence dashboard + simulator replay
```

## Direct Code Walkthrough

This section shows the important code parts directly and explains what each part does.
The goal is not to copy every line from every file, but to make the real project code readable for presentation and questions.

### 1. Hardware Pin Map

File: `firmware/shared/HardwareMap.h`

```cpp
namespace node_a {

constexpr UltrasonicPins kFarSensor = {
    3,
    5,
};

constexpr UltrasonicPins kNearSensor = {
    6,
    7,
};

}  // namespace node_a
```

What this does:

This defines the physical pins for Node A. The far ultrasonic sensor uses `TRIG GPIO3` and `ECHO GPIO5`. The near ultrasonic sensor uses `TRIG GPIO6` and `ECHO GPIO7`. The firmware reads these constants instead of hard-coding pin numbers inside the main logic.

```cpp
namespace node_b {

constexpr UltrasonicPins kFarSensor = {
    4,
    5,
};

constexpr UltrasonicPins kNearSensor = {
    6,
    7,
};

constexpr uint8_t kEmergencyButton = 3;

constexpr TrafficLightPins kSideALights = {
    33,
    34,
    35,
};

constexpr TrafficLightPins kSideBLights = {
    38,
    39,
    40,
};

}  // namespace node_b
```

What this does:

This defines Node B wiring. Node B has two ultrasonic sensors, one physical emergency button, and six LED outputs. `kSideALights` and `kSideBLights` are the red/yellow/green outputs for the two traffic-light directions.

### 2. Shared Configuration

File: `firmware/shared/ProjectConfig.h`

```cpp
constexpr uint32_t kLoopIntervalMs = 200;
constexpr uint32_t kTelemetryIntervalMs = 1000;
constexpr uint32_t kRemoteTelemetryTimeoutMs = 3000;

constexpr float kFarThresholdCm = 50.0f;
constexpr float kNearThresholdCm = 50.0f;
constexpr uint8_t kUltrasonicMedianSamples = 3;
constexpr uint8_t kOccupancyDebounceSamples = 2;
```

What this does:

The firmware loop runs every `200 ms`. Each node prints/sends telemetry every `1000 ms`. If Node B does not receive fresh Node A data for `3000 ms`, Node A is considered stale. The live demo threshold is `50 cm` for both far and near sensors. Each distance uses a median of 3 samples, and occupancy must be stable for 2 samples before changing.

```cpp
constexpr uint32_t kMinGreenMs = 5000;
constexpr uint32_t kMaxGreenMs = 20000;
constexpr uint32_t kYellowMs = 2000;
constexpr uint32_t kAdvantageMargin = 4;
```

What this does:

These are the traffic-light timing rules. A side keeps green for at least `5 seconds`, switches through a `2 second` yellow phase, and does not hold green forever because max green is `20 seconds`.

### 3. Node A Startup

File: `firmware/node_a/main.cpp`

```cpp
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);

  pinMode(hw::node_a::kFarSensor.trig, OUTPUT);
  pinMode(hw::node_a::kFarSensor.echo, INPUT);
  pinMode(hw::node_a::kNearSensor.trig, OUTPUT);
  pinMode(hw::node_a::kNearSensor.echo, INPUT);

  Serial.println("Node A ready.");
  loRaBegin(false, Serial);
  loRaPrintConfig(Serial);
  ina219Begin(
      hw::heltec_v3::kIna219I2c.sda,
      hw::heltec_v3::kIna219I2c.scl,
      config::kIna219Address,
      Serial);
  printBenchHelp();
}
```

What this does:

When Node A starts, it opens the serial monitor, configures the two ultrasonic sensors, starts the LoRa radio in transmit mode, tries to initialize INA219 energy sensing, and prints the available test commands. Node A does not drive LEDs; its role is sensing and telemetry.

### 4. Node A Reads Sensors

File: `firmware/node_a/main.cpp`

```cpp
const SensorReading farReading = readFilteredUltrasonicSensor(
    hw::node_a::kFarSensor.trig,
    hw::node_a::kFarSensor.echo,
    farThresholdCm,
    farDebouncer,
    config::kUltrasonicMedianSamples,
    config::kOccupancyDebounceSamples);
const SensorReading nearReading = readFilteredUltrasonicSensor(
    hw::node_a::kNearSensor.trig,
    hw::node_a::kNearSensor.echo,
    nearThresholdCm,
    nearDebouncer,
    config::kUltrasonicMedianSamples,
    config::kOccupancyDebounceSamples);
farDistance = farReading.distanceCm;
nearDistance = nearReading.distanceCm;
farOccupied = farReading.stableOccupied;
nearOccupied = nearReading.stableOccupied;
```

What this does:

Node A reads the far and near ultrasonic sensors. The helper function does three things: reads distance, applies median filtering, then applies debounce. The final result is not just a raw distance; it is a stable `occupied/free` decision.

### 5. Node A Estimates Queue And Sends LoRa

File: `firmware/node_a/main.cpp`

```cpp
SideTelemetry telemetry = laneEstimator.update(SideId::A, farOccupied, nearOccupied, nowMs);
telemetry.emergencyRequested = manualEmergencyRequested;
telemetry.farDistanceCm = farDistance;
telemetry.nearDistanceCm = nearDistance;
```

What this does:

The two sensor states are converted into one `SideTelemetry` object. This object contains the queue estimate, far/near occupancy, emergency flag, timestamp, and distances.

```cpp
const String payload = encodeTelemetry(telemetry);
sendTelemetryOverLoRa(payload);
```

What this does:

The telemetry object is encoded into a short CSV-like LoRa packet and transmitted to Node B.

```cpp
Serial.print("A STATUS | source=");
Serial.print(sourceLabel());
Serial.print(" | thresholds=");
Serial.print(farThresholdCm, 1);
Serial.print("/");
Serial.print(nearThresholdCm, 1);
Serial.print(" | far=");
Serial.print(farDistance, 1);
Serial.print("cm/");
Serial.print(occupancyLabel(farOccupied));
Serial.print(" | near=");
Serial.print(nearDistance, 1);
Serial.print("cm/");
Serial.print(occupancyLabel(nearOccupied));
Serial.print(" | queue=");
Serial.print(telemetry.estimatedQueue);
Serial.print(" | tx=");
Serial.print(txBackendLabel());
```

What this does:

This prints the human-readable Node A evidence line. It lets us prove that Node A is reading real distances, calculating a queue, and transmitting over LoRa.

### 6. Ultrasonic Distance Reading

File: `lib/traffic_control/SensorSupport.cpp`

```cpp
float readUltrasonicDistanceCm(uint8_t trigPin, uint8_t echoPin, unsigned long timeoutUs) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  const unsigned long durationUs = pulseIn(echoPin, HIGH, timeoutUs);
  if (durationUs == 0) {
    return 999.0f;
  }

  return static_cast<float>(durationUs) * 0.0343f / 2.0f;
}
```

What this does:

This is the low-level HC-SR04 measurement. The ESP32 sends a `10 us` trigger pulse, waits for the echo pulse, and converts echo duration into distance. `999 cm` means timeout/no echo, so it is treated as no valid object.

### 7. Median Filter And Debounce

File: `lib/traffic_control/SensorSupport.cpp`

```cpp
SensorReading readFilteredUltrasonicSensor(
    uint8_t trigPin,
    uint8_t echoPin,
    float thresholdCm,
    OccupancyDebouncer& debouncer,
    uint8_t medianSampleCount,
    uint8_t debounceSamples,
    unsigned long timeoutUs) {
  SensorReading reading;
  reading.distanceCm = readMedianUltrasonicDistanceCm(trigPin, echoPin, medianSampleCount, timeoutUs);
  reading.rawOccupied = isDistanceOccupied(reading.distanceCm, thresholdCm);
  reading.stableOccupied = debouncer.update(reading.rawOccupied, debounceSamples);
  return reading;
}
```

What this does:

This is the reliability layer. It first gets a filtered distance, then checks if the distance is inside the threshold, then debounces the result. This reduces false positives caused by one noisy ultrasonic reading.

```cpp
bool OccupancyDebouncer::update(bool rawOccupied, uint8_t requiredSamples) {
  ...
  if (candidateCount_ >= requiredSamples) {
    stableOccupied_ = rawOccupied;
    candidateCount_ = 0;
  }

  return stableOccupied_;
}
```

What this does:

The debouncer does not immediately trust one new `occupied/free` value. It waits until the new value appears repeatedly. This is why the professor can see we tried to reduce false positives technically, not only by guessing.

### 8. Sensor Health

File: `lib/traffic_control/SensorSupport.cpp`

```cpp
void SensorHealthTracker::update(float distanceCm) {
  const bool valid = isUltrasonicDistanceValid(distanceCm);
  ++health_.totalSamples;
  health_.lastValid = valid;

  if (valid) {
    health_.consecutiveInvalid = 0;
    return;
  }

  ++health_.invalidSamples;
  if (health_.consecutiveInvalid < 65535U) {
    ++health_.consecutiveInvalid;
  }
}
```

What this does:

The code counts invalid readings. If a sensor keeps returning invalid values, the live log can show `WARN` or `FAIL`. This helped us detect the Node A far sensor problem.

### 9. Queue Estimation

File: `lib/traffic_control/TrafficSensing.cpp`

```cpp
SideTelemetry LaneEstimator::update(SideId side, bool farOccupied, bool nearOccupied, uint32_t nowMs) {
  if (farOccupied && !farWasOccupied_) {
    ++incomingCount_;
  }

  if (!nearOccupied && nearWasOccupied_ && passedCount_ < incomingCount_) {
    ++passedCount_;
  }

  farWasOccupied_ = farOccupied;
  nearWasOccupied_ = nearOccupied;

  uint32_t estimatedQueue = incomingCount_ >= passedCount_ ? incomingCount_ - passedCount_ : 0U;

  if (nearOccupied && estimatedQueue == 0U) {
    estimatedQueue = 1U;
  }
```

What this does:

The far sensor counts vehicles entering the queue area. The near sensor counts vehicles leaving the stop-line area. Queue is estimated as incoming vehicles minus passed vehicles. If the near sensor sees a car but counters are zero, the queue is forced to at least one car.

### 10. LoRa Payload Encoding

File: `lib/traffic_control/NodeMessaging.cpp`

```cpp
String encodeTelemetry(const SideTelemetry& telemetry) {
  return String(sideName(telemetry.side)) + "," + String(telemetry.farOccupied ? 1 : 0) + "," +
         String(telemetry.nearOccupied ? 1 : 0) + "," + String(telemetry.incomingCount) + "," +
         String(telemetry.passedCount) + "," + String(telemetry.estimatedQueue) + "," +
         String(telemetry.emergencyRequested ? 1 : 0) + "," + String(telemetry.timestampMs) + "," +
         String(telemetry.farDistanceCm, 1) + "," + String(telemetry.nearDistanceCm, 1);
}
```

What this does:

This converts telemetry into a compact packet such as:

```text
A,1,0,4,2,2,0,12345,42.0,999.0
```

That packet means: Side A, far occupied, near free, 4 incoming, 2 passed, queue 2, no emergency, timestamp, far distance, near distance.

```cpp
bool decodeTelemetry(const String& payload, SideTelemetry& telemetry) {
  ...
  int matched = sscanf(
      payload.c_str(),
      "%c,%d,%d,%lu,%lu,%lu,%d,%lu,%f,%f",
      &sideToken,
      &farOccupied,
      &nearOccupied,
      &incomingCount,
      &passedCount,
      &estimatedQueue,
      &emergencyRequested,
      &timestampMs,
      &farDistanceCm,
      &nearDistanceCm);
```

What this does:

Node B decodes the LoRa string back into a `SideTelemetry` object. This is how Node B receives Node A queue and distance data.

### 11. LoRa Send And Receive

File: `lib/traffic_control/LoRaTransport.cpp`

```cpp
bool loRaBegin(bool startReceiving, Stream& debug) {
  radioSpi.begin(
      hw::heltec_v3::kLoRaSpi.sck,
      hw::heltec_v3::kLoRaSpi.miso,
      hw::heltec_v3::kLoRaSpi.mosi,
      hw::heltec_v3::kLoRaRadio.cs);

  const int16_t state = radio.begin(
      config::kLoRaFrequencyMHz,
      config::kLoRaBandwidthKHz,
      config::kLoRaSpreadingFactor,
      config::kLoRaCodingRate,
      config::kLoRaSyncWord,
      config::kLoRaOutputPowerDbm,
      config::kLoRaPreambleLength);
```

What this does:

This initializes the Heltec V3 onboard SX1262 LoRa radio using the shared radio settings. Node A starts it for transmit. Node B starts it for receive.

```cpp
bool loRaSendText(const String& payload, Stream& debug) {
  if (!radioReady) {
    return false;
  }

  const int16_t state = radio.transmit(payload.c_str());
  ...
}
```

What this does:

Node A sends the telemetry payload over LoRa.

```cpp
bool loRaTryReceive(LoRaRxPacket& packet, Stream& debug) {
  if (!radioReady || !receiveMode || !packetReceivedFlag) {
    return false;
  }

  packetReceivedFlag = false;
  packet.payload = "";
  const int16_t state = radio.readData(packet.payload);
  packet.rssi = radio.getRSSI();
  packet.snr = radio.getSNR();

  restartReceive(debug);
```

What this does:

Node B checks if a LoRa packet arrived. If yes, it reads the payload and also stores RSSI/SNR for link-quality evidence.

### 12. Node B Receives Node A Data

File: `firmware/node_b/main.cpp`

```cpp
LoRaRxPacket packet;
if (loRaTryReceive(packet, Serial)) {
  SideTelemetry receivedTelemetry;
  if (parseTelemetryLine(packet.payload, receivedTelemetry) && receivedTelemetry.side == SideId::A) {
    remoteTelemetry = receivedTelemetry;
    remoteTelemetryInjected = false;
    lastRemoteRxMs = nowMs;
    lastRemoteSource = "LORA_RADIO";
    lastRssiDbm = packet.rssi;
    lastSnrDb = packet.snr;
    lastRxWasRadio = true;
    remoteTelemetryStale = false;
  }
}
```

What this does:

Node B listens for Node A telemetry. When a valid Side A packet arrives, Node B stores it, marks the source as live LoRa, updates the last receive time, and records signal quality.

### 13. Node A Failure Backup

File: `firmware/node_b/main.cpp`

```cpp
SideTelemetry effectiveRemoteTelemetry(uint32_t nowMs) {
  if (lastRemoteRxMs == 0 || (nowMs - lastRemoteRxMs) > config::kRemoteTelemetryTimeoutMs) {
    setNodeABackupActive(true, "NODE_A_STALE");
    remoteTelemetryStale = true;
    lastRemoteSource = "LORA_STALE";
    return applyRemoteEmergencyOverride(makeNodeABackupTelemetry(nowMs));
  }

  setNodeABackupActive(false, "LORA_RADIO");
  remoteTelemetryStale = false;
  lastRemoteSource = "LORA_RADIO";
  return applyRemoteEmergencyOverride(remoteTelemetry);
}
```

What this does:

If Node B does not receive Node A packets for the stale timeout, it enters backup mode. Instead of pretending Side A has no cars, it creates conservative backup telemetry. When Node A returns, backup turns off automatically.

```cpp
SideTelemetry makeNodeABackupTelemetry(uint32_t nowMs) {
  SideTelemetry telemetry = makeRemoteTelemetry(false, false, false, kBackupRemoteQueue, nowMs);
  telemetry.farDistanceCm = 999.0f;
  telemetry.nearDistanceCm = 999.0f;
  return telemetry;
}
```

What this does:

This is the backup assumption. Distances are unknown, but Side A queue is assumed to be non-zero, so the controller still serves Side A safely.

### 14. Emergency Button

File: `firmware/node_b/main.cpp`

```cpp
pinMode(hw::node_b::kEmergencyButton, INPUT_PULLUP);
```

What this does:

The button is wired between `GPIO3` and `GND`. `INPUT_PULLUP` means the pin is normally high and becomes low when pressed.

```cpp
void activateEmergencyTarget(SideId targetSide, const char* sourceLabel, uint8_t clicks) {
  if (targetSide == SideId::A) {
    remoteEmergencyRequested = true;
    localEmergencyRequested = false;
  } else {
    localEmergencyRequested = true;
    remoteEmergencyRequested = false;
  }

  Serial.print(sourceLabel);
  Serial.print(" | clicks=");
  Serial.print(static_cast<int>(clicks));
  Serial.print(" | emergency_target=");
  Serial.print(sideName(targetSide));
}
```

What this does:

This function selects which side gets emergency priority. One click targets Side B. Two clicks target Side A.

```cpp
if (!emergencyButtonStablePressed &&
    emergencyButtonClickCount > 0 &&
    (nowMs - emergencyButtonLastReleaseMs) >= kButtonClickWindowMs) {
  const uint8_t clicks = emergencyButtonClickCount;
  emergencyButtonClickCount = 0;

  if (clicks == 1) {
    activateEmergencyTarget(SideId::B, "BUTTON EVENT", clicks);
  } else {
    activateEmergencyTarget(SideId::A, "BUTTON EVENT", clicks);
  }
}
```

What this does:

After the click window ends, the firmware decides whether it was a single click or double click. Single click means Node B/Side B emergency. Two or more clicks means Node A/Side A emergency.

### 15. Node B Controller Update

File: `firmware/node_b/main.cpp`

```cpp
SideTelemetry localTelemetry = laneEstimator.update(SideId::B, farOccupied, nearOccupied, nowMs);
localTelemetry.emergencyRequested = localEmergencyRequested;
localTelemetry.farDistanceCm = farDistance;
localTelemetry.nearDistanceCm = nearDistance;
const SideTelemetry remoteTelemetryNow = effectiveRemoteTelemetry(nowMs);
const TrafficDecision decision = controller.update(remoteTelemetryNow, localTelemetry, nowMs);
```

What this does:

Node B builds telemetry for its own side, gets the latest effective Side A telemetry, and gives both sides to the adaptive controller. `effectiveRemoteTelemetry` may be real LoRa data, serial-emulated data, or backup data if Node A is stale.

```cpp
applyLights(decision.lights);
```

What this does:

The controller decision becomes real LED outputs.

```cpp
Serial.print("B STATUS | A_queue=");
Serial.print(remoteTelemetryNow.estimatedQueue);
Serial.print(" | B_queue=");
Serial.print(localTelemetry.estimatedQueue);
Serial.print(" | A_far=");
printDistanceState(Serial, remoteTelemetryNow.farDistanceCm, remoteTelemetryNow.farOccupied);
Serial.print(" | B_far=");
printDistanceState(Serial, farDistance, farOccupied);
Serial.print(" | source=");
Serial.print(lastRemoteSource);
Serial.print(" | stale=");
Serial.print(onOffLabel(remoteTelemetryStale));
Serial.print(" | backup=");
Serial.print(backupModeLabel());
Serial.print(" | emergency=");
Serial.print(onOffLabel(decision.emergencyOverride));
Serial.print(" | lights=A:");
```

What this does:

This is the most important demo line. It prints queue estimates, all sensor distances, LoRa status, backup state, emergency state, and traffic-light outputs. The Python logger reads this line and saves it to CSV.

### 16. Adaptive Controller

File: `lib/traffic_control/AdaptiveController.cpp`

```cpp
TrafficDecision AdaptiveController::update(const SideTelemetry& sideA, const SideTelemetry& sideB, uint32_t nowMs) {
  uint32_t phaseElapsedMs = nowMs - phaseStartedMs_;
  const SideTelemetry& emergencyPriority = selectEmergencyPriority(sideA, sideB);

  if (phase_ == SignalPhase::Yellow && hasEmergency(emergencyPriority)) {
    pendingGreenSide_ = emergencyPriority.side;
  }

  if (phase_ == SignalPhase::Yellow && phaseElapsedMs >= config_.yellowMs) {
    switchGreen(nowMs);
  }
```

What this does:

The controller checks the current phase. If it is yellow, it waits until yellow time is finished before switching green. Emergency can change the next target side, but it does not skip yellow.

```cpp
if (phase_ == SignalPhase::Green) {
  if (hasEmergency(emergencyPriority)) {
    if (emergencyPriority.side != greenSide_) {
      beginYellow(emergencyPriority.side, nowMs);
    }
  } else {
    const bool canSwitch = phaseElapsedMs >= config_.minGreenMs;
    const bool currentEmpty = !hasDemand(current);
    const bool otherBusy = hasDemand(other);
    const bool reachedMaxGreen = phaseElapsedMs >= config_.maxGreenMs;
    const bool otherClearlyBusier = demandScore(other) > (demandScore(current) + config_.advantageMargin);

    if (canSwitch && ((currentEmpty && otherBusy) || (otherBusy && otherClearlyBusier) || (reachedMaxGreen && otherBusy))) {
      beginYellow(other.side, nowMs);
    }
  }
}
```

What this does:

If there is emergency demand, the controller prioritizes that side. Otherwise it uses queue and sensor demand. It only switches after minimum green and only if the other side needs service.

### 17. Demand Score

File: `lib/traffic_control/TrafficTypes.h`

```cpp
inline uint32_t demandScore(const SideTelemetry& telemetry) {
  const uint32_t queueWeight = telemetry.estimatedQueue * 3U;
  const uint32_t incomingWeight = telemetry.farOccupied ? 2U : 0U;
  const uint32_t stopLineWeight = telemetry.nearOccupied ? 4U : 0U;
  return queueWeight + incomingWeight + stopLineWeight;
}
```

What this does:

This gives each side a demand score. Queue length has strong weight. A far sensor detection adds approaching-vehicle demand. A near sensor detection adds stop-line demand.

### 18. Python Logger Parses Firmware Output

File: `tools/road_data_logger.py`

```python
def parse_status_line(line: str) -> dict[str, str]:
    row = blank_row(line)
    text = line.strip()

    if text.startswith("B STATUS"):
        values = split_status_parts(text)
        row["node"] = "B"
        row["source"] = values.get("source", "")
        row["remote_source"] = values.get("source", "")
        row["a_queue"] = values.get("A_queue") or values.get("remoteQ", "")
        row["b_queue"] = values.get("B_queue") or values.get("localQ", "")
        row["a_far_cm"], row["a_far_occupied"] = parse_sensor(values.get("A_far", ""))
        row["b_far_cm"], row["b_far_occupied"] = parse_sensor(values.get("B_far", ""))
        row["remote_stale"] = values.get("stale", "")
        row["backup_mode"] = values.get("backup", "")
        row["emergency"] = values.get("emergency", "")
        row["lights_a"], row["lights_b"] = parse_lights(values.get("lights", ""))
        return row
```

What this does:

The logger converts the long `B STATUS` text line into structured CSV columns. This is why our demo terminal and saved CSV contain the same evidence.

```python
def detection_result(row: dict[str, str]) -> str:
    truth = row.get("truth_any_vehicle", "")
    if truth not in {"0", "1"}:
        return "-"

    detected = row.get("far_occupied") == "1" or row.get("near_occupied") == "1"
    actual = truth == "1"
    if actual and detected:
        return "TP"
    if actual and not detected:
        return "FN"
    if not actual and detected:
        return "FP"
    return "TN"
```

What this does:

This scores each labelled road sample as true positive, false positive, true negative, or false negative. That is how the project gets measured detection accuracy.

### 19. Evidence Report Metrics

File: `tools/final_evidence_report.py`

```python
@dataclass(frozen=True)
class DetectionMetrics:
    tp: int
    tn: int
    fp: int
    fn: int

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.scored * 100.0 if self.scored else 0.0

    @property
    def false_positive_rate(self) -> float:
        return self.fp / (self.fp + self.tn) * 100.0 if (self.fp + self.tn) else 0.0
```

What this does:

This converts the labelled CSV results into the final metrics: accuracy, false positive rate, and false negative rate. This is the evidence behind the project evaluation.

### 20. Simulator Controller Logic

File: `simulation/traffic_logic.py`

```python
def demand_score(telemetry: SideTelemetry) -> int:
    return telemetry.estimated_queue * 3 + (2 if telemetry.far_occupied else 0) + (4 if telemetry.near_occupied else 0)
```

What this does:

The simulator uses the same demand-score idea as the firmware, so the digital twin comparison is connected to the real controller behavior.

```python
if can_switch and ((current_empty and other_busy) or (other_busy and other_clearly_busier) or (reached_max_green and other_busy)):
    self.phase = Phase.YELLOW
    self.phase_started_ms = now_ms
```

What this does:

The simulator switches to yellow using the same logic: minimum green must be satisfied, and the other side must need service.

## Firmware Structure

### `firmware/node_a/main.cpp`

Node A is the sensing and telemetry node.

Important responsibilities:

- reads Side A far and near ultrasonic sensors;
- applies median filtering and occupancy debounce through `SensorSupport`;
- estimates Side A queue with `LaneEstimator`;
- sends compact LoRa payloads using `encodeTelemetry`;
- prints `A STATUS` lines for testing and CSV logging;
- supports serial commands for threshold tuning, emulation, and reports.

Professor-facing summary:

> Node A is not a simulation. It converts physical ultrasonic readings into a queue estimate and sends that measurement to Node B over LoRa.

### `firmware/node_b/main.cpp`

Node B is the controller and actuator node.

Important responsibilities:

- reads Side B far and near ultrasonic sensors;
- receives Side A telemetry over LoRa;
- runs the adaptive controller;
- drives both traffic-light heads;
- logs one complete `B STATUS` line with all four sensor distances;
- handles the physical emergency button;
- enters backup mode when Node A telemetry becomes stale.

Key log fields:

- `A_queue`, `B_queue`: estimated queue on each side;
- `A_far`, `A_near`, `B_far`, `B_near`: four real ultrasonic readings;
- `source=LORA_RADIO`: Node A data is live;
- `stale=ON`: Node A data is missing or old;
- `backup=ON`: Node B is using fail-safe assumptions for Side A;
- `emergency_target=A/B`: physical emergency priority target;
- `lights=A:... B:...`: current LED output state.

### `firmware/shared/HardwareMap.h`

This is the source of truth for pins.

Examples:

- Node A far sensor: `TRIG GPIO3 / J3-14`, `ECHO GPIO5 / J3-16`;
- Node B emergency button: `GPIO3 / J3-14` to `GND`;
- Node B Side B LEDs: `GPIO38/GPIO39/GPIO40`.

Changing hardware pins should happen here first, then the documents should be updated.

### `firmware/shared/ProjectConfig.h`

This file contains shared constants:

- loop period;
- telemetry period;
- stale timeout;
- ultrasonic thresholds;
- median/debounce values;
- traffic-light timing;
- LoRa radio settings;
- INA219 energy measurement settings.

The live demo threshold is `50 cm / 50 cm`. The validated road CSV used `100 cm / 100 cm`, which is why evaluation numbers must be described separately from the demo threshold.

### `firmware/shared/Ina219Support.*`

This optional module reads INA219 current and power measurements.

If INA219 is not connected, the firmware continues normally and prints `INA219_NA`.
That keeps the traffic-light demo independent from the energy measurement hardware.

## Shared Firmware Library

### `lib/traffic_control/TrafficTypes.h`

Defines the common data structures:

- `SideTelemetry`: one side's sensor state, counters, queue, emergency flag, and distances;
- `TrafficDecision`: controller output, active green side, phase, emergency priority, and lights;
- `demandScore`: converts queue and sensor state into a simple priority number.

### `lib/traffic_control/TrafficSensing.*`

Implements `LaneEstimator`.

Logic:

- far sensor rising edge means a vehicle is approaching;
- near sensor falling edge means a vehicle passed the stop line;
- queue estimate is `incomingCount - passedCount`;
- if near sensor is occupied but queue is zero, report queue as at least one.

This is simple, explainable, and suitable for a classroom prototype.

### `lib/traffic_control/SensorSupport.*`

Implements ultrasonic measurement reliability:

- sends the HC-SR04 trigger pulse;
- converts echo duration to distance;
- uses `999 cm` as timeout/no echo;
- applies median-of-3 filtering;
- applies occupancy debounce;
- tracks sensor health as `OK`, `WARN`, or `FAIL`.

This directly addresses the professor's concern about false positives and sensor reliability.

### `lib/traffic_control/NodeMessaging.*`

Encodes and decodes the LoRa packet.

Current payload format:

```text
side,far,near,in,out,queue,emergency,timestamp,far_cm,near_cm
```

The decoder also accepts older shorter payloads so old test logs and older firmware formats remain understandable.

### `lib/traffic_control/AdaptiveController.*`

Implements the two-phase adaptive light controller.

Rules:

- keep a minimum green time to avoid rapid oscillation;
- switch when the current side is empty and the other side has demand;
- switch when the other side is clearly busier;
- switch after maximum green if the other side is waiting;
- emergency requests override normal demand, but still pass through yellow first.

### `lib/traffic_control/LoRaTransport.*`

Wraps the Heltec V3 SX1262 LoRa radio.

Node A uses transmit mode.
Node B uses receive mode.

The wrapper keeps radio setup in one place and still allows the firmware to build with serial-emulation fallback if RadioLib is not enabled.

### `lib/traffic_control/DebugSupport.h`

Small helpers for readable serial logs:

- log mode labels;
- `ON/OFF` formatting;
- common `status` and `report` commands.

## Python Tools

### `tools/road_data_logger.py`

This is the field logger used during the demo and road tests.

It:

- opens the ESP32 serial port;
- parses `A STATUS` and `B STATUS` lines;
- displays a clean live table;
- saves a CSV with sensor, queue, LoRa, emergency, backup, and power fields;
- lets the user type manual labels such as `v`, `n`, `far 1`, `near 0`, and `note ...`.

### `tools/final_evidence_report.py`

Builds the final dashboard and report from the validated road CSV.

It summarizes:

- duration;
- sample count;
- TP/TN/FP/FN;
- accuracy;
- false positive and false negative rates;
- LoRa stale percentage;
- energy estimate;
- simulator comparison link.

### `tools/final_presentation_graphs.py`

Generates slide-ready graphs:

- confusion matrix;
- detection quality rates;
- energy consumption;
- LoRa reliability;
- traffic demand over time;
- detected activations;
- time-saving estimate;
- digital-twin pipeline;
- INA219 power time series.

### Other Tools

- `road_data_summary.py`: summarizes one road CSV.
- `sensor_threshold_analysis.py`: explores threshold choices from labelled data.
- `ina219_energy_summary.py`: summarizes measured current and energy.
- `energy_estimator.py`: quick current/battery estimate.
- `road_dashboard.py`: lightweight live CSV dashboard.

## Simulation Code

### `simulation/traffic_logic.py`

Pure-Python controller equivalent used for simulator and graph scripts.
It mirrors the demand-score and adaptive switching rules used in firmware.

### `simulation/visual_simulator_real_data.py`

Replays the validated road CSV inside the visual simulator.
Cars still enter from outside the crossroad, but real CSV queue pressure controls the replay.

### Other Simulators

- `simulate_traffic.py`: text-based controller demo.
- `visual_simulator.py`: visual traffic demo.
- `visual_simulator_emergency.py`: visual demo with emergency behavior.
- `test_controller.py`: repeatable software checks for controller rules.

## Reliability Features To Explain

### False Positive Control

The firmware reduces false positives with:

- configurable per-sensor thresholds;
- median-of-3 distance filtering;
- 2-sample occupancy debounce;
- manual road labels for measured TP/TN/FP/FN.

### Sensor Health

Repeated invalid ultrasonic readings are reported as:

```text
health=F:OK,N:OK
health=F:WARN,N:OK
health=F:FAIL,N:OK
```

This helps distinguish "no car" from "sensor probably disconnected or badly aimed."

### Node A Failure

Node B detects stale Node A telemetry after the stale timeout.

Expected log:

```text
source=LORA_STALE | stale=ON | backup=ON | recovery=WAITING_FOR_LORA
```

Node B then uses conservative Side A demand instead of pretending that Side A is empty.
When Node A returns, Node B logs recovery and resumes live LoRa data.

### Node B Failure

Node B currently controls the physical LEDs, so a true Node B failure requires hardware redundancy.
The proposed solution is a tri-state buffer or failover selector so Node A can safely drive the lights only when Node B is disconnected from the LED lines.

Do not connect two ESP32 GPIOs directly to the same LED line.

## How To Read The Live Demo Log

Example:

```text
B STATUS | A_queue=1 | B_queue=0 | A_far=169.2cm/FREE | A_near=165.6cm/FREE | B_far=14.9cm/OCC | B_near=142.6cm/FREE | thresholds=50.0/50.0 | source=LORA_RADIO | stale=OFF | backup=OFF | recovery=LIVE | green=B | phase=GREEN | emergency=OFF | lights=A:RED B:GREEN
```

Meaning:

- Node B is receiving Node A data over LoRa.
- Side A queue is `1`; Side B queue is `0`.
- B far sensor detects an object at `14.9 cm`.
- Backup is off because LoRa is live.
- B side currently has green.

## What To Say In The Presentation

Use this short explanation:

> The project is organized around two ESP32 LoRa nodes. Node A senses one road side and sends compact telemetry. Node B senses the second road side, receives Node A data, runs the adaptive controller, and drives the LEDs. The logger stores real sensor distances, queue estimates, LoRa freshness, emergency state, backup state, and power values. The simulator is then used as a digital twin to replay the measured road demand and compare adaptive behavior against fixed timing.

The most important point is that the evaluation is based on real sensor data and manual labels, not only simulated cars.
