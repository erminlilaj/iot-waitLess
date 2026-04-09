#include "SensorSupport.h"

float readUltrasonicDistanceCm(uint8_t trigPin, uint8_t echoPin, unsigned long timeoutUs) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  const unsigned long durationUs = pulseIn(echoPin, HIGH, timeoutUs);
  if (durationUs == 0) {
    return 999.0f;
  }

  return static_cast<float>(durationUs) * 0.0343f / 2.0f;
}

bool isDistanceOccupied(float distanceCm, float thresholdCm) {
  return distanceCm > 0.0f && distanceCm < thresholdCm;
}
