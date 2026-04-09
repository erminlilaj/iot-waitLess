# Bring-Up Guide

This is the fastest path to start testing when the hardware arrives.

## Recommended Order

1. Read [hardware-map.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/hardware-map.md)
   Use this to wire the boards correctly.

2. Follow [hardware-arrival-checklist.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/hardware-arrival-checklist.md)
   Use this to avoid setup mistakes before deeper debugging.

3. Test Node B alone with [node-b-standalone-bench-test.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/node-b-standalone-bench-test.md)
   This verifies LEDs, local sensing, and controller behavior first.

4. Test Node A alone with [node-a-telemetry-bench-test.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/node-a-telemetry-bench-test.md)
   This verifies telemetry and queue estimation.

5. Connect both through [two-node-serial-emulation.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/two-node-serial-emulation.md)
   This isolates communication-format issues before radio debugging.

6. Use [fixed-test-scenarios.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/fixed-test-scenarios.md)
   This gives you repeatable scenarios and expected logs.

7. Move to real LoRa with [lora-integration.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/lora-integration.md)
   This is the final software/hardware communication step.

8. Use [logging-and-results.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/logging-and-results.md)
   Keep both nodes in `summary` mode unless you are debugging a specific problem.

9. Paste final snapshots into [test-results-log.md](c:/Users/Lenovo/Desktop/Sperenza/Spring_2026/iot/group_project/docs/test-results-log.md)
   This keeps software and hardware evidence in one organized place.

## Goal Of This Order

The order is intentional:

- sensing first
- controller second
- communication format third
- radio fourth

That keeps debugging focused and reduces the number of unknowns in each step.
