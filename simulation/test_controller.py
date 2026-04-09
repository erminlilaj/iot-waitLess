from traffic_logic import AdaptiveController, Phase, Side, SideTelemetry


def make_telemetry(side: Side, queue: int, timestamp_ms: int) -> SideTelemetry:
    return SideTelemetry(
        side=side,
        far_occupied=queue > 0,
        near_occupied=queue > 0,
        incoming_count=queue,
        passed_count=0,
        estimated_queue=queue,
        timestamp_ms=timestamp_ms,
    )


def run_timeline(queues: list[tuple[int, int]]) -> list[tuple[int, str, str]]:
    controller = AdaptiveController()
    observed: list[tuple[int, str, str]] = []

    for second, (queue_a, queue_b) in enumerate(queues):
        decision = controller.update(
            make_telemetry(Side.A, queue_a, second * 1000),
            make_telemetry(Side.B, queue_b, second * 1000),
            second * 1000,
        )
        observed.append((second, decision.green_side.value, decision.phase.value))

    return observed


def assert_state(observed: list[tuple[int, str, str]], second: int, green_side: str, phase: str) -> None:
    actual = observed[second]
    expected = (second, green_side, phase)
    if actual != expected:
        raise AssertionError(f"Expected {expected}, got {actual}")


def test_empty_lane_yield() -> str:
    queues = [(3, 0)] * 6 + [(0, 2)] * 4
    observed = run_timeline(queues)
    assert_state(observed, 6, "A", "YELLOW")
    assert_state(observed, 8, "B", "GREEN")
    return "PASS empty-lane yield: yellow at 6s, B green at 8s"


def test_busier_side_switch() -> str:
    queues = [(2, 1)] * 6 + [(1, 4)] * 4
    observed = run_timeline(queues)
    assert_state(observed, 6, "A", "YELLOW")
    assert_state(observed, 8, "B", "GREEN")
    return "PASS busier-side switch: yellow at 6s, B green at 8s"


def test_max_green_enforcement() -> str:
    queues = [(1, 1)] * 25
    observed = run_timeline(queues)
    assert_state(observed, 20, "A", "YELLOW")
    assert_state(observed, 22, "B", "GREEN")
    return "PASS max-green enforcement: yellow at 20s, B green at 22s"


def test_balanced_demand_holds_green() -> str:
    queues = [(2, 2)] * 12
    observed = run_timeline(queues)
    for second, green_side, phase in observed:
        expected = (second, "A", Phase.GREEN.value)
        actual = (second, green_side, phase)
        if actual != expected:
            raise AssertionError(f"Expected balanced demand to hold A green, got {actual}")
    return "PASS balanced demand: controller kept A green during equal queues"


def main() -> None:
    tests = [
        test_balanced_demand_holds_green,
        test_empty_lane_yield,
        test_busier_side_switch,
        test_max_green_enforcement,
    ]

    print("Wait Less software controller checks")
    print("----------------------------------")
    for test in tests:
        print(test())
    print("ALL SOFTWARE CONTROLLER CHECKS PASSED")


if __name__ == "__main__":
    main()
