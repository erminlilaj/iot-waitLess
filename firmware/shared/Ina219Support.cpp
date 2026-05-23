#include "Ina219Support.h"

#include <Wire.h>

#include "shared/ProjectConfig.h"

namespace {

constexpr uint8_t kRegConfig = 0x00;
constexpr uint8_t kRegShuntVoltage = 0x01;
constexpr uint8_t kRegBusVoltage = 0x02;
constexpr uint16_t kConfig32V320Mv12BitContinuous = 0x399F;

// The INA219 is optional. If it is not present, firmware keeps running and
// reports INA219_NA so the live demo is not blocked by the energy sensor.
uint8_t gAddress = config::kIna219Address;
bool gAvailable = false;

bool writeRegister(uint8_t reg, uint16_t value) {
  Wire.beginTransmission(gAddress);
  Wire.write(reg);
  Wire.write(static_cast<uint8_t>(value >> 8));
  Wire.write(static_cast<uint8_t>(value & 0xFF));
  return Wire.endTransmission() == 0;
}

bool readRegister(uint8_t reg, uint16_t& value) {
  Wire.beginTransmission(gAddress);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }

  if (Wire.requestFrom(static_cast<int>(gAddress), 2) != 2) {
    return false;
  }

  const uint8_t msb = Wire.read();
  const uint8_t lsb = Wire.read();
  value = (static_cast<uint16_t>(msb) << 8) | lsb;
  return true;
}

}  // namespace

bool ina219Begin(uint8_t sdaPin, uint8_t sclPin, uint8_t address, Stream& out) {
  gAddress = address;
  Wire.begin(sdaPin, sclPin);
  delay(20);

  uint16_t configValue = 0;
  gAvailable = readRegister(kRegConfig, configValue);
  if (gAvailable) {
    // Continuous 12-bit bus/shunt measurements are enough for average current.
    gAvailable = writeRegister(kRegConfig, kConfig32V320Mv12BitContinuous);
  }

  out.print("[INA219] ");
  if (gAvailable) {
    out.print("ready at 0x");
    out.print(gAddress, HEX);
    out.print(" SDA=");
    out.print(sdaPin);
    out.print(" SCL=");
    out.println(sclPin);
  } else {
    out.print("not detected at 0x");
    out.print(gAddress, HEX);
    out.print(" SDA=");
    out.print(sdaPin);
    out.print(" SCL=");
    out.println(sclPin);
  }
  return gAvailable;
}

Ina219Reading ina219Read() {
  Ina219Reading reading;
  if (!gAvailable) {
    return reading;
  }

  uint16_t rawBus = 0;
  uint16_t rawShunt = 0;
  if (!readRegister(kRegBusVoltage, rawBus) || !readRegister(kRegShuntVoltage, rawShunt)) {
    gAvailable = false;
    return reading;
  }

  const int16_t signedShunt = static_cast<int16_t>(rawShunt);
  reading.ok = true;
  // Datasheet conversion: bus LSB is 4 mV and shunt LSB is 10 uV.
  reading.busVoltageV = static_cast<float>((rawBus >> 3) * 4) / 1000.0f;
  reading.shuntVoltageMv = static_cast<float>(signedShunt) * 0.01f;
  reading.currentMa = (reading.shuntVoltageMv / config::kIna219ShuntOhms);
  reading.powerMw = reading.busVoltageV * reading.currentMa;
  return reading;
}

void printIna219Reading(Stream& out, const Ina219Reading& reading) {
  if (!reading.ok) {
    out.println("INA219_NA");
    return;
  }

  out.print(reading.busVoltageV, 3);
  out.print("V/");
  out.print(reading.currentMa, 1);
  out.print("mA/");
  out.print(reading.powerMw, 1);
  out.println("mW");
}
