#!/usr/bin/env python3
"""Render a PPT-friendly PNG diagram for the Wait Less code flow."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "code-flow-picture.png"

W, H = 2600, 1600
BG = "#F6FAFD"
INK = "#172033"
MUTED = "#566579"
BLUE = "#1F6FEB"
GREEN = "#138A43"
AMBER = "#F4B000"
RED = "#D92D20"
TEAL = "#0F766E"
SURFACE = "#FFFFFF"
LINE = "#CFE3F5"
WASH_BLUE = "#EAF4FF"
WASH_GREEN = "#EAF8EF"
WASH_AMBER = "#FFF7DD"
WASH_RED = "#FFF0EF"
WASH_TEAL = "#E8F7F4"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


TITLE = font(62, True)
SUBTITLE = font(30)
SECTION = font(30, True)
BODY = font(23)
BODY_BOLD = font(23, True)
SMALL = font(19)
MONO = font(20)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str, width: int = 3, radius: int = 22) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fill: str = INK, fnt: ImageFont.FreeTypeFont = BODY, anchor: str | None = None) -> None:
    draw.text(xy, value, fill=fill, font=fnt, anchor=anchor)


def wrap_text(value: str, chars: int) -> list[str]:
    lines: list[str] = []
    for raw in value.split("\n"):
        if not raw.strip():
            lines.append("")
            continue
        lines.extend(wrap(raw, width=chars, break_long_words=False))
    return lines


def box(
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    width: int,
    height: int,
    title: str,
    body: str,
    color: str,
    fill: str,
    title_size: ImageFont.FreeTypeFont = BODY_BOLD,
    body_size: ImageFont.FreeTypeFont = SMALL,
) -> tuple[int, int, int, int]:
    rounded(draw, (left, top, left + width, top + height), fill, color, 3)
    text(draw, (left + 24, top + 18), title, color, title_size)
    y = top + 62
    for line in wrap_text(body, max(18, int(width / 13))):
        text(draw, (left + 24, y), line, INK, body_size)
        y += 26
    return (left, top, left + width, top + height)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = MUTED, width: int = 5) -> None:
    draw.line([start, end], fill=color, width=width)
    sx, sy = start
    ex, ey = end
    if abs(ex - sx) >= abs(ey - sy):
        sign = 1 if ex >= sx else -1
        points = [(ex, ey), (ex - sign * 24, ey - 12), (ex - sign * 24, ey + 12)]
    else:
        sign = 1 if ey >= sy else -1
        points = [(ex, ey), (ex - 12, ey - sign * 24), (ex + 12, ey - sign * 24)]
    draw.polygon(points, fill=color)


def poly_arrow(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str = MUTED, width: int = 5) -> None:
    if len(points) < 2:
        return
    for start, end in zip(points, points[1:]):
        draw.line([start, end], fill=color, width=width)
    start, end = points[-2], points[-1]
    sx, sy = start
    ex, ey = end
    if abs(ex - sx) >= abs(ey - sy):
        sign = 1 if ex >= sx else -1
        arrow_points = [(ex, ey), (ex - sign * 24, ey - 12), (ex - sign * 24, ey + 12)]
    else:
        sign = 1 if ey >= sy else -1
        arrow_points = [(ex, ey), (ex - 12, ey - sign * 24), (ex + 12, ey - sign * 24)]
    draw.polygon(arrow_points, fill=color)


def connector_label(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, color: str) -> None:
    pad_x, pad_y = 16, 7
    bbox = draw.textbbox((x, y), label, font=SMALL)
    rounded(
        draw,
        (bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y),
        SURFACE,
        color,
        2,
        14,
    )
    text(draw, (x, y), label, color, SMALL)


def main() -> None:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)

    text(draw, (90, 64), "Wait Less Code Flow", INK, TITLE)
    text(
        draw,
        (92, 138),
        "From physical sensors to LoRa, LED control, saved CSV evidence, and simulator replay",
        MUTED,
        SUBTITLE,
    )

    rounded(draw, (70, 215, 660, 1330), "#F8FBFF", "#A9CCF5", 4)
    rounded(draw, (720, 215, 1510, 1330), "#F8FFFB", "#A7DAB8", 4)
    rounded(draw, (1570, 215, 2460, 1330), "#FFFFFF", "#B8D8F2", 4)

    text(draw, (100, 245), "NODE A: sensing + LoRa transmit", BLUE, SECTION)
    text(draw, (750, 245), "NODE B: receive + control + output", GREEN, SECTION)
    text(draw, (1600, 245), "LAPTOP: evidence + digital twin", TEAL, SECTION)

    a1 = box(draw, 110, 325, 500, 150, "1. Read Side A sensors", "firmware/node_a/main.cpp loop()\nreadFilteredUltrasonicSensor()\nfar + near ultrasonic distances", BLUE, WASH_BLUE)
    a2 = box(draw, 110, 525, 500, 150, "2. Estimate Side A queue", "LaneEstimator::update()\ncounts incoming and passed vehicles\noutputs SideTelemetry", BLUE, WASH_BLUE)
    a3 = box(draw, 110, 725, 500, 150, "3. Encode packet", "NodeMessaging.cpp\nencodeTelemetry(telemetry)\ncompact CSV payload", BLUE, WASH_BLUE)
    a4 = box(draw, 110, 925, 500, 150, "4. Send over LoRa", "sendTelemetryOverLoRa()\nloRaSendText(payload)\nRadioLib / SX1262", BLUE, WASH_BLUE)
    a5 = box(draw, 110, 1125, 500, 120, "Serial debug", "A STATUS / payload printed for bench evidence", BLUE, "#FFFFFF")

    b1 = box(draw, 780, 325, 330, 145, "LoRa receive", "loRaTryReceive(packet)\ngets Node A payload", GREEN, WASH_GREEN)
    b2 = box(draw, 1160, 325, 300, 145, "Decode A data", "parseTelemetryLine()\ndecodeTelemetry()", GREEN, WASH_GREEN)
    b3 = box(draw, 780, 535, 330, 145, "Read Side B sensors", "readFilteredUltrasonicSensor()\nB_far + B_near", GREEN, WASH_GREEN)
    b4 = box(draw, 1160, 535, 300, 145, "Estimate B queue", "LaneEstimator::update()\nlocal SideTelemetry", GREEN, WASH_GREEN)
    b5 = box(draw, 780, 750, 330, 150, "Choose A source", "effectiveRemoteTelemetry()\nLORA_RADIO or LORA_STALE\nbackup if Node A fails", GREEN, WASH_GREEN)
    b6 = box(draw, 1160, 750, 300, 150, "Adaptive control", "AdaptiveController::update()\nuses Side A + Side B", GREEN, WASH_GREEN)
    b7 = box(draw, 780, 980, 330, 145, "Physical output", "applyLights()\nSide A LEDs + Side B LEDs", RED, WASH_RED)
    b8 = box(draw, 1160, 980, 300, 145, "Evidence output", "B STATUS serial line\nqueues, distances,\nLoRa, backup, lights", GREEN, "#FFFFFF")

    p1 = box(draw, 1630, 325, 760, 145, "Logger reads serial", "tools/road_data_logger.py parses A STATUS and B STATUS using parse_status_line()", TEAL, WASH_TEAL)
    p2 = box(draw, 1630, 535, 760, 145, "Saved CSV evidence", "road_26-05-19_crossroads.csv contains queues, distances, LoRa source, lights, truth labels, and power", TEAL, WASH_TEAL)
    p3 = box(draw, 1630, 745, 760, 145, "Evaluation scripts", "tools/final_evidence_report.py and final_presentation_graphs.py calculate TP/TN/FP/FN, LoRa stale, energy, and graphs", TEAL, WASH_TEAL)
    p4 = box(draw, 1630, 955, 760, 170, "Simulator CSV replay", "simulation/visual_simulator.py loads CSV with load_road_frames(); _csv_spawn_rates() turns real queue pressure into visible cars", TEAL, WASH_TEAL)
    p5 = box(draw, 1630, 1180, 760, 115, "Final demo output", "Laptop screen shows real data replay, queues, sensor distances, and digital twin behavior", TEAL, "#FFFFFF")

    # Node A vertical flow.
    for upper, lower in [(a1, a2), (a2, a3), (a3, a4), (a4, a5)]:
        arrow(draw, ((upper[0] + upper[2]) // 2, upper[3] + 10), ((lower[0] + lower[2]) // 2, lower[1] - 12), BLUE)

    # LoRa link.
    arrow(draw, (a4[2] + 30, (a4[1] + a4[3]) // 2), (b1[0] - 35, (b1[1] + b1[3]) // 2), AMBER, 7)
    connector_label(draw, 660, 970, "LoRa: Node A -> Node B", AMBER)

    # Node B flows.
    arrow(draw, (b1[2] + 20, 398), (b2[0] - 22, 398), GREEN)
    arrow(draw, (b3[2] + 20, 608), (b4[0] - 22, 608), GREEN)
    poly_arrow(
        draw,
        [
            (b2[2] + 20, (b2[1] + b2[3]) // 2),
            (1488, (b2[1] + b2[3]) // 2),
            (1488, 718),
            ((b5[0] + b5[2]) // 2, 718),
            ((b5[0] + b5[2]) // 2, b5[1] - 20),
        ],
        GREEN,
    )
    arrow(draw, (b5[2] + 20, 825), (b6[0] - 22, 825), GREEN)
    arrow(draw, ((b4[0] + b4[2]) // 2, b4[3] + 20), ((b6[0] + b6[2]) // 2, b6[1] - 20), GREEN)
    arrow(draw, ((b6[0] + b6[2]) // 2, b6[3] + 20), ((b7[0] + b7[2]) // 2, b7[1] - 20), RED)
    arrow(draw, ((b6[0] + b6[2]) // 2, b6[3] + 20), ((b8[0] + b8[2]) // 2, b8[1] - 20), GREEN)

    # Serial/logging/evidence flows.
    arrow(draw, (b8[2] + 40, 1052), (p1[0] - 35, 398), TEAL, 6)
    connector_label(draw, 1455, 1018, "USB serial: B STATUS", TEAL)
    arrow(draw, ((p1[0] + p1[2]) // 2, p1[3] + 20), ((p2[0] + p2[2]) // 2, p2[1] - 20), TEAL)
    arrow(draw, ((p2[0] + p2[2]) // 2, p2[3] + 20), ((p3[0] + p3[2]) // 2, p3[1] - 20), TEAL)
    arrow(draw, ((p2[0] + p2[2]) // 2, p2[3] + 20), ((p4[0] + p4[2]) // 2, p4[1] - 20), TEAL)
    arrow(draw, ((p4[0] + p4[2]) // 2, p4[3] + 20), ((p5[0] + p5[2]) // 2, p5[1] - 20), TEAL)

    # Bottom explanation strip.
    rounded(draw, (90, 1400, 2510, 1515), "#FFFFFF", LINE, 3, 22)
    text(draw, (125, 1422), "One-sentence story", BLUE, BODY_BOLD)
    story = (
        "Node A converts ultrasonic readings into LoRa telemetry; Node B combines that with its own sensors, "
        "controls the LEDs, prints B STATUS, the laptop saves CSV evidence, and the simulator replays that CSV "
        "so the digital twin uses real road demand."
    )
    y = 1460
    for line in wrap_text(story, 135):
        text(draw, (125, y), line, INK, BODY)
        y += 30

    # Small legend.
    legend = [("Sensor/firmware", BLUE), ("LoRa", AMBER), ("Control/output", GREEN), ("Laptop/simulator", TEAL), ("Physical LEDs", RED)]
    x = 1280
    for label, color in legend:
        draw.rectangle((x, 145, x + 34, 179), fill=color)
        text(draw, (x + 46, 146), label, MUTED, SMALL)
        x += 225

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
