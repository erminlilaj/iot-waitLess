#pragma once

#include <Arduino.h>

// Thin wrapper around the Heltec V3 onboard SX1262 radio.
// Keeping radio operations behind this interface lets the firmware still build
// with a serial-emulation fallback when RadioLib is not enabled.
struct LoRaRxPacket {
  String payload;
  float rssi = 0.0f;
  float snr = 0.0f;
};

bool loRaBegin(bool startReceiving, Stream& debug);
bool loRaSendText(const String& payload, Stream& debug);
bool loRaTryReceive(LoRaRxPacket& packet, Stream& debug);
bool loRaIsActive();
const char* loRaBackendName();
void loRaPrintConfig(Stream& debug);
