#include "TrafficSensing.h"

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

