#!/usr/bin/env python3
"""Summarize road-session detection quality from logger CSV output."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def occupied(value: str | None) -> bool:
    return value == "1"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarize(rows: list[dict[str, str]]) -> str:
    parsed = [row for row in rows if row.get("node") in {"A", "B"}]
    scored = []
    for row in parsed:
        truth = row.get("truth_any_vehicle", "")
        if truth in {"0", "1"}:
            scored.append(row)

    tp = tn = fp = fn = 0
    far_values = []
    near_values = []
    for row in scored:
        actual = row.get("truth_any_vehicle") == "1"
        detected = occupied(row.get("far_occupied")) or occupied(row.get("near_occupied"))
        if actual and detected:
            tp += 1
        elif actual and not detected:
            fn += 1
        elif not actual and detected:
            fp += 1
        else:
            tn += 1

        for key, bucket in (("far_cm", far_values), ("near_cm", near_values)):
            try:
                bucket.append(float(row.get(key, "")))
            except ValueError:
                pass

    total = len(scored)
    accuracy = ((tp + tn) / total * 100.0) if total else 0.0
    fpr = (fp / (fp + tn) * 100.0) if (fp + tn) else 0.0
    fnr = (fn / (fn + tp) * 100.0) if (fn + tp) else 0.0
    far_avg = sum(far_values) / len(far_values) if far_values else 0.0
    near_avg = sum(near_values) / len(near_values) if near_values else 0.0

    first_time = parsed[0].get("timestamp_iso", "-") if parsed else "-"
    last_time = parsed[-1].get("timestamp_iso", "-") if parsed else "-"

    return "\n".join(
        [
            "Wait Less Road Data Summary",
            "---------------------------",
            f"Parsed ESP32 samples: {len(parsed)}",
            f"First sample: {first_time}",
            f"Last sample: {last_time}",
            "",
            "Detection quality from labeled samples",
            f"Scored samples: {total}",
            f"True positives: {tp}",
            f"True negatives: {tn}",
            f"False positives: {fp}",
            f"False negatives: {fn}",
            f"Accuracy: {accuracy:.1f}%",
            f"False positive rate: {fpr:.1f}%",
            f"False negative rate: {fnr:.1f}%",
            "",
            "Distance sanity check",
            f"Average far distance: {far_avg:.1f} cm",
            f"Average near distance: {near_avg:.1f} cm",
            "",
            "Next analysis command",
            "python tools\\sensor_threshold_analysis.py --csv <this_csv> --sensor both",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize road-session CSV metrics.")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="Optional text file to write the summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = summarize(read_rows(args.csv))
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
