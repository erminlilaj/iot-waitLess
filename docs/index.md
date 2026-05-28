# Wait Less

**An ESP32 + LoRa adaptive traffic-light prototype tested with real road data.**

![Wait Less service architecture](presentation_assets/01-service-architecture.png)

Wait Less connects real ultrasonic sensors, ESP32 firmware, LoRa telemetry, adaptive traffic-light control, CSV evidence, energy measurements, and a digital-twin replay.

```text
real sensors -> ESP32 firmware -> LoRa telemetry -> traffic-light control -> CSV evidence -> evaluation -> simulator replay
```

## Project Highlights

| Metric | Result |
| --- | ---: |
| Road dataset duration | `18.0 min` |
| Labelled samples | `2160` |
| Detection accuracy | `96.6%` |
| False positive rate | `6.7%` |
| False negative rate | `1.2%` |
| LoRa stale rows | `3.0%` |
| Conservative vehicle-speed target | `35-40 km/h` |

[Read the full project blog post](final/blog_post.html)

## What The System Uses

- 2 x ESP32 Heltec WiFi LoRa 32 V3 boards
- 4 x HC-SR04 ultrasonic sensors
- LoRa communication between road-side nodes
- Adaptive controller with queue estimation
- INA219 current sensing for energy measurements
- Real road CSV logs and simulator replay

![Vehicle speed detection calculation](presentation_assets/07-speed-detection-calculation.png)
