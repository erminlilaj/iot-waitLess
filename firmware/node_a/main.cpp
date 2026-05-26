#include <Arduino.h>
#include <stdio.h>

// Node A is the side-A sensing node. It reads two ultrasonic sensors, estimates
// queue pressure for its side, and sends compact LoRa telemetry to Node B.

#include "DebugSupport.h"
#include "LoRaTransport.h"
#include "NodeMessaging.h"
#include "SensorSupport.h"
#include "shared/HardwareMap.h"
#include "shared/Ina219Support.h"
#include "TrafficSensing.h"
#include "shared/ProjectConfig.h"

namespace {

LaneEstimator laneEstimator;

enum class EnergyTxMode : uint8_t {
  ActiveTelemetry = 0,
  IdleHeartbeat = 1,
  PeakHeartbeat = 2,
};

// Runtime state is kept explicit so it can be printed in status/report logs.
bool emulationEnabled = false;
bool emulatedFarOccupied = false;
bool emulatedNearOccupied = false;
bool manualEmergencyRequested = false;
bool manualPeakTrafficMode = false;
bool autoPeakTrafficMode = false;
int8_t demoHour = -1;
LogMode logMode = LogMode::Summary;
float farThresholdCm = config::kFarThresholdCm;
float nearThresholdCm = config::kNearThresholdCm;
uint32_t lastLoopMs = 0;
uint32_t lastStatusMs = 0;
uint32_t lastFullTelemetryMs = 0;
uint32_t lastHeartbeatMs = 0;
bool lastTxUsedRadio = false;
bool hasSnapshot = false;
bool hasLastSentTelemetry = false;
float lastFarDistanceCm = 999.0f;
float lastNearDistanceCm = 999.0f;
bool lastFarOccupied = false;
bool lastNearOccupied = false;
SideTelemetry lastTelemetry;
SideTelemetry lastSentTelemetry;
String lastPayload;
String lastTxPacketKind = "NONE";
EnergyTxMode lastTxMode = EnergyTxMode::ActiveTelemetry;
Ina219Reading lastPowerReading;
OccupancyDebouncer farDebouncer;
OccupancyDebouncer nearDebouncer;
SensorHealthTracker farHealth;
SensorHealthTracker nearHealth;

void sendTelemetryOverLoRa(const String& payload) {
  // The payload is saved even if radio transmission fails so the serial log
  // still shows exactly what would have been sent.
  lastPayload = payload;
  lastTxPacketKind = "TELEMETRY";
  lastTxUsedRadio = loRaSendText(payload, Serial);
}

void sendHeartbeatOverLoRa(EnergyTxMode mode, uint32_t nowMs) {
  const HeartbeatMode heartbeatMode = mode == EnergyTxMode::PeakHeartbeat ? HeartbeatMode::Peak : HeartbeatMode::Idle;
  lastPayload = encodeHeartbeat(SideId::A, heartbeatMode, nowMs);
  lastTxPacketKind = heartbeatMode == HeartbeatMode::Peak ? "HEARTBEAT_PEAK" : "HEARTBEAT_IDLE";
  lastTxUsedRadio = loRaSendText(lastPayload, Serial);
}

bool hourInPeakWindow(int8_t hour) {
  return (hour >= config::kMorningPeakStartHour && hour < config::kMorningPeakEndHour) ||
         (hour >= config::kEveningPeakStartHour && hour < config::kEveningPeakEndHour);
}

bool peakTrafficModeActive() {
  return manualPeakTrafficMode || (autoPeakTrafficMode && demoHour >= 0 && hourInPeakWindow(demoHour));
}

const char* energyModeLabel(EnergyTxMode mode) {
  if (mode == EnergyTxMode::IdleHeartbeat) {
    return "IDLE_HEARTBEAT";
  }
  if (mode == EnergyTxMode::PeakHeartbeat) {
    return "PEAK_HEARTBEAT";
  }
  return "ACTIVE_TELEMETRY";
}

EnergyTxMode chooseEnergyTxMode(const SideTelemetry& telemetry) {
  if (telemetry.emergencyRequested) {
    return EnergyTxMode::ActiveTelemetry;
  }
  if (peakTrafficModeActive()) {
    return EnergyTxMode::PeakHeartbeat;
  }
  if (!hasDemand(telemetry)) {
    return EnergyTxMode::IdleHeartbeat;
  }
  return EnergyTxMode::ActiveTelemetry;
}

bool trafficStateChanged(const SideTelemetry& current, const SideTelemetry& previous) {
  return current.farOccupied != previous.farOccupied ||
         current.nearOccupied != previous.nearOccupied ||
         current.emergencyRequested != previous.emergencyRequested ||
         current.estimatedQueue != previous.estimatedQueue;
}

void printBenchHelp() {
  Serial.println("Node A commands:");
  Serial.println("  help");
  Serial.println("  emu_on");
  Serial.println("  emu_off");
  Serial.println("  reset_counts");
  Serial.println("  thresholds");
  Serial.println("  set_thresholds <far_cm> <near_cm>");
  Serial.println("  set_far_threshold <cm>");
  Serial.println("  set_near_threshold <cm>");
  Serial.println("  filter");
  Serial.println("  health");
  Serial.println("  power");
  Serial.println("  energy");
  Serial.println("  peak_on");
  Serial.println("  peak_off");
  Serial.println("  peak_auto_on");
  Serial.println("  peak_auto_off");
  Serial.println("  set_demo_hour <0-23>");
  Serial.println("  ambulance_on");
  Serial.println("  ambulance_off");
  Serial.println("  state <far> <near>");
  printLogModeCommands(Serial);
}

const char* occupancyLabel(bool occupied) {
  return occupied ? "OCC" : "FREE";
}

const char* sourceLabel() {
  return emulationEnabled ? "SERIAL_EMU" : "SENSORS";
}

const char* txBackendLabel() {
  return lastTxUsedRadio ? "RADIO_TX_OK" : "SERIAL_STUB";
}

bool isValidThreshold(float thresholdCm) {
  return thresholdCm >= 5.0f && thresholdCm <= 400.0f;
}

void printThresholds(Stream& out) {
  out.print("far_threshold_cm: ");
  out.println(farThresholdCm, 1);
  out.print("near_threshold_cm: ");
  out.println(nearThresholdCm, 1);
}

void printEnergyStatus(Stream& out) {
  printSectionHeader(out, "ENERGY COMMUNICATION");
  out.print("manual_peak_mode: ");
  out.println(onOffLabel(manualPeakTrafficMode));
  out.print("auto_peak_mode: ");
  out.println(onOffLabel(autoPeakTrafficMode));
  out.print("demo_hour: ");
  if (demoHour >= 0) {
    out.println(demoHour);
  } else {
    out.println("NOT_SET");
  }
  out.print("peak_window: ");
  out.print(config::kMorningPeakStartHour);
  out.print("-");
  out.print(config::kMorningPeakEndHour);
  out.print(", ");
  out.print(config::kEveningPeakStartHour);
  out.print("-");
  out.println(config::kEveningPeakEndHour);
  out.print("current_tx_mode: ");
  out.println(energyModeLabel(lastTxMode));
  out.print("last_packet_kind: ");
  out.println(lastTxPacketKind);
  out.print("last_payload: ");
  out.println(lastPayload.length() > 0 ? lastPayload : "NONE");
}

void printSensorFilterValue(Stream& out) {
  out.print("median");
  out.print(static_cast<int>(config::kUltrasonicMedianSamples));
  out.print("_debounce");
  out.print(static_cast<int>(config::kOccupancyDebounceSamples));
}

void printSensorFilter(Stream& out) {
  out.print("sensor_filter: ");
  printSensorFilterValue(out);
  out.println();
}

void printSensorHealthValue(Stream& out) {
  out.print("F:");
  out.print(farHealth.status(config::kSensorHealthWarnInvalidSamples, config::kSensorHealthFailInvalidSamples));
  out.print(",N:");
  out.print(nearHealth.status(config::kSensorHealthWarnInvalidSamples, config::kSensorHealthFailInvalidSamples));
}

void printSensorHealth(Stream& out) {
  const SensorHealth& far = farHealth.snapshot();
  const SensorHealth& near = nearHealth.snapshot();

  out.print("sensor_health: ");
  printSensorHealthValue(out);
  out.println();
  out.print("far_invalid_streak: ");
  out.println(far.consecutiveInvalid);
  out.print("far_invalid_rate_pct: ");
  out.println(farHealth.invalidRatePercent());
  out.print("near_invalid_streak: ");
  out.println(near.consecutiveInvalid);
  out.print("near_invalid_rate_pct: ");
  out.println(nearHealth.invalidRatePercent());
}

void resetSensorFilters() {
  farDebouncer.reset(false);
  nearDebouncer.reset(false);
}

bool applyThresholdCommand(const String& command, Stream& out) {
  if (command.equalsIgnoreCase("thresholds")) {
    printSectionHeader(out, "SENSOR THRESHOLDS");
    printThresholds(out);
    printSensorFilter(out);
    return true;
  }

  if (command.equalsIgnoreCase("filter")) {
    printSectionHeader(out, "SENSOR FILTER");
    printSensorFilter(out);
    out.println("median filtering rejects single ultrasonic spikes; debounce requires repeated agreement before occupancy changes.");
    return true;
  }

  if (command.equalsIgnoreCase("health")) {
    printSectionHeader(out, "SENSOR HEALTH");
    printSensorHealth(out);
    out.println("WARN/FAIL means repeated invalid ultrasonic readings, usually timeout, bad angle, loose wiring, or sensor power issue.");
    return true;
  }

  float farCm = 0.0f;
  float nearCm = 0.0f;
  if (sscanf(command.c_str(), "set_thresholds %f %f", &farCm, &nearCm) == 2) {
    if (!isValidThreshold(farCm) || !isValidThreshold(nearCm)) {
      out.println("Thresholds must be between 5 cm and 400 cm.");
      return true;
    }

    farThresholdCm = farCm;
    nearThresholdCm = nearCm;
    resetSensorFilters();
    out.println("Sensor thresholds updated.");
    printThresholds(out);
    printSensorFilter(out);
    return true;
  }

  if (sscanf(command.c_str(), "set_far_threshold %f", &farCm) == 1) {
    if (!isValidThreshold(farCm)) {
      out.println("Far threshold must be between 5 cm and 400 cm.");
      return true;
    }

    farThresholdCm = farCm;
    resetSensorFilters();
    out.println("Far sensor threshold updated.");
    printThresholds(out);
    printSensorFilter(out);
    return true;
  }

  if (sscanf(command.c_str(), "set_near_threshold %f", &nearCm) == 1) {
    if (!isValidThreshold(nearCm)) {
      out.println("Near threshold must be between 5 cm and 400 cm.");
      return true;
    }

    nearThresholdCm = nearCm;
    resetSensorFilters();
    out.println("Near sensor threshold updated.");
    printThresholds(out);
    printSensorFilter(out);
    return true;
  }

  return false;
}

void printStatusSnapshot(Stream& out) {
  printSectionHeader(out, "NODE A STATUS");

  if (!hasSnapshot) {
    out.println("No telemetry snapshot yet. Wait one telemetry interval, then run status again.");
    return;
  }

  out.print("log_mode: ");
  out.println(logModeName(logMode));
  out.print("source: ");
  out.println(sourceLabel());
  printThresholds(out);
  printSensorFilter(out);
  printSensorHealth(out);
  out.print("far_sensor: ");
  if (emulationEnabled) {
    out.println(occupancyLabel(lastFarOccupied));
  } else {
    out.print(lastFarDistanceCm, 1);
    out.print(" cm | ");
    out.println(occupancyLabel(lastFarOccupied));
  }
  out.print("near_sensor: ");
  if (emulationEnabled) {
    out.println(occupancyLabel(lastNearOccupied));
  } else {
    out.print(lastNearDistanceCm, 1);
    out.print(" cm | ");
    out.println(occupancyLabel(lastNearOccupied));
  }
  out.print("incoming_count: ");
  out.println(lastTelemetry.incomingCount);
  out.print("passed_count: ");
  out.println(lastTelemetry.passedCount);
  out.print("estimated_queue: ");
  out.println(lastTelemetry.estimatedQueue);
  out.print("ambulance_override: ");
  out.println(onOffLabel(lastTelemetry.emergencyRequested));
  out.print("energy_tx_mode: ");
  out.println(energyModeLabel(lastTxMode));
  out.print("last_packet_kind: ");
  out.println(lastTxPacketKind);
  out.print("tx_backend: ");
  out.println(txBackendLabel());
  out.print("last_payload: ");
  out.println(lastPayload.length() > 0 ? lastPayload : "NONE");
  out.print("power: ");
  printIna219Reading(out, lastPowerReading);
}

void printReport(Stream& out) {
  printSectionHeader(out, "REPORT NODE_A");

  if (!hasSnapshot) {
    out.println("status: NO_DATA_YET");
    return;
  }

  out.print("log_mode: ");
  out.println(logModeName(logMode));
  out.print("source: ");
  out.println(sourceLabel());
  printThresholds(out);
  printSensorFilter(out);
  printSensorHealth(out);
  out.print("far_occupied: ");
  out.println(lastFarOccupied ? "YES" : "NO");
  out.print("far_distance_cm: ");
  out.println(emulationEnabled ? "EMU" : String(lastFarDistanceCm, 1));
  out.print("near_occupied: ");
  out.println(lastNearOccupied ? "YES" : "NO");
  out.print("near_distance_cm: ");
  out.println(emulationEnabled ? "EMU" : String(lastNearDistanceCm, 1));
  out.print("incoming_count: ");
  out.println(lastTelemetry.incomingCount);
  out.print("passed_count: ");
  out.println(lastTelemetry.passedCount);
  out.print("estimated_queue: ");
  out.println(lastTelemetry.estimatedQueue);
  out.print("ambulance_override: ");
  out.println(onOffLabel(lastTelemetry.emergencyRequested));
  out.print("energy_tx_mode: ");
  out.println(energyModeLabel(lastTxMode));
  out.print("last_packet_kind: ");
  out.println(lastTxPacketKind);
  out.print("tx_backend: ");
  out.println(txBackendLabel());
  out.print("payload: ");
  out.println(lastPayload.length() > 0 ? lastPayload : "NONE");
  out.print("power_bus_v: ");
  out.println(lastPowerReading.ok ? String(lastPowerReading.busVoltageV, 3) : "NA");
  out.print("power_current_ma: ");
  out.println(lastPowerReading.ok ? String(lastPowerReading.currentMa, 1) : "NA");
  out.print("power_mw: ");
  out.println(lastPowerReading.ok ? String(lastPowerReading.powerMw, 1) : "NA");
}

bool handleBenchCommand(const String& rawCommand) {
  String command = rawCommand;
  command.trim();

  if (command.length() == 0) {
    return false;
  }

  if (tryApplyLogModeCommand(command, logMode, Serial)) {
    return true;
  }

  if (applyThresholdCommand(command, Serial)) {
    return true;
  }

  if (command.equalsIgnoreCase("help")) {
    printBenchHelp();
    return false;
  }

  if (command.equalsIgnoreCase("status")) {
    printStatusSnapshot(Serial);
    return false;
  }

  if (command.equalsIgnoreCase("report")) {
    printReport(Serial);
    return false;
  }

  if (command.equalsIgnoreCase("power")) {
    Serial.print("INA219 power: ");
    printIna219Reading(Serial, lastPowerReading);
    return false;
  }

  if (command.equalsIgnoreCase("energy")) {
    printEnergyStatus(Serial);
    return false;
  }

  if (command.equalsIgnoreCase("peak_on")) {
    manualPeakTrafficMode = true;
    Serial.println("Node A peak low-communication mode enabled.");
    return true;
  }

  if (command.equalsIgnoreCase("peak_off")) {
    manualPeakTrafficMode = false;
    Serial.println("Node A peak low-communication mode disabled.");
    return true;
  }

  if (command.equalsIgnoreCase("peak_auto_on")) {
    autoPeakTrafficMode = true;
    Serial.println("Node A automatic peak window mode enabled. Use set_demo_hour <0-23> for demo time.");
    return true;
  }

  if (command.equalsIgnoreCase("peak_auto_off")) {
    autoPeakTrafficMode = false;
    Serial.println("Node A automatic peak window mode disabled.");
    return true;
  }

  int hour = -1;
  if (sscanf(command.c_str(), "set_demo_hour %d", &hour) == 1) {
    if (hour < 0 || hour > 23) {
      Serial.println("Demo hour must be between 0 and 23.");
      return true;
    }
    demoHour = static_cast<int8_t>(hour);
    Serial.print("Node A demo hour set to ");
    Serial.print(demoHour);
    Serial.print(" | in_peak_window=");
    Serial.println(onOffLabel(hourInPeakWindow(demoHour)));
    return true;
  }

  if (command.equalsIgnoreCase("emu_on")) {
    emulationEnabled = true;
    Serial.println("Node A switched to emulation mode.");
    return true;
  }

  if (command.equalsIgnoreCase("emu_off")) {
    emulationEnabled = false;
    emulatedFarOccupied = false;
    emulatedNearOccupied = false;
    resetSensorFilters();
    Serial.println("Node A switched to sensor mode.");
    return true;
  }

  if (command.equalsIgnoreCase("reset_counts")) {
    laneEstimator = LaneEstimator{};
    Serial.println("Node A estimator counters reset.");
    return true;
  }

  if (command.equalsIgnoreCase("ambulance_on")) {
    manualEmergencyRequested = true;
    Serial.println("Node A ambulance override enabled.");
    return true;
  }

  if (command.equalsIgnoreCase("ambulance_off")) {
    manualEmergencyRequested = false;
    Serial.println("Node A ambulance override cleared.");
    return true;
  }

  int farOccupied = 0;
  int nearOccupied = 0;
  if (sscanf(command.c_str(), "state %d %d", &farOccupied, &nearOccupied) == 2) {
    emulationEnabled = true;
    emulatedFarOccupied = farOccupied != 0;
    emulatedNearOccupied = nearOccupied != 0;
    Serial.print("Node A emulated state updated | far=");
    Serial.print(emulatedFarOccupied ? "1" : "0");
    Serial.print(" near=");
    Serial.println(emulatedNearOccupied ? "1" : "0");
    return true;
  }

  Serial.print("Unknown command: ");
  Serial.println(command);
  printBenchHelp();
  return false;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);

  // Sensor pins are defined in one shared hardware map to avoid drift between
  // the wiring diagram and firmware.
  pinMode(hw::node_a::kFarSensor.trig, OUTPUT);
  pinMode(hw::node_a::kFarSensor.echo, INPUT);
  pinMode(hw::node_a::kNearSensor.trig, OUTPUT);
  pinMode(hw::node_a::kNearSensor.echo, INPUT);

  Serial.println("Node A ready.");
  Serial.print("Node A far sensor trig/echo: ");
  Serial.print(hw::node_a::kFarSensor.trig);
  Serial.print("/");
  Serial.println(hw::node_a::kFarSensor.echo);
  Serial.print("Node A near sensor trig/echo: ");
  Serial.print(hw::node_a::kNearSensor.trig);
  Serial.print("/");
  Serial.println(hw::node_a::kNearSensor.echo);
  loRaBegin(false, Serial);
  loRaPrintConfig(Serial);
  ina219Begin(
      hw::heltec_v3::kIna219I2c.sda,
      hw::heltec_v3::kIna219I2c.scl,
      config::kIna219Address,
      Serial);
  printBenchHelp();
}

void loop() {
  // Serial commands are used for bench tests, threshold tuning, and emergency
  // emulation without reflashing the board.
  if (Serial.available()) {
    const String input = Serial.readStringUntil('\n');
    handleBenchCommand(input);
  }

  const uint32_t nowMs = millis();

  if (nowMs - lastLoopMs < config::kLoopIntervalMs) {
    return;
  }
  lastLoopMs = nowMs;

  float farDistance = 999.0f;
  float nearDistance = 999.0f;
  bool farOccupied = false;
  bool nearOccupied = false;

  if (emulationEnabled) {
    // Emulation mode feeds known states into the same estimator used by sensors.
    farOccupied = emulatedFarOccupied;
    nearOccupied = emulatedNearOccupied;
  } else {
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
    farHealth.update(farDistance);
    nearHealth.update(nearDistance);
  }

  SideTelemetry telemetry = laneEstimator.update(SideId::A, farOccupied, nearOccupied, nowMs);
  telemetry.emergencyRequested = manualEmergencyRequested;
  telemetry.farDistanceCm = farDistance;
  telemetry.nearDistanceCm = nearDistance;
  lastFarDistanceCm = farDistance;
  lastNearDistanceCm = nearDistance;
  lastFarOccupied = farOccupied;
  lastNearOccupied = nearOccupied;
  lastTelemetry = telemetry;
  lastPowerReading = ina219Read();
  hasSnapshot = true;

  const EnergyTxMode currentTxMode = chooseEnergyTxMode(telemetry);
  const bool modeChanged = currentTxMode != lastTxMode;
  bool sendFullTelemetry = false;
  bool sendHeartbeat = false;

  if (currentTxMode == EnergyTxMode::ActiveTelemetry) {
    sendFullTelemetry = modeChanged || (nowMs - lastFullTelemetryMs >= config::kTelemetryIntervalMs);
  } else if (currentTxMode == EnergyTxMode::IdleHeartbeat) {
    sendFullTelemetry = !hasLastSentTelemetry || trafficStateChanged(telemetry, lastSentTelemetry);
    sendHeartbeat = !sendFullTelemetry && (modeChanged || (nowMs - lastHeartbeatMs >= config::kHeartbeatIntervalMs));
  } else {
    const bool emergencyChanged = hasLastSentTelemetry && telemetry.emergencyRequested != lastSentTelemetry.emergencyRequested;
    sendFullTelemetry = emergencyChanged;
    sendHeartbeat = !sendFullTelemetry && (modeChanged || (nowMs - lastHeartbeatMs >= config::kPeakHeartbeatIntervalMs));
  }

  if (sendFullTelemetry) {
    const String payload = encodeTelemetry(telemetry);
    sendTelemetryOverLoRa(payload);
    lastFullTelemetryMs = nowMs;
    lastHeartbeatMs = nowMs;
    lastSentTelemetry = telemetry;
    hasLastSentTelemetry = true;
  } else if (sendHeartbeat) {
    sendHeartbeatOverLoRa(currentTxMode, nowMs);
    lastHeartbeatMs = nowMs;
  }
  lastTxMode = currentTxMode;

  if (nowMs - lastStatusMs >= config::kTelemetryIntervalMs) {
    lastStatusMs = nowMs;

    if (logMode == LogMode::Summary) {
      Serial.print("A STATUS | source=");
      Serial.print(sourceLabel());
      Serial.print(" | thresholds=");
      Serial.print(farThresholdCm, 1);
      Serial.print("/");
      Serial.print(nearThresholdCm, 1);
      Serial.print(" | filter=");
      printSensorFilterValue(Serial);
      Serial.print(" | health=");
      printSensorHealthValue(Serial);
      Serial.print(" | far=");
      if (emulationEnabled) {
        Serial.print(occupancyLabel(farOccupied));
      } else {
        Serial.print(farDistance, 1);
        Serial.print("cm/");
        Serial.print(occupancyLabel(farOccupied));
      }
      Serial.print(" | near=");
      if (emulationEnabled) {
        Serial.print(occupancyLabel(nearOccupied));
      } else {
        Serial.print(nearDistance, 1);
        Serial.print("cm/");
        Serial.print(occupancyLabel(nearOccupied));
      }
      Serial.print(" | queue=");
      Serial.print(telemetry.estimatedQueue);
      Serial.print(" | in=");
      Serial.print(telemetry.incomingCount);
      Serial.print(" | out=");
      Serial.print(telemetry.passedCount);
      Serial.print(" | emergency=");
      Serial.print(onOffLabel(telemetry.emergencyRequested));
      Serial.print(" | energy_mode=");
      Serial.print(energyModeLabel(currentTxMode));
      Serial.print(" | last_packet=");
      Serial.print(lastTxPacketKind);
      Serial.print(" | tx=");
      Serial.print(txBackendLabel());
      Serial.print(" | power=");
      if (lastPowerReading.ok) {
        Serial.print(lastPowerReading.busVoltageV, 3);
        Serial.print("V/");
        Serial.print(lastPowerReading.currentMa, 1);
        Serial.print("mA/");
        Serial.print(lastPowerReading.powerMw, 1);
        Serial.print("mW");
      } else {
        Serial.print("INA219_NA");
      }
      Serial.print(" | payload=");
      Serial.println(lastPayload.length() > 0 ? lastPayload : "NONE");
    } else if (logMode == LogMode::Verbose) {
      Serial.print("A SENSE | source=");
      Serial.print(sourceLabel());
      Serial.print(" | far=");
      if (emulationEnabled) {
        Serial.print(occupancyLabel(farOccupied));
      } else {
        Serial.print(farDistance, 1);
        Serial.print("cm ");
        Serial.print(occupancyLabel(farOccupied));
      }
      Serial.print(" | near=");
      if (emulationEnabled) {
        Serial.print(occupancyLabel(nearOccupied));
      } else {
        Serial.print(nearDistance, 1);
        Serial.print("cm ");
        Serial.print(occupancyLabel(nearOccupied));
      }
      Serial.print(" | incoming=");
      Serial.print(telemetry.incomingCount);
      Serial.print(" passed=");
      Serial.print(telemetry.passedCount);
      Serial.print(" queue=");
      Serial.print(telemetry.estimatedQueue);
      Serial.print(" ambulance=");
      Serial.print(onOffLabel(telemetry.emergencyRequested));
      Serial.print(" energyMode=");
      Serial.print(energyModeLabel(currentTxMode));
      Serial.print(" power=");
      printIna219Reading(Serial, lastPowerReading);

      Serial.print("A TX | backend=");
      Serial.print(txBackendLabel());
      Serial.print(" kind=");
      Serial.print(lastTxPacketKind);
      Serial.print(" | payload=");
      Serial.println(lastPayload.length() > 0 ? lastPayload : "NONE");
    }
  }
}
