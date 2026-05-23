#pragma once

#include <Arduino.h>

#include "TrafficTypes.h"

// Compact LoRa payload used between Node A and Node B.
// Format: side,far,near,in,out,queue,emergency,timestamp,far_cm,near_cm
String encodeTelemetry(const SideTelemetry& telemetry);
bool decodeTelemetry(const String& payload, SideTelemetry& telemetry);
