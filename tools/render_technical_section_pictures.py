#!/usr/bin/env python3
"""Render slide-ready PNGs for the technical architecture section."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "presentation_assets"

W, H = 1920, 1080
BG = "#F6FAFD"
SURFACE = "#FFFFFF"
INK = "#172033"
MUTED = "#5B6575"
LINE = "#CFE3F5"
BLUE = "#1F6FEB"
GREEN = "#138A43"
AMBER = "#F4B000"
RED = "#D92D20"
TEAL = "#0F766E"
PURPLE = "#6B4EFF"
WASH_BLUE = "#EAF4FF"
WASH_GREEN = "#EAF8EF"
WASH_AMBER = "#FFF7DD"
WASH_RED = "#FFF0EF"
WASH_TEAL = "#E8F7F4"
WASH_PURPLE = "#F0EDFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


TITLE = font(54, True)
SUB = font(26)
H1 = font(30, True)
H2 = font(24, True)
BODY = font(21)
SMALL = font(17)
TINY = font(15)
MONO = font(18)
MONO_BOLD = font(18, True)
ESP_IMAGE = ROOT / "docs" / "esp.png"


def new_canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 18), fill=BLUE)
    draw.text((68, 56), title, fill=INK, font=TITLE)
    draw.text((70, 120), subtitle, fill=MUTED, font=SUB)
    draw.text((70, 1032), "Wait Less | Technical architecture, algorithms, and software components", fill=MUTED, font=TINY)
    return image, draw


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str, width: int = 3, radius: int = 24) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, max_chars: int, fill: str = INK, fnt: ImageFont.FreeTypeFont = BODY, line_gap: int = 27) -> int:
    for raw in text.split("\n"):
        lines = wrap(raw, width=max_chars, break_long_words=False) or [""]
        for line in lines:
            draw.text((x, y), line, fill=fill, font=fnt)
            y += line_gap
    return y


def card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    body: str,
    color: str,
    fill: str,
    max_chars: int | None = None,
) -> tuple[int, int, int, int]:
    rounded(draw, (x, y, x + w, y + h), fill, color, 3)
    draw.text((x + 24, y + 20), title, fill=color, font=H2)
    wrapped(draw, x + 24, y + 60, body, max_chars or max(18, w // 14), INK, SMALL, 23)
    return (x, y, x + w, y + h)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: str, fill: str = SURFACE) -> tuple[int, int, int, int]:
    bbox = draw.textbbox((x, y), text, font=SMALL)
    box = (x - 14, y - 7, bbox[2] + 14, bbox[3] + 7)
    rounded(draw, box, fill, color, 2, 16)
    draw.text((x, y), text, fill=color, font=SMALL)
    return box


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str = MUTED, width: int = 5) -> None:
    draw.line([start, end], fill=color, width=width)
    sx, sy = start
    ex, ey = end
    if abs(ex - sx) >= abs(ey - sy):
        sign = 1 if ex >= sx else -1
        pts = [(ex, ey), (ex - sign * 24, ey - 12), (ex - sign * 24, ey + 12)]
    else:
        sign = 1 if ey >= sy else -1
        pts = [(ex, ey), (ex - 12, ey - sign * 24), (ex + 12, ey - sign * 24)]
    draw.polygon(pts, fill=color)


def poly_arrow(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str = MUTED, width: int = 5) -> None:
    if len(points) < 2:
        return
    for start, end in zip(points, points[1:]):
        draw.line([start, end], fill=color, width=width)
    arrow(draw, points[-2], points[-1], color, width)


def label(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: str) -> None:
    bbox = draw.textbbox((x, y), text, font=SMALL)
    rounded(draw, (bbox[0] - 12, bbox[1] - 7, bbox[2] + 12, bbox[3] + 7), SURFACE, color, 2, 14)
    draw.text((x, y), text, fill=color, font=SMALL)


def paste_fit(base: Image.Image, image_path: Path, box: tuple[int, int, int, int]) -> None:
    if not image_path.exists():
        return
    src = Image.open(image_path).convert("RGBA")
    target_w = box[2] - box[0]
    target_h = box[3] - box[1]
    src.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    x = box[0] + (target_w - src.width) // 2
    y = box[1] + (target_h - src.height) // 2
    base.paste(src, (x, y), src)


def draw_ultrasonic_module(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0) -> None:
    w = int(118 * scale)
    h = int(56 * scale)
    rounded(draw, (x, y, x + w, y + h), "#155EEF", "#0B3B8C", 2, int(8 * scale))
    draw.rectangle((x + int(40 * scale), y + h, x + int(78 * scale), y + h + int(18 * scale)), fill="#1F2937")
    for pin_x in [48, 58, 68]:
        draw.rectangle((x + int(pin_x * scale), y + h + int(18 * scale), x + int((pin_x + 4) * scale), y + h + int(32 * scale)), fill="#111827")
    for cx in [34, 84]:
        cx_s = x + int(cx * scale)
        cy_s = y + int(29 * scale)
        draw.ellipse((cx_s - int(20 * scale), cy_s - int(20 * scale), cx_s + int(20 * scale), cy_s + int(20 * scale)), fill="#D1D5DB", outline="#475467", width=max(1, int(2 * scale)))
        draw.ellipse((cx_s - int(12 * scale), cy_s - int(12 * scale), cx_s + int(12 * scale), cy_s + int(12 * scale)), fill="#111827", outline="#98A2B3", width=max(1, int(2 * scale)))
        draw.ellipse((cx_s - int(6 * scale), cy_s - int(6 * scale), cx_s + int(6 * scale), cy_s + int(6 * scale)), fill="#2F3846")
    draw.text((x + int(28 * scale), y + int(4 * scale)), "HC-SR04", fill="#FFFFFF", font=TINY)


def draw_ina219_module(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0) -> None:
    w = int(138 * scale)
    h = int(82 * scale)
    rounded(draw, (x, y, x + w, y + h), "#1D4ED8", "#0B3B8C", 2, int(9 * scale))
    draw.text((x + int(36 * scale), y + int(8 * scale)), "INA219", fill="#FFFFFF", font=TINY)
    draw.rectangle((x + int(18 * scale), y + int(34 * scale), x + int(120 * scale), y + int(47 * scale)), fill="#D1D5DB", outline="#667085")
    draw.rectangle((x + int(27 * scale), y + int(57 * scale), x + int(62 * scale), y + int(74 * scale)), fill="#F97316", outline="#9A3412")
    draw.rectangle((x + int(76 * scale), y + int(57 * scale), x + int(111 * scale), y + int(74 * scale)), fill="#F97316", outline="#9A3412")
    for idx, label_text in enumerate(["VCC", "GND", "SDA", "SCL"]):
        px = x + int((16 + idx * 29) * scale)
        draw.ellipse((px, y + int(18 * scale), px + int(8 * scale), y + int(26 * scale)), fill="#FDE68A", outline="#92400E")
        draw.text((px - int(5 * scale), y + int(28 * scale)), label_text, fill="#FFFFFF", font=font(max(8, int(9 * scale)), True))


def draw_laptop_icon(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0) -> None:
    w = int(170 * scale)
    h = int(110 * scale)
    rounded(draw, (x, y, x + w, y + int(82 * scale)), "#172033", "#475467", 2, int(10 * scale))
    rounded(draw, (x + int(12 * scale), y + int(12 * scale), x + w - int(12 * scale), y + int(70 * scale)), "#DDF8F2", TEAL, 2, int(5 * scale))
    draw.text((x + int(28 * scale), y + int(30 * scale)), "B STATUS", fill=TEAL, font=TINY)
    draw.rectangle((x - int(16 * scale), y + int(82 * scale), x + w + int(16 * scale), y + int(98 * scale)), fill="#CBD5E1", outline="#667085")
    draw.rectangle((x + int(52 * scale), y + int(86 * scale), x + int(118 * scale), y + int(92 * scale)), fill="#94A3B8")


def save(image: Image.Image, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    image.save(path)
    print(path)
    return path


def render_service_architecture() -> None:
    image, draw = new_canvas(
        "1. Service Architecture",
        "The IoT service connects physical sensing, local control, evidence logging, and digital-twin replay.",
    )

    road = (690, 260, 1230, 745)
    rounded(draw, road, "#E7EDF3", "#9EB4C8", 4, 28)
    draw.rectangle((905, 260, 1015, 745), fill="#485460")
    draw.rectangle((690, 448, 1230, 558), fill="#485460")
    draw.rectangle((910, 448, 1010, 558), fill="#313942")
    draw.text((820, 375), "Real crossroad", fill="#FFFFFF", font=H1)
    draw.text((805, 410), "Side A + Side B queues", fill="#DDE7F0", font=SMALL)

    a = card(draw, 80, 275, 450, 170, "Node A", "2 ultrasonic sensors\nSide A queue estimate\nLoRa telemetry transmit", BLUE, WASH_BLUE)
    b = card(draw, 1390, 275, 450, 210, "Node B", "2 ultrasonic sensors\nLoRa receive\nAdaptive controller\nTraffic-light LEDs", GREEN, WASH_GREEN)
    lights = card(draw, 1390, 545, 450, 140, "Physical light output", "applyLights() drives Side A and Side B red/yellow/green LEDs.", RED, WASH_RED)
    logger = card(draw, 1390, 745, 450, 150, "Laptop evidence", "Serial log -> road CSV -> dashboard, graphs, and simulator replay.", TEAL, WASH_TEAL)

    arrow(draw, (530, 360), (690, 360), BLUE, 6)
    label(draw, 555, 325, "A sensors point at Side A", BLUE)
    arrow(draw, (1230, 360), (1390, 360), GREEN, 6)
    label(draw, 1248, 325, "B sensors + control", GREEN)
    poly_arrow(draw, [(530, 445), (600, 510), (1320, 510), (1390, 395)], AMBER, 7)
    label(draw, 760, 500, "LoRa: Node A -> Node B", AMBER)
    arrow(draw, (1615, 485), (1615, 545), RED, 6)
    arrow(draw, (1615, 685), (1615, 745), TEAL, 6)

    rounded(draw, (80, 820, 1230, 948), SURFACE, LINE, 3)
    draw.text((110, 842), "Service outputs", fill=BLUE, font=H2)
    pill(draw, 340, 845, "live traffic-light state", RED)
    pill(draw, 610, 845, "B STATUS terminal log", GREEN)
    pill(draw, 875, 845, "CSV evidence", TEAL)
    pill(draw, 1080, 845, "digital twin", PURPLE)
    wrapped(
        draw,
        110,
        888,
        "This is the service story: field sensing produces telemetry, telemetry controls the lights, and the same output is saved for evaluation and replay.",
        116,
        MUTED,
        SMALL,
        22,
    )
    save(image, "01-service-architecture.png")


def render_lora() -> None:
    image, draw = new_canvas(
        "2. LoRa Communication Path",
        "Node A sends compact Side A telemetry; Node B receives it and checks freshness before control.",
    )

    steps = [
        (95, 260, 300, 150, "Read sensors", "Node A loop()\nfar_cm + near_cm\noccupied/free", BLUE, WASH_BLUE),
        (455, 260, 300, 150, "Queue telemetry", "LaneEstimator::update()\nSideTelemetry", BLUE, WASH_BLUE),
        (815, 260, 300, 150, "Encode packet", "encodeTelemetry()\nside, queue, distances", BLUE, WASH_BLUE),
        (1175, 260, 300, 150, "LoRa TX", "loRaSendText()\n868 MHz SX1262", AMBER, WASH_AMBER),
        (1525, 260, 300, 150, "LoRa RX", "loRaTryReceive()\nRSSI + SNR", GREEN, WASH_GREEN),
    ]
    boxes = [card(draw, *step) for step in steps]
    for left, right in zip(boxes, boxes[1:]):
        arrow(draw, (left[2] + 20, 335), (right[0] - 22, 335), AMBER if right == boxes[4] else MUTED, 5)

    packet = card(
        draw,
        210,
        505,
        1480,
        155,
        "LoRa payload content",
        "A,farOccupied,nearOccupied,incomingCount,passedCount,queue,emergency,timestampMs,farDistanceCm,nearDistanceCm",
        AMBER,
        "#FFFFFF",
        128,
    )
    for i, txt in enumerate(["side", "far/near", "queue", "emergency", "timestamp", "distances"]):
        pill(draw, 285 + i * 210, 595, txt, AMBER, WASH_AMBER)

    decode = card(draw, 245, 740, 430, 150, "Node B decode", "parseTelemetryLine()\ndecodeTelemetry()\nupdates remoteTelemetry", GREEN, WASH_GREEN)
    fresh = card(draw, 745, 740, 430, 150, "Freshness check", "effectiveRemoteTelemetry()\nLORA_RADIO if fresh\nLORA_STALE if timeout", GREEN, WASH_GREEN)
    backup = card(draw, 1245, 740, 430, 150, "Fail-safe behavior", "If stale, Node B does not assume empty road.\nIt uses backup queue=1.", RED, WASH_RED)
    arrow(draw, ((packet[0] + packet[2]) // 2, packet[3] + 20), ((decode[0] + decode[2]) // 2, decode[1] - 20), GREEN)
    arrow(draw, (decode[2] + 20, 815), (fresh[0] - 20, 815), GREEN)
    arrow(draw, (fresh[2] + 20, 815), (backup[0] - 20, 815), RED)

    save(image, "02-lora-communication.png")


def render_algorithm() -> None:
    image, draw = new_canvas(
        "3. Adaptive Control Algorithm",
        "The algorithm is simple enough to justify, but robust enough to handle noisy sensors and emergency priority.",
    )

    s1 = card(draw, 80, 250, 360, 185, "Sensor reliability", "median-of-3 distance\nthreshold check\n2-sample debounce", BLUE, WASH_BLUE)
    s2 = card(draw, 520, 250, 360, 185, "Queue estimate", "far rising edge = incoming\nnear leaving edge = passed\nqueue = incoming - passed", GREEN, WASH_GREEN)
    s3 = card(draw, 960, 250, 360, 185, "Demand score", "3 * queue\n+ 2 * far occupied\n+ 4 * near occupied", PURPLE, WASH_PURPLE)
    s4 = card(draw, 1400, 250, 360, 185, "Decision rules", "minimum green\nmaximum green\nyellow before switch", AMBER, WASH_AMBER)
    for left, right in zip([s1, s2, s3], [s2, s3, s4]):
        arrow(draw, (left[2] + 25, 337), (right[0] - 25, 337), MUTED, 5)

    rounded(draw, (170, 520, 1750, 690), "#FFFFFF", LINE, 3, 28)
    draw.text((205, 550), "Core formula used by firmware and simulator", fill=PURPLE, font=H2)
    draw.text((585, 600), "demand = 3 x queue + 2 x farOccupied + 4 x nearOccupied", fill=INK, font=font(34, True))

    e1 = card(draw, 160, 760, 420, 170, "Emergency override", "Button or telemetry can request priority.\nStill transitions through yellow.", RED, WASH_RED)
    e2 = card(draw, 750, 760, 420, 170, "Stale LoRa handling", "Old Node A packets are not trusted.\nBackup keeps Side A non-empty.", AMBER, WASH_AMBER)
    e3 = card(draw, 1340, 760, 420, 170, "Output", "TrafficDecision -> applyLights()\nSide A or Side B gets green.", GREEN, WASH_GREEN)
    arrow(draw, (s4[0] + 180, s4[3] + 20), (e3[0] + 210, e3[1] - 20), GREEN)
    arrow(draw, (e1[2] + 35, 842), (e2[0] - 35, 842), MUTED)
    arrow(draw, (e2[2] + 35, 842), (e3[0] - 35, 842), MUTED)

    save(image, "03-adaptive-algorithm.png")


def render_software_components() -> None:
    image, draw = new_canvas(
        "4. Software Components",
        "The repository is divided into firmware, shared control logic, laptop tools, simulator, and final evidence assets.",
    )

    firmware = card(draw, 80, 255, 500, 230, "Firmware nodes", "firmware/node_a/main.cpp\nfirmware/node_b/main.cpp\nsetup(), loop(), sensor reads,\nLoRa calls, LED output", BLUE, WASH_BLUE)
    shared = card(draw, 710, 255, 500, 230, "Shared C++ libraries", "SensorSupport.cpp\nTrafficSensing.cpp\nAdaptiveController.cpp\nNodeMessaging.cpp\nLoRaTransport.cpp", GREEN, WASH_GREEN)
    tools = card(draw, 1340, 255, 500, 230, "Laptop tools", "road_data_logger.py\nfinal_evidence_report.py\nfinal_presentation_graphs.py\nroad_dashboard.py", TEAL, WASH_TEAL)

    sim = card(draw, 230, 630, 500, 230, "Simulator", "visual_simulator.py\ntraffic_logic.py\nCSV replay, direct queues,\nrandom/scenario modes", PURPLE, WASH_PURPLE)
    data = card(draw, 860, 630, 500, 230, "Data + evidence", "road_26-05-19_crossroads.csv\npresentation graphs\nPPT diagrams\nfinal reports", AMBER, WASH_AMBER)
    docs = card(draw, 1490, 630, 350, 230, "Docs", "hardware map\ncode guide\nlive log format\ncode-flow diagrams", RED, WASH_RED)

    arrow(draw, (firmware[2] + 35, 370), (shared[0] - 35, 370), GREEN)
    label(draw, 600, 340, "uses", GREEN)
    arrow(draw, (shared[2] + 35, 370), (tools[0] - 35, 370), TEAL)
    label(draw, 1250, 340, "parsed by", TEAL)
    poly_arrow(draw, [(tools[0] + 250, tools[3] + 25), (tools[0] + 250, 590), (data[0] + 250, data[1] - 25)], TEAL)
    label(draw, 1380, 540, "writes CSV / graphs", TEAL)
    arrow(draw, (data[0] - 35, 745), (sim[2] + 35, 745), PURPLE)
    label(draw, 760, 713, "CSV replay input", PURPLE)
    arrow(draw, (data[2] + 35, 745), (docs[0] - 35, 745), RED)
    label(draw, 1390, 713, "explained in", RED)

    rounded(draw, (80, 930, 1840, 1012), "#FFFFFF", LINE, 3, 20)
    wrapped(
        draw,
        110,
        948,
        "Key point for the professor: the simulator and evidence scripts are not separate stories; they consume the same controller ideas and the same real CSV produced by the IoT hardware.",
        145,
        INK,
        BODY,
        27,
    )
    save(image, "04-software-components.png")


def render_digital_twin() -> None:
    image, draw = new_canvas(
        "5. Real Data To Simulator Replay",
        "The digital twin is connected to the field test: real queue pressure drives the visual simulator.",
    )

    p1 = card(draw, 75, 270, 310, 180, "Road demo", "phone video\nreal crossroad\ntruth labels", BLUE, WASH_BLUE)
    p2 = card(draw, 445, 270, 310, 180, "Live terminal", "B STATUS\nqueues + distances\nLoRa freshness", GREEN, WASH_GREEN)
    p3 = card(draw, 815, 270, 310, 180, "Saved CSV", "2160 samples\n18.0 min\nvehicle/empty labels", TEAL, WASH_TEAL)
    p4 = card(draw, 1185, 270, 310, 180, "Evidence metrics", "TP/TN/FP/FN\naccuracy\nLoRa stale\nenergy", AMBER, WASH_AMBER)
    p5 = card(draw, 1555, 270, 310, 180, "Simulator replay", "load_road_frames()\n_csv_spawn_rates()\nvisual cars", PURPLE, WASH_PURPLE)
    for left, right in zip([p1, p2, p3, p4], [p2, p3, p4, p5]):
        arrow(draw, (left[2] + 24, 360), (right[0] - 24, 360), MUTED, 5)

    rounded(draw, (150, 575, 1770, 805), "#FFFFFF", LINE, 3, 28)
    draw.text((190, 600), "Mapping from CSV to simulator", fill=PURPLE, font=H2)
    mappings = [
        ("a_queue / remote_queue", "Side A traffic pressure"),
        ("b_queue / local_queue", "Side B traffic pressure"),
        ("a_far_cm, b_far_cm", "display real sensor distances"),
        ("remote_source", "show LORA_RADIO or LORA_STALE"),
        ("green_side + phase", "compare firmware and simulator state"),
    ]
    x = 190
    for i, (field, meaning) in enumerate(mappings):
        yy = 650 + (i % 3) * 46
        xx = x + (i // 3) * 760
        pill(draw, xx, yy, field, TEAL, WASH_TEAL)
        draw.text((xx + 300, yy), meaning, fill=INK, font=SMALL)

    rounded(draw, (250, 885, 1670, 970), WASH_GREEN, GREEN, 3, 22)
    wrapped(
        draw,
        285,
        905,
        "Correct explanation: the simulator does not prove the road saved time directly; it replays the measured demand and estimates what adaptive control would do compared with fixed-time control.",
        120,
        INK,
        BODY,
        27,
    )
    save(image, "05-real-data-simulator-loop.png")


def render_hardware_network() -> None:
    image, draw = new_canvas(
        "Main Hardware Components + Network Diagram",
        "Live-demo prototype: two ESP32 LoRa nodes, four ultrasonic sensors, traffic-light LEDs, emergency input, logging, and energy measurement.",
    )

    sensor_a = card(
        draw,
        80,
        245,
        440,
        170,
        "Side A physical sensors",
        "2x HC-SR04 modules\nA_far: approaching vehicle\nA_near: stop-line / queue\nDemo threshold: 50 cm",
        BLUE,
        WASH_BLUE,
        30,
    )
    node_a = card(
        draw,
        80,
        505,
        440,
        235,
        "Node A - sensing node",
        "Heltec WiFi LoRa 32 V3\nSide A queue estimator\nLoRa telemetry TX",
        BLUE,
        SURFACE,
        28,
    )

    lora = card(
        draw,
        650,
        305,
        620,
        245,
        "Wireless network",
        "LoRa 868 MHz link\nDirection: Node A -> Node B\nPacket contains queue, far/near occupancy, distances, emergency flag, and timestamp\nNode B checks freshness before control",
        AMBER,
        WASH_AMBER,
        56,
    )

    laptop = card(
        draw,
        650,
        675,
        620,
        230,
        "Laptop evidence pipeline",
        "USB serial from Node B\nroad_data_logger.py saves live CSV\nfinal_evidence_report.py: TP/TN/FP/FN, accuracy, stale %, energy\nvisual_simulator.py replays real queue pressure",
        TEAL,
        WASH_TEAL,
        48,
    )

    sensor_b = card(
        draw,
        1400,
        245,
        440,
        170,
        "Side B physical sensors",
        "2x HC-SR04 modules\nB_far: approaching vehicle\nB_near: stop-line / queue\nDemo threshold: 50 cm",
        GREEN,
        WASH_GREEN,
        30,
    )
    node_b = card(
        draw,
        1400,
        505,
        440,
        250,
        "Node B - controller node",
        "Heltec WiFi LoRa 32 V3\nSide B + LoRa RX\nControls lights + button",
        GREEN,
        SURFACE,
        28,
    )
    actuators = card(
        draw,
        1400,
        795,
        440,
        145,
        "Actuators",
        "6 LEDs with resistors\nSide A: red/yellow/green\nSide B: red/yellow/green",
        RED,
        WASH_RED,
        36,
    )

    energy = card(
        draw,
        80,
        795,
        440,
        145,
        "INA219 energy measurement",
        "INA219 in 5V supply path\nNode A: 123.0 mA avg\nNode B: 174.8 mA avg",
        PURPLE,
        WASH_PURPLE,
        38,
    )

    # Component pictures inside the diagram cards.
    draw_ultrasonic_module(draw, 372, 318, 0.82)
    draw.text((427, 386), "x2", fill=BLUE, font=H2)
    paste_fit(image, ESP_IMAGE, (190, 615, 500, 730))
    draw_ultrasonic_module(draw, 1692, 318, 0.82)
    draw.text((1747, 386), "x2", fill=GREEN, font=H2)
    paste_fit(image, ESP_IMAGE, (1540, 640, 1815, 735))
    draw_laptop_icon(draw, 1060, 760, 0.85)
    draw_ina219_module(draw, 356, 835, 0.86)

    # Hardware signal arrows.
    arrow(draw, ((sensor_a[0] + sensor_a[2]) // 2, sensor_a[3] + 22), ((node_a[0] + node_a[2]) // 2, node_a[1] - 22), BLUE, 6)
    label(draw, 180, 450, "GPIO trigger/echo", BLUE)
    arrow(draw, (node_a[2] + 28, 610), (lora[0] - 28, 430), AMBER, 7)
    label(draw, 545, 500, "LoRa TX", AMBER)
    arrow(draw, (lora[2] + 28, 430), (node_b[0] - 28, 610), AMBER, 7)
    label(draw, 1298, 500, "LoRa RX", AMBER)
    arrow(draw, ((sensor_b[0] + sensor_b[2]) // 2, sensor_b[3] + 22), ((node_b[0] + node_b[2]) // 2, node_b[1] - 22), GREEN, 6)
    label(draw, 1500, 450, "GPIO trigger/echo", GREEN)
    arrow(draw, ((node_b[0] + node_b[2]) // 2, node_b[3] + 20), ((actuators[0] + actuators[2]) // 2, actuators[1] - 20), RED, 6)
    label(draw, 1515, 765, "GPIO LED outputs", RED)
    poly_arrow(draw, [(1400, 685), (1315, 685), (1315, 790), (1270, 790)], TEAL, 6)
    label(draw, 1278, 650, "USB serial log", TEAL)
    arrow(draw, (960, 550), (960, 675), TEAL, 6)
    label(draw, 985, 595, "saved evidence", TEAL)

    # Small visual hints for the traffic-light heads.
    for x in [1660, 1760]:
        draw.rounded_rectangle((x, 835, x + 56, 902), radius=14, fill="#202833", outline="#667085", width=2)
        for y, color in [(848, RED), (868, AMBER), (888, GREEN)]:
            draw.ellipse((x + 20, y, x + 36, y + 16), fill=color, outline="#111827")
    draw.text((1646, 910), "Side A", fill=MUTED, font=TINY)
    draw.text((1746, 910), "Side B", fill=MUTED, font=TINY)

    rounded(draw, (80, 950, 1840, 1015), "#FFFFFF", LINE, 3, 18)
    wrapped(
        draw,
        110,
        966,
        "Voltage notes: boards and HC-SR04 sensors are powered from 5V; ESP32 GPIO is 3.3V logic, so each HC-SR04 ECHO line needs a divider or level shifter. LED outputs use current-limiting resistors.",
        150,
        INK,
        SMALL,
        22,
    )

    save(image, "06-hardware-network-diagram.png")


def main() -> None:
    render_service_architecture()
    render_lora()
    render_algorithm()
    render_software_components()
    render_digital_twin()
    render_hardware_network()


if __name__ == "__main__":
    main()
