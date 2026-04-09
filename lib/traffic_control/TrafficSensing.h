#pragma once

#include "TrafficTypes.h"

class LaneEstimator {
 public:
  SideTelemetry update(SideId side, bool farOccupied, bool nearOccupied, uint32_t nowMs);

 private:
  bool farWasOccupied_ = false;
  bool nearWasOccupied_ = false;
  uint32_t incomingCount_ = 0;
  uint32_t passedCount_ = 0;
};

