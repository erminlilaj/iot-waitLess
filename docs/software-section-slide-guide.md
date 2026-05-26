# Software Section Slide Guide

Use this deck section for the professor's software / algorithm part.

PPTX file:

- `docs/Wait_Less_Software_Section.pptx`

## Slide Order

| Slide | Topic | Main message |
| --- | --- | --- |
| 1 | General structure | Software is a pipeline: sensors -> firmware -> shared logic -> LoRa -> logger -> evaluation -> simulator. |
| 2 | Node A / Node B | Node A senses and transmits; Node B receives, decides, controls lights, and logs evidence. |
| 3 | Shared code | Shared modules keep both nodes consistent: sensing, queue estimation, packets, controller, INA219. |
| 4 | Algorithm | Demand score is explainable: `3*queue + 2*far + 4*near`, with safe timing and emergency rules. |
| 5 | Communication before improving | Early packet sending proved connectivity but did not prove freshness, distances, emergency, or reliability. |
| 6 | Communication after improving | Final packet includes distances and emergency; Node B detects stale data and backup mode. Future heartbeat separates no cars from node failure. |
| 7 | Power before / after | INA219 measured the baseline; adaptive duty cycling is the next optimization. Do not claim it is already measured. |
| 8 | Simulators | CSV replay connects real-road data to the visual simulator, making it a digital-twin replay. |

## Important Phrases To Say

- "The simulator is not the evidence by itself; the evidence is the real CSV collected from the road."
- "The first communication version only showed that a packet could be sent. The final version sends useful state and handles stale data."
- "For energy, the measured INA219 values are the baseline. Sleep and heartbeat are proposed improvements, with a known detection tradeoff."
- "HC-SR04 cannot wake a sleeping ESP32 alone, because it needs a trigger pulse. True wake-on-car needs a low-power detector."

## Source Files Behind The Snippets

- `firmware/node_a/main.cpp`
- `firmware/node_b/main.cpp`
- `lib/traffic_control/SensorSupport.cpp`
- `lib/traffic_control/TrafficSensing.cpp`
- `lib/traffic_control/TrafficTypes.h`
- `lib/traffic_control/AdaptiveController.cpp`
- `lib/traffic_control/NodeMessaging.cpp`
- `firmware/shared/Ina219Support.cpp`
- `simulation/visual_simulator.py`
