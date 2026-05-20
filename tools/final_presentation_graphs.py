#!/usr/bin/env python3
"""Generate final presentation graphs from the validated road dataset."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT = Path(__file__).resolve().parents[1]
SIMULATION_DIR = ROOT / "simulation"
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from traffic_logic import AdaptiveController, Side, SideTelemetry, demand_score  # noqa: E402


DEFAULT_CSV = Path("data") / "data_readed" / "road_26-05-19_crossroads.csv"
DEFAULT_OUT = Path("data") / "data_readed" / "presentation_graphs"

NODE_A_MA = 121.4
NODE_B_MA = 174.8
NODE_A_MW = 609.4
NODE_B_MW = 875.7
BATTERY_MAH = 10000.0
BATTERY_EFFICIENCY = 0.75

COLORS = {
    "green": "#1B998B",
    "blue": "#2D6CDF",
    "yellow": "#F4B942",
    "red": "#D1495B",
    "dark": "#1F2933",
    "muted": "#6B7280",
    "light": "#EEF2F7",
    "orange": "#E76F51",
}


@dataclass(frozen=True)
class Metrics:
    tp: int
    tn: int
    fp: int
    fn: int
    radio: int
    stale: int
    duration_min: float
    samples: int
    fixed_wait_pressure: float
    adaptive_wait_pressure: float

    @property
    def accuracy(self) -> float:
        total = self.tp + self.tn + self.fp + self.fn
        return (self.tp + self.tn) / total * 100.0 if total else 0.0

    @property
    def false_positive_rate(self) -> float:
        denominator = self.fp + self.tn
        return self.fp / denominator * 100.0 if denominator else 0.0

    @property
    def false_negative_rate(self) -> float:
        denominator = self.fn + self.tp
        return self.fn / denominator * 100.0 if denominator else 0.0

    @property
    def lora_stale_rate(self) -> float:
        denominator = self.radio + self.stale
        return self.stale / denominator * 100.0 if denominator else 0.0

    @property
    def estimated_wait_reduction(self) -> float:
        if self.fixed_wait_pressure <= 0:
            return 0.0
        return (self.fixed_wait_pressure - self.adaptive_wait_pressure) / self.fixed_wait_pressure * 100.0


def parse_float(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value or "")
    except ValueError:
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(float(value or ""))
    except ValueError:
        return default


def occupied(row: dict[str, str], key: str) -> bool:
    return row.get(key) == "1"


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("node") in {"A", "B"}]
    rows.sort(key=lambda row: parse_float(row.get("elapsed_s")))
    return rows


def detection_bucket(row: dict[str, str]) -> str | None:
    truth = row.get("truth_any_vehicle", "")
    if truth not in {"0", "1"}:
        return None
    detected = occupied(row, "far_occupied") or occupied(row, "near_occupied")
    actual = truth == "1"
    if actual and detected:
        return "TP"
    if actual and not detected:
        return "FN"
    if not actual and detected:
        return "FP"
    return "TN"


def paired_frames(rows: list[dict[str, str]]) -> list[tuple[float, dict[str, str], dict[str, str], dict[str, str]]]:
    latest: dict[str, dict[str, str] | None] = {"A": None, "B": None}
    frames: list[tuple[float, dict[str, str], dict[str, str], dict[str, str]]] = []
    for row in rows:
        latest[row["node"]] = row
        if latest["A"] is None or latest["B"] is None:
            continue
        frames.append((parse_float(row.get("elapsed_s")), dict(latest["A"]), dict(latest["B"]), row))
    return frames


def side_a_queue(row_a: dict[str, str], row_b: dict[str, str]) -> int:
    return parse_int(row_a.get("local_queue") or row_a.get("queue") or row_b.get("remote_queue"))


def side_b_queue(row_b: dict[str, str]) -> int:
    return parse_int(row_b.get("local_queue"))


def telemetry_a(row_a: dict[str, str], row_b: dict[str, str], elapsed_s: float) -> SideTelemetry:
    return SideTelemetry(
        side=Side.A,
        far_occupied=occupied(row_a, "far_occupied"),
        near_occupied=occupied(row_a, "near_occupied"),
        incoming_count=parse_int(row_a.get("incoming_count")),
        passed_count=parse_int(row_a.get("passed_count")),
        estimated_queue=side_a_queue(row_a, row_b),
        timestamp_ms=int(elapsed_s * 1000),
    )


def telemetry_b(row_b: dict[str, str], elapsed_s: float) -> SideTelemetry:
    return SideTelemetry(
        side=Side.B,
        far_occupied=occupied(row_b, "far_occupied"),
        near_occupied=occupied(row_b, "near_occupied"),
        incoming_count=0,
        passed_count=0,
        estimated_queue=side_b_queue(row_b),
        timestamp_ms=int(elapsed_s * 1000),
    )


def fixed_time_state(elapsed_s: float) -> tuple[str, str]:
    cycle_s = 44.0
    phase_s = elapsed_s % cycle_s
    if phase_s < 20.0:
        return "A", "GREEN"
    if phase_s < 22.0:
        return "A", "YELLOW"
    if phase_s < 42.0:
        return "B", "GREEN"
    return "B", "YELLOW"


def waiting_pressure(side_a: SideTelemetry, side_b: SideTelemetry, green_side: str, phase: str) -> int:
    demand_a = demand_score(side_a)
    demand_b = demand_score(side_b)
    if phase != "GREEN":
        return demand_a + demand_b
    return demand_b if green_side == "A" else demand_a


def digital_twin_wait_comparison(rows: list[dict[str, str]]) -> tuple[float, float]:
    frames = paired_frames(rows)
    if len(frames) < 2:
        return 0.0, 0.0

    controller = AdaptiveController(min_green_ms=5000, max_green_ms=20000, yellow_ms=2000, margin=4)
    fixed_pressure = 0.0
    adaptive_pressure = 0.0
    last_elapsed = frames[0][0]

    for elapsed_s, row_a, row_b, _row in frames[1:]:
        dt_s = max(0.0, elapsed_s - last_elapsed)
        last_elapsed = elapsed_s

        side_a = telemetry_a(row_a, row_b, elapsed_s)
        side_b = telemetry_b(row_b, elapsed_s)

        fixed_side, fixed_phase = fixed_time_state(elapsed_s)
        fixed_pressure += waiting_pressure(side_a, side_b, fixed_side, fixed_phase) * dt_s

        decision = controller.update(side_a, side_b, int(elapsed_s * 1000))
        adaptive_pressure += waiting_pressure(side_a, side_b, decision.green_side.value, decision.phase.value) * dt_s

    return fixed_pressure, adaptive_pressure


def collect_metrics(rows: list[dict[str, str]]) -> Metrics:
    buckets = Counter(bucket for row in rows if (bucket := detection_bucket(row)) is not None)
    lora = Counter(row.get("remote_source") or row.get("source") or "" for row in rows)
    elapsed = [parse_float(row.get("elapsed_s")) for row in rows]
    fixed_pressure, adaptive_pressure = digital_twin_wait_comparison(rows)
    duration_min = (max(elapsed) - min(elapsed)) / 60.0 if elapsed else 0.0
    return Metrics(
        tp=buckets["TP"],
        tn=buckets["TN"],
        fp=buckets["FP"],
        fn=buckets["FN"],
        radio=lora["LORA_RADIO"],
        stale=lora["LORA_STALE"],
        duration_min=duration_min,
        samples=len(rows),
        fixed_wait_pressure=fixed_pressure,
        adaptive_wait_pressure=adaptive_pressure,
    )


def setup_figure(title: str, subtitle: str | None = None) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(13.33, 7.5), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    fig.suptitle(title, x=0.06, y=0.96, ha="left", fontsize=22, fontweight="bold", color=COLORS["dark"])
    if subtitle:
        fig.text(0.06, 0.905, subtitle, ha="left", fontsize=11, color=COLORS["muted"])
    return fig, ax


def finish(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def annotate_bars(ax: plt.Axes, values: list[float], suffix: str = "", precision: int = 0) -> None:
    for index, value in enumerate(values):
        label = f"{value:.{precision}f}{suffix}"
        ax.text(index, value, label, ha="center", va="bottom", fontsize=11, color=COLORS["dark"])


def graph_confusion_matrix(metrics: Metrics, out_dir: Path) -> None:
    fig, ax = setup_figure(
        "Detection Confusion Matrix",
        "Real crossroad labels compared with ultrasonic sensor occupancy.",
    )
    values = [[metrics.tp, metrics.fn], [metrics.fp, metrics.tn]]
    colors = [[COLORS["green"], COLORS["red"]], [COLORS["orange"], COLORS["blue"]]]
    labels = [["TP", "FN"], ["FP", "TN"]]
    for row in range(2):
        for col in range(2):
            rect = plt.Rectangle((col, row), 1, 1, facecolor=colors[row][col], alpha=0.92)
            ax.add_patch(rect)
            ax.text(
                col + 0.5,
                row + 0.44,
                labels[row][col],
                ha="center",
                va="center",
                fontsize=22,
                fontweight="bold",
                color="white",
            )
            ax.text(
                col + 0.5,
                row + 0.62,
                f"{values[row][col]} samples",
                ha="center",
                va="center",
                fontsize=14,
                color="white",
            )
    ax.set_xlim(0, 2)
    ax.set_ylim(2, 0)
    ax.set_xticks([0.5, 1.5], ["Detected vehicle", "Did not detect"])
    ax.set_yticks([0.5, 1.5], ["Vehicle present", "Road empty"])
    ax.tick_params(length=0, labelsize=13)
    for spine in ax.spines.values():
        spine.set_visible(False)
    finish(fig, out_dir / "01_detection_confusion_matrix.png")


def graph_detection_rates(metrics: Metrics, out_dir: Path) -> None:
    fig, ax = setup_figure(
        "Detection Quality",
        "False positives and false negatives are measured from real labelled road samples.",
    )
    labels = ["Accuracy", "False positive", "False negative"]
    values = [metrics.accuracy, metrics.false_positive_rate, metrics.false_negative_rate]
    bars = ax.bar(labels, values, color=[COLORS["green"], COLORS["orange"], COLORS["red"]], width=0.55)
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.grid(axis="y", color="#E5E7EB")
    ax.set_axisbelow(True)
    annotate_bars(ax, values, suffix="%", precision=1)
    ax.tick_params(axis="x", labelsize=13)
    ax.tick_params(axis="y", labelsize=11)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.bar_label(bars, labels=[f"{v:.1f}%" for v in values], padding=4, fontsize=12)
    finish(fig, out_dir / "02_detection_quality_rates.png")


def graph_energy(out_dir: Path, duration_min: float) -> None:
    fig, (ax_current, ax_power) = plt.subplots(1, 2, figsize=(13.33, 7.5), dpi=160)
    fig.patch.set_facecolor("white")
    fig.suptitle("Measured Energy Consumption", x=0.06, y=0.96, ha="left", fontsize=22, fontweight="bold", color=COLORS["dark"])
    fig.text(0.06, 0.905, "INA219 measurements from Node A and Node B, including sensors, LoRa, and LEDs.", ha="left", fontsize=11, color=COLORS["muted"])

    current_values = [NODE_A_MA, NODE_B_MA, NODE_A_MA + NODE_B_MA]
    power_values = [NODE_A_MW, NODE_B_MW, NODE_A_MW + NODE_B_MW]
    labels = ["Node A", "Node B", "Total"]

    ax_current.bar(labels, current_values, color=[COLORS["blue"], COLORS["green"], COLORS["dark"]], width=0.55)
    ax_current.set_title("Average Current", loc="left", fontweight="bold")
    ax_current.set_ylabel("mA")
    annotate_bars(ax_current, current_values, suffix=" mA", precision=1)

    ax_power.bar(labels, power_values, color=[COLORS["blue"], COLORS["green"], COLORS["dark"]], width=0.55)
    ax_power.set_title("Average Power", loc="left", fontweight="bold")
    ax_power.set_ylabel("mW")
    annotate_bars(ax_power, power_values, suffix=" mW", precision=1)

    used_mah = (NODE_A_MA + NODE_B_MA) * (duration_min / 60.0)
    runtime_h = (BATTERY_MAH * BATTERY_EFFICIENCY) / (NODE_A_MA + NODE_B_MA)
    fig.text(
        0.06,
        0.075,
        f"Road run energy: {used_mah:.1f} mAh over {duration_min:.1f} min. Estimated 10000 mAh runtime: {runtime_h:.1f} h at 75% usable capacity.",
        fontsize=12,
        color=COLORS["dark"],
    )
    for ax in (ax_current, ax_power):
        ax.grid(axis="y", color="#E5E7EB")
        ax.set_axisbelow(True)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=12)
    finish(fig, out_dir / "03_energy_consumption.png")


def graph_lora(metrics: Metrics, out_dir: Path) -> None:
    fig, ax = setup_figure(
        "LoRa Link Freshness",
        "Stale packets are detected so old remote data cannot keep a phantom queue alive.",
    )
    labels = ["Live LoRa", "Stale"]
    values = [metrics.radio, metrics.stale]
    total = sum(values)
    colors = [COLORS["green"], COLORS["red"]]
    ax.bar(labels, values, color=colors, width=0.5)
    ax.set_ylabel("Rows")
    ax.grid(axis="y", color="#E5E7EB")
    ax.set_axisbelow(True)
    for index, value in enumerate(values):
        pct = value / total * 100.0 if total else 0.0
        ax.text(index, value, f"{value}\n{pct:.1f}%", ha="center", va="bottom", fontsize=12, color=COLORS["dark"])
    ax.spines[["top", "right", "left"]].set_visible(False)
    finish(fig, out_dir / "04_lora_reliability.png")


def rolling_average(points: list[tuple[float, float]], window_s: float = 45.0) -> tuple[list[float], list[float]]:
    times: list[float] = []
    values: list[float] = []
    start = 0
    running = 0.0
    for end, (time_s, value) in enumerate(points):
        running += value
        while time_s - points[start][0] > window_s:
            running -= points[start][1]
            start += 1
        count = end - start + 1
        times.append(time_s / 60.0)
        values.append(running / count if count else 0.0)
    return times, values


def graph_traffic_demand(rows: list[dict[str, str]], out_dir: Path) -> None:
    frames = paired_frames(rows)
    points_a: list[tuple[float, float]] = []
    points_b: list[tuple[float, float]] = []
    for elapsed_s, row_a, row_b, _row in frames:
        points_a.append((elapsed_s, float(side_a_queue(row_a, row_b))))
        points_b.append((elapsed_s, float(side_b_queue(row_b))))

    time_a, queue_a = rolling_average(points_a)
    time_b, queue_b = rolling_average(points_b)
    fig, ax = setup_figure(
        "Real Road Queue Pressure Over Time",
        "45-second rolling average from Node A and Node B queue estimates.",
    )
    ax.plot(time_a, queue_a, color=COLORS["blue"], linewidth=2.5, label="Side A queue")
    ax.plot(time_b, queue_b, color=COLORS["green"], linewidth=2.5, label="Side B queue")
    ax.fill_between(time_a, queue_a, color=COLORS["blue"], alpha=0.10)
    ax.fill_between(time_b, queue_b, color=COLORS["green"], alpha=0.10)
    ax.set_xlabel("Minutes from start")
    ax.set_ylabel("Estimated queue")
    ax.grid(color="#E5E7EB")
    ax.legend(frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    finish(fig, out_dir / "05_traffic_demand_over_time.png")


def activation_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    previous: dict[tuple[str, str], bool] = {}
    for row in rows:
        node = row.get("node", "")
        if node not in {"A", "B"}:
            continue
        for sensor, key in (("far", "far_occupied"), ("near", "near_occupied")):
            current = occupied(row, key)
            previous_key = (node, sensor)
            if current and not previous.get(previous_key, False):
                counts[f"Node {node} {sensor}"] += 1
            previous[previous_key] = current
    return counts


def graph_activation_counts(rows: list[dict[str, str]], out_dir: Path) -> None:
    counts = activation_counts(rows)
    labels = ["Node A far", "Node A near", "Node B far", "Node B near"]
    values = [counts.get(label, 0) for label in labels]
    fig, ax = setup_figure(
        "Detected Vehicle Activations",
        "Rising-edge count of each ultrasonic occupancy signal during the real road run.",
    )
    ax.bar(labels, values, color=[COLORS["blue"], COLORS["blue"], COLORS["green"], COLORS["green"]], width=0.6)
    ax.set_ylabel("Activation count")
    ax.grid(axis="y", color="#E5E7EB")
    ax.set_axisbelow(True)
    annotate_bars(ax, [float(value) for value in values], precision=0)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="x", labelrotation=12)
    finish(fig, out_dir / "06_detected_vehicle_activations.png")


def graph_time_saving(metrics: Metrics, out_dir: Path) -> None:
    fig, ax = setup_figure(
        "Estimated Waiting-Time Reduction",
        "Digital-twin replay: real road demand compared under fixed-time control vs adaptive control.",
    )
    values = [metrics.fixed_wait_pressure, metrics.adaptive_wait_pressure]
    labels = ["Fixed-time baseline", "Adaptive controller"]
    ax.bar(labels, values, color=[COLORS["muted"], COLORS["green"]], width=0.52)
    ax.set_ylabel("Waiting pressure units")
    ax.grid(axis="y", color="#E5E7EB")
    ax.set_axisbelow(True)
    for index, value in enumerate(values):
        ax.text(index, value, f"{value:,.0f}", ha="center", va="bottom", fontsize=12, color=COLORS["dark"])
    ax.text(
        0.5,
        max(values) * 0.72,
        f"{metrics.estimated_wait_reduction:.1f}% lower\nwaiting pressure",
        ha="center",
        va="center",
        fontsize=22,
        fontweight="bold",
        color=COLORS["green"],
    )
    ax.spines[["top", "right", "left"]].set_visible(False)
    finish(fig, out_dir / "07_time_saving_estimate.png")


def graph_digital_twin_pipeline(out_dir: Path) -> None:
    fig, ax = setup_figure(
        "Real Data To Digital Twin",
        "The simulator is not standalone anymore: real sensor data drives the replay.",
    )
    ax.axis("off")
    boxes = [
        ("Real crossroad", "phone video + truth labels"),
        ("ESP32 nodes", "4 ultrasonic sensors + LoRa"),
        ("CSV dataset", "distance, queue, labels, energy"),
        ("Evidence graphs", "FP/FN, LoRa, energy, demand"),
        ("Simulator replay", "cars generated from real queue pressure"),
    ]
    xs = [0.08, 0.29, 0.50, 0.71, 0.90]
    for index, ((title, body), x) in enumerate(zip(boxes, xs)):
        ax.text(
            x,
            0.55,
            f"{title}\n{body}",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color=COLORS["dark"],
            bbox=dict(boxstyle="round,pad=0.55,rounding_size=0.08", facecolor=COLORS["light"], edgecolor="#CBD5E1"),
        )
        if index < len(boxes) - 1:
            ax.annotate(
                "",
                xy=(xs[index + 1] - 0.09, 0.55),
                xytext=(x + 0.09, 0.55),
                xycoords=ax.transAxes,
                arrowprops=dict(arrowstyle="->", color=COLORS["dark"], linewidth=2),
            )
    finish(fig, out_dir / "08_digital_twin_pipeline.png")


def write_summary(metrics: Metrics, out_dir: Path) -> None:
    used_mah = (NODE_A_MA + NODE_B_MA) * (metrics.duration_min / 60.0)
    runtime_h = (BATTERY_MAH * BATTERY_EFFICIENCY) / (NODE_A_MA + NODE_B_MA)
    lines = [
        "Wait Less final presentation metrics",
        "------------------------------------",
        f"Road CSV samples: {metrics.samples}",
        f"Road CSV duration: {metrics.duration_min:.1f} min",
        f"TP/TN/FP/FN: {metrics.tp}/{metrics.tn}/{metrics.fp}/{metrics.fn}",
        f"Accuracy: {metrics.accuracy:.1f}%",
        f"False positive rate: {metrics.false_positive_rate:.1f}%",
        f"False negative rate: {metrics.false_negative_rate:.1f}%",
        f"LoRa stale rate: {metrics.lora_stale_rate:.1f}%",
        f"Node A average current: {NODE_A_MA:.1f} mA",
        f"Node B average current: {NODE_B_MA:.1f} mA",
        f"Total average current: {NODE_A_MA + NODE_B_MA:.1f} mA",
        f"Road run energy: {used_mah:.1f} mAh",
        f"Estimated 10000 mAh runtime: {runtime_h:.1f} h",
        f"Digital-twin waiting-pressure reduction: {metrics.estimated_wait_reduction:.1f}%",
        "",
        "Time-saving graph wording:",
        "Digital-twin estimate using real road demand. It compares the same CSV demand under fixed-time control and adaptive control.",
    ]
    (out_dir / "presentation_metrics.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate(csv_path: Path, out_dir: Path) -> Metrics:
    rows = load_rows(csv_path)
    metrics = collect_metrics(rows)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph_confusion_matrix(metrics, out_dir)
    graph_detection_rates(metrics, out_dir)
    graph_energy(out_dir, metrics.duration_min)
    graph_lora(metrics, out_dir)
    graph_traffic_demand(rows, out_dir)
    graph_activation_counts(rows, out_dir)
    graph_time_saving(metrics, out_dir)
    graph_digital_twin_pipeline(out_dir)
    write_summary(metrics, out_dir)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate final presentation graph PNGs.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    metrics = generate(args.csv, args.out_dir)
    print("Generated final presentation graphs")
    print("-----------------------------------")
    print(f"Output directory: {args.out_dir}")
    print(f"Accuracy: {metrics.accuracy:.1f}%")
    print(f"LoRa stale rate: {metrics.lora_stale_rate:.1f}%")
    print(f"Digital-twin waiting-pressure reduction: {metrics.estimated_wait_reduction:.1f}%")


if __name__ == "__main__":
    main()
