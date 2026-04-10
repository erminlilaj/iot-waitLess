#pragma once

#include <Arduino.h>

namespace config {

constexpr uint32_t kLoopIntervalMs = 200;
constexpr uint32_t kTelemetryIntervalMs = 1000;
constexpr uint32_t kRemoteTelemetryTimeoutMs = 3000;

constexpr float kFarThresholdCm = 100.0f;
constexpr float kNearThresholdCm = 100.0f;

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
