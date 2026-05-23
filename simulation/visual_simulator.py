import csv
import math
import random
import tkinter as tk
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog

from traffic_logic import AdaptiveController, Phase, Side, SideTelemetry, demand_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = PROJECT_ROOT / "data" / "data_readed" / "road_26-05-19_crossroads.csv"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 1040
MIN_VIEWPORT_HEIGHT = 760
MIN_VIEWPORT_WIDTH = 1120
CANVAS_WIDTH = 940
CANVAS_HEIGHT = 1000
FRAME_MS = 40
RANDOM_RATE_REFRESH_MS = 5000
DEFAULT_REPLAY_SPEED = 1.5
DEFAULT_QUEUE_SCALE = 3.0
DEFAULT_MAX_CARS_PER_DIRECTION = 8
MAX_SIDE_SPAWN_RATE = 1.45
MOTION_SPEED_LIMIT = 1.25
MIN_SENSOR_ACTIVE_RATE = 0.18
CAR_SPEED = 135.0
CAR_LENGTH = 30.0
CAR_WIDTH = 18.0
CAR_SPACING = 52.0
STOP_MARGIN = 22.0
EXIT_MARGIN = 80.0
PIXELS_PER_METER = 80.0

ROAD_LEFT = 330.0
ROAD_TOP = 330.0
ROAD_RIGHT = 610.0
ROAD_BOTTOM = 610.0
NORTH_LANE_X = 430.0
SOUTH_LANE_X = 510.0
EAST_LANE_Y = 430.0
WEST_LANE_Y = 510.0
STOP_TOP = 390.0
STOP_BOTTOM = 550.0
STOP_LEFT = 390.0
STOP_RIGHT = 550.0
SPAWN_MARGIN = 220.0

SENSOR_FAR_OFFSET = 360.0
SENSOR_NEAR_OFFSET = 44.0
SENSOR_FAR_RANGE = 72.0
SENSOR_NEAR_RANGE = 24.0
SENSOR_MODULE_OFFSET = 78.0
SENSOR_ZONE_HALF_WIDTH = 24.0


@dataclass(frozen=True)
class LaneConfig:
    name: str
    side: Side
    start: tuple[float, float]
    end: tuple[float, float]
    stop_progress: float
    light_anchor: tuple[float, float]
    label_anchor: tuple[float, float]

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)


@dataclass
class Car:
    direction: str
    progress: float
    color: str
    counted_incoming: bool = False
    counted_passed: bool = False


@dataclass(frozen=True)
class RoadFrame:
    elapsed_s: float
    row_a: dict[str, str]
    row_b: dict[str, str]
    controller_row: dict[str, str]


LANES = {
    "north": LaneConfig(
        "North",
        Side.A,
        (NORTH_LANE_X, -SPAWN_MARGIN),
        (NORTH_LANE_X, CANVAS_HEIGHT + SPAWN_MARGIN),
        STOP_TOP + SPAWN_MARGIN,
        (ROAD_LEFT + 40.0, STOP_TOP - 42.0),
        ((ROAD_LEFT + ROAD_RIGHT) / 2, ROAD_TOP / 2),
    ),
    "south": LaneConfig(
        "South",
        Side.A,
        (SOUTH_LANE_X, CANVAS_HEIGHT + SPAWN_MARGIN),
        (SOUTH_LANE_X, -SPAWN_MARGIN),
        CANVAS_HEIGHT + SPAWN_MARGIN - STOP_BOTTOM,
        (ROAD_RIGHT - 66.0, STOP_BOTTOM - 36.0),
        ((ROAD_LEFT + ROAD_RIGHT) / 2, (ROAD_BOTTOM + CANVAS_HEIGHT) / 2),
    ),
    "west": LaneConfig(
        "West",
        Side.B,
        (-SPAWN_MARGIN, WEST_LANE_Y),
        (CANVAS_WIDTH + SPAWN_MARGIN, WEST_LANE_Y),
        STOP_LEFT + SPAWN_MARGIN,
        (STOP_LEFT - 48.0, ROAD_BOTTOM - 66.0),
        (ROAD_LEFT / 2, (ROAD_TOP + ROAD_BOTTOM) / 2),
    ),
    "east": LaneConfig(
        "East",
        Side.B,
        (CANVAS_WIDTH + SPAWN_MARGIN, EAST_LANE_Y),
        (-SPAWN_MARGIN, EAST_LANE_Y),
        CANVAS_WIDTH + SPAWN_MARGIN - STOP_RIGHT,
        (STOP_RIGHT - 34.0, ROAD_TOP + 42.0),
        ((ROAD_RIGHT + CANVAS_WIDTH) / 2, (ROAD_TOP + ROAD_BOTTOM) / 2),
    ),
}

CAR_COLORS = {
    "north": "#30b0c7",
    "south": "#3f88ff",
    "west": "#ff9f43",
    "east": "#f6c344",
}


def point_on_lane(lane: LaneConfig, progress: float) -> tuple[float, float]:
    ratio = max(0.0, min(1.0, progress / lane.length))
    x = lane.start[0] + (lane.end[0] - lane.start[0]) * ratio
    y = lane.start[1] + (lane.end[1] - lane.start[1]) * ratio
    return x, y


def side_label(side: Side) -> str:
    return "North/South" if side == Side.A else "East/West"


def pixels_to_meters(distance_px: float) -> float:
    return distance_px / PIXELS_PER_METER


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


def side_a_queue_for_frame(frame: RoadFrame) -> int:
    return parse_int(frame.row_a.get("local_queue") or frame.row_a.get("queue") or frame.row_b.get("remote_queue"))


def side_b_queue_for_frame(frame: RoadFrame) -> int:
    return parse_int(frame.row_b.get("local_queue"))


def load_road_frames(path: Path) -> list[RoadFrame]:
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


def csv_status_line(frames: list[RoadFrame], path: Path) -> str:
    if not frames:
        return f"No usable frames in {path.name}"

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for frame in frames:
        for row in (frame.row_a, frame.row_b):
            key = (row.get("timestamp_iso", ""), row.get("elapsed_s", ""), row.get("node", ""), row.get("raw_line", ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    lora = Counter((row.get("remote_source") or row.get("source") or "") for row in rows)
    duration = frames[-1].elapsed_s - frames[0].elapsed_s
    return f"{path.name}: {len(rows)} samples, {duration / 60.0:.1f} min, stale {lora['LORA_STALE']}"


class VisualTrafficSimulator:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Wait Less - Visual Traffic Simulator")
        self.root.configure(bg="#f3efe7")

        self.scroll_host = tk.Canvas(root, bg="#f3efe7", highlightthickness=0, bd=0)
        self.scroll_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(root, orient=tk.VERTICAL, command=self.scroll_host.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_host.configure(yscrollcommand=self.scrollbar.set)

        content = tk.Frame(self.scroll_host, bg="#f3efe7")
        self.content_frame = content
        self.content_window = self.scroll_host.create_window((0, 0), window=content, anchor="nw")
        self.scroll_host.bind("<Configure>", self._sync_scroll_width)
        self.content_frame.bind("<Configure>", self._refresh_scroll_region)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas = tk.Canvas(
            content,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            bg="#d8d2c2",
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, padx=(18, 12), pady=18)

        panel = tk.Frame(content, bg="#f3efe7")
        panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 18), pady=18)
        self.panel = panel

        tk.Label(
            panel,
            text="Wait Less Visual Demo",
            font=("Segoe UI", 18, "bold"),
            bg="#f3efe7",
            fg="#1f2a30",
        ).pack(anchor="w")

        tk.Label(
            panel,
            text="Four directions, one lane each.\nNorth/South share one adaptive phase,\nEast/West share the other.",
            justify="left",
            font=("Segoe UI", 10),
            bg="#f3efe7",
            fg="#41505a",
        ).pack(anchor="w", pady=(8, 14))

        self.status_var = tk.StringVar()
        self.queue_var = tk.StringVar()
        self.count_var = tk.StringVar()
        self.scenario_var = tk.StringVar()
        self.sensor_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="scenario")
        self.csv_status_var = tk.StringVar(value="CSV replay: default road CSV not loaded yet")
        self.csv_path_var = tk.StringVar(value=str(DEFAULT_CSV))
        self.csv_replay_speed_var = tk.DoubleVar(value=DEFAULT_REPLAY_SPEED)
        self.csv_queue_scale_var = tk.DoubleVar(value=DEFAULT_QUEUE_SCALE)
        self.direct_queue_vars = {
            Side.A: tk.IntVar(value=2),
            Side.B: tk.IntVar(value=1),
        }
        self.manual_rate_vars = {
            "north": tk.DoubleVar(value=0.70),
            "south": tk.DoubleVar(value=0.60),
            "east": tk.DoubleVar(value=0.30),
            "west": tk.DoubleVar(value=0.30),
        }

        control_card = tk.Frame(panel, bg="#f7f4ee", relief="groove", bd=1)
        control_card.pack(anchor="w", fill=tk.X, pady=(0, 12))
        self.control_card = control_card

        tk.Label(
            control_card,
            text="Traffic Source",
            font=("Segoe UI", 11, "bold"),
            bg="#f7f4ee",
            fg="#1f2a30",
            padx=10,
            pady=8,
        ).pack(anchor="w")

        mode_row = tk.Frame(control_card, bg="#f7f4ee")
        mode_row.pack(anchor="w", padx=8, pady=(0, 6))
        mode_row_2 = tk.Frame(control_card, bg="#f7f4ee")
        mode_row_2.pack(anchor="w", padx=8, pady=(0, 6))

        for value, label, parent in (
            ("scenario", "Scenario", mode_row),
            ("csv", "CSV replay", mode_row),
            ("direct", "Direct queues", mode_row),
            ("manual", "Manual rates", mode_row_2),
            ("random", "Random", mode_row_2),
        ):
            tk.Radiobutton(
                parent,
                text=label,
                value=value,
                variable=self.mode_var,
                command=self._set_mode,
                bg="#f7f4ee",
                fg="#243746",
                selectcolor="#f7f4ee",
                activebackground="#f7f4ee",
            ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(
            control_card,
            text="Direct queue targets for demo control:",
            justify="left",
            font=("Segoe UI", 9),
            bg="#f7f4ee",
            fg="#55636d",
            padx=10,
        ).pack(anchor="w", pady=(0, 2))

        self.direct_queue_scales = []
        for side, label in ((Side.A, "Side A"), (Side.B, "Side B")):
            row = tk.Frame(control_card, bg="#f7f4ee")
            row.pack(fill=tk.X, padx=8, pady=2)

            tk.Label(
                row,
                text=label,
                width=7,
                anchor="w",
                font=("Segoe UI", 9, "bold"),
                bg="#f7f4ee",
                fg="#243746",
            ).pack(side=tk.LEFT)

            scale = tk.Scale(
                row,
                from_=0,
                to=8,
                resolution=1,
                orient=tk.HORIZONTAL,
                variable=self.direct_queue_vars[side],
                command=lambda _value: self._apply_direct_queues_if_active(),
                length=180,
                showvalue=True,
                bg="#f7f4ee",
                highlightthickness=0,
                troughcolor="#d8d2c2",
                fg="#243746",
            )
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.direct_queue_scales.append(scale)

        tk.Button(
            control_card,
            text="Apply Direct Queues",
            command=self._apply_direct_queues,
            bg="#2f7d4c",
            fg="white",
            relief="flat",
        ).pack(anchor="w", padx=10, pady=(4, 10))

        tk.Label(
            control_card,
            text="Manual spawn frequencies in cars/second:",
            justify="left",
            font=("Segoe UI", 9),
            bg="#f7f4ee",
            fg="#55636d",
            padx=10,
        ).pack(anchor="w", pady=(0, 2))

        self.rate_scales = []
        for key, label in (("north", "North"), ("south", "South"), ("east", "East"), ("west", "West")):
            row = tk.Frame(control_card, bg="#f7f4ee")
            row.pack(fill=tk.X, padx=8, pady=2)

            tk.Label(
                row,
                text=label,
                width=6,
                anchor="w",
                font=("Segoe UI", 9, "bold"),
                bg="#f7f4ee",
                fg="#243746",
            ).pack(side=tk.LEFT)

            scale = tk.Scale(
                row,
                from_=0.0,
                to=1.20,
                resolution=0.05,
                orient=tk.HORIZONTAL,
                variable=self.manual_rate_vars[key],
                length=180,
                showvalue=True,
                bg="#f7f4ee",
                highlightthickness=0,
                troughcolor="#d8d2c2",
                fg="#243746",
            )
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.rate_scales.append(scale)

        csv_card = tk.Frame(control_card, bg="#f7f4ee")
        csv_card.pack(anchor="w", fill=tk.X, padx=8, pady=(8, 10))

        tk.Label(
            csv_card,
            text="CSV replay controls:",
            font=("Segoe UI", 9, "bold"),
            bg="#f7f4ee",
            fg="#243746",
        ).pack(anchor="w")

        csv_button_row = tk.Frame(csv_card, bg="#f7f4ee")
        csv_button_row.pack(anchor="w", pady=(4, 4))

        tk.Button(
            csv_button_row,
            text="Load CSV",
            width=10,
            command=self._choose_csv_file,
            bg="#2766b0",
            fg="white",
            relief="flat",
        ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            csv_button_row,
            text="Use Default",
            width=10,
            command=self._load_default_csv,
            bg="#4f6d7a",
            fg="white",
            relief="flat",
        ).pack(side=tk.LEFT)

        csv_speed_row = tk.Frame(csv_card, bg="#f7f4ee")
        csv_speed_row.pack(fill=tk.X, pady=2)
        tk.Label(csv_speed_row, text="Speed", width=7, anchor="w", bg="#f7f4ee", fg="#243746", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.csv_speed_scale = tk.Scale(
            csv_speed_row,
            from_=0.5,
            to=4.0,
            resolution=0.5,
            orient=tk.HORIZONTAL,
            variable=self.csv_replay_speed_var,
            length=180,
            showvalue=True,
            bg="#f7f4ee",
            highlightthickness=0,
            troughcolor="#d8d2c2",
            fg="#243746",
        )
        self.csv_speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        csv_scale_row = tk.Frame(csv_card, bg="#f7f4ee")
        csv_scale_row.pack(fill=tk.X, pady=2)
        tk.Label(csv_scale_row, text="Scale", width=7, anchor="w", bg="#f7f4ee", fg="#243746", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.csv_queue_scale = tk.Scale(
            csv_scale_row,
            from_=1.0,
            to=6.0,
            resolution=0.5,
            orient=tk.HORIZONTAL,
            variable=self.csv_queue_scale_var,
            length=180,
            showvalue=True,
            bg="#f7f4ee",
            highlightthickness=0,
            troughcolor="#d8d2c2",
            fg="#243746",
        )
        self.csv_queue_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            csv_card,
            textvariable=self.csv_status_var,
            justify="left",
            wraplength=270,
            font=("Segoe UI", 8),
            bg="#f7f4ee",
            fg="#55636d",
        ).pack(anchor="w", pady=(4, 0))

        for variable in (self.status_var, self.queue_var, self.count_var, self.scenario_var, self.sensor_var):
            tk.Label(
                panel,
                textvariable=variable,
                justify="left",
                font=("Consolas", 10),
                bg="#f7f4ee",
                fg="#222b30",
                relief="groove",
                bd=1,
                padx=10,
                pady=8,
                width=32,
                anchor="w",
            ).pack(anchor="w", fill=tk.X, pady=(0, 10))

        button_row = tk.Frame(panel, bg="#f3efe7")
        button_row.pack(anchor="w", pady=(8, 10))
        self.button_row = button_row

        self.toggle_button = tk.Button(
            button_row,
            text="Pause",
            width=10,
            command=self.toggle_running,
            bg="#243746",
            fg="white",
            relief="flat",
        )
        self.toggle_button.pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            button_row,
            text="Reset",
            width=10,
            command=self.reset,
            bg="#d95f5f",
            fg="white",
            relief="flat",
        ).pack(side=tk.LEFT)

        tk.Label(
            panel,
            text="Legend\nBlue cars: North/South\nOrange cars: East/West\nBlue modules: ultrasonic sensors",
            justify="left",
            font=("Segoe UI", 10),
            bg="#f3efe7",
            fg="#41505a",
        ).pack(anchor="w", pady=(12, 0))

        self.running = True
        self.cars: list[Car] = []
        self.spawn_budget: dict[str, float] = {}
        self.incoming_counts: dict[Side, int] = {}
        self.passed_counts: dict[Side, int] = {}
        self.random_rates: dict[str, float] = {direction: 0.0 for direction in LANES}
        self.random_profile_name = "random warm-up"
        self.next_random_update_ms = 0
        self.next_decision = None
        self.latest_side_a = None
        self.latest_side_b = None
        self.sim_time_ms = 0
        self.csv_frames: list[RoadFrame] = []
        self.csv_current_frame: RoadFrame | None = None
        self.csv_frame_index = 0
        self._load_csv(DEFAULT_CSV, silent=True)

        self._draw_static_scene()
        self._sync_mode_controls()
        self.reset()
        self.root.after(FRAME_MS, self._tick)

    def _sync_scroll_width(self, event: tk.Event) -> None:
        self.scroll_host.itemconfigure(self.content_window, width=event.width)

    def _refresh_scroll_region(self, _event: tk.Event | None = None) -> None:
        self.scroll_host.configure(scrollregion=self.scroll_host.bbox("all"))

    def _on_mousewheel(self, event: tk.Event) -> None:
        if not self.scroll_host.winfo_exists():
            return
        step = int(-event.delta / 120)
        if step != 0:
            self.scroll_host.yview_scroll(step, "units")

    def _choose_csv_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Load road CSV for simulator replay",
            initialdir=str(DEFAULT_CSV.parent),
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if path:
            self._load_csv(Path(path))

    def _load_default_csv(self) -> None:
        self._load_csv(DEFAULT_CSV)
        self.mode_var.set("csv")
        self._set_mode()

    def _load_csv(self, path: Path, silent: bool = False) -> None:
        try:
            frames = load_road_frames(path)
        except OSError as exc:
            if not silent:
                self.csv_status_var.set(f"CSV load failed: {exc}")
            return

        if not frames:
            if not silent:
                self.csv_status_var.set(f"CSV replay: no usable A/B frames in {path.name}")
            return

        self.csv_frames = frames
        self.csv_current_frame = frames[0]
        self.csv_frame_index = 0
        self.csv_path_var.set(str(path))
        self.csv_status_var.set("CSV replay loaded: " + csv_status_line(frames, path))
        if self.mode_var.get() == "csv":
            self.reset()

    def _reset_csv_replay(self) -> None:
        self.csv_frame_index = 0
        self.csv_current_frame = self.csv_frames[0] if self.csv_frames else None
        if self.csv_current_frame is not None:
            self.sim_time_ms = int(self.csv_current_frame.elapsed_s * 1000)

    def _load_current_csv_frame(self) -> None:
        if not self.csv_frames:
            self.csv_current_frame = None
            return
        while (
            self.csv_frame_index + 1 < len(self.csv_frames)
            and int(self.csv_frames[self.csv_frame_index + 1].elapsed_s * 1000) <= self.sim_time_ms
        ):
            self.csv_frame_index += 1
        self.csv_current_frame = self.csv_frames[self.csv_frame_index]

    def _apply_direct_queues_if_active(self) -> None:
        if hasattr(self, "mode_var") and self.mode_var.get() == "direct":
            self._apply_direct_queues()

    def _apply_direct_queues(self) -> None:
        if not hasattr(self, "cars"):
            return

        self.mode_var.set("direct")
        target_a = self.direct_queue_vars[Side.A].get()
        target_b = self.direct_queue_vars[Side.B].get()
        self.cars = []
        self.spawn_budget = {direction: 0.0 for direction in LANES}
        self.incoming_counts = {Side.A: target_a, Side.B: target_b}
        self.passed_counts = {Side.A: 0, Side.B: 0}
        self._seed_side_queue(Side.A, target_a)
        self._seed_side_queue(Side.B, target_b)
        self.latest_side_a = self._build_side_telemetry(Side.A)
        self.latest_side_b = self._build_side_telemetry(Side.B)
        self.next_decision = self.controller.update(self.latest_side_a, self.latest_side_b, self.sim_time_ms)
        self._sync_mode_controls()
        self._redraw()

    def _seed_side_queue(self, side: Side, count: int) -> None:
        side_lanes = [direction for direction, lane in LANES.items() if lane.side == side]
        for index in range(max(0, count)):
            direction = side_lanes[index % len(side_lanes)]
            lane = LANES[direction]
            depth = index // len(side_lanes)
            progress = lane.stop_progress - STOP_MARGIN - (depth * CAR_SPACING)
            progress = max(self._sensor_progress(lane, "far") + CAR_LENGTH / 2, progress)
            self.cars.append(Car(direction=direction, progress=progress, color=CAR_COLORS[direction], counted_incoming=True))

    def reset(self) -> None:
        if self.mode_var.get() == "csv":
            self.controller = AdaptiveController(min_green_ms=5000, max_green_ms=20000, yellow_ms=2000, margin=4)
        else:
            self.controller = AdaptiveController(min_green_ms=6000, max_green_ms=18000, yellow_ms=2200, margin=5)
        self.cars = []
        self.spawn_budget = {direction: 0.0 for direction in LANES}
        self.incoming_counts = {Side.A: 0, Side.B: 0}
        self.passed_counts = {Side.A: 0, Side.B: 0}
        self.sim_time_ms = 0
        self.running = True
        self.toggle_button.configure(text="Pause")
        self._refresh_random_rates(force=True)
        if self.mode_var.get() == "csv":
            self._reset_csv_replay()
        elif self.mode_var.get() == "direct":
            self._apply_direct_queues()
            return

        empty_a = self._build_side_telemetry(Side.A)
        empty_b = self._build_side_telemetry(Side.B)
        self.next_decision = self.controller.update(empty_a, empty_b, 0)
        self.latest_side_a = empty_a
        self.latest_side_b = empty_b
        self._redraw()

    def toggle_running(self) -> None:
        self.running = not self.running
        self.toggle_button.configure(text="Pause" if self.running else "Resume")

    def _sync_mode_controls(self) -> None:
        mode = self.mode_var.get()
        for scale in self.rate_scales:
            scale.configure(state=tk.NORMAL if mode == "manual" else tk.DISABLED)
        for scale in self.direct_queue_scales:
            scale.configure(state=tk.NORMAL if mode == "direct" else tk.DISABLED)
        self.csv_speed_scale.configure(state=tk.NORMAL if mode == "csv" else tk.DISABLED)
        self.csv_queue_scale.configure(state=tk.NORMAL if mode == "csv" else tk.DISABLED)

    def _set_mode(self) -> None:
        mode = self.mode_var.get()
        self._sync_mode_controls()
        if mode == "random":
            self._refresh_random_rates(force=True)
        elif mode == "csv" and self.csv_frames:
            self.reset()
            return
        elif mode == "direct" and hasattr(self, "cars"):
            self._apply_direct_queues()
            return
        self._update_panel_text()

    def _tick(self) -> None:
        if self.running:
            self._advance(FRAME_MS / 1000.0)
        self._redraw()
        self.root.after(FRAME_MS, self._tick)

    def _advance(self, dt: float) -> None:
        motion_dt = dt
        if self.mode_var.get() == "csv" and self.csv_frames:
            self.sim_time_ms += int(FRAME_MS * self.csv_replay_speed_var.get())
            end_ms = int(self.csv_frames[-1].elapsed_s * 1000)
            if self.sim_time_ms > end_ms:
                self.reset()
                return
            self._load_current_csv_frame()
            motion_dt = dt * min(max(self.csv_replay_speed_var.get(), 0.1), MOTION_SPEED_LIMIT)
        else:
            self.sim_time_ms += FRAME_MS

        self._spawn_cars(motion_dt)

        side_a = self._build_side_telemetry(Side.A)
        side_b = self._build_side_telemetry(Side.B)
        self.next_decision = self.controller.update(side_a, side_b, self.sim_time_ms)
        self.latest_side_a = side_a
        self.latest_side_b = side_b

        survivors = []
        for direction, lane in LANES.items():
            lane_cars = [car for car in self.cars if car.direction == direction]
            lane_cars.sort(key=lambda car: car.progress, reverse=True)

            lead_progress = None
            can_enter_intersection = self.next_decision.phase == Phase.GREEN and self.next_decision.green_side == lane.side
            far_sensor_progress = self._sensor_progress(lane, "far")

            for car in lane_cars:
                proposed_progress = car.progress + CAR_SPEED * motion_dt

                if car.progress < lane.stop_progress and not can_enter_intersection:
                    proposed_progress = min(proposed_progress, lane.stop_progress - STOP_MARGIN)

                if lead_progress is not None:
                    proposed_progress = min(proposed_progress, lead_progress - CAR_SPACING)

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

                if car.progress <= lane.length + EXIT_MARGIN:
                    survivors.append(car)

        self.cars = survivors

    def _spawn_cars(self, dt: float) -> None:
        for direction, rate in self._spawn_rates().items():
            self.spawn_budget[direction] = min(self.spawn_budget[direction] + rate * dt, 2.5)
            while self.spawn_budget[direction] >= 1.0:
                if not self._can_spawn(direction):
                    break
                self._create_car(direction)
                self.spawn_budget[direction] -= 1.0

    def _spawn_rates(self) -> dict[str, float]:
        mode = self.mode_var.get()
        if mode == "csv":
            return self._csv_spawn_rates()
        if mode == "direct":
            return self._direct_queue_rates()
        if mode == "manual":
            return self._manual_rates()
        if mode == "random":
            self._refresh_random_rates()
            return self.random_rates
        return self._scenario_rates()

    def _manual_rates(self) -> dict[str, float]:
        return {direction: self.manual_rate_vars[direction].get() for direction in LANES}

    def _direct_queue_rates(self) -> dict[str, float]:
        target_a = self.direct_queue_vars[Side.A].get()
        target_b = self.direct_queue_vars[Side.B].get()
        current_a = self._direction_queue("north") + self._direction_queue("south")
        current_b = self._direction_queue("west") + self._direction_queue("east")
        side_a_rate = self._target_gap_rate(target_a - current_a)
        side_b_rate = self._target_gap_rate(target_b - current_b)
        return {
            "north": side_a_rate * 0.55,
            "south": side_a_rate * 0.45,
            "west": side_b_rate * 0.55,
            "east": side_b_rate * 0.45,
        }

    def _target_gap_rate(self, gap: int) -> float:
        if gap <= 0:
            return 0.0
        return min(1.20, 0.25 + gap * 0.35)

    def _csv_spawn_rates(self) -> dict[str, float]:
        if self.csv_current_frame is None:
            return {direction: 0.0 for direction in LANES}

        raw_a_queue = side_a_queue_for_frame(self.csv_current_frame)
        raw_b_queue = side_b_queue_for_frame(self.csv_current_frame)
        sim_a_queue = self._direction_queue("north") + self._direction_queue("south")
        sim_b_queue = self._direction_queue("west") + self._direction_queue("east")
        side_a_active = occupied(self.csv_current_frame.row_a, "far_occupied") or occupied(self.csv_current_frame.row_a, "near_occupied")
        side_b_active = occupied(self.csv_current_frame.row_b, "far_occupied") or occupied(self.csv_current_frame.row_b, "near_occupied")
        side_a_rate = self._side_spawn_rate(raw_a_queue, sim_a_queue, side_a_active)
        side_b_rate = self._side_spawn_rate(raw_b_queue, sim_b_queue, side_b_active)

        phase_bucket = int(self.csv_current_frame.elapsed_s // 10) % 2
        ns_bias = 0.58 if phase_bucket == 0 else 0.42
        ew_bias = 0.56 if phase_bucket == 0 else 0.44
        return {
            "north": side_a_rate * ns_bias,
            "south": side_a_rate * (1.0 - ns_bias),
            "west": side_b_rate * ew_bias,
            "east": side_b_rate * (1.0 - ew_bias),
        }

    def _side_spawn_rate(self, raw_queue: int, simulated_queue: int, sensor_active: bool) -> float:
        visual_target = min(raw_queue / max(1.0, self.csv_queue_scale_var.get()), DEFAULT_MAX_CARS_PER_DIRECTION * 2)
        queue_error = visual_target - simulated_queue
        if raw_queue <= 0 and not sensor_active:
            return 0.0

        rate = 0.14 * visual_target + 0.40 * queue_error
        if sensor_active:
            rate = max(rate, MIN_SENSOR_ACTIVE_RATE)
        return max(0.0, min(MAX_SIDE_SPAWN_RATE, rate))

    def _scenario_rates(self) -> dict[str, float]:
        second = (self.sim_time_ms / 1000.0) % 72.0

        if second < 16.0:
            return {"north": 0.85, "south": 0.65, "west": 0.15, "east": 0.10}
        if second < 30.0:
            return {"north": 0.45, "south": 0.40, "west": 0.40, "east": 0.35}
        if second < 46.0:
            return {"north": 0.20, "south": 0.20, "west": 0.80, "east": 0.75}
        if second < 58.0:
            return {"north": 0.10, "south": 0.18, "west": 0.70, "east": 0.95}
        return {"north": 0.55, "south": 0.60, "west": 0.30, "east": 0.25}

    def _refresh_random_rates(self, force: bool = False) -> None:
        if not force and self.sim_time_ms < self.next_random_update_ms:
            return

        profile = random.choice(["balanced", "north_south", "east_west", "north_peak", "south_peak", "east_peak", "west_peak"])
        rates = {direction: random.uniform(0.05, 0.35) for direction in LANES}

        if profile == "balanced":
            rates = {direction: random.uniform(0.25, 0.55) for direction in LANES}
        elif profile == "north_south":
            rates["north"] += random.uniform(0.35, 0.70)
            rates["south"] += random.uniform(0.30, 0.65)
        elif profile == "east_west":
            rates["east"] += random.uniform(0.35, 0.70)
            rates["west"] += random.uniform(0.30, 0.65)
        elif profile == "north_peak":
            rates["north"] += random.uniform(0.50, 0.85)
        elif profile == "south_peak":
            rates["south"] += random.uniform(0.50, 0.85)
        elif profile == "east_peak":
            rates["east"] += random.uniform(0.50, 0.85)
        elif profile == "west_peak":
            rates["west"] += random.uniform(0.50, 0.85)

        self.random_rates = {direction: round(min(1.20, value), 2) for direction, value in rates.items()}
        self.random_profile_name = profile.replace("_", "/")
        self.next_random_update_ms = self.sim_time_ms + RANDOM_RATE_REFRESH_MS

    def _scenario_name(self) -> str:
        second = (self.sim_time_ms / 1000.0) % 72.0
        if second < 16.0:
            return "Scenario: north/south dominant"
        if second < 30.0:
            return "Scenario: balanced flow"
        if second < 46.0:
            return "Scenario: east/west build-up"
        if second < 58.0:
            return "Scenario: strong east/west pressure"
        return "Scenario: north/south recovery"

    def _traffic_source_text(self) -> str:
        mode = self.mode_var.get()
        if mode == "csv":
            if self.csv_current_frame is None:
                return "Mode: CSV replay\n  load a road CSV to replay real demand"
            row = self.csv_current_frame.controller_row
            elapsed = self.csv_current_frame.elapsed_s
            total = self.csv_frames[-1].elapsed_s if self.csv_frames else 0.0
            real = f"{row.get('green_side', '-')}/{row.get('phase', '-')}"
            sim = f"{self.next_decision.green_side.value}/{self.next_decision.phase.value}" if self.next_decision else "-"
            return (
                "Mode: CSV replay\n"
                f"  t={elapsed:5.1f}s / {total:5.1f}s @ {self.csv_replay_speed_var.get():g}x\n"
                f"  visual scale: 1 car per {self.csv_queue_scale_var.get():g} queue units\n"
                f"  real firmware: {real}\n"
                f"  simulator ctrl: {sim}"
            )

        if mode == "direct":
            return (
                "Mode: direct queues\n"
                f"  target Side A queue: {self.direct_queue_vars[Side.A].get()}\n"
                f"  target Side B queue: {self.direct_queue_vars[Side.B].get()}\n"
                "  Use Apply Direct Queues for an instant scene reset."
            )

        if mode == "manual":
            rates = self._manual_rates()
            return (
                "Mode: manual frequencies\n"
                "  N: {north:.2f}  S: {south:.2f}\n"
                "  E: {east:.2f}  W: {west:.2f}"
            ).format(**rates)

        if mode == "random":
            rates = self.random_rates
            return (
                "Mode: random flow ({})\n"
                "  N: {:.2f}  S: {:.2f}\n"
                "  E: {:.2f}  W: {:.2f}"
            ).format(
                self.random_profile_name,
                rates["north"],
                rates["south"],
                rates["east"],
                rates["west"],
            )

        return self._scenario_name()

    def _sensor_offset(self, sensor_kind: str) -> float:
        return SENSOR_FAR_OFFSET if sensor_kind == "far" else SENSOR_NEAR_OFFSET

    def _sensor_range(self, sensor_kind: str) -> float:
        return SENSOR_FAR_RANGE if sensor_kind == "far" else SENSOR_NEAR_RANGE

    def _sensor_progress(self, lane: LaneConfig, sensor_kind: str) -> float:
        return lane.stop_progress - self._sensor_offset(sensor_kind)

    def _sensor_point(self, lane: LaneConfig, sensor_kind: str) -> tuple[float, float]:
        return point_on_lane(lane, self._sensor_progress(lane, sensor_kind))

    def _sensor_module_center(self, direction: str, sensor_point: tuple[float, float]) -> tuple[float, float]:
        if direction == "north":
            return sensor_point[0] - SENSOR_MODULE_OFFSET, sensor_point[1]
        if direction == "south":
            return sensor_point[0] + SENSOR_MODULE_OFFSET, sensor_point[1]
        if direction == "west":
            return sensor_point[0], sensor_point[1] + SENSOR_MODULE_OFFSET
        return sensor_point[0], sensor_point[1] - SENSOR_MODULE_OFFSET

    def _sensor_is_occupied(self, direction: str, sensor_kind: str) -> bool:
        lane = LANES[direction]
        sensor_progress = self._sensor_progress(lane, sensor_kind)
        capture_range = self._sensor_range(sensor_kind) + CAR_LENGTH / 2

        return any(
            car.direction == direction
            and car.progress < lane.stop_progress
            and abs(car.progress - sensor_progress) <= capture_range
            for car in self.cars
        )

    def _sensor_active_list(self) -> list[str]:
        active = []
        for direction in LANES:
            if self._sensor_is_occupied(direction, "far"):
                active.append(f"{direction[0].upper()}-F")
            if self._sensor_is_occupied(direction, "near"):
                active.append(f"{direction[0].upper()}-N")
        return active

    def _can_spawn(self, direction: str) -> bool:
        if self.mode_var.get() == "csv":
            lane = LANES[direction]
            visible_in_lane = sum(
                1
                for car in self.cars
                if car.direction == direction and car.progress < lane.stop_progress
            )
            if visible_in_lane >= DEFAULT_MAX_CARS_PER_DIRECTION:
                return False
        return not any(car.direction == direction and car.progress < CAR_SPACING * 1.4 for car in self.cars)

    def _create_car(self, direction: str) -> None:
        self.cars.append(Car(direction=direction, progress=0.0, color=CAR_COLORS[direction]))

    def _build_side_telemetry(self, side: Side) -> SideTelemetry:
        queue_count = 0

        for car in self.cars:
            lane = LANES[car.direction]
            far_sensor_progress = self._sensor_progress(lane, "far")
            if lane.side != side or car.progress < far_sensor_progress or car.progress >= lane.stop_progress:
                continue

            queue_count += 1

        far_occupied = any(self._sensor_is_occupied(direction, "far") for direction, lane in LANES.items() if lane.side == side)
        near_occupied = any(self._sensor_is_occupied(direction, "near") for direction, lane in LANES.items() if lane.side == side)

        return SideTelemetry(
            side=side,
            far_occupied=far_occupied,
            near_occupied=near_occupied,
            incoming_count=self.incoming_counts[side],
            passed_count=self.passed_counts[side],
            estimated_queue=queue_count,
            timestamp_ms=self.sim_time_ms,
        )

    def _direction_queue(self, direction: str) -> int:
        lane = LANES[direction]
        far_sensor_progress = self._sensor_progress(lane, "far")
        return sum(
            1
            for car in self.cars
            if car.direction == direction and far_sensor_progress <= car.progress < lane.stop_progress
        )

    def _light_state(self, side: Side) -> str:
        if self.next_decision.phase == Phase.GREEN:
            return "green" if self.next_decision.green_side == side else "red"
        return "yellow" if self.next_decision.green_side == side else "red"

    def _redraw(self) -> None:
        self.canvas.delete("dynamic")
        self._draw_sensor_activity()
        self._draw_lights()
        self._draw_cars()
        self._update_panel_text()

    def _draw_static_scene(self) -> None:
        self.canvas.create_rectangle(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, fill="#ddd4c3", outline="", tags="static")
        self.canvas.create_rectangle(22, 22, CANVAS_WIDTH - 22, CANVAS_HEIGHT - 22, outline="#a69983", width=2, tags="static")

        self.canvas.create_rectangle(ROAD_LEFT - 10, 0, ROAD_RIGHT + 10, CANVAS_HEIGHT, fill="#56606a", outline="", tags="static")
        self.canvas.create_rectangle(0, ROAD_TOP - 10, CANVAS_WIDTH, ROAD_BOTTOM + 10, fill="#56606a", outline="", tags="static")
        self.canvas.create_rectangle(ROAD_LEFT, 0, ROAD_RIGHT, CANVAS_HEIGHT, fill="#444d57", outline="", tags="static")
        self.canvas.create_rectangle(0, ROAD_TOP, CANVAS_WIDTH, ROAD_BOTTOM, fill="#444d57", outline="", tags="static")
        self.canvas.create_rectangle(ROAD_LEFT, ROAD_TOP, ROAD_RIGHT, ROAD_BOTTOM, fill="#303840", outline="", tags="static")

        for x in (390, 550):
            self.canvas.create_line(x, 0, x, ROAD_TOP, fill="#ece7da", width=3, dash=(12, 12), tags="static")
            self.canvas.create_line(x, ROAD_BOTTOM, x, CANVAS_HEIGHT, fill="#ece7da", width=3, dash=(12, 12), tags="static")
        for y in (390, 550):
            self.canvas.create_line(0, y, ROAD_LEFT, y, fill="#ece7da", width=3, dash=(12, 12), tags="static")
            self.canvas.create_line(ROAD_RIGHT, y, CANVAS_WIDTH, y, fill="#ece7da", width=3, dash=(12, 12), tags="static")

        self.canvas.create_line(NORTH_LANE_X, STOP_TOP, SOUTH_LANE_X, STOP_TOP, fill="white", width=4, tags="static")
        self.canvas.create_line(NORTH_LANE_X, STOP_BOTTOM, SOUTH_LANE_X, STOP_BOTTOM, fill="white", width=4, tags="static")
        self.canvas.create_line(STOP_LEFT, EAST_LANE_Y, STOP_LEFT, WEST_LANE_Y, fill="white", width=4, tags="static")
        self.canvas.create_line(STOP_RIGHT, EAST_LANE_Y, STOP_RIGHT, WEST_LANE_Y, fill="white", width=4, tags="static")

        self.canvas.create_rectangle(34, 30, 332, 112, fill="#f5efe4", outline="#b6a487", width=2, tags="static")
        self.canvas.create_text(58, 50, text="Wait Less", anchor="w", fill="#22303a", font=("Segoe UI", 22, "bold"), tags="static")
        self.canvas.create_text(
            58,
            78,
            text="Adaptive traffic control with\nultrasonic sensing",
            anchor="nw",
            width=250,
            fill="#5e6b74",
            font=("Segoe UI", 10),
            tags="static",
        )

        for direction, lane in LANES.items():
            self.canvas.create_text(
                lane.label_anchor[0],
                lane.label_anchor[1],
                text=lane.name,
                fill="#f6f2eb",
                font=("Segoe UI", 16, "bold"),
                tags="static",
            )

    def _draw_sensor_activity(self) -> None:
        for direction, lane in LANES.items():
            for sensor_kind in ("far", "near"):
                sensor_point = self._sensor_point(lane, sensor_kind)
                module_x, module_y = self._sensor_module_center(direction, sensor_point)
                active = self._sensor_is_occupied(direction, sensor_kind)
                capture_range = self._sensor_range(sensor_kind)
                zone_color = "#2eb67d" if sensor_kind == "far" else "#e59b42"
                outline_color = zone_color if active else "#8b847a"
                module_color = "#3f82d6" if active else "#6a86a6"
                label = "F" if sensor_kind == "far" else "N"

                if direction in ("north", "south"):
                    self.canvas.create_oval(
                        sensor_point[0] - SENSOR_ZONE_HALF_WIDTH,
                        sensor_point[1] - capture_range,
                        sensor_point[0] + SENSOR_ZONE_HALF_WIDTH,
                        sensor_point[1] + capture_range,
                        fill=zone_color if active else "",
                        stipple="gray25" if active else "",
                        outline=outline_color,
                        width=2,
                        tags="dynamic",
                    )
                else:
                    self.canvas.create_oval(
                        sensor_point[0] - capture_range,
                        sensor_point[1] - SENSOR_ZONE_HALF_WIDTH,
                        sensor_point[0] + capture_range,
                        sensor_point[1] + SENSOR_ZONE_HALF_WIDTH,
                        fill=zone_color if active else "",
                        stipple="gray25" if active else "",
                        outline=outline_color,
                        width=2,
                        tags="dynamic",
                    )

                if direction in ("north", "south"):
                    self.canvas.create_line(module_x + (18 if direction == "north" else -18), module_y, sensor_point[0], sensor_point[1], fill="#7f7669", width=2, tags="dynamic")
                else:
                    self.canvas.create_line(module_x, module_y + (-18 if direction == "east" else 18), sensor_point[0], sensor_point[1], fill="#7f7669", width=2, tags="dynamic")

                self.canvas.create_rectangle(module_x - 18, module_y - 12, module_x + 18, module_y + 12, fill=module_color, outline="#24496d", width=2, tags="dynamic")
                self.canvas.create_oval(module_x - 13, module_y - 7, module_x - 1, module_y + 7, fill="#d9e3ee", outline="#9aa8b7", tags="dynamic")
                self.canvas.create_oval(module_x + 1, module_y - 7, module_x + 13, module_y + 7, fill="#d9e3ee", outline="#9aa8b7", tags="dynamic")
                self.canvas.create_text(module_x, module_y - 22, text=label, fill="#20303a", font=("Segoe UI", 9, "bold"), tags="dynamic")

                if direction in ("north", "south"):
                    text_x = module_x + (0 if direction == "north" else 0)
                    text_y = sensor_point[1] + (capture_range + 16 if sensor_kind == "far" else capture_range + 16)
                else:
                    text_x = sensor_point[0]
                    text_y = module_y + (24 if direction == "west" else -24)

                self.canvas.create_text(
                    text_x,
                    text_y,
                    text=f"{pixels_to_meters(capture_range * 2):.1f}m",
                    fill=outline_color,
                    font=("Segoe UI", 8, "bold"),
                    tags="dynamic",
                )

    def _draw_lights(self) -> None:
        for lane in LANES.values():
            state = self._light_state(lane.side)
            x, y = lane.light_anchor
            housing = self.canvas.create_rectangle(x, y, x + 28, y + 74, fill="#1c2327", outline="#101417", width=2, tags="dynamic")
            self.canvas.tag_raise(housing)

            colors = {
                "red": "#d94b4b" if state == "red" else "#4f2b2b",
                "yellow": "#f1c44f" if state == "yellow" else "#564a29",
                "green": "#36c66a" if state == "green" else "#254a34",
            }

            self.canvas.create_oval(x + 6, y + 6, x + 22, y + 22, fill=colors["red"], outline="", tags="dynamic")
            self.canvas.create_oval(x + 6, y + 29, x + 22, y + 45, fill=colors["yellow"], outline="", tags="dynamic")
            self.canvas.create_oval(x + 6, y + 52, x + 22, y + 68, fill=colors["green"], outline="", tags="dynamic")

    def _draw_cars(self) -> None:
        for car in self.cars:
            lane = LANES[car.direction]
            x, y = point_on_lane(lane, car.progress)

            if car.direction in ("north", "south"):
                self.canvas.create_rectangle(
                    x - CAR_WIDTH / 2,
                    y - CAR_LENGTH / 2,
                    x + CAR_WIDTH / 2,
                    y + CAR_LENGTH / 2,
                    fill=car.color,
                    outline="#152027",
                    width=2,
                    tags="dynamic",
                )
            else:
                self.canvas.create_rectangle(
                    x - CAR_LENGTH / 2,
                    y - CAR_WIDTH / 2,
                    x + CAR_LENGTH / 2,
                    y + CAR_WIDTH / 2,
                    fill=car.color,
                    outline="#152027",
                    width=2,
                    tags="dynamic",
                )

    def _update_csv_panel_text(self) -> None:
        if self.csv_current_frame is None or self.next_decision is None:
            return

        real_a_queue = side_a_queue_for_frame(self.csv_current_frame)
        real_b_queue = side_b_queue_for_frame(self.csv_current_frame)
        visual_a_queue = self.latest_side_a.estimated_queue if self.latest_side_a else 0
        visual_b_queue = self.latest_side_b.estimated_queue if self.latest_side_b else 0
        active_sensors = ", ".join(self._sensor_active_list()) or "none"
        row_a = self.csv_current_frame.row_a
        row_b = self.csv_current_frame.row_b
        row = self.csv_current_frame.controller_row

        real_state = f"{row.get('green_side', '-')}/{row.get('phase', '-')}"
        sim_state = f"{self.next_decision.green_side.value}/{self.next_decision.phase.value}"

        self.status_var.set(
            "Time: {:5.1f} s\nCSV firmware: {}\nSimulator: {}\nLoRa source: {}".format(
                self.csv_current_frame.elapsed_s,
                real_state,
                sim_state,
                row.get("remote_source") or row.get("source") or "-",
            )
        )

        self.queue_var.set(
            "CSV -> Visual Queues\n"
            "  Real A/B: {:2d}/{:2d}\n"
            "  Visual A/B: {:2d}/{:2d}\n"
            "  North/South: {:2d}/{:2d}\n"
            "  East/West  : {:2d}/{:2d}".format(
                real_a_queue,
                real_b_queue,
                visual_a_queue,
                visual_b_queue,
                self._direction_queue("north"),
                self._direction_queue("south"),
                self._direction_queue("east"),
                self._direction_queue("west"),
            )
        )

        self.count_var.set(
            "Real Sensor Distances\n"
            "  A far/near: {:>5}cm / {:>5}cm ({})\n"
            "  B far/near: {:>5}cm / {:>5}cm ({})\n"
            "  A real F/N: {}/{}\n"
            "  B real F/N: {}/{}".format(
                row_a.get("far_cm") or "?",
                row_a.get("near_cm") or "?",
                detection_bucket(row_a),
                row_b.get("far_cm") or "?",
                row_b.get("near_cm") or "?",
                detection_bucket(row_b),
                "OCC" if occupied(row_a, "far_occupied") else "FREE",
                "OCC" if occupied(row_a, "near_occupied") else "FREE",
                "OCC" if occupied(row_b, "far_occupied") else "FREE",
                "OCC" if occupied(row_b, "near_occupied") else "FREE",
            )
        )

        self.scenario_var.set(self._traffic_source_text())
        self.sensor_var.set(
            "Digital twin replay\n"
            "  CSV: {}\n"
            "  Active visual sensors: {}\n"
            "  Event: {}".format(
                Path(self.csv_path_var.get()).name,
                active_sensors,
                row.get("event_label") or "-",
            )
        )

    def _update_panel_text(self) -> None:
        if self.mode_var.get() == "csv" and self.csv_current_frame is not None:
            self._update_csv_panel_text()
            return

        ns_queue = self.latest_side_a.estimated_queue if self.latest_side_a else 0
        ew_queue = self.latest_side_b.estimated_queue if self.latest_side_b else 0
        active_sensors = ", ".join(self._sensor_active_list()) or "none"

        self.status_var.set(
            "Time: {:5.1f} s\nActive axis: {}\nPhase: {}\nPhase time: {:4.1f} s".format(
                self.sim_time_ms / 1000.0,
                side_label(self.next_decision.green_side),
                self.next_decision.phase.value,
                self.next_decision.elapsed_ms / 1000.0,
            )
        )

        self.queue_var.set(
            "Queues\n"
            "  North: {:2d}\n"
            "  South: {:2d}\n"
            "  East : {:2d}\n"
            "  West : {:2d}\n"
            "  NS total: {:2d}\n"
            "  EW total: {:2d}".format(
                self._direction_queue("north"),
                self._direction_queue("south"),
                self._direction_queue("east"),
                self._direction_queue("west"),
                ns_queue,
                ew_queue,
            )
        )

        self.count_var.set(
            "Telemetry\n"
            "  NS demand score: {:2d}\n"
            "  EW demand score: {:2d}\n"
            "  NS in/out: {:2d}/{:2d}\n"
            "  EW in/out: {:2d}/{:2d}".format(
                demand_score(self.latest_side_a),
                demand_score(self.latest_side_b),
                self.incoming_counts[Side.A],
                self.passed_counts[Side.A],
                self.incoming_counts[Side.B],
                self.passed_counts[Side.B],
            )
        )

        self.scenario_var.set(self._traffic_source_text())
        self.sensor_var.set(
            "Ultrasonic setup\n"
            "  Far: {:>3.1f}m from stop, {:>3.1f}m catch\n"
            "  Near: {:>3.1f}m from stop, {:>3.1f}m catch\n"
            "  Active: {}".format(
                pixels_to_meters(SENSOR_FAR_OFFSET),
                pixels_to_meters(SENSOR_FAR_RANGE * 2),
                pixels_to_meters(SENSOR_NEAR_OFFSET),
                pixels_to_meters(SENSOR_NEAR_RANGE * 2),
                active_sensors,
            )
        )


def main() -> None:
    root = tk.Tk()
    simulator = VisualTrafficSimulator(root)
    window_width = min(WINDOW_WIDTH, max(MIN_VIEWPORT_WIDTH, root.winfo_screenwidth() - 80))
    window_height = min(WINDOW_HEIGHT, max(MIN_VIEWPORT_HEIGHT, root.winfo_screenheight() - 120))
    root.geometry(f"{int(window_width)}x{int(window_height)}")
    root.mainloop()


if __name__ == "__main__":
    main()
