#pragma once

#include <Arduino.h>

#include "TrafficTypes.h"

String encodeTelemetry(const SideTelemetry& telemetry);
bool decodeTelemetry(const String& payload, SideTelemetry& telemetry);

