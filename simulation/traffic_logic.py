from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    A = "A"
    B = "B"


class Phase(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"


@dataclass
class SideTelemetry:
    side: Side
    far_occupied: bool
    near_occupied: bool
    incoming_count: int
    passed_count: int
    estimated_queue: int
    timestamp_ms: int


@dataclass
class Decision:
    green_side: Side
    phase: Phase
    current_demand: int
    other_demand: int
    elapsed_ms: int


def demand_score(telemetry: SideTelemetry) -> int:
    return telemetry.estimated_queue * 3 + (2 if telemetry.far_occupied else 0) + (4 if telemetry.near_occupied else 0)


def has_demand(telemetry: SideTelemetry) -> bool:
    return telemetry.estimated_queue > 0 or telemetry.far_occupied or telemetry.near_occupied


class AdaptiveController:
    def __init__(self, min_green_ms: int = 5000, max_green_ms: int = 20000, yellow_ms: int = 2000, margin: int = 4):
        self.min_green_ms = min_green_ms
        self.max_green_ms = max_green_ms
        self.yellow_ms = yellow_ms
        self.margin = margin
        self.green_side = Side.A
        self.phase = Phase.GREEN
        self.phase_started_ms = 0

    def update(self, side_a: SideTelemetry, side_b: SideTelemetry, now_ms: int) -> Decision:
        elapsed_ms = now_ms - self.phase_started_ms

        if self.phase == Phase.YELLOW and elapsed_ms >= self.yellow_ms:
            self.green_side = Side.B if self.green_side == Side.A else Side.A
            self.phase = Phase.GREEN
            self.phase_started_ms = now_ms

        current = side_a if self.green_side == Side.A else side_b
        other = side_b if self.green_side == Side.A else side_a
        elapsed_ms = now_ms - self.phase_started_ms

        if self.phase == Phase.GREEN:
            can_switch = elapsed_ms >= self.min_green_ms
            current_empty = not has_demand(current)
            other_busy = has_demand(other)
            reached_max_green = elapsed_ms >= self.max_green_ms
            other_clearly_busier = demand_score(other) > demand_score(current) + self.margin

            if can_switch and ((current_empty and other_busy) or (other_busy and other_clearly_busier) or (reached_max_green and other_busy)):
                self.phase = Phase.YELLOW
                self.phase_started_ms = now_ms

        current = side_a if self.green_side == Side.A else side_b
        other = side_b if self.green_side == Side.A else side_a
        return Decision(
            green_side=self.green_side,
            phase=self.phase,
            current_demand=demand_score(current),
            other_demand=demand_score(other),
            elapsed_ms=now_ms - self.phase_started_ms,
        )

