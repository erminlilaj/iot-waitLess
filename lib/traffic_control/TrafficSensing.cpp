#include "TrafficSensing.h"

SideTelemetry LaneEstimator::update(SideId side, bool farOccupied, bool nearOccupied, uint32_t nowMs) {
  // Count an approaching vehicle once, when the far sensor first becomes occupied.
  if (farOccupied && !farWasOccupied_) {
    ++incomingCount_;
  }

  // Count a vehicle as passed when it leaves the near/stop-line sensor.
  if (!nearOccupied && nearWasOccupied_ && passedCount_ < incomingCount_) {
    ++passedCount_;
  }

  farWasOccupied_ = farOccupied;
  nearWasOccupied_ = nearOccupied;

  uint32_t estimatedQueue = incomingCount_ >= passedCount_ ? incomingCount_ - passedCount_ : 0U;

  // If a car is sitting on the near sensor but counters are still zero,
  // report at least one queued vehicle so the controller can react.
  if (nearOccupied && estimatedQueue == 0U) {
    estimatedQueue = 1U;
  }

  SideTelemetry telemetry;
  telemetry.side = side;
  telemetry.farOccupied = farOccupied;
  telemetry.nearOccupied = nearOccupied;
  telemetry.incomingCount = incomingCount_;
  telemetry.passedCount = passedCount_;
  telemetry.estimatedQueue = estimatedQueue;
  telemetry.timestampMs = nowMs;
  return telemetry;
}
