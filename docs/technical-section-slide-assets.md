# Technical Section Slide Assets

Use these pictures for the professor's required section:

> The architecture of your service, the algorithms and software components (3-4 minute)

For the separate required hardware/network slide:

| Slide picture | What to say |
| --- | --- |
| `presentation_assets/06-hardware-network-diagram.png` | "The physical IoT system uses two Heltec ESP32 LoRa nodes. Node A measures Side A with two ultrasonic sensors and sends LoRa telemetry. Node B measures Side B, receives Node A, drives both traffic-light heads, sends the live log to the laptop, and was measured with INA219 for energy." |

Recommended split:

| Time | Slide picture | What to say |
| --- | --- | --- |
| 0:00-0:45 | `presentation_assets/01-service-architecture.png` | "This is the full IoT service: Node A senses Side A, Node B senses Side B, LoRa connects them, Node B controls the lights, and the laptop stores evidence." |
| 0:45-1:30 | `presentation_assets/02-lora-communication.png` | "Node A sends a compact telemetry packet. Node B decodes it and checks whether it is fresh or stale before using it." |
| 1:30-2:20 | `presentation_assets/03-adaptive-algorithm.png` | "The algorithm filters sensor readings, estimates the queue, computes demand, then switches lights using min-green/yellow/emergency rules." |
| 2:20-3:05 | `presentation_assets/04-software-components.png` | "The codebase is separated into firmware nodes, shared C++ logic, laptop tools, simulator, data, and documentation." |
| 3:05-3:45 | `presentation_assets/05-real-data-simulator-loop.png` | "The simulator replay is connected to the field CSV; it is a digital twin driven by real queue pressure, not only invented traffic." |

If the presentation is short, merge the first and fourth pictures:

- show `01-service-architecture.png` for the overall architecture;
- show `02-lora-communication.png` for LoRa;
- show `03-adaptive-algorithm.png` for the algorithm;
- show `05-real-data-simulator-loop.png` for the real-data simulator connection.

## Picture Files

- `docs/presentation_assets/01-service-architecture.png`
- `docs/presentation_assets/02-lora-communication.png`
- `docs/presentation_assets/03-adaptive-algorithm.png`
- `docs/presentation_assets/04-software-components.png`
- `docs/presentation_assets/05-real-data-simulator-loop.png`
- `docs/presentation_assets/06-hardware-network-diagram.png`

These files are 16:9 PNGs, so they can be used as full-slide images in PowerPoint.
