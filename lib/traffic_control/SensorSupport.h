#pragma once

#include <Arduino.h>

float readUltrasonicDistanceCm(uint8_t trigPin, uint8_t echoPin, unsigned long timeoutUs = 25000UL);
bool isDistanceOccupied(float distanceCm, float thresholdCm);
