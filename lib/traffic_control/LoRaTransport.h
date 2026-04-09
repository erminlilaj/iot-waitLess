#pragma once

#include <Arduino.h>

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
