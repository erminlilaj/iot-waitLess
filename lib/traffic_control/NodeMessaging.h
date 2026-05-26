#pragma once

#include <Arduino.h>

#include "TrafficTypes.h"

// Compact LoRa payload used between Node A and Node B.
// Format: side,far,near,in,out,queue,emergency,timestamp,far_cm,near_cm
String encodeTelemetry(const SideTelemetry& telemetry);
bool decodeTelemetry(const String& payload, SideTelemetry& telemetry);

enum class HeartbeatMode : uint8_t {
  Idle = 0,
  Peak = 1,
};

struct NodeHeartbeat {
  SideId side = SideId::A;
  HeartbeatMode mode = HeartbeatMode::Idle;
  uint32_t timestampMs = 0;
};

// Lightweight LoRa payload used when full traffic telemetry is not needed.
// Format: H,side,mode,timestamp where mode is I=idle or P=peak-period.
String encodeHeartbeat(SideId side, HeartbeatMode mode, uint32_t timestampMs);
bool decodeHeartbeat(const String& payload, NodeHeartbeat& heartbeat);
const char* heartbeatModeName(HeartbeatMode mode);
