#pragma once

#include <Arduino.h>

namespace hw {

struct UltrasonicPins {
  uint8_t trig;
  uint8_t echo;
};

struct TrafficLightPins {
  uint8_t red;
  uint8_t yellow;
  uint8_t green;
};

struct SpiPins {
  uint8_t sck;
  uint8_t miso;
  uint8_t mosi;
};

struct I2cPins {
  uint8_t sda;
  uint8_t scl;
};

struct LoRaRadioPins {
  uint8_t cs;
  uint8_t irq;
  uint8_t reset;
  uint8_t busy;
};

namespace heltec_v3 {

// Heltec WiFi LoRa 32 V3 onboard SX1262 wiring used by the shared LoRa transport.
constexpr SpiPins kLoRaSpi = {
    9,
    11,
    10,
};

constexpr LoRaRadioPins kLoRaRadio = {
    8,
    14,
    12,
    13,
};

// Optional external INA219 current sensor. These pins are free in the current
// prototype wiring and are exposed on the J3 header.
constexpr I2cPins kIna219I2c = {
    41,
    42,
};

}  // namespace heltec_v3

namespace node_a {

// Bench-test wiring for the side-A sensing ESP32.
constexpr UltrasonicPins kFarSensor = {
    3,
    5,
};

constexpr UltrasonicPins kNearSensor = {
    6,
    7,
};

}  // namespace node_a

namespace node_b {

// Bench-test wiring for the side-B sensing + controller ESP32.
constexpr UltrasonicPins kFarSensor = {
    4,
    5,
};

constexpr UltrasonicPins kNearSensor = {
    6,
    7,
};

// Node B drives both traffic-light heads in the current firmware design.
constexpr TrafficLightPins kSideALights = {
    33,
    34,
    35,
};

constexpr TrafficLightPins kSideBLights = {
    38,
    39,
    40,
};

}  // namespace node_b

}  // namespace hw
