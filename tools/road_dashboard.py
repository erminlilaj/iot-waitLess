#!/usr/bin/env python3
"""Live dashboard for a road-session CSV file."""

from __future__ import annotations

import argparse
import csv
import time
import tkinter as tk
from pathlib import Path


WINDOW_WIDTH = 1180
WINDOW_HEIGHT = 720
CANVAS_WIDTH = 760
CANVAS_HEIGHT = 680


def latest_session_csv() -> Path | None:
    folder = Path("data") / "road_sessions"
    files = sorted(folder.glob("*.csv"), key=lambda path: path.stat().st_mtime)
    return files[-1] if files else None


def read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (FileNotFoundError, PermissionError):
        return []


def latest_sample(rows: list[dict[str, str]]) -> dict[str, str] | None:
    for row in reversed(rows):
        if row.get("node") in {"A", "B"}:
            return row
    return None


def occupied(value: str | None) -> bool:
    return value == "1"


def compute_metrics(rows: list[dict[str, str]]) -> dict[str, float | int]:
    tp = tn = fp = fn = 0
    scored = 0
    for row in rows:
        truth = row.get("truth_any_vehicle", "")
        if truth not in {"0", "1"}:
            continue
        if not row.get("node"):
            continue
        detected = occupied(row.get("far_occupied")) or occupied(row.get("near_occupied"))
        actual = truth == "1"
        scored += 1
        if actual and detected:
            tp += 1
        elif actual and not detected:
            fn += 1
        elif not actual and detected:
            fp += 1
        else:
            tn += 1

    accuracy = ((tp + tn) / scored * 100.0) if scored else 0.0
    false_positive_rate = (fp / (fp + tn) * 100.0) if (fp + tn) else 0.0
    false_negative_rate = (fn / (fn + tp) * 100.0) if (fn + tp) else 0.0
    return {
        "scored": scored,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": accuracy,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
    }


class RoadDashboard:
    def __init__(self, root: tk.Tk, csv_path: Path):
        self.root = root
        self.csv_path = csv_path
        self.root.title("Wait Less - Road Digital Twin")
        self.root.configure(bg="#eef1f2")

        self.canvas = tk.Canvas(root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="#d9dedb", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=18, pady=18)

        panel = tk.Frame(root, bg="#eef1f2")
        panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 18), pady=18)

        self.title_var = tk.StringVar()
        self.sensor_var = tk.StringVar()
        self.control_var = tk.StringVar()
        self.metric_var = tk.StringVar()
        self.raw_var = tk.StringVar()

        for variable, size in (
            (self.title_var, 15),
            (self.sensor_var, 11),
            (self.control_var, 11),
            (self.metric_var, 11),
            (self.raw_var, 9),
        ):
            tk.Label(
                panel,
                textvariable=variable,
                justify="left",
                anchor="nw",
                font=("Consolas", size),
                bg="#fbfbf8",
                fg="#1f2c32",
                relief="groove",
                bd=1,
                padx=12,
                pady=10,
                wraplength=340,
            ).pack(fill=tk.X, pady=(0, 12))

        self.root.after(300, self.refresh)

    def refresh(self) -> None:
        rows = read_rows(self.csv_path)
        sample = latest_sample(rows)
        metrics = compute_metrics(rows)
        self.draw_scene(sample)
        self.update_text(sample, rows, metrics)
        self.root.after(500, self.refresh)

    def draw_scene(self, sample: dict[str, str] | None) -> None:
        c = self.canvas
        c.delete("all")
        c.create_rectangle(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, fill="#d9dedb", outline="")
        c.create_rectangle(292, 0, 468, CANVAS_HEIGHT, fill="#444d57", outline="")
        c.create_rectangle(0, 252, CANVAS_WIDTH, 428, fill="#444d57", outline="")
        c.create_rectangle(292, 252, 468, 428, fill="#303840", outline="")

        for x in (332, 428):
            c.create_line(x, 0, x, 252, fill="#f3eee5", width=3, dash=(12, 12))
            c.create_line(x, 428, x, CANVAS_HEIGHT, fill="#f3eee5", width=3, dash=(12, 12))
        for y in (292, 388):
            c.create_line(0, y, 292, y, fill="#f3eee5", width=3, dash=(12, 12))
            c.create_line(468, y, CANVAS_WIDTH, y, fill="#f3eee5", width=3, dash=(12, 12))

        node = sample.get("node", "") if sample else ""
        far_on = occupied(sample.get("far_occupied")) if sample else False
        near_on = occupied(sample.get("near_occupied")) if sample else False
        truth = sample.get("truth_any_vehicle", "") if sample else ""

        green_side = sample.get("green_side", "") if sample else ""
        phase = sample.get("phase", "") if sample else ""
        self.draw_light(245, 224, "A", green_side, phase)
        self.draw_light(486, 432, "B", green_side, phase)

        axis = "A" if node == "A" else "B"
        self.draw_sensor(axis, "far", far_on, truth)
        self.draw_sensor(axis, "near", near_on, truth)

        if sample:
            local_q = sample.get("local_queue") or sample.get("queue") or "0"
            remote_q = sample.get("remote_queue") or "0"
            c.create_text(116, 78, text=f"Road session\nNode {node or '?'} live", fill="#20303a", font=("Segoe UI", 22, "bold"))
            c.create_text(116, 130, text=f"Local queue: {local_q}\nRemote queue: {remote_q}", fill="#20303a", font=("Consolas", 15), justify="left")

        detection = far_on or near_on
        if truth in {"0", "1"}:
            ok = (truth == "1" and detection) or (truth == "0" and not detection)
            fill = "#2c9f67" if ok else "#c74a4a"
            text = "MATCH" if ok else ("FALSE POSITIVE" if detection else "FALSE NEGATIVE")
            c.create_rectangle(28, 570, 338, 628, fill=fill, outline="")
            c.create_text(183, 599, text=text, fill="white", font=("Segoe UI", 18, "bold"))

    def draw_light(self, x: int, y: int, side: str, green_side: str, phase: str) -> None:
        state = "RED"
        if green_side == side and phase == "GREEN":
            state = "GREEN"
        elif green_side == side and phase == "YELLOW":
            state = "YELLOW"

        colors = {
            "RED": "#d94b4b" if state == "RED" else "#4d2b2b",
            "YELLOW": "#f0c64d" if state == "YELLOW" else "#5a4d2c",
            "GREEN": "#2dc56d" if state == "GREEN" else "#254b35",
        }
        self.canvas.create_rectangle(x, y, x + 34, y + 92, fill="#1c2327", outline="#0d1215", width=2)
        self.canvas.create_oval(x + 8, y + 8, x + 26, y + 26, fill=colors["RED"], outline="")
        self.canvas.create_oval(x + 8, y + 36, x + 26, y + 54, fill=colors["YELLOW"], outline="")
        self.canvas.create_oval(x + 8, y + 64, x + 26, y + 82, fill=colors["GREEN"], outline="")

    def draw_sensor(self, axis: str, kind: str, active: bool, truth: str) -> None:
        color = "#2eb67d" if active else "#7d8d98"
        outline = "#206c49" if active else "#40515c"
        label = f"{axis} {kind.upper()}"
        if axis == "A":
            y = 160 if kind == "far" else 240
            x = 430
            self.canvas.create_oval(x - 32, y - 26, x + 32, y + 26, fill=color, stipple="gray25" if active else "", outline=outline, width=3)
            if active:
                self.canvas.create_rectangle(x - 12, y - 20, x + 12, y + 20, fill="#35a7ff", outline="#18344a")
        else:
            x = 560 if kind == "far" else 480
            y = 292
            self.canvas.create_oval(x - 30, y - 32, x + 30, y + 32, fill=color, stipple="gray25" if active else "", outline=outline, width=3)
            if active:
                self.canvas.create_rectangle(x - 20, y - 12, x + 20, y + 12, fill="#ffb445", outline="#523814")
        self.canvas.create_text(x, y - 44, text=label, fill="#20303a", font=("Segoe UI", 10, "bold"))
        if truth == "1" and active:
            self.canvas.create_text(x, y + 48, text="vehicle", fill="#206c49", font=("Segoe UI", 10, "bold"))
        elif truth == "0" and active:
            self.canvas.create_text(x, y + 48, text="check FP", fill="#a33232", font=("Segoe UI", 10, "bold"))

    def update_text(self, sample: dict[str, str] | None, rows: list[dict[str, str]], metrics: dict[str, float | int]) -> None:
        modified = time.strftime("%H:%M:%S", time.localtime(self.csv_path.stat().st_mtime)) if self.csv_path.exists() else "missing"
        self.title_var.set(f"WAIT LESS ROAD DIGITAL TWIN\nfile: {self.csv_path}\nupdated: {modified}\nrows: {len(rows)}")

        if not sample:
            self.sensor_var.set("Waiting for parsed A STATUS or B STATUS rows...")
            self.control_var.set("")
            self.metric_var.set("")
            self.raw_var.set("")
            return

        far = f"{sample.get('far_cm') or '?'} cm / {'OCC' if occupied(sample.get('far_occupied')) else 'FREE'}"
        near = f"{sample.get('near_cm') or '?'} cm / {'OCC' if occupied(sample.get('near_occupied')) else 'FREE'}"
        thresholds = "{}/{} cm".format(sample.get("far_threshold_cm") or "?", sample.get("near_threshold_cm") or "?")
        truth = sample.get("truth_any_vehicle") or "unlabeled"
        self.sensor_var.set(
            "LIVE SENSOR\n"
            f"node: {sample.get('node')}\n"
            f"thresholds F/N: {thresholds}\n"
            f"far : {far}\n"
            f"near: {near}\n"
            f"truth label: {truth}\n"
            f"note: {sample.get('truth_note') or '-'}"
        )

        self.control_var.set(
            "CONTROL / NETWORK\n"
            f"green: {sample.get('green_side') or '-'}\n"
            f"phase: {sample.get('phase') or '-'}\n"
            f"local queue: {sample.get('local_queue') or sample.get('queue') or '-'}\n"
            f"remote queue: {sample.get('remote_queue') or '-'}\n"
            f"source: {sample.get('remote_source') or sample.get('source') or '-'}\n"
            f"stale: {sample.get('remote_stale') or '-'}"
        )

        self.metric_var.set(
            "DETECTION METRICS\n"
            f"scored samples: {metrics['scored']}\n"
            f"TP/TN/FP/FN: {metrics['tp']}/{metrics['tn']}/{metrics['fp']}/{metrics['fn']}\n"
            f"accuracy: {metrics['accuracy']:.1f}%\n"
            f"false positives: {metrics['false_positive_rate']:.1f}%\n"
            f"false negatives: {metrics['false_negative_rate']:.1f}%"
        )
        self.raw_var.set(f"LAST SERIAL LINE\n{sample.get('raw_line', '')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show a live digital twin from a road-session CSV.")
    parser.add_argument("--csv", type=Path, help="CSV from tools/road_data_logger.py. Defaults to newest session.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = args.csv or latest_session_csv()
    if not csv_path:
        print("No CSV found. Start the logger first, or pass --csv path/to/session.csv")
        return 2
    root = tk.Tk()
    RoadDashboard(root, csv_path)
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
