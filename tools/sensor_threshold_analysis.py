#!/usr/bin/env python3
"""Find useful ultrasonic thresholds from a labelled road-session CSV."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Result:
    threshold_cm: float
    tp: int
    tn: int
    fp: int
    fn: int

    @property
    def scored(self) -> int:
        return self.tp + self.tn + self.fp + self.fn

    @property
    def accuracy(self) -> float:
        return ((self.tp + self.tn) / self.scored * 100.0) if self.scored else 0.0

    @property
    def false_positive_rate(self) -> float:
        return (self.fp / (self.fp + self.tn) * 100.0) if (self.fp + self.tn) else 0.0

    @property
    def false_negative_rate(self) -> float:
        return (self.fn / (self.fn + self.tp) * 100.0) if (self.fn + self.tp) else 0.0

    @property
    def error_count(self) -> int:
        return self.fp + self.fn


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def labelled_distances(rows: list[dict[str, str]], sensor: str) -> list[tuple[float, bool]]:
    key = f"{sensor}_cm"
    points: list[tuple[float, bool]] = []
    for row in rows:
        truth = row.get("truth_any_vehicle", "")
        if truth not in {"0", "1"}:
            continue
        distance = parse_float(row.get(key))
        if distance is None or distance <= 0.0 or distance >= 998.0:
            continue
        points.append((distance, truth == "1"))
    return points


def evaluate(points: list[tuple[float, bool]], threshold_cm: float) -> Result:
    tp = tn = fp = fn = 0
    for distance_cm, actual_vehicle in points:
        detected = distance_cm < threshold_cm
        if actual_vehicle and detected:
            tp += 1
        elif actual_vehicle and not detected:
            fn += 1
        elif not actual_vehicle and detected:
            fp += 1
        else:
            tn += 1
    return Result(threshold_cm=threshold_cm, tp=tp, tn=tn, fp=fp, fn=fn)


def sweep(points: list[tuple[float, bool]], start: int, stop: int, step: int) -> list[Result]:
    return [evaluate(points, float(threshold)) for threshold in range(start, stop + 1, step)]


def choose_best(results: list[Result]) -> Result | None:
    if not results:
        return None
    return min(results, key=lambda result: (result.error_count, result.false_positive_rate, result.false_negative_rate, result.threshold_cm))


def format_result(result: Result) -> str:
    return (
        f"{result.threshold_cm:6.1f} cm | "
        f"TP/TN/FP/FN {result.tp:4d}/{result.tn:4d}/{result.fp:4d}/{result.fn:4d} | "
        f"acc {result.accuracy:5.1f}% | "
        f"FP {result.false_positive_rate:5.1f}% | "
        f"FN {result.false_negative_rate:5.1f}%"
    )


def analyze_sensor(rows: list[dict[str, str]], sensor: str, start: int, stop: int, step: int) -> str:
    points = labelled_distances(rows, sensor)
    lines = [f"{sensor.upper()} sensor threshold analysis", "-" * 36]
    lines.append(f"Labelled samples with usable distance: {len(points)}")

    if not points:
        lines.append("No labelled distance samples found.")
        return "\n".join(lines)

    vehicle_distances = [distance for distance, actual in points if actual]
    empty_distances = [distance for distance, actual in points if not actual]
    if vehicle_distances:
        lines.append(f"Vehicle distance range: {min(vehicle_distances):.1f} - {max(vehicle_distances):.1f} cm")
    if empty_distances:
        lines.append(f"Empty distance range: {min(empty_distances):.1f} - {max(empty_distances):.1f} cm")

    results = sweep(points, start, stop, step)
    best = choose_best(results)
    if best:
        lines.append("")
        lines.append("Recommended threshold:")
        lines.append(format_result(best))

    lines.append("")
    lines.append("Top candidates:")
    for result in sorted(results, key=lambda item: (item.error_count, item.false_positive_rate, item.false_negative_rate, item.threshold_cm))[:8]:
        lines.append(format_result(result))

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend ultrasonic thresholds from labelled road CSV data.")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--sensor", choices=["far", "near", "both"], default="both")
    parser.add_argument("--start", type=int, default=10)
    parser.add_argument("--stop", type=int, default=250)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--out", type=Path, help="Optional text file to write the analysis.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = read_rows(args.csv)
    sensors = ["far", "near"] if args.sensor == "both" else [args.sensor]
    text = "\n\n".join(analyze_sensor(rows, sensor, args.start, args.stop, args.step) for sensor in sensors)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
