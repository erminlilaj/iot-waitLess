#include "SensorSupport.h"

namespace {

// The median filter uses a tiny fixed array because the ESP32 loop runs often
// and we only need a few samples to reject one-off ultrasonic spikes.
void swapFloat(float& left, float& right) {
  const float temp = left;
  left = right;
  right = temp;
}

void sortSmall(float* values, uint8_t count) {
  for (uint8_t i = 1; i < count; ++i) {
    uint8_t j = i;
    while (j > 0 && values[j] < values[j - 1]) {
      swapFloat(values[j], values[j - 1]);
      --j;
    }
  }
}

}  // namespace

float readUltrasonicDistanceCm(uint8_t trigPin, uint8_t echoPin, unsigned long timeoutUs) {
  // HC-SR04 trigger pulse: hold low, send a 10 us high pulse, then measure echo.
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  const unsigned long durationUs = pulseIn(echoPin, HIGH, timeoutUs);
  if (durationUs == 0) {
    // 999 cm is a sentinel for timeout/no echo; it is treated as FREE and invalid.
    return 999.0f;
  }

  // Speed of sound is about 0.0343 cm/us; divide by two for round trip.
  return static_cast<float>(durationUs) * 0.0343f / 2.0f;
}

float readMedianUltrasonicDistanceCm(
    uint8_t trigPin,
    uint8_t echoPin,
    uint8_t sampleCount,
    unsigned long timeoutUs) {
  if (sampleCount <= 1) {
    return readUltrasonicDistanceCm(trigPin, echoPin, timeoutUs);
  }

  if (sampleCount > 5) {
    sampleCount = 5;
  }

  float samples[5] = {};
  for (uint8_t i = 0; i < sampleCount; ++i) {
    samples[i] = readUltrasonicDistanceCm(trigPin, echoPin, timeoutUs);
    if (i + 1 < sampleCount) {
      delay(5);
    }
  }

  sortSmall(samples, sampleCount);
  return samples[sampleCount / 2];
}

bool isDistanceOccupied(float distanceCm, float thresholdCm) {
  return distanceCm > 0.0f && distanceCm < thresholdCm;
}

bool isUltrasonicDistanceValid(float distanceCm) {
  return distanceCm > 0.0f && distanceCm < 900.0f;
}

bool OccupancyDebouncer::update(bool rawOccupied, uint8_t requiredSamples) {
  if (requiredSamples <= 1) {
    initialized_ = true;
    stableOccupied_ = rawOccupied;
    candidateOccupied_ = rawOccupied;
    candidateCount_ = 0;
    return stableOccupied_;
  }

  if (!initialized_) {
    initialized_ = true;
    stableOccupied_ = rawOccupied;
    candidateOccupied_ = rawOccupied;
    candidateCount_ = 0;
    return stableOccupied_;
  }

  if (rawOccupied == stableOccupied_) {
    candidateOccupied_ = rawOccupied;
    candidateCount_ = 0;
    return stableOccupied_;
  }

  if (rawOccupied != candidateOccupied_) {
    candidateOccupied_ = rawOccupied;
    candidateCount_ = 1;
  } else if (candidateCount_ < requiredSamples) {
    ++candidateCount_;
  }

  // Only commit the new state after enough consecutive matching samples.
  if (candidateCount_ >= requiredSamples) {
    stableOccupied_ = rawOccupied;
    candidateCount_ = 0;
  }

  return stableOccupied_;
}

void OccupancyDebouncer::reset(bool occupied) {
  initialized_ = false;
  stableOccupied_ = occupied;
  candidateOccupied_ = occupied;
  candidateCount_ = 0;
}

SensorReading readFilteredUltrasonicSensor(
    uint8_t trigPin,
    uint8_t echoPin,
    float thresholdCm,
    OccupancyDebouncer& debouncer,
    uint8_t medianSampleCount,
    uint8_t debounceSamples,
    unsigned long timeoutUs) {
  SensorReading reading;
  // The final occupancy state is median filtered, thresholded, then debounced.
  reading.distanceCm = readMedianUltrasonicDistanceCm(trigPin, echoPin, medianSampleCount, timeoutUs);
  reading.rawOccupied = isDistanceOccupied(reading.distanceCm, thresholdCm);
  reading.stableOccupied = debouncer.update(reading.rawOccupied, debounceSamples);
  return reading;
}

void SensorHealthTracker::update(float distanceCm) {
  const bool valid = isUltrasonicDistanceValid(distanceCm);
  ++health_.totalSamples;
  health_.lastValid = valid;

  if (valid) {
    // A valid echo clears the consecutive-failure streak.
    health_.consecutiveInvalid = 0;
    return;
  }

  ++health_.invalidSamples;
  if (health_.consecutiveInvalid < 65535U) {
    ++health_.consecutiveInvalid;
  }
}

void SensorHealthTracker::reset() {
  health_ = SensorHealth{};
}

const SensorHealth& SensorHealthTracker::snapshot() const {
  return health_;
}

uint8_t SensorHealthTracker::invalidRatePercent() const {
  if (health_.totalSamples == 0) {
    return 0;
  }

  const uint32_t rate = (health_.invalidSamples * 100U) / health_.totalSamples;
  return rate > 100U ? 100U : static_cast<uint8_t>(rate);
}

const char* SensorHealthTracker::status(uint16_t warnInvalidSamples, uint16_t failInvalidSamples) const {
  if (health_.consecutiveInvalid >= failInvalidSamples) {
    return "FAIL";
  }
  if (health_.consecutiveInvalid >= warnInvalidSamples) {
    return "WARN";
  }
  return "OK";
}
