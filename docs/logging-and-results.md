# Logging And Results Workflow

This project now has a simple debug workflow designed to keep serial output readable.

The main idea is:

- keep the live serial monitor in `summary` mode most of the time
- switch to `verbose` only when you are actively debugging a problem
- use `status` and `report` to generate clean snapshots
- paste the `report` output into `docs/test-results-log.md`

## Log Modes

Both `Node A` and `Node B` support the same commands:

- `log quiet`
  Turns off periodic status lines. Use this when you only want command acknowledgements.

- `log summary`
  Prints one compact line per telemetry period. This is the recommended default.

- `log verbose`
  Prints the detailed sensing/controller lines. Use this only when you need deeper debugging.

- `status`
  Prints a readable multi-line snapshot of the current state.

- `report`
  Prints a copy-friendly block intended for the results log.

## Recommended Usage

### During Normal Bring-Up

1. set both nodes to `log summary`
2. run one test scenario
3. call `status`
4. call `report`
5. paste the report blocks into `docs/test-results-log.md`

### During Deep Debugging

1. switch only the problematic node to `log verbose`
2. reproduce the issue
3. capture the detailed output
4. switch back to `log summary`

## Typical Workflow

### Node A

```text
log summary
emu_on
reset_counts
state 1 0
status
report
```

### Node B

```text
log summary
remote_queue 3
status
report
```

## Why This Is Better

Instead of reading a long scrolling console, you can now work in three layers:

- `summary` for live monitoring
- `status` for a clean human-readable snapshot
- `report` for documentation and test evidence

That makes it much easier to separate:

- software behavior
- hardware observations
- final experiment results
