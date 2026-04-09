#pragma once

#include "TrafficTypes.h"

struct ControllerConfig {
  uint32_t minGreenMs = 5000;
  uint32_t maxGreenMs = 20000;
  uint32_t yellowMs = 2000;
  uint32_t advantageMargin = 4;
};

class AdaptiveController {
 public:
 explicit AdaptiveController(ControllerConfig config = {});

  TrafficDecision update(const SideTelemetry& sideA, const SideTelemetry& sideB, uint32_t nowMs);

 private:
  const SideTelemetry& selectEmergencyPriority(const SideTelemetry& sideA, const SideTelemetry& sideB) const;
  TrafficDecision buildDecision(const SideTelemetry& current, const SideTelemetry& other, uint32_t nowMs) const;
  void beginYellow(SideId nextGreenSide, uint32_t nowMs);
  void switchGreen(uint32_t nowMs);

  ControllerConfig config_;
  SideId greenSide_;
  SideId pendingGreenSide_;
  SignalPhase phase_;
  uint32_t phaseStartedMs_;
};
