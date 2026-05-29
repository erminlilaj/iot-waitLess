# Bring-Up Guide

This is the fastest path to start testing the final prototype.

## Recommended Order

1. Read [hardware-map.md](hardware-map.md)
   Use this to wire the boards correctly.

2. Verify power and wiring before connecting sensors or LEDs:
   use level shifting for HC-SR04 `ECHO`, use resistors on all LEDs, and confirm USB data cables are working.

3. Test Node B alone with [node-b-standalone-bench-test.md](node-b-standalone-bench-test.md)
   This verifies LEDs, local sensing, and controller behavior first.

4. Test Node A alone with [node-a-telemetry-bench-test.md](node-a-telemetry-bench-test.md)
   This verifies telemetry and queue estimation.

5. Connect both through [two-node-serial-emulation.md](two-node-serial-emulation.md)
   This isolates communication-format issues before radio debugging.

6. Use [fixed-test-scenarios.md](fixed-test-scenarios.md)
   This gives you repeatable scenarios and expected logs.

7. Move to real LoRa with [lora-integration.md](lora-integration.md)
   This is the final software/hardware communication step.

8. Use [logging-and-results.md](logging-and-results.md)
   Keep both nodes in `summary` mode unless you are debugging a specific problem.

9. Paste final snapshots into [test-results-log.md](test-results-log.md)
   This keeps software and hardware evidence in one organized place.

## Goal Of This Order

The order is intentional:

- sensing first
- controller second
- communication format third
- radio fourth

That keeps debugging focused and reduces the number of unknowns in each step.
