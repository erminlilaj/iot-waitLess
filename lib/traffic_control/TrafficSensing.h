#pragma once

#include "TrafficTypes.h"

// Converts far/near sensor occupancy into simple vehicle counters.
// Far rising edge means a vehicle entered the measured lane; near falling
// edge means a vehicle left the stop-line area and is counted as passed.
class LaneEstimator {
 public:
  SideTelemetry update(SideId side, bool farOccupied, bool nearOccupied, uint32_t nowMs);

 private:
  bool farWasOccupied_ = false;
  bool nearWasOccupied_ = false;
  uint32_t incomingCount_ = 0;
  uint32_t passedCount_ = 0;
};
