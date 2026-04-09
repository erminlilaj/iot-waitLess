#include <Arduino.h>
#include <stdio.h>

#include "DebugSupport.h"
#include "LoRaTransport.h"
#include "NodeMessaging.h"
#include "SensorSupport.h"
#include "shared/HardwareMap.h"
#include "TrafficSensing.h"
#include "shared/ProjectConfig.h"

namespace {

LaneEstimator laneEstimator;
bool emulationEnabled = false;
bool emulatedFarOccupied = false;
bool emulatedNearOccupied = false;
bool manualEmergencyRequested = false;
LogMode logMode = LogMode::Summary;
uint32_t lastLoopMs = 0;
uint32_t lastTelemetryMs = 0;
bool lastTxUsedRadio = false;
bool hasSnapshot = false;
float lastFarDistanceCm = 999.0f;
float lastNearDistanceCm = 999.0f;
bool lastFarOccupied = false;
bool lastNearOccupied = false;
SideTelemetry lastTelemetry;
String lastPayload;

void sendTelemetryOverLoRa(const String& payload) {
  lastPayload = payload;
  lastTxUsedRadio = loRaSendText(payload, Serial);
}

void printBenchHelp() {
  Serial.println("Node A commands:");
  Serial.println("  help");
  Serial.println("  emu_on");
  Serial.println("  emu_off");
  Serial.println("  reset_counts");
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
  out.print("tx_backend: ");
  out.println(txBackendLabel());
  out.print("last_payload: ");
  out.println(lastPayload);
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
  out.print("tx_backend: ");
  out.println(txBackendLabel());
  out.print("payload: ");
  out.println(lastPayload);
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

  if (command.equalsIgnoreCase("emu_on")) {
    emulationEnabled = true;
    Serial.println("Node A switched to emulation mode.");
    return true;
  }

  if (command.equalsIgnoreCase("emu_off")) {
    emulationEnabled = false;
    emulatedFarOccupied = false;
    emulatedNearOccupied = false;
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
  printBenchHelp();
}

void loop() {
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
    farOccupied = emulatedFarOccupied;
    nearOccupied = emulatedNearOccupied;
  } else {
    farDistance = readUltrasonicDistanceCm(hw::node_a::kFarSensor.trig, hw::node_a::kFarSensor.echo);
    nearDistance = readUltrasonicDistanceCm(hw::node_a::kNearSensor.trig, hw::node_a::kNearSensor.echo);
    farOccupied = isDistanceOccupied(farDistance, config::kFarThresholdCm);
    nearOccupied = isDistanceOccupied(nearDistance, config::kNearThresholdCm);
  }

  SideTelemetry telemetry = laneEstimator.update(SideId::A, farOccupied, nearOccupied, nowMs);
  telemetry.emergencyRequested = manualEmergencyRequested;
  lastFarDistanceCm = farDistance;
  lastNearDistanceCm = nearDistance;
  lastFarOccupied = farOccupied;
  lastNearOccupied = nearOccupied;
  lastTelemetry = telemetry;
  hasSnapshot = true;

  if (nowMs - lastTelemetryMs >= config::kTelemetryIntervalMs) {
    lastTelemetryMs = nowMs;

    const String payload = encodeTelemetry(telemetry);
    sendTelemetryOverLoRa(payload);

    if (logMode == LogMode::Summary) {
      Serial.print("A STATUS | source=");
      Serial.print(sourceLabel());
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
      Serial.print(" | tx=");
      Serial.print(txBackendLabel());
      Serial.print(" | payload=");
      Serial.println(lastPayload);
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
      Serial.println(onOffLabel(telemetry.emergencyRequested));

      Serial.print("A TX | backend=");
      Serial.print(txBackendLabel());
      Serial.print(" | payload=");
      Serial.println(lastPayload);
    }
  }
}
