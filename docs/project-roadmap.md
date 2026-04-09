# Project Roadmap

Roadmap for the `Wait Less` adaptive traffic light project, from the current setup phase to the final course delivery.

## Planning Assumptions

- Current checkpoint deadline: Friday, April 10, 2026
- The exact final-delivery date is not yet written in this repository, so the last stages are organized by milestone rather than a fixed calendar date
- The project can use a mix of real hardware and simulated demos while the full system is still being integrated

## Stage 0 - Project Alignment and Technical Foundation

### Goal

Turn the initial idea into a structured technical project with shared architecture, code layout, and demo-ready logic.

### Main Tasks

- align the project story across slides, notes, and code
- define the roles of Node A and Node B
- create the firmware structure for both ESP32 boards
- define the telemetry format and adaptive control logic
- create a local simulator for early demos

### Deliverables

- repository structure
- README
- shared controller logic
- firmware skeleton for both nodes
- local simulation script

### Exit Criteria

- the project is no longer only a concept deck
- the team can explain the system architecture clearly
- the adaptive behavior can already be shown in simulation

## Stage 1 - Checkpoint Delivery on April 10, 2026

### Goal

Present clear technical progress and demonstrate core functionalities in a 5-minute checkpoint delivery.

### Main Tasks

- prepare a short technical presentation focused on implementation, not only the idea
- state the current baseline requirements using explicit numbers
- define the metrics used to verify those requirements
- summarize the experiments already executed and the current results
- show the architecture: sensors, LoRa communication, controller, LEDs
- demo at least one core functionality:
  - local simulator
  - bench demo with LEDs and emulated sensor inputs
  - partial LoRa or message-flow demo
- report early evaluation of individual components
- record and upload a public YouTube video
- publish all material in the same GitHub repository

### Deliverables

- 5-minute presentation
- checkpoint demo video
- GitHub repository with code and documentation
- requirements, metrics, and experiments summary
- short evaluation summary of what has already been tested
- plan for the remaining development

### Exit Criteria

- the group can explain what has been built so far
- the group can demo a working part of the system
- the group can defend the checkpoint using requirements, metrics, and experiments
- the repository is ready to be shared through Google Classroom

## Stage 2 - Hardware Bring-Up and Sensor Validation

### Goal

Make the sensing setup reliable on the real boards and verify that each side can detect traffic events correctly.

### Main Tasks

- wire the far and near sensors on both sides
- confirm the final sensor choice and keep documentation consistent
- calibrate detection thresholds
- test false positives and missed detections
- verify LED outputs for all traffic-light states

### Deliverables

- validated pin mapping
- sensor calibration notes
- simple bench tests for vehicle presence and queue detection

### Exit Criteria

- both sides can produce stable occupancy readings
- the team knows the safe operating thresholds for the sensors
- the LED states match the intended traffic phases

## Stage 3 - LoRa Communication Integration

### Goal

Replace the current communication stub with real LoRa messaging between the two ESP32 nodes.

### Main Tasks

- integrate the selected LoRa library
- send and receive telemetry packets between nodes
- validate packet format and parsing
- choose update frequency and retransmission strategy if needed
- measure practical latency and message reliability

### Deliverables

- real LoRa packet exchange between Node A and Node B
- tested telemetry format
- basic communication logs

### Exit Criteria

- Node B receives valid data from Node A consistently
- telemetry updates arrive in the expected time window
- the system can continue operating if one packet is missed

## Stage 4 - Full Adaptive Traffic-Light Control

### Goal

Connect live sensing and LoRa data to the traffic-light controller so the LEDs react to real traffic demand.

### Main Tasks

- connect the shared controller logic to the real sensor data
- apply minimum green, yellow, and maximum green timing rules
- switch sides based on queue pressure and empty-lane detection
- prevent rapid oscillation or unstable behavior
- test typical scenarios on the bench

### Deliverables

- integrated end-to-end prototype
- controller timing parameters
- scenario-based validation notes

### Exit Criteria

- the system adapts its green side based on demand
- yellow transitions happen safely before switching
- the controller behaves predictably across multiple traffic scenarios

## Stage 5 - Evaluation and System Improvement

### Goal

Collect evidence that the system works and improve the weak points before the final submission.

### Main Tasks

- evaluate latency, responsiveness, and queue handling
- estimate or measure energy usage on each node
- log representative traffic scenarios
- compare adaptive behavior against a simple fixed-cycle baseline
- refine thresholds, timing values, and message intervals

### Deliverables

- evaluation results
- comparison tables or charts
- tuned configuration values

### Exit Criteria

- the team can support its design choices with data
- the project includes measurable technical evaluation, not only implementation
- the final demo behavior is stable enough to present confidently

## Stage 6 - Final Delivery and Project Packaging

### Goal

Package the project as a complete final submission with a coherent technical story, final demo, and supporting material.

### Main Tasks

- finalize code and documentation
- prepare final slides and final demo video
- summarize architecture, implementation, evaluation, and lessons learned
- clean the repository structure
- verify that all required links and files are included

### Deliverables

- final repository
- final presentation
- final demo
- final evaluation summary

### Exit Criteria

- the project is complete, documented, and easy to review
- the final demo matches the implementation shown in the repository
- the team is ready for questions on design, tradeoffs, and evaluation

## Suggested Order of Work Right Now

1. Finish Stage 1 material for April 10, 2026.
2. Start Stage 2 sensor wiring and validation in parallel.
3. Move to Stage 3 LoRa integration as soon as one sensing path is stable.
4. Use Stages 4 and 5 to turn the prototype into a complete final system.
