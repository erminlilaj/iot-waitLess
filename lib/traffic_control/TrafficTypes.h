#pragma once

#include <Arduino.h>

enum class SideId : uint8_t {
  A = 0,
  B = 1,
};

enum class SignalPhase : uint8_t {
  Green = 0,
  Yellow = 1,
};

struct LightOutput {
  bool aRed = false;
  bool aYellow = false;
  bool aGreen = false;
  bool bRed = false;
  bool bYellow = false;
  bool bGreen = false;
};

struct SideTelemetry {
  SideId side = SideId::A;
  bool farOccupied = false;
  bool nearOccupied = false;
  bool emergencyRequested = false;
  uint32_t incomingCount = 0;
  uint32_t passedCount = 0;
  uint32_t estimatedQueue = 0;
  uint32_t timestampMs = 0;
  float farDistanceCm = 999.0f;
  float nearDistanceCm = 999.0f;
};

struct TrafficDecision {
  SideId greenSide = SideId::A;
  SignalPhase phase = SignalPhase::Green;
  bool switchScheduled = false;
  uint32_t phaseElapsedMs = 0;
  uint32_t currentDemand = 0;
  uint32_t otherDemand = 0;
  bool emergencyOverride = false;
  SideId prioritySide = SideId::A;
  LightOutput lights;
};

inline SideId otherSide(SideId side) {
  return side == SideId::A ? SideId::B : SideId::A;
}

inline const char* sideName(SideId side) {
  return side == SideId::A ? "A" : "B";
}

inline uint32_t demandScore(const SideTelemetry& telemetry) {
  const uint32_t queueWeight = telemetry.estimatedQueue * 3U;
  const uint32_t incomingWeight = telemetry.farOccupied ? 2U : 0U;
  const uint32_t stopLineWeight = telemetry.nearOccupied ? 4U : 0U;
  return queueWeight + incomingWeight + stopLineWeight;
}

inline bool hasDemand(const SideTelemetry& telemetry) {
  return telemetry.estimatedQueue > 0U || telemetry.farOccupied || telemetry.nearOccupied;
}

inline bool hasEmergency(const SideTelemetry& telemetry) {
  return telemetry.emergencyRequested;
}

inline LightOutput makeLights(SideId greenSide, SignalPhase phase) {
  LightOutput output;

  if (greenSide == SideId::A) {
    output.aGreen = phase == SignalPhase::Green;
    output.aYellow = phase == SignalPhase::Yellow;
    output.bRed = true;
    return output;
  }

  output.bGreen = phase == SignalPhase::Green;
  output.bYellow = phase == SignalPhase::Yellow;
  output.aRed = true;
  return output;
}
