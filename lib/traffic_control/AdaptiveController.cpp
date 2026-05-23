#include "AdaptiveController.h"

AdaptiveController::AdaptiveController(ControllerConfig config)
    : config_(config), greenSide_(SideId::A), pendingGreenSide_(SideId::A), phase_(SignalPhase::Green), phaseStartedMs_(0) {}

TrafficDecision AdaptiveController::update(const SideTelemetry& sideA, const SideTelemetry& sideB, uint32_t nowMs) {
  uint32_t phaseElapsedMs = nowMs - phaseStartedMs_;
  const SideTelemetry& emergencyPriority = selectEmergencyPriority(sideA, sideB);

  // If an emergency appears during yellow, finish yellow but target that side next.
  if (phase_ == SignalPhase::Yellow && hasEmergency(emergencyPriority)) {
    pendingGreenSide_ = emergencyPriority.side;
  }

  // Yellow is always completed before changing green, even for emergency priority.
  if (phase_ == SignalPhase::Yellow && phaseElapsedMs >= config_.yellowMs) {
    switchGreen(nowMs);
  }

  const SideTelemetry& current = greenSide_ == SideId::A ? sideA : sideB;
  const SideTelemetry& other = greenSide_ == SideId::A ? sideB : sideA;

  phaseElapsedMs = nowMs - phaseStartedMs_;

  if (phase_ == SignalPhase::Green) {
    if (hasEmergency(emergencyPriority)) {
      if (emergencyPriority.side != greenSide_) {
        beginYellow(emergencyPriority.side, nowMs);
      }
    } else {
      // Normal adaptive rule: switch only after minimum green and only when
      // the other side has meaningful demand or current side is empty.
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

  const SideTelemetry& updatedCurrent = greenSide_ == SideId::A ? sideA : sideB;
  const SideTelemetry& updatedOther = greenSide_ == SideId::A ? sideB : sideA;
  return buildDecision(updatedCurrent, updatedOther, nowMs);
}

const SideTelemetry& AdaptiveController::selectEmergencyPriority(
    const SideTelemetry& sideA,
    const SideTelemetry& sideB) const {
  if (hasEmergency(sideA) && hasEmergency(sideB)) {
    // If both sides request emergency priority, keep the current green side
    // to avoid unnecessary oscillation.
    return greenSide_ == SideId::A ? sideA : sideB;
  }

  if (hasEmergency(sideA)) {
    return sideA;
  }

  if (hasEmergency(sideB)) {
    return sideB;
  }

  return greenSide_ == SideId::A ? sideA : sideB;
}

TrafficDecision AdaptiveController::buildDecision(
    const SideTelemetry& current,
    const SideTelemetry& other,
    uint32_t nowMs) const {
  TrafficDecision decision;
  decision.greenSide = greenSide_;
  decision.phase = phase_;
  decision.switchScheduled = phase_ == SignalPhase::Yellow;
  decision.phaseElapsedMs = nowMs - phaseStartedMs_;
  decision.currentDemand = demandScore(current);
  decision.otherDemand = demandScore(other);
  decision.emergencyOverride = hasEmergency(current) || hasEmergency(other);
  decision.prioritySide = decision.emergencyOverride ? pendingGreenSide_ : greenSide_;
  decision.lights = makeLights(greenSide_, phase_);
  return decision;
}

void AdaptiveController::beginYellow(SideId nextGreenSide, uint32_t nowMs) {
  pendingGreenSide_ = nextGreenSide;
  phase_ = SignalPhase::Yellow;
  phaseStartedMs_ = nowMs;
}

void AdaptiveController::switchGreen(uint32_t nowMs) {
  greenSide_ = pendingGreenSide_;
  phase_ = SignalPhase::Green;
  phaseStartedMs_ = nowMs;
}
