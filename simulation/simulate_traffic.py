from traffic_logic import AdaptiveController, Side, SideTelemetry


def scenario_step(second: int) -> tuple[SideTelemetry, SideTelemetry]:
    if second < 6:
        queue_a, queue_b = 3, 0
    elif second < 12:
        queue_a, queue_b = 2, 2
    elif second < 18:
        queue_a, queue_b = 1, 4
    elif second < 24:
        queue_a, queue_b = 0, 3
    else:
        queue_a, queue_b = 2, 1

    side_a = SideTelemetry(
        side=Side.A,
        far_occupied=queue_a > 0,
        near_occupied=queue_a > 0,
        incoming_count=max(queue_a + second // 4, 0),
        passed_count=max(second // 5, 0),
        estimated_queue=queue_a,
        timestamp_ms=second * 1000,
    )
    side_b = SideTelemetry(
        side=Side.B,
        far_occupied=queue_b > 0,
        near_occupied=queue_b > 0,
        incoming_count=max(queue_b + second // 3, 0),
        passed_count=max(second // 6, 0),
        estimated_queue=queue_b,
        timestamp_ms=second * 1000,
    )
    return side_a, side_b


def main() -> None:
    controller = AdaptiveController()

    print("Adaptive traffic-light simulation")
    print("time | queueA | queueB | green | phase  | currentDemand | otherDemand")
    print("-" * 72)

    for second in range(0, 31):
        side_a, side_b = scenario_step(second)
        decision = controller.update(side_a, side_b, second * 1000)

        print(
            f"{second:>4}s |"
            f" {side_a.estimated_queue:>6} |"
            f" {side_b.estimated_queue:>6} |"
            f" {decision.green_side.value:>5} |"
            f" {decision.phase.value:>6} |"
            f" {decision.current_demand:>13} |"
            f" {decision.other_demand:>11}"
        )


if __name__ == "__main__":
    main()
