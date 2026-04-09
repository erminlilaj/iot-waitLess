#include <Arduino.h>
#include <stdio.h>

#include "AdaptiveController.h"
#include "DebugSupport.h"
#include "LoRaTransport.h"
#include "NodeMessaging.h"
#include "SensorSupport.h"
#include "shared/HardwareMap.h"
#include "TrafficSensing.h"
#include "shared/ProjectConfig.h"

namespace {

constexpr uint16_t kLightSelfTestOnMs = 350;
constexpr uint16_t kLightSelfTestOffMs = 120;

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
bool remoteTelemetryInjected = false;
LogMode logMode = LogMode::Summary;
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

const char* lightStateLabel(bool red, bool yellow, bool green);

SideTelemetry makeRemoteTelemetry(
    bool farOccupied,
    bool nearOccupied,
    bool emergencyRequested,
    uint32_t estimatedQueue,
    uint32_t nowMs);

SideTelemetry effectiveRemoteTelemetry(uint32_t nowMs) {
  if (remoteTelemetryInjected) {
    remoteTelemetryStale = false;
    lastRemoteSource = "SERIAL_EMU";
    return remoteTelemetry;
  }

  if (!loRaIsActive()) {
    remoteTelemetryStale = false;
    lastRemoteSource = "IDLE";
    return remoteTelemetry;
  }

  if (lastRemoteRxMs == 0 || (nowMs - lastRemoteRxMs) > config::kRemoteTelemetryTimeoutMs) {
    remoteTelemetryStale = true;
    lastRemoteSource = "LORA_STALE";
    return makeRemoteTelemetry(false, false, false, 0, nowMs);
  }

  remoteTelemetryStale = false;
  lastRemoteSource = "LORA_RADIO";
  return remoteTelemetry;
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
  Serial.println("  remote_ambulance_on");
  Serial.println("  remote_ambulance_off");
  Serial.println("  local_ambulance_on");
  Serial.println("  local_ambulance_off");
  Serial.println("  A,1,0,4,2,2,0,12345   (raw telemetry payload)");
  printLogModeCommands(Serial);
}

void printStatusSnapshot(Stream& out) {
  printSectionHeader(out, "NODE B STATUS");

  if (!hasSnapshot) {
    out.println("No controller snapshot yet. Wait one loop interval, then run status again.");
    return;
  }

  out.print("log_mode: ");
  out.println(logModeName(logMode));
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
  out.print("remote_source: ");
  out.println(lastRemoteSource);
  out.print("remote_stale: ");
  out.println(onOffLabel(remoteTelemetryStale));
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
}

void printReport(Stream& out) {
  printSectionHeader(out, "REPORT NODE_B");

  if (!hasSnapshot) {
    out.println("status: NO_DATA_YET");
    return;
  }

  out.print("log_mode: ");
  out.println(logModeName(logMode));
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
  out.print("remote_source: ");
  out.println(lastRemoteSource);
  out.print("remote_stale: ");
  out.println(onOffLabel(remoteTelemetryStale));
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
    remoteTelemetry.emergencyRequested = true;
    remoteTelemetry.timestampMs = nowMs;
    remoteTelemetryInjected = true;
    lastRemoteRxMs = 0;
    remoteTelemetryStale = false;
    lastRxWasRadio = false;
    lastRemoteSource = "SERIAL_EMU";
    Serial.println("Remote ambulance override enabled.");
    return true;
  }

  if (command.equalsIgnoreCase("remote_ambulance_off")) {
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

  processSerialInput(nowMs);

  if (nowMs - lastLoopMs < config::kLoopIntervalMs) {
    return;
  }
  lastLoopMs = nowMs;

  const float farDistance = readUltrasonicDistanceCm(hw::node_b::kFarSensor.trig, hw::node_b::kFarSensor.echo);
  const float nearDistance = readUltrasonicDistanceCm(hw::node_b::kNearSensor.trig, hw::node_b::kNearSensor.echo);

  const bool farOccupied = isDistanceOccupied(farDistance, config::kFarThresholdCm);
  const bool nearOccupied = isDistanceOccupied(nearDistance, config::kNearThresholdCm);

  SideTelemetry localTelemetry = laneEstimator.update(SideId::B, farOccupied, nearOccupied, nowMs);
  localTelemetry.emergencyRequested = localEmergencyRequested;
  const SideTelemetry remoteTelemetryNow = effectiveRemoteTelemetry(nowMs);
  const TrafficDecision decision = controller.update(remoteTelemetryNow, localTelemetry, nowMs);
  lastFarDistanceCm = farDistance;
  lastNearDistanceCm = nearDistance;
  lastFarOccupied = farOccupied;
  lastNearOccupied = nearOccupied;
  lastLocalTelemetry = localTelemetry;
  lastEffectiveRemoteTelemetry = remoteTelemetryNow;
  lastDecision = decision;
  hasSnapshot = true;

  applyLights(decision.lights);

  if (nowMs - lastStatusMs >= config::kTelemetryIntervalMs) {
    lastStatusMs = nowMs;

    if (logMode == LogMode::Summary) {
      Serial.print("B STATUS | far=");
      Serial.print(farDistance, 1);
      Serial.print("cm/");
      Serial.print(farOccupied ? "OCC" : "FREE");
      Serial.print(" | near=");
      Serial.print(nearDistance, 1);
      Serial.print("cm/");
      Serial.print(nearOccupied ? "OCC" : "FREE");
      Serial.print(" | localQ=");
      Serial.print(localTelemetry.estimatedQueue);
      Serial.print(" | remoteQ=");
      Serial.print(remoteTelemetryNow.estimatedQueue);
      Serial.print(" | source=");
      Serial.print(lastRemoteSource);
      Serial.print(" | stale=");
      Serial.print(onOffLabel(remoteTelemetryStale));
      Serial.print(" | green=");
      Serial.print(sideName(decision.greenSide));
      Serial.print(" | phase=");
      Serial.print(decision.phase == SignalPhase::Green ? "GREEN" : "YELLOW");
      Serial.print(" | emergency=");
      Serial.print(onOffLabel(decision.emergencyOverride));
      Serial.print(" | priority=");
      Serial.print(sideName(decision.prioritySide));
      Serial.print(" | lights=A:");
      Serial.print(lightStateLabel(decision.lights.aRed, decision.lights.aYellow, decision.lights.aGreen));
      Serial.print(" B:");
      Serial.println(lightStateLabel(decision.lights.bRed, decision.lights.bYellow, decision.lights.bGreen));
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
      Serial.print(" priority=");
      Serial.print(sideName(decision.prioritySide));
      Serial.print(" | sideA=");
      Serial.print(lightStateLabel(decision.lights.aRed, decision.lights.aYellow, decision.lights.aGreen));
      Serial.print(" sideB=");
      Serial.println(lightStateLabel(decision.lights.bRed, decision.lights.bYellow, decision.lights.bGreen));
    }
  }
}
