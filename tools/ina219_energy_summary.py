#!/usr/bin/env python3
"""Summarize INA219 current/power samples from Wait Less CSV logs."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


CURRENT_KEYS = ("power_current_ma", "current_ma", "current_mA", "current")
VOLTAGE_KEYS = ("power_bus_v", "bus_voltage_v", "voltage_v", "voltage")
POWER_KEYS = ("power_mw", "power_mW", "power")


@dataclass(frozen=True)
class PowerSample:
    node: str
    elapsed_s: float
    voltage_v: float
    current_ma: float
    power_mw: float


@dataclass(frozen=True)
class NodeEnergy:
    node: str
    samples: int
    duration_s: float
    avg_voltage_v: float
    avg_current_ma: float
    min_current_ma: float
    max_current_ma: float
    avg_power_mw: float
    used_mah: float
    used_wh: float


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def first_float(row: dict[str, str], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = parse_float(row.get(key))
        if value is not None:
            return value
    return None


def read_samples(paths: list[Path], default_node: str) -> list[PowerSample]:
    samples: list[PowerSample] = []
    fallback_elapsed = 0.0

    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                current_ma = first_float(row, CURRENT_KEYS)
                if current_ma is None:
                    continue

                voltage_v = first_float(row, VOLTAGE_KEYS)
                power_mw = first_float(row, POWER_KEYS)
                elapsed_s = parse_float(row.get("elapsed_s"))
                if elapsed_s is None:
                    elapsed_s = fallback_elapsed
                    fallback_elapsed += 1.0

                if voltage_v is None and power_mw is not None and current_ma != 0:
                    voltage_v = power_mw / current_ma
                if voltage_v is None:
                    voltage_v = 5.0
                if power_mw is None:
                    power_mw = voltage_v * current_ma

                node = row.get("node") or default_node
                samples.append(
                    PowerSample(
                        node=node,
                        elapsed_s=elapsed_s,
                        voltage_v=voltage_v,
                        current_ma=current_ma,
                        power_mw=power_mw,
                    )
                )

    return samples


def integrate(samples: list[PowerSample]) -> tuple[float, float]:
    if len(samples) < 2:
        return 0.0, 0.0

    used_mas = 0.0
    used_mws = 0.0
    ordered = sorted(samples, key=lambda sample: sample.elapsed_s)
    for previous, current in zip(ordered, ordered[1:]):
        dt_s = max(0.0, current.elapsed_s - previous.elapsed_s)
        used_mas += ((previous.current_ma + current.current_ma) / 2.0) * dt_s
        used_mws += ((previous.power_mw + current.power_mw) / 2.0) * dt_s

    return used_mas / 3600.0, used_mws / 3600.0 / 1000.0


def summarize_node(node: str, samples: list[PowerSample]) -> NodeEnergy:
    ordered = sorted(samples, key=lambda sample: sample.elapsed_s)
    duration_s = max(0.0, ordered[-1].elapsed_s - ordered[0].elapsed_s) if len(ordered) > 1 else 0.0
    currents = [sample.current_ma for sample in ordered]
    voltages = [sample.voltage_v for sample in ordered]
    powers = [sample.power_mw for sample in ordered]
    used_mah, used_wh = integrate(ordered)

    return NodeEnergy(
        node=node,
        samples=len(ordered),
        duration_s=duration_s,
        avg_voltage_v=sum(voltages) / len(voltages),
        avg_current_ma=sum(currents) / len(currents),
        min_current_ma=min(currents),
        max_current_ma=max(currents),
        avg_power_mw=sum(powers) / len(powers),
        used_mah=used_mah,
        used_wh=used_wh,
    )


def summarize(samples: list[PowerSample]) -> list[NodeEnergy]:
    by_node: dict[str, list[PowerSample]] = {}
    for sample in samples:
        by_node.setdefault(sample.node or "UNKNOWN", []).append(sample)
    return [summarize_node(node, node_samples) for node, node_samples in sorted(by_node.items())]


def render(summaries: list[NodeEnergy], road_csv: Path | None) -> str:
    lines = ["INA219 Energy Measurement Summary", "--------------------------------"]
    if not summaries:
        lines.append("No INA219 current samples found.")
        return "\n".join(lines)

    node_a_avg = None
    node_b_avg = None
    for item in summaries:
        lines.extend(
            [
                "",
                f"Node {item.node}",
                f"  Samples: {item.samples}",
                f"  Duration: {item.duration_s / 60.0:.1f} min",
                f"  Average voltage: {item.avg_voltage_v:.3f} V",
                f"  Average current: {item.avg_current_ma:.1f} mA",
                f"  Current min/max: {item.min_current_ma:.1f}/{item.max_current_ma:.1f} mA",
                f"  Average power: {item.avg_power_mw:.1f} mW",
                f"  Energy used: {item.used_mah:.1f} mAh ({item.used_wh:.3f} Wh)",
            ]
        )
        if item.node == "A":
            node_a_avg = item.avg_current_ma
        elif item.node == "B":
            node_b_avg = item.avg_current_ma

    if road_csv and node_a_avg is not None and node_b_avg is not None:
        lines.extend(
            [
                "",
                "Regenerate final evidence report with measured current:",
                (
                    "python tools\\final_evidence_report.py "
                    f"--csv {road_csv} "
                    f"--node-a-ma {node_a_avg:.1f} "
                    f"--node-b-ma {node_b_avg:.1f} "
                    "--energy-note \"Current values were measured with an INA219 high-side current sensor.\""
                ),
            ]
        )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize INA219 energy readings from CSV.")
    parser.add_argument("--csv", type=Path, action="append", required=True, help="One or more CSV logs with INA219 columns.")
    parser.add_argument("--node", default="UNKNOWN", help="Node label to use if the CSV has no node column.")
    parser.add_argument("--road-csv", type=Path, help="Road CSV path to include in the final-report command.")
    parser.add_argument("--out", type=Path, help="Optional text file to write the summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    samples = read_samples(args.csv, args.node)
    text = render(summarize(samples), args.road_csv)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
