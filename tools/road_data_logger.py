#!/usr/bin/env python3
"""Record ESP32 road-test serial output as CSV.

The script is intentionally field-friendly: connect one node over USB, start
this logger, and optionally type short ground-truth labels while watching the
real sensor area.
"""

from __future__ import annotations

import argparse
import csv
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover - only hit on machines without pyserial.
    serial = None
    list_ports = None


FIELDS = [
    "timestamp_iso",
    "elapsed_s",
    "node",
    "source",
    "far_threshold_cm",
    "near_threshold_cm",
    "sensor_filter",
    "sensor_health",
    "a_queue",
    "b_queue",
    "a_far_cm",
    "a_far_occupied",
    "a_near_cm",
    "a_near_occupied",
    "b_far_cm",
    "b_far_occupied",
    "b_near_cm",
    "b_near_occupied",
    "far_cm",
    "far_occupied",
    "near_cm",
    "near_occupied",
    "queue",
    "local_queue",
    "remote_queue",
    "incoming_count",
    "passed_count",
    "remote_source",
    "remote_stale",
    "green_side",
    "phase",
    "emergency",
    "emergency_target",
    "button_override",
    "priority_side",
    "lights_a",
    "lights_b",
    "power_bus_v",
    "power_current_ma",
    "power_mw",
    "tx_backend",
    "payload",
    "rssi_dbm",
    "snr_db",
    "truth_any_vehicle",
    "truth_far",
    "truth_near",
    "truth_note",
    "event_label",
    "raw_line",
]


SENSOR_RE = re.compile(r"^(?:(?P<cm>-?\d+(?:\.\d+)?)cm/)?(?P<state>OCC|FREE)$", re.I)
POWER_RE = re.compile(
    r"^(?P<voltage>-?\d+(?:\.\d+)?)V/(?P<current>-?\d+(?:\.\d+)?)mA/(?P<power>-?\d+(?:\.\d+)?)mW$",
    re.I,
)


@dataclass
class LabelState:
    any_vehicle: str = ""
    far: str = ""
    near: str = ""
    note: str = ""
    event: str = ""


def detect_port() -> str | None:
    ports = list(list_ports.comports()) if list_ports else []
    if len(ports) == 1:
        return ports[0].device
    return None


def show_ports() -> None:
    ports = list(list_ports.comports()) if list_ports else []
    if not ports:
        print("No serial ports detected. Plug in the ESP32 and try again.")
        return
    print("Detected serial ports:")
    for port in ports:
        print(f"  {port.device:8s} {port.description}")


def blank_row(raw_line: str = "") -> dict[str, str]:
    row = {field: "" for field in FIELDS}
    row["raw_line"] = raw_line
    return row


def split_status_parts(line: str) -> dict[str, str]:
    parts = [part.strip() for part in line.split("|")]
    values: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_sensor(value: str) -> tuple[str, str]:
    match = SENSOR_RE.match(value.strip())
    if not match:
        return "", ""
    cm = match.group("cm") or ""
    occupied = "1" if match.group("state").upper() == "OCC" else "0"
    return cm, occupied


def parse_lights(value: str) -> tuple[str, str]:
    lights_a = ""
    lights_b = ""
    for token in value.split():
        if token.startswith("A:"):
            lights_a = token[2:]
        elif token.startswith("B:"):
            lights_b = token[2:]
    return lights_a, lights_b


def parse_power(value: str) -> tuple[str, str, str]:
    match = POWER_RE.match(value.strip())
    if not match:
        return "", "", ""
    return match.group("voltage"), match.group("current"), match.group("power")


def parse_thresholds(value: str) -> tuple[str, str]:
    if "/" not in value:
        return "", ""
    far, near = value.split("/", 1)
    return far.strip(), near.strip()


def parse_status_line(line: str) -> dict[str, str]:
    row = blank_row(line)
    text = line.strip()

    if text.startswith("A STATUS"):
        values = split_status_parts(text)
        row["node"] = "A"
        row["source"] = values.get("source", "")
        row["far_threshold_cm"], row["near_threshold_cm"] = parse_thresholds(values.get("thresholds", ""))
        row["sensor_filter"] = values.get("filter", "")
        row["sensor_health"] = values.get("health", "")
        row["far_cm"], row["far_occupied"] = parse_sensor(values.get("far", ""))
        row["near_cm"], row["near_occupied"] = parse_sensor(values.get("near", ""))
        row["queue"] = values.get("queue", "")
        row["a_queue"] = row["queue"]
        row["a_far_cm"] = row["far_cm"]
        row["a_far_occupied"] = row["far_occupied"]
        row["a_near_cm"] = row["near_cm"]
        row["a_near_occupied"] = row["near_occupied"]
        row["incoming_count"] = values.get("in", "")
        row["passed_count"] = values.get("out", "")
        row["emergency"] = values.get("emergency", "")
        row["power_bus_v"], row["power_current_ma"], row["power_mw"] = parse_power(values.get("power", ""))
        row["tx_backend"] = values.get("tx", "")
        row["payload"] = values.get("payload", "")
        return row

    if text.startswith("B STATUS"):
        values = split_status_parts(text)
        row["node"] = "B"
        row["source"] = values.get("source", "")
        row["remote_source"] = values.get("source", "")
        row["far_threshold_cm"], row["near_threshold_cm"] = parse_thresholds(values.get("thresholds", ""))
        row["sensor_filter"] = values.get("filter", "")
        row["sensor_health"] = values.get("health", "")
        row["a_queue"] = values.get("A_queue") or values.get("remoteQ", "")
        row["b_queue"] = values.get("B_queue") or values.get("localQ", "")
        row["a_far_cm"], row["a_far_occupied"] = parse_sensor(values.get("A_far", ""))
        row["a_near_cm"], row["a_near_occupied"] = parse_sensor(values.get("A_near", ""))
        row["b_far_cm"], row["b_far_occupied"] = parse_sensor(values.get("B_far", ""))
        row["b_near_cm"], row["b_near_occupied"] = parse_sensor(values.get("B_near", ""))
        row["far_cm"], row["far_occupied"] = parse_sensor(values.get("B_far") or values.get("far", ""))
        row["near_cm"], row["near_occupied"] = parse_sensor(values.get("B_near") or values.get("near", ""))
        row["b_far_cm"] = row["b_far_cm"] or row["far_cm"]
        row["b_far_occupied"] = row["b_far_occupied"] or row["far_occupied"]
        row["b_near_cm"] = row["b_near_cm"] or row["near_cm"]
        row["b_near_occupied"] = row["b_near_occupied"] or row["near_occupied"]
        row["local_queue"] = values.get("B_queue") or values.get("localQ", "")
        row["remote_queue"] = values.get("A_queue") or values.get("remoteQ", "")
        row["remote_stale"] = values.get("stale", "")
        row["green_side"] = values.get("green", "")
        row["phase"] = values.get("phase", "")
        row["emergency"] = values.get("emergency", "")
        row["emergency_target"] = values.get("emergency_target", "")
        row["button_override"] = values.get("button_override", "")
        row["priority_side"] = values.get("priority", "")
        row["lights_a"], row["lights_b"] = parse_lights(values.get("lights", ""))
        row["power_bus_v"], row["power_current_ma"], row["power_mw"] = parse_power(values.get("power", ""))
        return row

    return row


def apply_labels(row: dict[str, str], labels: LabelState) -> None:
    row["truth_any_vehicle"] = labels.any_vehicle
    row["truth_far"] = labels.far
    row["truth_near"] = labels.near
    row["truth_note"] = labels.note
    row["event_label"] = labels.event


def label_help() -> None:
    print()
    print("Ground-truth labels you can type while logging:")
    print("  v              vehicle is inside the observed sensor area")
    print("  n              observed sensor area is empty")
    print("  u              uncertain / do not score these samples")
    print("  far 1 | far 0  set far-sensor truth only")
    print("  near 1| near 0 set near-sensor truth only")
    print("  note <text>    attach a note to future samples")
    print("  event <text>   attach an event label, e.g. road_busy")
    print("  thresholds     ask the ESP32 to print current thresholds")
    print("  set_thresholds <far_cm> <near_cm>  send threshold update to ESP32")
    print("  cmd <command>  send any raw command to the ESP32")
    print("  clear          clear all labels and notes")
    print("  q              stop logging")
    print()


def stdin_worker(commands: "queue.Queue[str]") -> None:
    while True:
        try:
            command = input().strip()
        except EOFError:
            return
        commands.put(command)
        if command.lower() in {"q", "quit", "exit"}:
            return


def set_binary(value: str) -> str | None:
    if value in {"1", "yes", "y", "true", "on", "occ", "vehicle"}:
        return "1"
    if value in {"0", "no", "n", "false", "off", "free", "empty"}:
        return "0"
    return None


def serial_command_from_input(command: str) -> str | None:
    lower = command.strip().lower()
    if not lower:
        return None
    if lower.startswith("cmd "):
        raw = command.strip()[4:].strip()
        return raw or None

    direct_commands = {
        "help",
        "status",
        "report",
        "power",
        "thresholds",
        "emu_on",
        "emu_off",
        "reset_counts",
        "ambulance_on",
        "ambulance_off",
    }
    if lower in direct_commands:
        return command.strip()

    direct_prefixes = (
        "log ",
        "set_thresholds ",
        "set_far_threshold ",
        "set_near_threshold ",
        "state ",
        "remote_",
        "local_",
    )
    if lower.startswith(direct_prefixes):
        return command.strip()

    return None


def handle_label_command(command: str, labels: LabelState) -> tuple[bool, str]:
    normalized = command.strip()
    lower = normalized.lower()
    if not lower:
        return False, ""
    if lower in {"q", "quit", "exit"}:
        return True, "stop requested"
    if lower in {"?", "h", "help"}:
        label_help()
        return False, "help"
    if lower in {"v", "vehicle", "car"}:
        labels.any_vehicle = "1"
        return False, "truth_any_vehicle=1"
    if lower in {"n", "empty", "none", "clearroad"}:
        labels.any_vehicle = "0"
        return False, "truth_any_vehicle=0"
    if lower in {"u", "unknown", "uncertain"}:
        labels.any_vehicle = ""
        return False, "truth_any_vehicle=uncertain"
    if lower == "clear":
        labels.any_vehicle = ""
        labels.far = ""
        labels.near = ""
        labels.note = ""
        labels.event = ""
        return False, "labels cleared"
    if lower.startswith("note "):
        labels.note = normalized[5:].strip()
        return False, f"note={labels.note}"
    if lower.startswith("event "):
        labels.event = normalized[6:].strip()
        return False, f"event={labels.event}"
    if lower.startswith("far "):
        value = set_binary(lower.split(None, 1)[1])
        if value is not None:
            labels.far = value
            return False, f"truth_far={value}"
    if lower.startswith("near "):
        value = set_binary(lower.split(None, 1)[1])
        if value is not None:
            labels.near = value
            return False, f"truth_near={value}"
    return False, f"unknown label command: {command}"


def state_label(value: str) -> str:
    if value == "1":
        return "OCC"
    if value == "0":
        return "FREE"
    return "?"


def detection_result(row: dict[str, str]) -> str:
    truth = row.get("truth_any_vehicle", "")
    if truth not in {"0", "1"}:
        return "-"

    detected = row.get("far_occupied") == "1" or row.get("near_occupied") == "1"
    actual = truth == "1"
    if actual and detected:
        return "TP"
    if actual and not detected:
        return "FN"
    if not actual and detected:
        return "FP"
    return "TN"


def queue_text(row: dict[str, str]) -> str:
    if row["node"] == "A":
        return f"q={row['queue'] or '-'}"
    if row["node"] == "B":
        return f"lq={row['local_queue'] or '-'} rq={row['remote_queue'] or '-'}"
    return "-"


def control_text(row: dict[str, str]) -> str:
    if row["node"] == "A":
        return row["tx_backend"] or "-"
    if row["node"] == "B":
        green = row["green_side"] or "-"
        phase = row["phase"] or "-"
        source = row["remote_source"] or row["source"] or "-"
        if row.get("emergency") == "ON":
            target = row.get("emergency_target") or row.get("priority_side") or "?"
            return f"{green}/{phase} EM:{target}"
        return f"{green}/{phase} {source}"
    return "-"


def print_live_header() -> None:
    print()
    print(
        " time(s) node A_Q B_Q A_far        A_near       B_far        B_near       mA      health      control             truth result"
    )
    print(
        "------- ---- --- --- ------------ ------------ ------------ ------------ ------- ----------- ------------------- ----- ------"
    )


def sensor_text(row: dict[str, str], cm_key: str, occupied_key: str) -> str:
    cm = row.get(cm_key) or "?"
    state = state_label(row.get(occupied_key, ""))
    return f"{cm}cm/{state}" if cm != "?" else f"?/{state}"


def format_sample(row: dict[str, str]) -> str:
    sensor_health = row.get("sensor_health") or "-"
    truth = row.get("truth_any_vehicle") or "-"
    a_queue = row.get("a_queue") or row.get("remote_queue") or row.get("queue") or "-"
    b_queue = row.get("b_queue") or row.get("local_queue") or "-"
    a_far = sensor_text(row, "a_far_cm", "a_far_occupied")
    a_near = sensor_text(row, "a_near_cm", "a_near_occupied")
    b_far = sensor_text(row, "b_far_cm", "b_far_occupied")
    b_near = sensor_text(row, "b_near_cm", "b_near_occupied")
    return (
        f"{row['elapsed_s']:>7} "
        f"{row['node'] or '-':<4} "
        f"{a_queue:>3} "
        f"{b_queue:>3} "
        f"{a_far[:12]:<12} "
        f"{a_near[:12]:<12} "
        f"{b_far[:12]:<12} "
        f"{b_near[:12]:<12} "
        f"{row.get('power_current_ma') or '?':>7} "
        f"{sensor_health[:11]:<11} "
        f"{control_text(row)[:19]:<19} "
        f"{truth:^5} "
        f"{detection_result(row):^6}"
    )


def default_output_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("data") / "road_sessions" / f"road_session_{stamp}.csv"


def write_setup_commands(ser: "serial.Serial", node: str) -> None:
    commands = ["log summary"]
    if node == "node_a":
        commands.append("emu_off")
    for command in commands:
        ser.write((command + "\n").encode("utf-8"))
        ser.flush()
        time.sleep(0.25)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log Wait Less ESP32 serial data to CSV.")
    parser.add_argument("--port", help="Serial port, for example COM3. Auto-detects if exactly one port exists.")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--node", choices=["auto", "node_a", "node_b"], default="auto")
    parser.add_argument("--out", type=Path, default=default_output_path())
    parser.add_argument("--no-setup", action="store_true", help="Do not send log summary / emu_off setup commands.")
    parser.add_argument("--list-ports", action="store_true", help="Print available serial ports and exit.")
    parser.add_argument("--duration-s", type=float, help="Stop automatically after this many seconds.")
    return parser.parse_args()


def main() -> int:
    if serial is None:
        print("Missing dependency: pyserial")
        print("Install it with: python -m pip install pyserial")
        return 2

    args = parse_args()
    if args.list_ports:
        show_ports()
        return 0

    port = args.port or detect_port()
    if not port:
        show_ports()
        print("Choose one port, then run again with --port COMx.")
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    raw_path = args.out.with_suffix(".raw.log")
    labels = LabelState()
    commands: "queue.Queue[str]" = queue.Queue()
    start = time.time()

    label_help()
    print(f"Opening {port} at {args.baud} baud")
    print(f"CSV output: {args.out}")
    print(f"Raw serial log: {raw_path}")

    try:
        ser = serial.Serial(port, args.baud, timeout=0.25)
    except serial.SerialException as exc:
        print(f"Could not open {port}: {exc}")
        return 2

    with ser, args.out.open("w", newline="", encoding="utf-8") as csv_file, raw_path.open("w", encoding="utf-8") as raw_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
        writer.writeheader()
        printed_samples = 0

        if not args.no_setup and args.node != "auto":
            write_setup_commands(ser, args.node)

        threading.Thread(target=stdin_worker, args=(commands,), daemon=True).start()
        print_live_header()

        try:
            while True:
                if args.duration_s is not None and time.time() - start >= args.duration_s:
                    print(f"\nTimed capture complete after {args.duration_s:.1f} seconds.")
                    return 0

                while not commands.empty():
                    command = commands.get_nowait()
                    serial_command = serial_command_from_input(command)
                    if serial_command:
                        ser.write((serial_command + "\n").encode("utf-8"))
                        ser.flush()
                        print(f"[serial] sent: {serial_command}")
                        event_row = blank_row(f"[SERIAL_CMD] {serial_command}")
                        event_row["timestamp_iso"] = datetime.now().isoformat(timespec="seconds")
                        event_row["elapsed_s"] = f"{time.time() - start:.2f}"
                        apply_labels(event_row, labels)
                        writer.writerow(event_row)
                        csv_file.flush()
                        continue

                    should_stop, message = handle_label_command(command, labels)
                    if message:
                        print(f"[label] {message}")
                        label_row = blank_row(f"[LABEL] {command}")
                        label_row["timestamp_iso"] = datetime.now().isoformat(timespec="seconds")
                        label_row["elapsed_s"] = f"{time.time() - start:.2f}"
                        apply_labels(label_row, labels)
                        writer.writerow(label_row)
                        csv_file.flush()
                    if should_stop:
                        return 0

                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                raw_file.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")
                raw_file.flush()

                row = parse_status_line(line)
                row["timestamp_iso"] = datetime.now().isoformat(timespec="seconds")
                row["elapsed_s"] = f"{time.time() - start:.2f}"
                apply_labels(row, labels)
                writer.writerow(row)
                csv_file.flush()

                if row["node"]:
                    if printed_samples > 0 and printed_samples % 20 == 0:
                        print_live_header()
                    print(format_sample(row))
                    printed_samples += 1

        except KeyboardInterrupt:
            print("\nStopped by Ctrl+C.")
            return 0


if __name__ == "__main__":
    sys.exit(main())
