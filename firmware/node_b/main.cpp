#include <Arduino.h>
#include <stdio.h>

#include "AdaptiveController.h"
#include "DebugSupport.h"
#include "LoRaTransport.h"
#include "NodeMessaging.h"
#include "SensorSupport.h"
#include "shared/HardwareMap.h"
#include "shared/Ina219Support.h"
#include "TrafficSensing.h"
#include "shared/ProjectConfig.h"

namespace {

constexpr uint16_t kLightSelfTestOnMs = 350;
constexpr uint16_t kLightSelfTestOffMs = 120;
constexpr uint16_t kButtonDebounceMs = 35;
constexpr uint16_t kButtonClickWindowMs = 450;
constexpr uint16_t kButtonLongPressMs = 1200;
constexpr uint32_t kBackupRemoteQueue = 1;

ControllerConfig makeControllerConfig() {
  ControllerConfig config;
  config.minGreenMs = config::kMinGreenMs;
  config.maxGreenMs = config::kMaxGreenMs;
  config.yellowMs = config::kYellowMs;
  config.advantageMargin = config::kAdvantageMargin;
  return config;
}

LaneEstimator laneEstimator;
AdaptiveController controller(makeControllerConfig());

SideTelemetry remoteTelemetry;

bool localEmergencyRequested = false;
bool remoteEmergencyRequested = false;
bool remoteTelemetryInjected = false;
LogMode logMode = LogMode::Summary;
float farThresholdCm = config::kFarThresholdCm;
float nearThresholdCm = config::kNearThresholdCm;
uint32_t lastLoopMs = 0;
uint32_t lastStatusMs = 0;
uint32_t lastRemoteRxMs = 0;
bool hasSnapshot = false;
float lastFarDistanceCm = 999.0f;
float lastNearDistanceCm = 999.0f;
bool lastFarOccupied = false;
bool lastNearOccupied = false;
SideTelemetry lastLocalTelemetry;
SideTelemetry lastEffectiveRemoteTelemetry;
TrafficDecision lastDecision;
String lastRemoteSource = "IDLE";
float lastRssiDbm = 0.0f;
float lastSnrDb = 0.0f;
bool lastRxWasRadio = false;
bool remoteTelemetryStale = false;
bool nodeABackupActive = false;
const char* nodeABackupReason = "NONE";
Ina219Reading lastPowerReading;
OccupancyDebouncer farDebouncer;
OccupancyDebouncer nearDebouncer;
SensorHealthTracker farHealth;
SensorHealthTracker nearHealth;
bool emergencyButtonStablePressed = false;
bool emergencyButtonLastRawPressed = false;
uint32_t emergencyButtonLastRawChangeMs = 0;
uint32_t emergencyButtonPressedAtMs = 0;
uint32_t emergencyButtonLastReleaseMs = 0;
uint8_t emergencyButtonClickCount = 0;
bool emergencyButtonLongHandled = false;

const char* lightStateLabel(bool red, bool yellow, bool green);

SideTelemetry makeRemoteTelemetry(
    bool farOccupied,
    bool nearOccupied,
    bool emergencyRequested,
    uint32_t estimatedQueue,
    uint32_t nowMs);

const char* backupModeLabel() {
  return nodeABackupActive ? "ON" : "OFF";
}

const char* recoveryStateLabel() {
  return nodeABackupActive ? "WAITING_FOR_LORA" : "LIVE";
}

void setNodeABackupActive(bool active, const char* reason) {
  if (nodeABackupActive == active) {
    if (active) {
      nodeABackupReason = reason;
    }
    return;
  }

  nodeABackupActive = active;
  nodeABackupReason = active ? reason : "NONE";

  if (active) {
    Serial.print("BACKUP EVENT | backup=ON | reason=");
    Serial.print(nodeABackupReason);
    Serial.println(" | node_b=TAKEOVER | recovery=WAITING_FOR_LORA");
  } else {
    Serial.println("RECOVERY EVENT | backup=OFF | reason=NODE_A_RECOVERED | recovery=LIVE");
  }
}

SideTelemetry applyRemoteEmergencyOverride(SideTelemetry telemetry) {
  telemetry.emergencyRequested = telemetry.emergencyRequested || remoteEmergencyRequested;
  return telemetry;
}

SideTelemetry makeNodeABackupTelemetry(uint32_t nowMs) {
  SideTelemetry telemetry = makeRemoteTelemetry(false, false, false, kBackupRemoteQueue, nowMs);
  telemetry.farDistanceCm = 999.0f;
  telemetry.nearDistanceCm = 999.0f;
  return telemetry;
}

SideTelemetry effectiveRemoteTelemetry(uint32_t nowMs) {
  if (remoteTelemetryInjected) {
    setNodeABackupActive(false, "SERIAL_EMU");
    remoteTelemetryStale = false;
    lastRemoteSource = "SERIAL_EMU";
    return applyRemoteEmergencyOverride(remoteTelemetry);
  }

  if (!loRaIsActive()) {
    setNodeABackupActive(true, "LORA_INACTIVE");
    remoteTelemetryStale = false;
    lastRemoteSource = "BACKUP_NO_LORA";
    return applyRemoteEmergencyOverride(makeNodeABackupTelemetry(nowMs));
  }

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

void applyLights(const LightOutput& lights) {
  digitalWrite(hw::node_b::kSideALights.red, lights.aRed ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideALights.yellow, lights.aYellow ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideALights.green, lights.aGreen ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideBLights.red, lights.bRed ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideBLights.yellow, lights.bYellow ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideBLights.green, lights.bGreen ? HIGH : LOW);
}

void setAllLightsOff() {
  digitalWrite(hw::node_b::kSideALights.red, LOW);
  digitalWrite(hw::node_b::kSideALights.yellow, LOW);
  digitalWrite(hw::node_b::kSideALights.green, LOW);
  digitalWrite(hw::node_b::kSideBLights.red, LOW);
  digitalWrite(hw::node_b::kSideBLights.yellow, LOW);
  digitalWrite(hw::node_b::kSideBLights.green, LOW);
}

void setBothHeads(bool red, bool yellow, bool green) {
  digitalWrite(hw::node_b::kSideALights.red, red ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideALights.yellow, yellow ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideALights.green, green ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideBLights.red, red ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideBLights.yellow, yellow ? HIGH : LOW);
  digitalWrite(hw::node_b::kSideBLights.green, green ? HIGH : LOW);
}

void runLightSelfTest() {
  setBothHeads(true, false, false);
  delay(kLightSelfTestOnMs);
  setAllLightsOff();
  delay(kLightSelfTestOffMs);

  setBothHeads(false, true, false);
  delay(kLightSelfTestOnMs);
  setAllLightsOff();
  delay(kLightSelfTestOffMs);

  setBothHeads(false, false, true);
  delay(kLightSelfTestOnMs);
  setAllLightsOff();
  delay(kLightSelfTestOffMs);
}

SideTelemetry makeRemoteTelemetry(
    bool farOccupied,
    bool nearOccupied,
    bool emergencyRequested,
    uint32_t estimatedQueue,
    uint32_t nowMs) {
  SideTelemetry telemetry;
  telemetry.side = SideId::A;
  telemetry.farOccupied = farOccupied;
  telemetry.nearOccupied = nearOccupied;
  telemetry.emergencyRequested = emergencyRequested;
  telemetry.incomingCount = estimatedQueue;
  telemetry.passedCount = 0;
  telemetry.estimatedQueue = estimatedQueue;
  telemetry.timestampMs = nowMs;
  telemetry.farDistanceCm = farOccupied ? 25.0f : 999.0f;
  telemetry.nearDistanceCm = nearOccupied ? 25.0f : 999.0f;
  return telemetry;
}

bool parseTelemetryLine(const String& rawLine, SideTelemetry& telemetry) {
  String line = rawLine;
  line.trim();

  if (line.startsWith("A,") || line.startsWith("B,")) {
    return decodeTelemetry(line, telemetry);
  }

  const int sideAIndex = line.indexOf("A,");
  const int sideBIndex = line.indexOf("B,");

  int payloadIndex = -1;
  if (sideAIndex >= 0 && sideBIndex >= 0) {
    payloadIndex = min(sideAIndex, sideBIndex);
  } else if (sideAIndex >= 0) {
    payloadIndex = sideAIndex;
  } else if (sideBIndex >= 0) {
    payloadIndex = sideBIndex;
  }

  if (payloadIndex < 0) {
    return false;
  }

  return decodeTelemetry(line.substring(payloadIndex), telemetry);
}

void printBenchHelp() {
  Serial.println("Bench commands:");
  Serial.println("  help");
  Serial.println("  remote_clear");
  Serial.println("  remote_queue <queue>");
  Serial.println("  remote_state <far> <near> <queue>");
  Serial.println("  thresholds");
  Serial.println("  set_thresholds <far_cm> <near_cm>");
  Serial.println("  set_far_threshold <cm>");
  Serial.println("  set_near_threshold <cm>");
  Serial.println("  filter");
  Serial.println("  health");
  Serial.println("  power");
  Serial.println("  remote_ambulance_on");
  Serial.println("  remote_ambulance_off");
  Serial.println("  local_ambulance_on");
  Serial.println("  local_ambulance_off");
  Serial.println("  physical button: 1 click=B emergency, 2 clicks=A emergency, long press=clear");
  Serial.println("  A,1,0,4,2,2,0,12345,42.0,999.0   (raw telemetry payload with distances)");
  printLogModeCommands(Serial);
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

void printDistanceState(Stream& out, float distanceCm, bool occupied) {
  out.print(distanceCm, 1);
  out.print("cm/");
  out.print(occupied ? "OCC" : "FREE");
}

void resetSensorFilters() {
  farDebouncer.reset(false);
  nearDebouncer.reset(false);
}

const char* requestedEmergencyTargetLabel() {
  if (remoteEmergencyRequested && localEmergencyRequested) {
    return "A+B";
  }
  if (remoteEmergencyRequested) {
    return "A";
  }
  if (localEmergencyRequested) {
    return "B";
  }
  return "OFF";
}

const char* decisionEmergencyTargetLabel(const TrafficDecision& decision) {
  return decision.emergencyOverride ? sideName(decision.prioritySide) : "NONE";
}

void clearEmergencyOverrides(const char* sourceLabel) {
  localEmergencyRequested = false;
  remoteEmergencyRequested = false;
  remoteTelemetry.emergencyRequested = false;
  Serial.print(sourceLabel);
  Serial.println(" | emergency_target=NONE | local_ambulance=OFF | remote_ambulance=OFF");
}

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
  Serial.print(" | local_ambulance=");
  Serial.print(onOffLabel(localEmergencyRequested));
  Serial.print(" | remote_ambulance=");
  Serial.println(onOffLabel(remoteEmergencyRequested));
}

void processEmergencyButton(uint32_t nowMs) {
  const bool rawPressed = digitalRead(hw::node_b::kEmergencyButton) == LOW;

  if (rawPressed != emergencyButtonLastRawPressed) {
    emergencyButtonLastRawPressed = rawPressed;
    emergencyButtonLastRawChangeMs = nowMs;
  }

  if ((nowMs - emergencyButtonLastRawChangeMs) >= kButtonDebounceMs &&
      rawPressed != emergencyButtonStablePressed) {
    emergencyButtonStablePressed = rawPressed;

    if (emergencyButtonStablePressed) {
      emergencyButtonPressedAtMs = nowMs;
      emergencyButtonLongHandled = false;
    } else if (!emergencyButtonLongHandled) {
      ++emergencyButtonClickCount;
      emergencyButtonLastReleaseMs = nowMs;
    }
  }

  if (emergencyButtonStablePressed &&
      !emergencyButtonLongHandled &&
      (nowMs - emergencyButtonPressedAtMs) >= kButtonLongPressMs) {
    emergencyButtonClickCount = 0;
    emergencyButtonLongHandled = true;
    clearEmergencyOverrides("BUTTON EVENT | action=CLEAR");
  }

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
  printSectionHeader(out, "NODE B STATUS");

  if (!hasSnapshot) {
    out.println("No controller snapshot yet. Wait one loop interval, then run status again.");
    return;
  }

  out.print("log_mode: ");
  out.println(logModeName(logMode));
  printThresholds(out);
  printSensorFilter(out);
  printSensorHealth(out);
  out.print("local_far_sensor: ");
  out.print(lastFarDistanceCm, 1);
  out.print(" cm | ");
  out.println(lastFarOccupied ? "OCC" : "FREE");
  out.print("local_near_sensor: ");
  out.print(lastNearDistanceCm, 1);
  out.print(" cm | ");
  out.println(lastNearOccupied ? "OCC" : "FREE");
  out.print("local_queue: ");
  out.println(lastLocalTelemetry.estimatedQueue);
  out.print("remote_queue: ");
  out.println(lastEffectiveRemoteTelemetry.estimatedQueue);
  out.print("remote_far_sensor: ");
  out.print(lastEffectiveRemoteTelemetry.farDistanceCm, 1);
  out.print(" cm | ");
  out.println(lastEffectiveRemoteTelemetry.farOccupied ? "OCC" : "FREE");
  out.print("remote_near_sensor: ");
  out.print(lastEffectiveRemoteTelemetry.nearDistanceCm, 1);
  out.print(" cm | ");
  out.println(lastEffectiveRemoteTelemetry.nearOccupied ? "OCC" : "FREE");
  out.print("remote_source: ");
  out.println(lastRemoteSource);
  out.print("remote_stale: ");
  out.println(onOffLabel(remoteTelemetryStale));
  out.print("backup_mode: ");
  out.println(backupModeLabel());
  out.print("backup_reason: ");
  out.println(nodeABackupReason);
  out.print("recovery_state: ");
  out.println(recoveryStateLabel());
  if (lastRemoteRxMs > 0) {
    out.print("last_radio_age_ms: ");
    out.println(millis() - lastRemoteRxMs);
  }
  out.print("green_side: ");
  out.println(sideName(lastDecision.greenSide));
  out.print("phase: ");
  out.println(lastDecision.phase == SignalPhase::Green ? "GREEN" : "YELLOW");
  out.print("phase_elapsed_ms: ");
  out.println(lastDecision.phaseElapsedMs);
  out.print("current_demand: ");
  out.println(lastDecision.currentDemand);
  out.print("other_demand: ");
  out.println(lastDecision.otherDemand);
  out.print("emergency_override: ");
  out.println(onOffLabel(lastDecision.emergencyOverride));
  out.print("emergency_target: ");
  out.println(decisionEmergencyTargetLabel(lastDecision));
  out.print("button_override: ");
  out.println(requestedEmergencyTargetLabel());
  out.print("priority_side: ");
  out.println(sideName(lastDecision.prioritySide));
  out.print("side_a_light: ");
  out.println(lightStateLabel(lastDecision.lights.aRed, lastDecision.lights.aYellow, lastDecision.lights.aGreen));
  out.print("side_b_light: ");
  out.println(lightStateLabel(lastDecision.lights.bRed, lastDecision.lights.bYellow, lastDecision.lights.bGreen));

  if (lastRxWasRadio) {
    out.print("last_rx_rssi_dbm: ");
    out.println(lastRssiDbm, 1);
    out.print("last_rx_snr_db: ");
    out.println(lastSnrDb, 1);
  }
  out.print("power: ");
  printIna219Reading(out, lastPowerReading);
}

void printReport(Stream& out) {
  printSectionHeader(out, "REPORT NODE_B");

  if (!hasSnapshot) {
    out.println("status: NO_DATA_YET");
    return;
  }

  out.print("log_mode: ");
  out.println(logModeName(logMode));
  printThresholds(out);
  printSensorFilter(out);
  printSensorHealth(out);
  out.print("local_far_distance_cm: ");
  out.println(lastFarDistanceCm, 1);
  out.print("local_far_occupied: ");
  out.println(lastFarOccupied ? "YES" : "NO");
  out.print("local_near_distance_cm: ");
  out.println(lastNearDistanceCm, 1);
  out.print("local_near_occupied: ");
  out.println(lastNearOccupied ? "YES" : "NO");
  out.print("local_queue: ");
  out.println(lastLocalTelemetry.estimatedQueue);
  out.print("remote_queue: ");
  out.println(lastEffectiveRemoteTelemetry.estimatedQueue);
  out.print("remote_far_distance_cm: ");
  out.println(lastEffectiveRemoteTelemetry.farDistanceCm, 1);
  out.print("remote_far_occupied: ");
  out.println(lastEffectiveRemoteTelemetry.farOccupied ? "YES" : "NO");
  out.print("remote_near_distance_cm: ");
  out.println(lastEffectiveRemoteTelemetry.nearDistanceCm, 1);
  out.print("remote_near_occupied: ");
  out.println(lastEffectiveRemoteTelemetry.nearOccupied ? "YES" : "NO");
  out.print("remote_source: ");
  out.println(lastRemoteSource);
  out.print("remote_stale: ");
  out.println(onOffLabel(remoteTelemetryStale));
  out.print("backup_mode: ");
  out.println(backupModeLabel());
  out.print("backup_reason: ");
  out.println(nodeABackupReason);
  out.print("recovery_state: ");
  out.println(recoveryStateLabel());
  if (lastRemoteRxMs > 0) {
    out.print("last_radio_age_ms: ");
    out.println(millis() - lastRemoteRxMs);
  }
  out.print("green_side: ");
  out.println(sideName(lastDecision.greenSide));
  out.print("phase: ");
  out.println(lastDecision.phase == SignalPhase::Green ? "GREEN" : "YELLOW");
  out.print("phase_elapsed_ms: ");
  out.println(lastDecision.phaseElapsedMs);
  out.print("current_demand: ");
  out.println(lastDecision.currentDemand);
  out.print("other_demand: ");
  out.println(lastDecision.otherDemand);
  out.print("emergency_override: ");
  out.println(onOffLabel(lastDecision.emergencyOverride));
  out.print("emergency_target: ");
  out.println(decisionEmergencyTargetLabel(lastDecision));
  out.print("button_override: ");
  out.println(requestedEmergencyTargetLabel());
  out.print("priority_side: ");
  out.println(sideName(lastDecision.prioritySide));
  out.print("side_a_light: ");
  out.println(lightStateLabel(lastDecision.lights.aRed, lastDecision.lights.aYellow, lastDecision.lights.aGreen));
  out.print("side_b_light: ");
  out.println(lightStateLabel(lastDecision.lights.bRed, lastDecision.lights.bYellow, lastDecision.lights.bGreen));

  if (lastRxWasRadio) {
    out.print("last_rx_rssi_dbm: ");
    out.println(lastRssiDbm, 1);
    out.print("last_rx_snr_db: ");
    out.println(lastSnrDb, 1);
  }
  out.print("power_bus_v: ");
  out.println(lastPowerReading.ok ? String(lastPowerReading.busVoltageV, 3) : "NA");
  out.print("power_current_ma: ");
  out.println(lastPowerReading.ok ? String(lastPowerReading.currentMa, 1) : "NA");
  out.print("power_mw: ");
  out.println(lastPowerReading.ok ? String(lastPowerReading.powerMw, 1) : "NA");
}

bool handleBenchCommand(const String& rawCommand, uint32_t nowMs) {
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

  if (command.equalsIgnoreCase("remote_clear")) {
    remoteTelemetry = makeRemoteTelemetry(false, false, false, 0, nowMs);
    remoteTelemetryInjected = false;
    lastRemoteRxMs = 0;
    remoteTelemetryStale = false;
    lastRxWasRadio = false;
    lastRemoteSource = "IDLE";
    Serial.println("Remote side reset to empty.");
    return true;
  }

  unsigned long queue = 0;
  if (sscanf(command.c_str(), "remote_queue %lu", &queue) == 1) {
    const bool occupied = queue > 0;
    remoteTelemetry = makeRemoteTelemetry(occupied, occupied, false, static_cast<uint32_t>(queue), nowMs);
    remoteTelemetryInjected = true;
    lastRemoteRxMs = 0;
    remoteTelemetryStale = false;
    lastRxWasRadio = false;
    lastRemoteSource = "SERIAL_EMU";
    Serial.print("Remote queue set to ");
    Serial.println(queue);
    return true;
  }

  if (command.equalsIgnoreCase("remote_ambulance_on")) {
    remoteEmergencyRequested = true;
    Serial.println("Remote ambulance override enabled.");
    return true;
  }

  if (command.equalsIgnoreCase("remote_ambulance_off")) {
    remoteEmergencyRequested = false;
    remoteTelemetry.emergencyRequested = false;
    remoteTelemetry.timestampMs = nowMs;
    remoteTelemetryStale = false;
    Serial.println("Remote ambulance override cleared.");
    return true;
  }

  if (command.equalsIgnoreCase("local_ambulance_on")) {
    localEmergencyRequested = true;
    Serial.println("Local ambulance override enabled.");
    return true;
  }

  if (command.equalsIgnoreCase("local_ambulance_off")) {
    localEmergencyRequested = false;
    Serial.println("Local ambulance override cleared.");
    return true;
  }

  int farOccupied = 0;
  int nearOccupied = 0;
  if (sscanf(command.c_str(), "remote_state %d %d %lu", &farOccupied, &nearOccupied, &queue) == 3) {
    remoteTelemetry = makeRemoteTelemetry(
        farOccupied != 0,
        nearOccupied != 0,
        remoteTelemetry.emergencyRequested,
        static_cast<uint32_t>(queue),
        nowMs);
    remoteTelemetryInjected = true;
    lastRemoteRxMs = 0;
    remoteTelemetryStale = false;
    lastRxWasRadio = false;
    lastRemoteSource = "SERIAL_EMU";
    Serial.print("Remote state updated | far=");
    Serial.print(farOccupied != 0 ? "1" : "0");
    Serial.print(" near=");
    Serial.print(nearOccupied != 0 ? "1" : "0");
    Serial.print(" queue=");
    Serial.print(queue);
    Serial.print(" ambulance=");
    Serial.println(remoteTelemetry.emergencyRequested ? "ON" : "OFF");
    return true;
  }

  SideTelemetry parsedTelemetry;
  if (parseTelemetryLine(command, parsedTelemetry) && parsedTelemetry.side == SideId::A) {
    remoteTelemetry = parsedTelemetry;
    remoteTelemetryInjected = true;
    lastRemoteRxMs = 0;
    remoteTelemetryStale = false;
    lastRxWasRadio = false;
    lastRemoteSource = "SERIAL_EMU";
    Serial.println("Remote telemetry payload accepted.");
    return true;
  }

  Serial.print("Unknown command: ");
  Serial.println(command);
  printBenchHelp();
  return false;
}

void processSerialInput(uint32_t nowMs) {
  if (!Serial.available()) {
    return;
  }

  const String input = Serial.readStringUntil('\n');
  handleBenchCommand(input, nowMs);
}

const char* lightStateLabel(bool red, bool yellow, bool green) {
  if (green) {
    return "GREEN";
  }
  if (yellow) {
    return "YELLOW";
  }
  if (red) {
    return "RED";
  }
  return "OFF";
}

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(25);

  pinMode(hw::node_b::kFarSensor.trig, OUTPUT);
  pinMode(hw::node_b::kFarSensor.echo, INPUT);
  pinMode(hw::node_b::kNearSensor.trig, OUTPUT);
  pinMode(hw::node_b::kNearSensor.echo, INPUT);
  pinMode(hw::node_b::kEmergencyButton, INPUT_PULLUP);
  emergencyButtonLastRawPressed = digitalRead(hw::node_b::kEmergencyButton) == LOW;
  emergencyButtonStablePressed = emergencyButtonLastRawPressed;
  emergencyButtonLastRawChangeMs = millis();

  pinMode(hw::node_b::kSideALights.red, OUTPUT);
  pinMode(hw::node_b::kSideALights.yellow, OUTPUT);
  pinMode(hw::node_b::kSideALights.green, OUTPUT);
  pinMode(hw::node_b::kSideBLights.red, OUTPUT);
  pinMode(hw::node_b::kSideBLights.yellow, OUTPUT);
  pinMode(hw::node_b::kSideBLights.green, OUTPUT);

  setAllLightsOff();
  runLightSelfTest();

  Serial.println("Node B ready.");
  Serial.println("Standalone bench mode is enabled.");
  Serial.print("Node B far sensor trig/echo: ");
  Serial.print(hw::node_b::kFarSensor.trig);
  Serial.print("/");
  Serial.println(hw::node_b::kFarSensor.echo);
  Serial.print("Node B near sensor trig/echo: ");
  Serial.print(hw::node_b::kNearSensor.trig);
  Serial.print("/");
  Serial.println(hw::node_b::kNearSensor.echo);
  Serial.print("Node B emergency button GPIO: ");
  Serial.print(hw::node_b::kEmergencyButton);
  Serial.println(" (active LOW, button to GND)");
  Serial.print("Node B side-A LEDs R/Y/G: ");
  Serial.print(hw::node_b::kSideALights.red);
  Serial.print("/");
  Serial.print(hw::node_b::kSideALights.yellow);
  Serial.print("/");
  Serial.println(hw::node_b::kSideALights.green);
  Serial.print("Node B side-B LEDs R/Y/G: ");
  Serial.print(hw::node_b::kSideBLights.red);
  Serial.print("/");
  Serial.print(hw::node_b::kSideBLights.yellow);
  Serial.print("/");
  Serial.println(hw::node_b::kSideBLights.green);
  loRaBegin(true, Serial);
  loRaPrintConfig(Serial);
  ina219Begin(
      hw::heltec_v3::kIna219I2c.sda,
      hw::heltec_v3::kIna219I2c.scl,
      config::kIna219Address,
      Serial);
  printBenchHelp();
}

void loop() {
  const uint32_t nowMs = millis();
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
      if (logMode == LogMode::Verbose) {
        Serial.print("[LoRa RX] ");
        Serial.print(packet.payload);
        Serial.print(" | RSSI=");
        Serial.print(packet.rssi, 1);
        Serial.print(" dBm SNR=");
        Serial.println(packet.snr, 1);
      }
    }
  }

  processEmergencyButton(nowMs);
  processSerialInput(nowMs);

  if (nowMs - lastLoopMs < config::kLoopIntervalMs) {
    return;
  }
  lastLoopMs = nowMs;

  const SensorReading farReading = readFilteredUltrasonicSensor(
      hw::node_b::kFarSensor.trig,
      hw::node_b::kFarSensor.echo,
      farThresholdCm,
      farDebouncer,
      config::kUltrasonicMedianSamples,
      config::kOccupancyDebounceSamples);
  const SensorReading nearReading = readFilteredUltrasonicSensor(
      hw::node_b::kNearSensor.trig,
      hw::node_b::kNearSensor.echo,
      nearThresholdCm,
      nearDebouncer,
      config::kUltrasonicMedianSamples,
      config::kOccupancyDebounceSamples);

  const float farDistance = farReading.distanceCm;
  const float nearDistance = nearReading.distanceCm;
  const bool farOccupied = farReading.stableOccupied;
  const bool nearOccupied = nearReading.stableOccupied;
  farHealth.update(farDistance);
  nearHealth.update(nearDistance);

  SideTelemetry localTelemetry = laneEstimator.update(SideId::B, farOccupied, nearOccupied, nowMs);
  localTelemetry.emergencyRequested = localEmergencyRequested;
  localTelemetry.farDistanceCm = farDistance;
  localTelemetry.nearDistanceCm = nearDistance;
  const SideTelemetry remoteTelemetryNow = effectiveRemoteTelemetry(nowMs);
  const TrafficDecision decision = controller.update(remoteTelemetryNow, localTelemetry, nowMs);
  lastFarDistanceCm = farDistance;
  lastNearDistanceCm = nearDistance;
  lastFarOccupied = farOccupied;
  lastNearOccupied = nearOccupied;
  lastLocalTelemetry = localTelemetry;
  lastEffectiveRemoteTelemetry = remoteTelemetryNow;
  lastDecision = decision;
  lastPowerReading = ina219Read();
  hasSnapshot = true;

  applyLights(decision.lights);

  if (nowMs - lastStatusMs >= config::kTelemetryIntervalMs) {
    lastStatusMs = nowMs;

    if (logMode == LogMode::Summary) {
      Serial.print("B STATUS | A_queue=");
      Serial.print(remoteTelemetryNow.estimatedQueue);
      Serial.print(" | B_queue=");
      Serial.print(localTelemetry.estimatedQueue);
      Serial.print(" | A_far=");
      printDistanceState(Serial, remoteTelemetryNow.farDistanceCm, remoteTelemetryNow.farOccupied);
      Serial.print(" | A_near=");
      printDistanceState(Serial, remoteTelemetryNow.nearDistanceCm, remoteTelemetryNow.nearOccupied);
      Serial.print(" | B_far=");
      printDistanceState(Serial, farDistance, farOccupied);
      Serial.print(" | B_near=");
      printDistanceState(Serial, nearDistance, nearOccupied);
      Serial.print(" | far=");
      printDistanceState(Serial, farDistance, farOccupied);
      Serial.print(" | near=");
      printDistanceState(Serial, nearDistance, nearOccupied);
      Serial.print(" | thresholds=");
      Serial.print(farThresholdCm, 1);
      Serial.print("/");
      Serial.print(nearThresholdCm, 1);
      Serial.print(" | filter=");
      printSensorFilterValue(Serial);
      Serial.print(" | health=");
      printSensorHealthValue(Serial);
      Serial.print(" | localQ=");
      Serial.print(localTelemetry.estimatedQueue);
      Serial.print(" | remoteQ=");
      Serial.print(remoteTelemetryNow.estimatedQueue);
      Serial.print(" | source=");
      Serial.print(lastRemoteSource);
      Serial.print(" | stale=");
      Serial.print(onOffLabel(remoteTelemetryStale));
      Serial.print(" | backup=");
      Serial.print(backupModeLabel());
      Serial.print(" | backup_reason=");
      Serial.print(nodeABackupReason);
      Serial.print(" | recovery=");
      Serial.print(recoveryStateLabel());
      Serial.print(" | green=");
      Serial.print(sideName(decision.greenSide));
      Serial.print(" | phase=");
      Serial.print(decision.phase == SignalPhase::Green ? "GREEN" : "YELLOW");
      Serial.print(" | emergency=");
      Serial.print(onOffLabel(decision.emergencyOverride));
      Serial.print(" | emergency_target=");
      Serial.print(decisionEmergencyTargetLabel(decision));
      Serial.print(" | button_override=");
      Serial.print(requestedEmergencyTargetLabel());
      Serial.print(" | priority=");
      Serial.print(sideName(decision.prioritySide));
      Serial.print(" | lights=A:");
      Serial.print(lightStateLabel(decision.lights.aRed, decision.lights.aYellow, decision.lights.aGreen));
      Serial.print(" B:");
      Serial.print(lightStateLabel(decision.lights.bRed, decision.lights.bYellow, decision.lights.bGreen));
      Serial.print(" | power=");
      if (lastPowerReading.ok) {
        Serial.print(lastPowerReading.busVoltageV, 3);
        Serial.print("V/");
        Serial.print(lastPowerReading.currentMa, 1);
        Serial.print("mA/");
        Serial.print(lastPowerReading.powerMw, 1);
        Serial.println("mW");
      } else {
        Serial.println("INA219_NA");
      }
    } else if (logMode == LogMode::Verbose) {
      Serial.print("SENSE | far=");
      Serial.print(farDistance, 1);
      Serial.print("cm ");
      Serial.print(farOccupied ? "OCC" : "FREE");
      Serial.print(" | near=");
      Serial.print(nearDistance, 1);
      Serial.print("cm ");
      Serial.print(nearOccupied ? "OCC" : "FREE");
      Serial.print(" | localQueue=");
      Serial.print(localTelemetry.estimatedQueue);
      Serial.print(" | remoteQueue=");
      Serial.print(remoteTelemetryNow.estimatedQueue);
      Serial.print(" | remoteSource=");
      Serial.print(lastRemoteSource);
      Serial.print(" | stale=");
      Serial.println(onOffLabel(remoteTelemetryStale));
      Serial.print("BACKUP | backup=");
      Serial.print(backupModeLabel());
      Serial.print(" reason=");
      Serial.print(nodeABackupReason);
      Serial.print(" recovery=");
      Serial.println(recoveryStateLabel());

      Serial.print("CTRL | green=");
      Serial.print(sideName(decision.greenSide));
      Serial.print(" phase=");
      Serial.print(decision.phase == SignalPhase::Green ? "GREEN" : "YELLOW");
      Serial.print(" phaseMs=");
      Serial.print(decision.phaseElapsedMs);
      Serial.print(" currentDemand=");
      Serial.print(decision.currentDemand);
      Serial.print(" otherDemand=");
      Serial.print(decision.otherDemand);
      Serial.print(" emergency=");
      Serial.print(onOffLabel(decision.emergencyOverride));
      Serial.print(" emergencyTarget=");
      Serial.print(decisionEmergencyTargetLabel(decision));
      Serial.print(" buttonOverride=");
      Serial.print(requestedEmergencyTargetLabel());
      Serial.print(" priority=");
      Serial.print(sideName(decision.prioritySide));
      Serial.print(" | sideA=");
      Serial.print(lightStateLabel(decision.lights.aRed, decision.lights.aYellow, decision.lights.aGreen));
      Serial.print(" sideB=");
      Serial.print(lightStateLabel(decision.lights.bRed, decision.lights.bYellow, decision.lights.bGreen));
      Serial.print(" power=");
      printIna219Reading(Serial, lastPowerReading);
    }
  }
}
