#include "NodeMessaging.h"

#include <stdio.h>

String encodeTelemetry(const SideTelemetry& telemetry) {
  return String(sideName(telemetry.side)) + "," + String(telemetry.farOccupied ? 1 : 0) + "," +
         String(telemetry.nearOccupied ? 1 : 0) + "," + String(telemetry.incomingCount) + "," +
         String(telemetry.passedCount) + "," + String(telemetry.estimatedQueue) + "," +
         String(telemetry.emergencyRequested ? 1 : 0) + "," + String(telemetry.timestampMs);
}

bool decodeTelemetry(const String& payload, SideTelemetry& telemetry) {
  char sideToken = 'A';
  int farOccupied = 0;
  int nearOccupied = 0;
  int emergencyRequested = 0;
  unsigned long incomingCount = 0;
  unsigned long passedCount = 0;
  unsigned long estimatedQueue = 0;
  unsigned long timestampMs = 0;

  int matched = sscanf(
      payload.c_str(),
      "%c,%d,%d,%lu,%lu,%lu,%d,%lu",
      &sideToken,
      &farOccupied,
      &nearOccupied,
      &incomingCount,
      &passedCount,
      &estimatedQueue,
      &emergencyRequested,
      &timestampMs);

  if (matched != 8) {
    matched = sscanf(
        payload.c_str(),
        "%c,%d,%d,%lu,%lu,%lu,%lu",
        &sideToken,
        &farOccupied,
        &nearOccupied,
        &incomingCount,
        &passedCount,
        &estimatedQueue,
        &timestampMs);
    emergencyRequested = 0;
  }

  if (matched != 8 && matched != 7) {
    return false;
  }

  telemetry.side = sideToken == 'B' ? SideId::B : SideId::A;
  telemetry.farOccupied = farOccupied != 0;
  telemetry.nearOccupied = nearOccupied != 0;
  telemetry.emergencyRequested = emergencyRequested != 0;
  telemetry.incomingCount = static_cast<uint32_t>(incomingCount);
  telemetry.passedCount = static_cast<uint32_t>(passedCount);
  telemetry.estimatedQueue = static_cast<uint32_t>(estimatedQueue);
  telemetry.timestampMs = static_cast<uint32_t>(timestampMs);
  return true;
}
