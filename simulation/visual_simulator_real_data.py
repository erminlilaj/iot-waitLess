#!/usr/bin/env python3
"""Run the existing visual simulator with real road CSV traffic counts.

This keeps the polished four-way simulator and changes only the traffic source:
queue estimates and sensor states come from the real ESP32 road dataset.
"""

from __future__ import annotations

import argparse
import csv
import tkinter as tk
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import visual_simulator as base
from traffic_logic import AdaptiveController, Side, SideTelemetry, demand_score


DEFAULT_CSV = Path("data") / "data_readed" / "road_26-05-19_crossroads.csv"
DEFAULT_REPLAY_SPEED = 1.5
DEFAULT_QUEUE_SCALE = 3.0
DEFAULT_MAX_CARS_PER_DIRECTION = 8
MAX_SIDE_SPAWN_RATE = 1.45
MOTION_SPEED_LIMIT = 1.25
MIN_SENSOR_ACTIVE_RATE = 0.18


@dataclass(frozen=True)
class RoadFrame:
    elapsed_s: float
    row_a: dict[str, str]
    row_b: dict[str, str]
    controller_row: dict[str, str]


@dataclass(frozen=True)
class ComparisonStats:
    samples: int
    green_matches: int
    phase_matches: int

    @property
    def green_match_rate(self) -> float:
        return self.green_matches / self.samples * 100.0 if self.samples else 0.0

    @property
    def phase_match_rate(self) -> float:
        return self.phase_matches / self.samples * 100.0 if self.samples else 0.0


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


def queue_for_row(row: dict[str, str], side: Side) -> int:
    if side == Side.A:
        return parse_int(row.get("queue") or row.get("local_queue"))
    return parse_int(row.get("local_queue"))


def side_a_queue_for_frame(frame: RoadFrame) -> int:
    return parse_int(frame.row_a.get("local_queue") or frame.row_a.get("queue") or frame.row_b.get("remote_queue"))


def side_b_queue_for_frame(frame: RoadFrame) -> int:
    return parse_int(frame.row_b.get("local_queue"))


def telemetry_from_row(row: dict[str, str], side: Side, timestamp_ms: int) -> SideTelemetry:
    return SideTelemetry(
        side=side,
        far_occupied=occupied(row, "far_occupied"),
        near_occupied=occupied(row, "near_occupied"),
        incoming_count=parse_int(row.get("incoming_count")),
        passed_count=parse_int(row.get("passed_count")),
        estimated_queue=queue_for_row(row, side),
        timestamp_ms=timestamp_ms,
    )


def telemetry_from_frame(frame: RoadFrame, side: Side, timestamp_ms: int) -> SideTelemetry:
    if side == Side.A:
        return SideTelemetry(
            side=Side.A,
            far_occupied=occupied(frame.row_a, "far_occupied"),
            near_occupied=occupied(frame.row_a, "near_occupied"),
            incoming_count=parse_int(frame.row_a.get("incoming_count")),
            passed_count=parse_int(frame.row_a.get("passed_count")),
            estimated_queue=side_a_queue_for_frame(frame),
            timestamp_ms=timestamp_ms,
        )

    return SideTelemetry(
        side=Side.B,
        far_occupied=occupied(frame.row_b, "far_occupied"),
        near_occupied=occupied(frame.row_b, "near_occupied"),
        incoming_count=parse_int(frame.row_b.get("incoming_count")),
        passed_count=parse_int(frame.row_b.get("passed_count")),
        estimated_queue=side_b_queue_for_frame(frame),
        timestamp_ms=timestamp_ms,
    )


def load_frames(path: Path) -> list[RoadFrame]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("node") in {"A", "B"}]

    rows.sort(key=lambda row: parse_float(row.get("elapsed_s")))
    latest: dict[str, dict[str, str] | None] = {"A": None, "B": None}
    frames: list[RoadFrame] = []

    for row in rows:
        latest[row["node"]] = row
        if latest["A"] is None or latest["B"] is None:
            continue
        frames.append(
            RoadFrame(
                elapsed_s=parse_float(row.get("elapsed_s")),
                row_a=dict(latest["A"]),
                row_b=dict(latest["B"]),
                controller_row=dict(row),
            )
        )

    return frames


def detection_bucket(row: dict[str, str]) -> str:
    truth = row.get("truth_any_vehicle", "")
    if truth not in {"0", "1"}:
        return "-"

    detected = occupied(row, "far_occupied") or occupied(row, "near_occupied")
    actual = truth == "1"
    if actual and detected:
        return "TP"
    if actual and not detected:
        return "FN"
    if not actual and detected:
        return "FP"
    return "TN"


def unique_data_rows(frames: list[RoadFrame]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for frame in frames:
        for row in (frame.row_a, frame.row_b):
            key = (
                row.get("timestamp_iso", ""),
                row.get("elapsed_s", ""),
                row.get("node", ""),
                row.get("raw_line", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    return rows


def dataset_summary(frames: list[RoadFrame]) -> str:
    if not frames:
        return "No frames loaded."

    rows = unique_data_rows(frames)
    lora = Counter((row.get("remote_source") or row.get("source") or "") for row in rows)
    buckets = Counter(detection_bucket(row) for row in rows)
    total_scored = buckets["TP"] + buckets["TN"] + buckets["FP"] + buckets["FN"]
    accuracy = (buckets["TP"] + buckets["TN"]) / total_scored * 100.0 if total_scored else 0.0
    duration = frames[-1].elapsed_s - frames[0].elapsed_s
    return "\n".join(
        [
            "Real-data visual simulator dataset",
            "----------------------------------",
            f"Paired replay frames: {len(frames)}",
            f"Raw node samples: {len(rows)}",
            f"Duration: {duration / 60.0:.1f} min",
            f"LORA_RADIO rows: {lora['LORA_RADIO']}",
            f"LORA_STALE rows: {lora['LORA_STALE']}",
            f"TP/TN/FP/FN: {buckets['TP']}/{buckets['TN']}/{buckets['FP']}/{buckets['FN']}",
            f"Detection accuracy: {accuracy:.1f}%",
        ]
    )


def compare_controller(frames: list[RoadFrame]) -> ComparisonStats:
    controller = AdaptiveController(min_green_ms=5000, max_green_ms=20000, yellow_ms=2000, margin=4)
    green_matches = 0
    phase_matches = 0
    samples = 0

    for frame in frames:
        timestamp_ms = int(frame.elapsed_s * 1000)
        side_a = telemetry_from_frame(frame, Side.A, timestamp_ms)
        side_b = telemetry_from_frame(frame, Side.B, timestamp_ms)
        decision = controller.update(side_a, side_b, timestamp_ms)
        real_green = frame.controller_row.get("green_side")
        real_phase = frame.controller_row.get("phase")
        if not real_green or not real_phase:
            continue
        samples += 1
        green_matches += int(decision.green_side.value == real_green)
        phase_matches += int(decision.phase.value == real_phase)

    return ComparisonStats(samples=samples, green_matches=green_matches, phase_matches=phase_matches)


class RealDataVisualSimulator(base.VisualTrafficSimulator):
    def __init__(
        self,
        root: tk.Tk,
        frames: list[RoadFrame],
        csv_path: Path,
        replay_speed: float,
        queue_scale: float,
        max_cars_per_direction: int,
    ):
        self.frames = frames
        self.csv_path = csv_path
        self.replay_speed = replay_speed
        self.queue_scale = max(1.0, queue_scale)
        self.max_cars_per_direction = max(1, max_cars_per_direction)
        self.frame_index = 0
        self.current_frame: RoadFrame | None = None
        self.comparison_stats = compare_controller(frames)
        super().__init__(root)
        self.root.title("Wait Less - Visual Simulator With Real Road Data")
        self.mode_var.set("scenario")
        for scale in self.rate_scales:
            scale.configure(state=tk.DISABLED)

    def reset(self) -> None:
        self.controller = AdaptiveController(min_green_ms=5000, max_green_ms=20000, yellow_ms=2000, margin=4)
        self.cars = []
        self.spawn_budget = {direction: 0.0 for direction in base.LANES}
        self.incoming_counts = {Side.A: 0, Side.B: 0}
        self.passed_counts = {Side.A: 0, Side.B: 0}
        self.random_rates = {direction: 0.0 for direction in base.LANES}
        self.random_profile_name = "real road data"
        self.next_random_update_ms = 0
        self.running = True
        if hasattr(self, "toggle_button"):
            self.toggle_button.configure(text="Pause")

        self.frame_index = 0
        first_elapsed = self.frames[0].elapsed_s if self.frames else 0.0
        self.sim_time_ms = int(first_elapsed * 1000)
        self.current_frame = self.frames[0] if self.frames else None
        self.next_decision = None
        self.latest_side_a = None
        self.latest_side_b = None
        self._load_current_frame()
        if self.current_frame is not None:
            timestamp_ms = int(self.current_frame.elapsed_s * 1000)
            empty_a = telemetry_from_frame(self.current_frame, Side.A, timestamp_ms)
            empty_b = telemetry_from_frame(self.current_frame, Side.B, timestamp_ms)
            self.next_decision = self.controller.update(empty_a, empty_b, timestamp_ms)
            self.latest_side_a = self._build_side_telemetry(Side.A)
            self.latest_side_b = self._build_side_telemetry(Side.B)

        if hasattr(self, "canvas"):
            self._redraw()

    def _set_mode(self) -> None:
        self._update_panel_text()

    def _advance(self, _dt: float) -> None:
        if not self.frames:
            return

        self.sim_time_ms += int(base.FRAME_MS * self.replay_speed)
        end_ms = int(self.frames[-1].elapsed_s * 1000)
        if self.sim_time_ms > end_ms:
            self.reset()
            return

        self._load_current_frame()

        motion_dt = (base.FRAME_MS / 1000.0) * min(max(self.replay_speed, 0.1), MOTION_SPEED_LIMIT)
        self._spawn_cars(motion_dt)

        side_a = self._build_side_telemetry(Side.A)
        side_b = self._build_side_telemetry(Side.B)
        self.next_decision = self.controller.update(side_a, side_b, self.sim_time_ms)
        self.latest_side_a = side_a
        self.latest_side_b = side_b

        survivors = []
        for direction, lane in base.LANES.items():
            lane_cars = [car for car in self.cars if car.direction == direction]
            lane_cars.sort(key=lambda car: car.progress, reverse=True)

            lead_progress = None
            can_enter_intersection = self.next_decision.phase == base.Phase.GREEN and self.next_decision.green_side == lane.side
            far_sensor_progress = self._sensor_progress(lane, "far")

            for car in lane_cars:
                proposed_progress = car.progress + base.CAR_SPEED * motion_dt

                if car.progress < lane.stop_progress and not can_enter_intersection:
                    proposed_progress = min(proposed_progress, lane.stop_progress - base.STOP_MARGIN)

                if lead_progress is not None:
                    proposed_progress = min(proposed_progress, lead_progress - base.CAR_SPACING)

                if proposed_progress < car.progress:
                    proposed_progress = car.progress

                car.progress = proposed_progress

                if not car.counted_incoming and car.progress >= far_sensor_progress:
                    self.incoming_counts[lane.side] += 1
                    car.counted_incoming = True

                if not car.counted_passed and car.progress >= lane.stop_progress:
                    self.passed_counts[lane.side] += 1
                    car.counted_passed = True

                lead_progress = car.progress

                if car.progress <= lane.length + base.EXIT_MARGIN:
                    survivors.append(car)

        self.cars = survivors

    def _load_current_frame(self) -> None:
        while self.frame_index + 1 < len(self.frames) and int(self.frames[self.frame_index + 1].elapsed_s * 1000) <= self.sim_time_ms:
            self.frame_index += 1
        self.current_frame = self.frames[self.frame_index]

    def _spawn_rates(self) -> dict[str, float]:
        if self.current_frame is None:
            return {direction: 0.0 for direction in base.LANES}

        raw_a_queue = side_a_queue_for_frame(self.current_frame)
        raw_b_queue = side_b_queue_for_frame(self.current_frame)
        sim_a_queue = self._direction_queue("north") + self._direction_queue("south")
        sim_b_queue = self._direction_queue("west") + self._direction_queue("east")
        side_a_active = occupied(self.current_frame.row_a, "far_occupied") or occupied(self.current_frame.row_a, "near_occupied")
        side_b_active = occupied(self.current_frame.row_b, "far_occupied") or occupied(self.current_frame.row_b, "near_occupied")
        side_a_rate = self._side_spawn_rate(raw_a_queue, sim_a_queue, side_a_active)
        side_b_rate = self._side_spawn_rate(raw_b_queue, sim_b_queue, side_b_active)

        phase_bucket = int(self.current_frame.elapsed_s // 10) % 2
        ns_bias = 0.58 if phase_bucket == 0 else 0.42
        ew_bias = 0.56 if phase_bucket == 0 else 0.44
        return {
            "north": side_a_rate * ns_bias,
            "south": side_a_rate * (1.0 - ns_bias),
            "west": side_b_rate * ew_bias,
            "east": side_b_rate * (1.0 - ew_bias),
        }

    def _side_spawn_rate(self, raw_queue: int, simulated_queue: int, sensor_active: bool) -> float:
        visual_target = min(raw_queue / self.queue_scale, self.max_cars_per_direction * 2)
        queue_error = visual_target - simulated_queue
        if raw_queue <= 0 and not sensor_active:
            return 0.0

        rate = 0.14 * visual_target + 0.40 * queue_error
        if sensor_active:
            rate = max(rate, MIN_SENSOR_ACTIVE_RATE)
        return max(0.0, min(MAX_SIDE_SPAWN_RATE, rate))

    def _can_spawn(self, direction: str) -> bool:
        lane = base.LANES[direction]
        visible_in_lane = sum(
            1
            for car in self.cars
            if car.direction == direction and car.progress < lane.stop_progress
        )
        if visible_in_lane >= self.max_cars_per_direction:
            return False
        return super()._can_spawn(direction)

    def _traffic_source_text(self) -> str:
        if self.current_frame is None:
            return "Mode: real road CSV\nwaiting for data"

        row = self.current_frame.controller_row
        real = f"{row.get('green_side', '-')}/{row.get('phase', '-')}"
        sim = f"{self.next_decision.green_side.value}/{self.next_decision.phase.value}" if self.next_decision else "-"
        elapsed = self.current_frame.elapsed_s
        total = self.frames[-1].elapsed_s if self.frames else 0.0
        return (
            "Mode: real road CSV\n"
            f"  t={elapsed:5.1f}s / {total:5.1f}s @ {self.replay_speed:g}x\n"
            f"  visual scale: 1 car per {self.queue_scale:g} queue units\n"
            f"  real firmware: {real}\n"
            f"  simulator ctrl: {sim}\n"
            f"  event: {row.get('event_label') or '-'}"
        )

    def _update_panel_text(self) -> None:
        if self.current_frame is None or self.next_decision is None:
            super()._update_panel_text()
            return

        real_a_queue = side_a_queue_for_frame(self.current_frame)
        real_b_queue = side_b_queue_for_frame(self.current_frame)
        visual_a_queue = self.latest_side_a.estimated_queue if self.latest_side_a else 0
        visual_b_queue = self.latest_side_b.estimated_queue if self.latest_side_b else 0
        visual_a_cars = self._side_visible_cars(Side.A)
        visual_b_cars = self._side_visible_cars(Side.B)
        active_sensors = ", ".join(self._sensor_active_list()) or "none"
        row_a = self.current_frame.row_a
        row_b = self.current_frame.row_b
        real_row = self.current_frame.controller_row
        real_state = f"{real_row.get('green_side', '-')}/{real_row.get('phase', '-')}"
        sim_state = f"{self.next_decision.green_side.value}/{self.next_decision.phase.value}"

        self.status_var.set(
            "Time: {:5.1f} s\nReal firmware: {}\nSimulator: {}\nMatch rates G/P: {:4.1f}%/{:4.1f}%".format(
                self.current_frame.elapsed_s,
                real_state,
                sim_state,
                self.comparison_stats.green_match_rate,
                self.comparison_stats.phase_match_rate,
            )
        )

        self.queue_var.set(
            "Real Data -> Visual Cars\n"
            "  Real raw A/B: {:2d}/{:2d}\n"
            "  Visual queue A/B: {:2d}/{:2d}\n"
            "  Visible cars A/B: {:2d}/{:2d}\n"
            "  North/South: {:2d}/{:2d}\n"
            "  East/West  : {:2d}/{:2d}".format(
                real_a_queue,
                real_b_queue,
                visual_a_queue,
                visual_b_queue,
                visual_a_cars,
                visual_b_cars,
                self._direction_queue("north"),
                self._direction_queue("south"),
                self._direction_queue("east"),
                self._direction_queue("west"),
            )
        )

        self.count_var.set(
            "Real vs Visual Detection\n"
            "  A demand score: {:2d}\n"
            "  B demand score: {:2d}\n"
            "  A real F/N: {}/{}\n"
            "  B real F/N: {}/{}\n"
            "  A visual F/N: {}/{}\n"
            "  B visual F/N: {}/{}\n"
            "  LoRa: {}".format(
                demand_score(self.latest_side_a),
                demand_score(self.latest_side_b),
                "OCC" if occupied(row_a, "far_occupied") else "FREE",
                "OCC" if occupied(row_a, "near_occupied") else "FREE",
                "OCC" if occupied(row_b, "far_occupied") else "FREE",
                "OCC" if occupied(row_b, "near_occupied") else "FREE",
                "OCC" if self.latest_side_a.far_occupied else "FREE",
                "OCC" if self.latest_side_a.near_occupied else "FREE",
                "OCC" if self.latest_side_b.far_occupied else "FREE",
                "OCC" if self.latest_side_b.near_occupied else "FREE",
                real_row.get("remote_source") or real_row.get("source") or "-",
            )
        )

        self.scenario_var.set(self._traffic_source_text())
        self.sensor_var.set(
            "Real Sensor Distances\n"
            "  A far/near: {:>5}cm / {:>5}cm ({})\n"
            "  B far/near: {:>5}cm / {:>5}cm ({})\n"
            "  Active visual sensors: {}".format(
                row_a.get("far_cm") or "?",
                row_a.get("near_cm") or "?",
                detection_bucket(row_a),
                row_b.get("far_cm") or "?",
                row_b.get("near_cm") or "?",
                detection_bucket(row_b),
                active_sensors,
            )
        )

    def _side_visible_cars(self, side: Side) -> int:
        return sum(
            1
            for car in self.cars
            if base.LANES[car.direction].side == side
            and car.progress < base.LANES[car.direction].stop_progress
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Use the existing visual simulator with real road CSV car counts.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--speed", type=float, default=DEFAULT_REPLAY_SPEED)
    parser.add_argument(
        "--queue-scale",
        type=float,
        default=DEFAULT_QUEUE_SCALE,
        help="How many raw queue units are represented by one drawn car.",
    )
    parser.add_argument(
        "--max-cars-per-direction",
        type=int,
        default=DEFAULT_MAX_CARS_PER_DIRECTION,
        help="Visual cap per lane direction to keep the scene readable.",
    )
    parser.add_argument("--summary", action="store_true", help="Print dataset and controller-comparison summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frames = load_frames(args.csv)
    if not frames:
        print(f"No usable frames found in {args.csv}")
        return 2

    if args.summary:
        comparison = compare_controller(frames)
        print(dataset_summary(frames))
        print()
        print("Simulator vs real firmware controller")
        print("-------------------------------------")
        print(f"Comparison samples: {comparison.samples}")
        print(f"Green-side match: {comparison.green_match_rate:.1f}%")
        print(f"Phase match: {comparison.phase_match_rate:.1f}%")
        return 0

    root = tk.Tk()
    RealDataVisualSimulator(root, frames, args.csv, args.speed, args.queue_scale, args.max_cars_per_direction)
    window_width = min(base.WINDOW_WIDTH, max(base.MIN_VIEWPORT_WIDTH, root.winfo_screenwidth() - 80))
    window_height = min(base.WINDOW_HEIGHT, max(base.MIN_VIEWPORT_HEIGHT, root.winfo_screenheight() - 120))
    root.geometry(f"{int(window_width)}x{int(window_height)}")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
