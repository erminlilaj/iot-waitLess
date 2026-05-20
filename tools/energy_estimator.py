#!/usr/bin/env python3
"""Estimate field-test energy usage and battery life.

Use measured current values from a USB power meter when possible. If you do not
have measurements, keep the default values and label the result as an estimate.
"""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate Wait Less node energy usage.")
    parser.add_argument("--duration-min", type=float, default=30.0, help="Road-test duration in minutes.")
    parser.add_argument("--node-a-ma", type=float, default=120.0, help="Average Node A current in mA.")
    parser.add_argument("--node-b-ma", type=float, default=160.0, help="Average Node B current in mA.")
    parser.add_argument("--battery-mah", type=float, default=10000.0, help="Battery/power-bank capacity in mAh.")
    parser.add_argument("--battery-efficiency", type=float, default=0.75, help="Usable fraction after converter losses.")
    parser.add_argument("--voltage-v", type=float, default=5.0, help="Supply voltage used for Wh estimate.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    duration_h = args.duration_min / 60.0
    usable_capacity = args.battery_mah * args.battery_efficiency
    total_current = args.node_a_ma + args.node_b_ma
    used_mah = total_current * duration_h
    used_wh = used_mah / 1000.0 * args.voltage_v
    battery_life_h = usable_capacity / total_current if total_current > 0 else 0.0

    print("Wait Less Energy Estimate")
    print("-------------------------")
    print(f"Duration: {args.duration_min:.1f} min")
    print(f"Node A average current: {args.node_a_ma:.1f} mA")
    print(f"Node B average current: {args.node_b_ma:.1f} mA")
    print(f"Total average current: {total_current:.1f} mA")
    print(f"Energy used during test: {used_mah:.1f} mAh ({used_wh:.2f} Wh at {args.voltage_v:.1f} V)")
    print(f"Usable battery capacity: {usable_capacity:.0f} mAh")
    print(f"Estimated battery life: {battery_life_h:.1f} h")
    print()
    print("For the report, state whether the current values were measured or estimated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
