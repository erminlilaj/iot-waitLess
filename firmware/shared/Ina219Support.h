#pragma once

#include <Arduino.h>

struct Ina219Reading {
  bool ok = false;
  float busVoltageV = 0.0f;
  float shuntVoltageMv = 0.0f;
  float currentMa = 0.0f;
  float powerMw = 0.0f;
};

bool ina219Begin(uint8_t sdaPin, uint8_t sclPin, uint8_t address, Stream& out);
Ina219Reading ina219Read();
void printIna219Reading(Stream& out, const Ina219Reading& reading);
