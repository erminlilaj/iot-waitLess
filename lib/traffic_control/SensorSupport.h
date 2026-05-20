#pragma once

#include <Arduino.h>

struct SensorReading {
  float distanceCm = 999.0f;
  bool rawOccupied = false;
  bool stableOccupied = false;
};

struct SensorHealth {
  uint32_t totalSamples = 0;
  uint32_t invalidSamples = 0;
  uint16_t consecutiveInvalid = 0;
  bool lastValid = true;
};

class OccupancyDebouncer {
 public:
  bool update(bool rawOccupied, uint8_t requiredSamples);
  void reset(bool occupied = false);

 private:
  bool initialized_ = false;
  bool stableOccupied_ = false;
  bool candidateOccupied_ = false;
  uint8_t candidateCount_ = 0;
};

class SensorHealthTracker {
 public:
  void update(float distanceCm);
  void reset();
  const SensorHealth& snapshot() const;
  uint8_t invalidRatePercent() const;
  const char* status(uint16_t warnInvalidSamples, uint16_t failInvalidSamples) const;

 private:
  SensorHealth health_;
};

float readUltrasonicDistanceCm(uint8_t trigPin, uint8_t echoPin, unsigned long timeoutUs = 25000UL);
float readMedianUltrasonicDistanceCm(
    uint8_t trigPin,
    uint8_t echoPin,
    uint8_t sampleCount,
    unsigned long timeoutUs = 25000UL);
bool isDistanceOccupied(float distanceCm, float thresholdCm);
SensorReading readFilteredUltrasonicSensor(
    uint8_t trigPin,
    uint8_t echoPin,
    float thresholdCm,
    OccupancyDebouncer& debouncer,
    uint8_t medianSampleCount,
    uint8_t debounceSamples,
    unsigned long timeoutUs = 25000UL);
bool isUltrasonicDistanceValid(float distanceCm);
