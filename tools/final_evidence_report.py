#!/usr/bin/env python3
"""Generate a final evidence dashboard/report from a road-session CSV."""

from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Template


@dataclass(frozen=True)
class DetectionMetrics:
    tp: int
    tn: int
    fp: int
    fn: int

    @property
    def scored(self) -> int:
        return self.tp + self.tn + self.fp + self.fn

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.scored * 100.0 if self.scored else 0.0

    @property
    def false_positive_rate(self) -> float:
        return self.fp / (self.fp + self.tn) * 100.0 if (self.fp + self.tn) else 0.0

    @property
    def false_negative_rate(self) -> float:
        return self.fn / (self.fn + self.tp) * 100.0 if (self.fn + self.tp) else 0.0


@dataclass(frozen=True)
class EnergyMetrics:
    duration_min: float
    node_a_ma: float
    node_b_ma: float
    total_ma: float
    used_mah: float
    used_wh: float
    usable_battery_mah: float
    battery_life_h: float


@dataclass(frozen=True)
class SimulatorMetrics:
    frames: int
    green_match_rate: float
    phase_match_rate: float


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


def pct(value: float) -> str:
    return f"{value:.1f}%"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def node_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("node") in {"A", "B"}]


def occupied(row: dict[str, str]) -> bool:
    return row.get("far_occupied") == "1" or row.get("near_occupied") == "1"


def detection_metrics(rows: list[dict[str, str]]) -> DetectionMetrics:
    tp = tn = fp = fn = 0
    for row in rows:
        truth = row.get("truth_any_vehicle", "")
        if truth not in {"0", "1"}:
            continue

        actual = truth == "1"
        detected = occupied(row)
        if actual and detected:
            tp += 1
        elif actual and not detected:
            fn += 1
        elif not actual and detected:
            fp += 1
        else:
            tn += 1

    return DetectionMetrics(tp=tp, tn=tn, fp=fp, fn=fn)


def duration_minutes(rows: list[dict[str, str]]) -> float:
    if len(rows) < 2:
        return 0.0
    first = parse_float(rows[0].get("elapsed_s"))
    last = parse_float(rows[-1].get("elapsed_s"))
    return max(0.0, (last - first) / 60.0)


def first_last_time(rows: list[dict[str, str]]) -> tuple[str, str]:
    if not rows:
        return "-", "-"
    return rows[0].get("timestamp_iso") or "-", rows[-1].get("timestamp_iso") or "-"


def lora_counts(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter((row.get("remote_source") or row.get("source") or "UNKNOWN") for row in rows)


def energy_metrics(
    duration_min: float,
    node_a_ma: float,
    node_b_ma: float,
    battery_mah: float,
    battery_efficiency: float,
    voltage_v: float,
) -> EnergyMetrics:
    duration_h = duration_min / 60.0
    total_ma = node_a_ma + node_b_ma
    used_mah = total_ma * duration_h
    used_wh = used_mah / 1000.0 * voltage_v
    usable_battery_mah = battery_mah * battery_efficiency
    battery_life_h = usable_battery_mah / total_ma if total_ma > 0 else 0.0
    return EnergyMetrics(
        duration_min=duration_min,
        node_a_ma=node_a_ma,
        node_b_ma=node_b_ma,
        total_ma=total_ma,
        used_mah=used_mah,
        used_wh=used_wh,
        usable_battery_mah=usable_battery_mah,
        battery_life_h=battery_life_h,
    )


def simulator_metrics(csv_path: Path) -> SimulatorMetrics | None:
    simulation_dir = Path(__file__).resolve().parents[1] / "simulation"
    sys.path.insert(0, str(simulation_dir))
    try:
        import visual_simulator_real_data as replay

        frames = replay.load_frames(csv_path)
        comparison = replay.compare_controller(frames)
        return SimulatorMetrics(
            frames=len(frames),
            green_match_rate=comparison.green_match_rate,
            phase_match_rate=comparison.phase_match_rate,
        )
    except Exception:
        return None
    finally:
        try:
            sys.path.remove(str(simulation_dir))
        except ValueError:
            pass


def queue_series(rows: list[dict[str, str]], node: str) -> list[tuple[float, int]]:
    points: list[tuple[float, int]] = []
    for row in rows:
        if row.get("node") != node:
            continue
        queue = parse_int(row.get("local_queue") or row.get("queue"))
        points.append((parse_float(row.get("elapsed_s")), queue))
    return points


def downsample(points: list[tuple[float, int]], limit: int = 140) -> list[tuple[float, int]]:
    if len(points) <= limit:
        return points
    step = max(1, len(points) // limit)
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def polyline(points: list[tuple[float, int]], start: float, end: float, max_y: int, color: str) -> str:
    if not points or end <= start or max_y <= 0:
        return ""

    coords = []
    for elapsed_s, value in downsample(points):
        x = 44 + (elapsed_s - start) / (end - start) * 652
        y = 176 - (value / max_y * 132)
        coords.append(f"{x:.1f},{y:.1f}")

    return f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />'


def queue_svg(rows: list[dict[str, str]]) -> str:
    side_a = queue_series(rows, "A")
    side_b = queue_series(rows, "B")
    all_points = side_a + side_b
    if not all_points:
        return "<p>No queue samples found.</p>"

    start = min(point[0] for point in all_points)
    end = max(point[0] for point in all_points)
    max_y = max(1, max(point[1] for point in all_points))
    return f"""
<svg class="queue-chart" viewBox="0 0 740 220" role="img" aria-label="Queue estimates over time">
  <rect x="0" y="0" width="740" height="220" rx="10" fill="#f8fafc" />
  <line x1="44" y1="176" x2="696" y2="176" stroke="#94a3b8" stroke-width="1.5" />
  <line x1="44" y1="44" x2="44" y2="176" stroke="#94a3b8" stroke-width="1.5" />
  <text x="44" y="200" fill="#64748b" font-size="12">start</text>
  <text x="648" y="200" fill="#64748b" font-size="12">end</text>
  <text x="16" y="50" fill="#64748b" font-size="12">{max_y}</text>
  {polyline(side_a, start, end, max_y, "#2563eb")}
  {polyline(side_b, start, end, max_y, "#f97316")}
  <circle cx="540" cy="24" r="5" fill="#2563eb" /><text x="552" y="28" fill="#334155" font-size="13">Side A queue</text>
  <circle cx="640" cy="24" r="5" fill="#f97316" /><text x="652" y="28" fill="#334155" font-size="13">Side B</text>
</svg>
""".strip()


def bar_row(label: str, value: int, total: int, color: str) -> str:
    percentage = value / total * 100.0 if total else 0.0
    return (
        '<div class="bar-row">'
        f'<span>{html.escape(label)}</span>'
        '<div class="bar-track">'
        f'<i style="width:{percentage:.1f}%;background:{color}"></i>'
        "</div>"
        f"<strong>{value} ({percentage:.1f}%)</strong>"
        "</div>"
    )


def metric_card(label: str, value: str, note: str = "") -> str:
    note_html = f"<small>{html.escape(note)}</small>" if note else ""
    return f'<section class="metric"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong>{note_html}</section>'


def most_common_text(rows: list[dict[str, str]], key: str, fallback: str = "-") -> str:
    values = [row.get(key, "") for row in rows if row.get(key, "")]
    if not values:
        return fallback
    return Counter(values).most_common(1)[0][0]


def label_count(rows: list[dict[str, str]], value: str) -> int:
    return sum(1 for row in rows if row.get("truth_any_vehicle") == value)


def render_markdown(
    csv_path: Path,
    rows: list[dict[str, str]],
    metrics: DetectionMetrics,
    lora: Counter[str],
    energy: EnergyMetrics,
    simulator: SimulatorMetrics | None,
    replay_command: str,
    energy_note: str,
) -> str:
    first_time, last_time = first_last_time(rows)
    stale = lora["LORA_STALE"]
    radio = lora["LORA_RADIO"]
    lora_total = sum(lora.values())
    stale_rate = stale / lora_total * 100.0 if lora_total else 0.0
    radio_rate = radio / lora_total * 100.0 if lora_total else 0.0
    far_threshold = most_common_text(rows, "far_threshold_cm")
    near_threshold = most_common_text(rows, "near_threshold_cm")
    vehicle_labels = label_count(rows, "1")
    empty_labels = label_count(rows, "0")
    simulator_lines = [
        "## Digital Twin Replay",
        "",
        "The same real road CSV is used as the traffic source for the visual simulator. The simulator keeps normal car movement: cars enter from outside the crossroad, pass the far and near sensor zones, and then the visual detections are compared with the real detections shown in the panel.",
        "",
        "```powershell",
        replay_command,
        "```",
    ]
    if simulator:
        simulator_lines.extend(
            [
                "",
                f"- Paired replay frames: {simulator.frames}",
                f"- Real firmware vs simulator green-side match: {simulator.green_match_rate:.1f}%",
                f"- Real firmware vs simulator phase match: {simulator.phase_match_rate:.1f}%",
            ]
        )

    return "\n".join(
        [
            "# Wait Less Final Evidence Report",
            "",
            f"Source CSV: `{csv_path}`",
            "",
            "## Data Collection",
            "",
            f"- First sample: {first_time}",
            f"- Last sample: {last_time}",
            f"- CSV duration: {energy.duration_min:.1f} min",
            f"- ESP32 node samples: {len(rows)}",
            "",
            "## Detection Quality",
            "",
            f"- TP/TN/FP/FN: {metrics.tp}/{metrics.tn}/{metrics.fp}/{metrics.fn}",
            f"- Accuracy: {metrics.accuracy:.1f}%",
            f"- False positive rate: {metrics.false_positive_rate:.1f}%",
            f"- False negative rate: {metrics.false_negative_rate:.1f}%",
            "",
            "## Sensor Reliability Explanation",
            "",
            f"- The road run used a fixed ultrasonic threshold of `{far_threshold} cm` on the far sensors and `{near_threshold} cm` on the near sensors.",
            f"- The reliability numbers are based on real road labels: `{vehicle_labels}` samples were labelled as vehicle present and `{empty_labels}` samples were labelled as empty.",
            f"- False positives were measured from the CSV, not guessed: `{metrics.fp}` empty-road samples were still detected as occupied.",
            f"- False negatives were also measured: `{metrics.fn}` vehicle-present samples were missed by the sensors.",
            "- Reliability response after the road test: the firmware now supports per-sensor threshold tuning, median-of-3 ultrasonic distance filtering, and 2-sample occupancy debouncing.",
            "- Why this tackles the measured problem: median filtering rejects one-sample distance spikes, while debouncing prevents a single noisy reading from immediately changing the vehicle state.",
            "- Hardware robustness response: the firmware now also reports sensor health, so repeated invalid ultrasonic readings become `WARN`/`FAIL` instead of silently looking like an empty road.",
            "- Next validation step: collect a second road CSV with the new `sensor_filter=median3_debounce2` and `sensor_health` log fields, then compare FP/FN against this baseline.",
            "",
            "## LoRa Reliability",
            "",
            f"- LORA_RADIO rows: {radio} ({radio_rate:.1f}%)",
            f"- LORA_STALE rows: {stale} ({stale_rate:.1f}%)",
            "",
            "## Energy Measurement / Estimate",
            "",
            f"- Node A average current: {energy.node_a_ma:.1f} mA",
            f"- Node B average current: {energy.node_b_ma:.1f} mA",
            f"- Total average current: {energy.total_ma:.1f} mA",
            f"- Energy used during this road run: {energy.used_mah:.1f} mAh ({energy.used_wh:.2f} Wh at 5 V)",
            f"- Estimated 10000 mAh power-bank runtime: {energy.battery_life_h:.1f} h",
            f"- {energy_note}",
            "",
            *simulator_lines,
            "",
            "## One-Sentence Evidence Claim",
            "",
            "This project uses real ultrasonic sensors on a real crossroad, measures false positives and false negatives from labelled road data, estimates field energy use, and replays the collected CSV inside the digital-twin simulator.",
            "",
        ]
    )


def render_html(
    csv_path: Path,
    rows: list[dict[str, str]],
    metrics: DetectionMetrics,
    lora: Counter[str],
    energy: EnergyMetrics,
    simulator: SimulatorMetrics | None,
    replay_command: str,
    energy_note: str,
) -> str:
    first_time, last_time = first_last_time(rows)
    stale = lora["LORA_STALE"]
    radio = lora["LORA_RADIO"]
    lora_total = sum(lora.values())
    stale_rate = stale / lora_total * 100.0 if lora_total else 0.0
    radio_rate = radio / lora_total * 100.0 if lora_total else 0.0
    simulator_detail = "Simulator comparison was not available."
    if simulator:
        simulator_detail = (
            f"{simulator.frames} paired replay frames, "
            f"{simulator.green_match_rate:.1f}% green-side match, "
            f"{simulator.phase_match_rate:.1f}% phase match."
        )

    cards = "\n".join(
        [
            metric_card("CSV duration", f"{energy.duration_min:.1f} min", f"{first_time} to {last_time}"),
            metric_card("ESP32 samples", f"{len(rows)}", "Node A + Node B rows"),
            metric_card("Accuracy", pct(metrics.accuracy), f"{metrics.scored} labelled samples"),
            metric_card("False positive rate", pct(metrics.false_positive_rate), f"{metrics.fp} false positives"),
            metric_card("False negative rate", pct(metrics.false_negative_rate), f"{metrics.fn} false negatives"),
            metric_card("LoRa stale", pct(stale_rate), f"{stale} of {lora_total} rows"),
            metric_card("Energy used", f"{energy.used_mah:.1f} mAh", f"{energy.used_wh:.2f} Wh at 5 V"),
            metric_card("Battery estimate", f"{energy.battery_life_h:.1f} h", "10000 mAh power bank at 75% usable capacity"),
        ]
    )

    lora_bars = "\n".join(
        [
            bar_row("LORA_RADIO", radio, lora_total, "#16a34a"),
            bar_row("LORA_STALE", stale, lora_total, "#dc2626"),
        ]
    )
    far_threshold = most_common_text(rows, "far_threshold_cm")
    near_threshold = most_common_text(rows, "near_threshold_cm")
    vehicle_labels = label_count(rows, "1")
    empty_labels = label_count(rows, "0")

    template = Template(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wait Less Final Evidence Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #15202b;
      --muted: #64748b;
      --line: #dbe3ef;
      --paper: #f6f8fb;
      --panel: #ffffff;
      --green: #16a34a;
      --orange: #f97316;
      --blue: #2563eb;
      --red: #dc2626;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background: var(--paper);
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }
    header {
      border-bottom: 1px solid var(--line);
      padding-bottom: 22px;
      margin-bottom: 22px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 38px;
      line-height: 1.05;
      letter-spacing: 0;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 20px;
      letter-spacing: 0;
    }
    p {
      color: var(--muted);
      line-height: 1.5;
      margin: 0;
    }
    code {
      background: #eaf0f8;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 2px 5px;
      color: #0f172a;
    }
    pre {
      white-space: pre-wrap;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 8px;
      padding: 14px 16px;
      overflow: auto;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .metric, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    }
    .metric {
      padding: 15px;
      min-height: 116px;
    }
    .metric span, .metric small {
      display: block;
      color: var(--muted);
    }
    .metric strong {
      display: block;
      margin: 9px 0 7px;
      font-size: 26px;
      line-height: 1;
    }
    .panel {
      padding: 18px;
      margin-top: 14px;
    }
    .two {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 8px;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 12px;
      text-align: center;
    }
    th {
      background: #edf3fb;
      color: #334155;
      font-weight: 700;
    }
    td strong {
      display: block;
      font-size: 24px;
    }
    .good { color: var(--green); }
    .bad { color: var(--red); }
    .bar-row {
      display: grid;
      grid-template-columns: 110px 1fr 130px;
      gap: 10px;
      align-items: center;
      margin: 12px 0;
      color: #334155;
    }
    .bar-track {
      height: 16px;
      background: #e2e8f0;
      border-radius: 999px;
      overflow: hidden;
    }
    .bar-track i {
      display: block;
      height: 100%;
      border-radius: 999px;
    }
    .claim {
      font-size: 18px;
      color: #243746;
      background: #eef7f0;
      border-color: #bbdfc5;
    }
    .queue-chart {
      width: 100%;
      height: auto;
      margin-top: 8px;
    }
    .footer-note {
      margin-top: 12px;
      font-size: 13px;
      color: var(--muted);
    }
    @media (max-width: 900px) {
      .grid, .two { grid-template-columns: 1fr; }
      h1 { font-size: 30px; }
      .bar-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Wait Less Final Evidence Dashboard</h1>
      <p>Real crossroad IoT data, detection reliability, LoRa status, energy estimate, and digital twin replay link.</p>
      <p class="footer-note">Source CSV: <code>$csv_path</code></p>
    </header>

    <section class="grid">
      $cards
    </section>

    <section class="two">
      <article class="panel">
        <h2>Detection Confusion Matrix</h2>
        <table>
          <thead>
            <tr><th></th><th>Sensor detected vehicle</th><th>Sensor did not detect</th></tr>
          </thead>
          <tbody>
            <tr><th>Vehicle present</th><td><strong class="good">$tp</strong>TP</td><td><strong class="bad">$fn</strong>FN</td></tr>
            <tr><th>Road empty</th><td><strong class="bad">$fp</strong>FP</td><td><strong class="good">$tn</strong>TN</td></tr>
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h2>Why The Sensor Result Is Credible</h2>
        <p>The road test used fixed ultrasonic thresholds: <strong>$far_threshold cm</strong> for far sensors and <strong>$near_threshold cm</strong> for near sensors.</p>
        <p>The false positives are measured from labelled real road samples, not guessed: <strong>$fp</strong> empty-road samples were detected as occupied.</p>
        <p>The labels also include <strong>$vehicle_labels</strong> vehicle-present samples and <strong>$empty_labels</strong> empty-road samples.</p>
        <p class="footer-note">Reliability response now implemented in firmware: per-sensor threshold commands, median3 distance filtering, debounce2 occupancy state, and sensor-health WARN/FAIL diagnostics. Next field run should compare FP/FN with this filter enabled.</p>
      </article>
    </section>

    <section class="two">
      <article class="panel">
        <h2>LoRa Communication</h2>
        $lora_bars
        <p>$radio_rate of rows had live LoRa data; $stale_rate were stale. This is the field communication evidence for the two-node setup.</p>
      </article>
      <article class="panel">
        <h2>Detection Interpretation</h2>
        <p>The reported <strong>$accuracy</strong> accuracy comes from comparing the sensor state against manually labelled real crossroad observations.</p>
        <p>False negative rate was <strong>$fnr</strong>, meaning most vehicle-present samples were detected. False positive rate was <strong>$fpr</strong>, which is the main target for future tuning.</p>
      </article>
    </section>

    <section class="panel">
      <h2>Queue Trend From Real Road CSV</h2>
      $queue_svg
      <p class="footer-note">The visual simulator uses these real queue estimates as traffic pressure, while still drawing cars that enter from outside and pass the far/near sensor zones normally.</p>
    </section>

    <section class="two">
      <article class="panel">
        <h2>Energy Measurement / Estimate</h2>
        <p>Node A: <strong>$node_a_ma mA</strong>, Node B: <strong>$node_b_ma mA</strong>, total: <strong>$total_ma mA</strong>.</p>
        <p>For this $duration_min minute road run, estimated usage is <strong>$used_mah mAh</strong> or <strong>$used_wh Wh</strong> at 5 V.</p>
        <p class="footer-note">$energy_note</p>
      </article>

      <article class="panel">
        <h2>Digital Twin Replay</h2>
        <p>$simulator_detail</p>
        <pre>$replay_command</pre>
      </article>
    </section>

    <section class="panel claim">
      This project uses real ultrasonic sensors on a real crossroad, measures false positives and false negatives from labelled road data, estimates field energy use, and replays the collected CSV inside the digital-twin simulator.
    </section>
  </main>
</body>
</html>
"""
    )
    return template.safe_substitute(
        cards=cards,
        accuracy=pct(metrics.accuracy),
        csv_path=html.escape(str(csv_path)),
        duration_min=f"{energy.duration_min:.1f}",
        energy_note=html.escape(energy_note),
        empty_labels=empty_labels,
        far_threshold=html.escape(far_threshold),
        fn=metrics.fn,
        fnr=pct(metrics.false_negative_rate),
        fp=metrics.fp,
        fpr=pct(metrics.false_positive_rate),
        lora_bars=lora_bars,
        near_threshold=html.escape(near_threshold),
        node_a_ma=f"{energy.node_a_ma:.1f}",
        node_b_ma=f"{energy.node_b_ma:.1f}",
        queue_svg=queue_svg(rows),
        radio_rate=pct(radio_rate),
        replay_command=html.escape(replay_command),
        simulator_detail=html.escape(simulator_detail),
        stale_rate=pct(stale_rate),
        tn=metrics.tn,
        total_ma=f"{energy.total_ma:.1f}",
        tp=metrics.tp,
        used_mah=f"{energy.used_mah:.1f}",
        used_wh=f"{energy.used_wh:.2f}",
        vehicle_labels=vehicle_labels,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate final Wait Less evidence report files.")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--out-html", type=Path)
    parser.add_argument("--out-md", type=Path)
    parser.add_argument("--node-a-ma", type=float, default=120.0)
    parser.add_argument("--node-b-ma", type=float, default=160.0)
    parser.add_argument("--battery-mah", type=float, default=10000.0)
    parser.add_argument("--battery-efficiency", type=float, default=0.75)
    parser.add_argument("--voltage-v", type=float, default=5.0)
    parser.add_argument(
        "--energy-note",
        default="Current values are estimates unless measured with an INA219, USB power meter, or multimeter.",
    )
    parser.add_argument("--sim-speed", type=float, default=1.5)
    parser.add_argument("--queue-scale", type=float, default=3.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = node_rows(read_rows(args.csv))
    if not rows:
        print(f"No Node A/B samples found in {args.csv}")
        return 2

    metrics = detection_metrics(rows)
    lora = lora_counts(rows)
    duration_min = duration_minutes(rows)
    energy = energy_metrics(
        duration_min=duration_min,
        node_a_ma=args.node_a_ma,
        node_b_ma=args.node_b_ma,
        battery_mah=args.battery_mah,
        battery_efficiency=args.battery_efficiency,
        voltage_v=args.voltage_v,
    )
    simulator = simulator_metrics(args.csv)
    replay_command = (
        "python simulation\\visual_simulator_real_data.py "
        f"--csv {args.csv} --speed {args.sim_speed:g} --queue-scale {args.queue_scale:g}"
    )

    out_html = args.out_html or args.csv.with_name(f"{args.csv.stem}_evidence_dashboard.html")
    out_md = args.out_md or args.csv.with_name(f"{args.csv.stem}_evidence_report.md")

    html_text = render_html(args.csv, rows, metrics, lora, energy, simulator, replay_command, args.energy_note)
    md_text = render_markdown(args.csv, rows, metrics, lora, energy, simulator, replay_command, args.energy_note)

    out_html.write_text(html_text, encoding="utf-8")
    out_md.write_text(md_text, encoding="utf-8")

    print("Wait Less final evidence package")
    print("--------------------------------")
    print(f"CSV duration: {duration_min:.1f} min")
    print(f"ESP32 samples: {len(rows)}")
    print(f"TP/TN/FP/FN: {metrics.tp}/{metrics.tn}/{metrics.fp}/{metrics.fn}")
    print(f"Accuracy: {metrics.accuracy:.1f}%")
    print(f"False positive rate: {metrics.false_positive_rate:.1f}%")
    print(f"False negative rate: {metrics.false_negative_rate:.1f}%")
    print(f"LoRa stale: {lora['LORA_STALE']} of {sum(lora.values())} rows")
    print(f"Energy used: {energy.used_mah:.1f} mAh ({energy.used_wh:.2f} Wh)")
    print(f"Wrote {out_html}")
    print(f"Wrote {out_md}")
    print()
    print(replay_command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
