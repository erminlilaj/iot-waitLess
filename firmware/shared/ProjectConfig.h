#pragma once

#include <Arduino.h>

namespace config {

// Timing values are shared by both nodes so sensing, telemetry, and stale-data
// detection remain consistent across the prototype.
constexpr uint32_t kLoopIntervalMs = 200;
constexpr uint32_t kTelemetryIntervalMs = 1000;
constexpr uint32_t kHeartbeatIntervalMs = 10000;
constexpr uint32_t kIdleHeartbeatEntryNoDemandMs = 180000;
constexpr uint32_t kIdleSleepNoDemandConfirmMs = 10000;
constexpr uint32_t kIdleSleepMs = 5000;
constexpr uint32_t kPeakHeartbeatIntervalMs = 15000;
constexpr uint32_t kPeakSleepMs = 15000;
constexpr uint32_t kPeakSleepCommandGraceMs = 5000;
constexpr uint32_t kRemoteTelemetryTimeoutMs = 3000;
constexpr uint32_t kRemoteHeartbeatTimeoutMs = 25000;

// Peak windows come from the road observations. The prototype can enable them
// manually during the demo; a deployed version would drive the same constants
// from RTC or NTP time.
constexpr uint8_t kMorningPeakStartHour = 9;
constexpr uint8_t kMorningPeakEndHour = 11;
constexpr uint8_t kEveningPeakStartHour = 16;
constexpr uint8_t kEveningPeakEndHour = 19;

// Live-demo thresholds. The validated road CSV was collected with 100/100 cm;
// the 50/50 cm default makes classroom triggering more controlled.
constexpr float kFarThresholdCm = 50.0f;
constexpr float kNearThresholdCm = 50.0f;
constexpr uint8_t kUltrasonicMedianSamples = 3;
constexpr uint8_t kOccupancyDebounceSamples = 2;
constexpr uint16_t kSensorHealthWarnInvalidSamples = 5;
constexpr uint16_t kSensorHealthFailInvalidSamples = 15;

// INA219 calibration assumes the common 0.1 ohm breakout shunt.
constexpr uint8_t kIna219Address = 0x40;
constexpr float kIna219ShuntOhms = 0.1f;

// Adaptive controller timings.
constexpr uint32_t kMinGreenMs = 5000;
constexpr uint32_t kMaxGreenMs = 20000;
constexpr uint32_t kYellowMs = 2000;
constexpr uint32_t kAdvantageMargin = 4;

// Adjust this to match the regional SKU of the board before flashing.
constexpr float kLoRaFrequencyMHz = 868.0f;
constexpr float kLoRaBandwidthKHz = 125.0f;
constexpr uint8_t kLoRaSpreadingFactor = 7;
constexpr uint8_t kLoRaCodingRate = 5;
constexpr uint8_t kLoRaSyncWord = 0x12;
constexpr int8_t kLoRaOutputPowerDbm = 14;
constexpr uint16_t kLoRaPreambleLength = 8;

}  // namespace config
