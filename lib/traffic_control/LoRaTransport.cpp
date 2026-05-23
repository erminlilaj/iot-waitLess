#include "LoRaTransport.h"

#include "shared/HardwareMap.h"
#include "shared/ProjectConfig.h"

#if defined(WAITLESS_USE_RADIOLIB)
#define WAITLESS_RADIOLIB_BACKEND 1
#include <RadioLib.h>
#include <SPI.h>
#else
#define WAITLESS_RADIOLIB_BACKEND 0
#endif

namespace {

#if WAITLESS_RADIOLIB_BACKEND
#if defined(HSPI)
SPIClass radioSpi(HSPI);
#else
SPIClass radioSpi(FSPI);
#endif
// Heltec V3 exposes the SX1262 on fixed board pins defined in HardwareMap.h.
SX1262 radio = new Module(
    hw::heltec_v3::kLoRaRadio.cs,
    hw::heltec_v3::kLoRaRadio.irq,
    hw::heltec_v3::kLoRaRadio.reset,
    hw::heltec_v3::kLoRaRadio.busy,
    radioSpi);

volatile bool packetReceivedFlag = false;
bool radioReady = false;
bool receiveMode = false;

void onPacketReceived() {
  packetReceivedFlag = true;
}

bool restartReceive(Stream& debug) {
  if (!radioReady || !receiveMode) {
    return false;
  }

  const int16_t state = radio.startReceive();
  if (state != RADIOLIB_ERR_NONE) {
    debug.print("[LoRa] startReceive failed, code ");
    debug.println(state);
    return false;
  }

  return true;
}
#else
bool radioReady = false;
#endif

}  // namespace

bool loRaBegin(bool startReceiving, Stream& debug) {
#if WAITLESS_RADIOLIB_BACKEND
  // SPI and radio settings are centralized here so both nodes use the same link.
  radioSpi.begin(
      hw::heltec_v3::kLoRaSpi.sck,
      hw::heltec_v3::kLoRaSpi.miso,
      hw::heltec_v3::kLoRaSpi.mosi,
      hw::heltec_v3::kLoRaRadio.cs);

  const int16_t state = radio.begin(
      config::kLoRaFrequencyMHz,
      config::kLoRaBandwidthKHz,
      config::kLoRaSpreadingFactor,
      config::kLoRaCodingRate,
      config::kLoRaSyncWord,
      config::kLoRaOutputPowerDbm,
      config::kLoRaPreambleLength);

  if (state != RADIOLIB_ERR_NONE) {
    debug.print("[LoRa] radio init failed, code ");
    debug.println(state);
    radioReady = false;
    return false;
  }

  radio.setPacketReceivedAction(onPacketReceived);
  receiveMode = startReceiving;
  radioReady = true;
  packetReceivedFlag = false;

  if (startReceiving) {
    restartReceive(debug);
  }

  return true;
#else
  (void)startReceiving;
  debug.println("[LoRa] RadioLib backend not available. Keeping serial-emulation path active.");
  radioReady = false;
  return false;
#endif
}

bool loRaSendText(const String& payload, Stream& debug) {
#if WAITLESS_RADIOLIB_BACKEND
  if (!radioReady) {
    return false;
  }

  // Transmit is blocking and short because payloads are compact telemetry lines.
  const int16_t state = radio.transmit(payload.c_str());
  if (state != RADIOLIB_ERR_NONE) {
    debug.print("[LoRa] transmit failed, code ");
    debug.println(state);
    return false;
  }

  return true;
#else
  (void)payload;
  (void)debug;
  return false;
#endif
}

bool loRaTryReceive(LoRaRxPacket& packet, Stream& debug) {
#if WAITLESS_RADIOLIB_BACKEND
  if (!radioReady || !receiveMode || !packetReceivedFlag) {
    return false;
  }

  packetReceivedFlag = false;
  packet.payload = "";
  const int16_t state = radio.readData(packet.payload);
  packet.rssi = radio.getRSSI();
  packet.snr = radio.getSNR();

  // Immediately return to receive mode so Node B keeps listening continuously.
  restartReceive(debug);

  if (state != RADIOLIB_ERR_NONE) {
    debug.print("[LoRa] read failed, code ");
    debug.println(state);
    return false;
  }

  return true;
#else
  (void)packet;
  (void)debug;
  return false;
#endif
}

bool loRaIsActive() {
  return radioReady;
}

const char* loRaBackendName() {
#if WAITLESS_RADIOLIB_BACKEND
  return radioReady ? "RadioLib SX1262" : "Serial stub";
#else
  return "Serial stub";
#endif
}

void loRaPrintConfig(Stream& debug) {
  debug.print("[LoRa] backend: ");
  debug.println(loRaBackendName());
  debug.print("[LoRa] freq=");
  debug.print(config::kLoRaFrequencyMHz, 1);
  debug.print(" MHz bw=");
  debug.print(config::kLoRaBandwidthKHz, 1);
  debug.print(" kHz sf=");
  debug.print(config::kLoRaSpreadingFactor);
  debug.print(" cr=");
  debug.print(config::kLoRaCodingRate);
  debug.print(" sync=0x");
  debug.print(config::kLoRaSyncWord, HEX);
  debug.print(" power=");
  debug.print(config::kLoRaOutputPowerDbm);
  debug.println(" dBm");
}
