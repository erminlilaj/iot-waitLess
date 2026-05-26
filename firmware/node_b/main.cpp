#include <Arduino.h>
#include <stdio.h>

// Node B is the controller node. It reads side-B sensors, receives side-A LoRa
// telemetry from Node A, drives both traffic-light heads, and prints the live
// evidence log used in the demo.

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

// Emergency and backup state is separated from raw LoRa telemetry so Node B can
// override behavior safely without modifying the last received packet.
bool localEmergencyRequested = false;
bool remoteEmergencyRequested = false;
bool remoteTelemetryInjected = false;
bool manualPeakTrafficMode = false;
bool autoPeakTrafficMode = false;
bool remotePeakHeartbeatActive = false;
LogMode logMode = LogMode::Summary;
float farThresholdCm = config::kFarThresholdCm;
float nearThresholdCm = config::kNearThresholdCm;
int8_t demoHour = -1;
uint32_t lastLoopMs = 0;
uint32_t lastStatusMs = 0;
uint32_t lastRemoteRxMs = 0;
uint32_t lastRemotePeakHeartbeatMs = 0;
uint32_t lastRemoteTimeoutMs = config::kRemoteTelemetryTimeoutMs;
bool hasSnapshot = false;
float lastFarDistanceCm = 999.0f;
float lastNearDistanceCm = 999.0f;
bool lastFarOccupied = false;
bool lastNearOccupied = false;
SideTelemetry lastLocalTelemetry;
SideTelemetry lastEffectiveRemoteTelemetry;
TrafficDecision lastDecision;
String lastRemoteSource = "IDLE";
String lastRemotePacketKind = "NONE";
float lastRssiDbm = 0.0f;
float lastSnrDb = 0.0f;
bool lastRxWasRadio = false;
bool lastRemotePacketWasHeartbeat = false;
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

bool hourInPeakWindow(int8_t hour) {
  return (hour >= config::kMorningPeakStartHour && hour < config::kMorningPeakEndHour) ||
         (hour >= config::kEveningPeakStartHour && hour < config::kEveningPeakEndHour);
}

bool remotePeakHeartbeatFresh(uint32_t nowMs) {
  return remotePeakHeartbeatActive &&
         lastRemotePeakHeartbeatMs > 0 &&
         (nowMs - lastRemotePeakHeartbeatMs) <= config::kRemoteHeartbeatTimeoutMs;
}

bool peakTrafficModeActive(uint32_t nowMs) {
  return manualPeakTrafficMode ||
         (autoPeakTrafficMode && demoHour >= 0 && hourInPeakWindow(demoHour)) ||
         remotePeakHeartbeatFresh(nowMs);
}

const char* controllerEnergyModeLabel(uint32_t nowMs) {
  return peakTrafficModeActive(nowMs) ? "PEAK_LOW_COMMUNICATION" : "ADAPTIVE_TELEMETRY";
}

void ensurePeakDemand(SideTelemetry& telemetry, SideId side, uint32_t nowMs) {
  telemetry.side = side;
  if (telemetry.estimatedQueue == 0) {
    telemetry.estimatedQueue = 1;
  }
  telemetry.timestampMs = nowMs;
}

void setNodeABackupActive(bool active, const char* reason) {
  // Backup/recovery events are printed only when the mode changes. This keeps
  // the live log readable while still making failures visible.
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
  // Conservative fallback: do not assume Side A is empty when Node A is stale.
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
    lastRemoteTimeoutMs = config::kRemoteTelemetryTimeoutMs;
    lastRemoteSource = "BACKUP_NO_LORA";
    return applyRemoteEmergencyOverride(makeNodeABackupTelemetry(nowMs));
  }

  const bool lowCommunicationExpected = lastRemotePacketWasHeartbeat || !hasDemand(remoteTelemetry);
  lastRemoteTimeoutMs = lowCommunicationExpected ? config::kRemoteHeartbeatTimeoutMs : config::kRemoteTelemetryTimeoutMs;

  if (lastRemoteRxMs == 0 || (nowMs - lastRemoteRxMs) > lastRemoteTimeoutMs) {
    setNodeABackupActive(true, "NODE_A_STALE");
    remoteTelemetryStale = true;
    remotePeakHeartbeatActive = false;
    lastRemoteSource = "LORA_STALE";
    return applyRemoteEmergencyOverride(makeNodeABackupTelemetry(nowMs));
  }

  setNodeABackupActive(false, "LORA_RADIO");
  remoteTelemetryStale = false;
  if (!lastRemotePacketWasHeartbeat) {
    lastRemoteSource = "LORA_RADIO";
  }
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
  Serial.println("  energy");
  Serial.println("  peak_on");
  Serial.println("  peak_off");
  Serial.println("  peak_auto_on");
  Serial.println("  peak_auto_off");
  Serial.println("  set_demo_hour <0-23>");
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

void printEnergyStatus(Stream& out) {
  printSectionHeader(out, "ENERGY COMMUNICATION");
  out.print("manual_peak_mode: ");
  out.println(onOffLabel(manualPeakTrafficMode));
  out.print("auto_peak_mode: ");
  out.println(onOffLabel(autoPeakTrafficMode));
  out.print("remote_peak_heartbeat: ");
  out.println(onOffLabel(remotePeakHeartbeatActive));
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
  out.print("controller_energy_mode: ");
  out.println(controllerEnergyModeLabel(millis()));
  out.print("last_remote_packet: ");
  out.println(lastRemotePacketKind);
  out.print("remote_timeout_ms: ");
  out.println(lastRemoteTimeoutMs);
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
  // The button is active LOW with INPUT_PULLUP. Debounce and click-window logic
  // turns one physical input into B emergency, A emergency, or clear.
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
  out.print("controller_energy_mode: ");
  out.println(controllerEnergyModeLabel(millis()));
  out.print("last_remote_packet: ");
  out.println(lastRemotePacketKind);
  out.print("remote_timeout_ms: ");
  out.println(lastRemoteTimeoutMs);
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
  out.print("controller_energy_mode: ");
  out.println(controllerEnergyModeLabel(millis()));
  out.print("last_remote_packet: ");
  out.println(lastRemotePacketKind);
  out.print("remote_timeout_ms: ");
  out.println(lastRemoteTimeoutMs);
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

  if (command.equalsIgnoreCase("energy")) {
    printEnergyStatus(Serial);
    return false;
  }

  if (command.equalsIgnoreCase("peak_on")) {
    manualPeakTrafficMode = true;
    Serial.println("Node B peak low-communication controller mode enabled.");
    return true;
  }

  if (command.equalsIgnoreCase("peak_off")) {
    manualPeakTrafficMode = false;
    Serial.println("Node B peak low-communication controller mode disabled.");
    return true;
  }

  if (command.equalsIgnoreCase("peak_auto_on")) {
    autoPeakTrafficMode = true;
    Serial.println("Node B automatic peak window mode enabled. Use set_demo_hour <0-23> for demo time.");
    return true;
  }

  if (command.equalsIgnoreCase("peak_auto_off")) {
    autoPeakTrafficMode = false;
    Serial.println("Node B automatic peak window mode disabled.");
    return true;
  }

  int hour = -1;
  if (sscanf(command.c_str(), "set_demo_hour %d", &hour) == 1) {
    if (hour < 0 || hour > 23) {
      Serial.println("Demo hour must be between 0 and 23.");
      return true;
    }
    demoHour = static_cast<int8_t>(hour);
    Serial.print("Node B demo hour set to ");
    Serial.print(demoHour);
    Serial.print(" | in_peak_window=");
    Serial.println(onOffLabel(hourInPeakWindow(demoHour)));
    return true;
  }

  if (command.equalsIgnoreCase("remote_clear")) {
    remoteTelemetry = makeRemoteTelemetry(false, false, false, 0, nowMs);
    remoteTelemetryInjected = false;
    lastRemoteRxMs = 0;
    remoteTelemetryStale = false;
    lastRxWasRadio = false;
    lastRemotePacketWasHeartbeat = false;
    remotePeakHeartbeatActive = false;
    lastRemotePacketKind = "NONE";
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
    lastRemotePacketWasHeartbeat = false;
    remotePeakHeartbeatActive = false;
    lastRemotePacketKind = "SERIAL_TELEMETRY";
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
    lastRemotePacketWasHeartbeat = false;
    remotePeakHeartbeatActive = false;
    lastRemotePacketKind = "SERIAL_TELEMETRY";
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
    lastRemotePacketWasHeartbeat = false;
    remotePeakHeartbeatActive = false;
    lastRemotePacketKind = "SERIAL_TELEMETRY";
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

  // Node B owns all actuator pins in the current prototype.
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
  // Radio reception runs before sensing so the controller uses the freshest
  // available Node A telemetry in this loop iteration.
  if (loRaTryReceive(packet, Serial)) {
    NodeHeartbeat heartbeat;
    SideTelemetry receivedTelemetry;
    if (decodeHeartbeat(packet.payload, heartbeat) && heartbeat.side == SideId::A) {
      remoteTelemetryInjected = false;
      lastRemoteRxMs = nowMs;
      lastRssiDbm = packet.rssi;
      lastSnrDb = packet.snr;
      lastRxWasRadio = true;
      lastRemotePacketWasHeartbeat = true;
      remoteTelemetryStale = false;

      if (heartbeat.mode == HeartbeatMode::Peak) {
        remoteTelemetry = makeRemoteTelemetry(false, false, false, 1, nowMs);
        remotePeakHeartbeatActive = true;
        lastRemotePeakHeartbeatMs = nowMs;
        lastRemotePacketKind = "HEARTBEAT_PEAK";
        lastRemoteSource = "LORA_HEARTBEAT_PEAK";
      } else {
        remoteTelemetry = makeRemoteTelemetry(false, false, false, 0, nowMs);
        remotePeakHeartbeatActive = false;
        lastRemotePacketKind = "HEARTBEAT_IDLE";
        lastRemoteSource = "LORA_HEARTBEAT_IDLE";
      }

      if (logMode == LogMode::Verbose) {
        Serial.print("[LoRa HB] ");
        Serial.print(packet.payload);
        Serial.print(" | mode=");
        Serial.print(heartbeatModeName(heartbeat.mode));
        Serial.print(" | RSSI=");
        Serial.print(packet.rssi, 1);
        Serial.print(" dBm SNR=");
        Serial.println(packet.snr, 1);
      }
    } else if (parseTelemetryLine(packet.payload, receivedTelemetry) && receivedTelemetry.side == SideId::A) {
      remoteTelemetry = receivedTelemetry;
      remoteTelemetryInjected = false;
      lastRemoteRxMs = nowMs;
      lastRemoteSource = "LORA_RADIO";
      lastRemotePacketKind = "TELEMETRY";
      lastRssiDbm = packet.rssi;
      lastSnrDb = packet.snr;
      lastRxWasRadio = true;
      lastRemotePacketWasHeartbeat = false;
      remotePeakHeartbeatActive = false;
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
  SideTelemetry controllerRemoteTelemetry = remoteTelemetryNow;
  SideTelemetry controllerLocalTelemetry = localTelemetry;
  if (peakTrafficModeActive(nowMs)) {
    ensurePeakDemand(controllerRemoteTelemetry, SideId::A, nowMs);
    ensurePeakDemand(controllerLocalTelemetry, SideId::B, nowMs);
  }
  // One controller update combines real side-B sensing, remote side-A data,
  // emergency requests, and backup mode into final traffic-light outputs.
  const TrafficDecision decision = controller.update(controllerRemoteTelemetry, controllerLocalTelemetry, nowMs);
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
      // This is the main demo evidence line parsed by tools/road_data_logger.py.
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
      Serial.print(" | remote_packet=");
      Serial.print(lastRemotePacketKind);
      Serial.print(" | stale=");
      Serial.print(onOffLabel(remoteTelemetryStale));
      Serial.print(" | timeout_ms=");
      Serial.print(lastRemoteTimeoutMs);
      Serial.print(" | backup=");
      Serial.print(backupModeLabel());
      Serial.print(" | backup_reason=");
      Serial.print(nodeABackupReason);
      Serial.print(" | recovery=");
      Serial.print(recoveryStateLabel());
      Serial.print(" | energy_mode=");
      Serial.print(controllerEnergyModeLabel(nowMs));
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
      Serial.print(" packet=");
      Serial.print(lastRemotePacketKind);
      Serial.print(" energyMode=");
      Serial.print(controllerEnergyModeLabel(nowMs));
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
