#pragma once

#include <Arduino.h>

enum class LogMode : uint8_t {
  Quiet = 0,
  Summary = 1,
  Verbose = 2,
};

inline const char* logModeName(LogMode mode) {
  switch (mode) {
    case LogMode::Quiet:
      return "QUIET";
    case LogMode::Summary:
      return "SUMMARY";
    case LogMode::Verbose:
      return "VERBOSE";
  }

  return "UNKNOWN";
}

inline const char* onOffLabel(bool enabled) {
  return enabled ? "ON" : "OFF";
}

inline void printLogModeCommands(Stream& out) {
  out.println("  log quiet");
  out.println("  log summary");
  out.println("  log verbose");
  out.println("  status");
  out.println("  report");
}

inline bool tryApplyLogModeCommand(const String& rawCommand, LogMode& mode, Stream& out) {
  String command = rawCommand;
  command.trim();

  if (command.equalsIgnoreCase("log quiet")) {
    mode = LogMode::Quiet;
  } else if (command.equalsIgnoreCase("log summary")) {
    mode = LogMode::Summary;
  } else if (command.equalsIgnoreCase("log verbose")) {
    mode = LogMode::Verbose;
  } else {
    return false;
  }

  out.print("Log mode set to ");
  out.println(logModeName(mode));
  return true;
}

inline void printSectionHeader(Stream& out, const char* title) {
  out.println();
  out.println("========================================");
  out.println(title);
  out.println("========================================");
}
