# April 10 Readiness Checklist

Checklist for the first group-project demo on Friday, April 10, 2026.

The checkpoint is ready only when all required submission items are complete, not only when the simulator works.

## Current Status Snapshot

- Core simulator demo: `done`
- Emergency-priority simulator: `done`
- Shared controller logic: `done`
- ESP32 firmware skeleton: `done`
- ESP32 firmware build and upload on both boards: `done`
- Real LoRa communication from Node A to Node B: `done`
- Requirements / metrics / experiments document: `done`
- 5-minute slide deck: `not done yet`
- Public YouTube video: `not done yet`
- Public GitHub repository: `not done yet`
- README updated with final repository/video links: `not done yet`

## Required For April 10

- [x] A working technical baseline exists in the repository
- [x] The project architecture is documented
- [x] A demo of a core functionality exists
- [x] Quantified baseline requirements are written down
- [x] Metrics for the checkpoint are written down
- [x] Experiments and current results are written down
- [ ] A 5-minute presentation is finalized
- [ ] A public YouTube demo video is recorded and uploaded
- [ ] A public GitHub repository is created
- [ ] The GitHub repository contains code, docs, and the video link
- [ ] The repository link is ready to submit on Google Classroom

## Recommended Slide Structure

- [ ] Slide 1: project goal and distributed architecture
- [ ] Slide 2: quantified baseline requirements
- [ ] Slide 3: metrics used for verification
- [ ] Slide 4: experiments, results, and conclusions
- [ ] Slide 5: remaining work until final delivery

## Demo Content Checklist

- [ ] Show one normal adaptive-switching scenario
- [ ] Explain the demand score with numbers
- [ ] Point out `min green = 5 s`, `yellow = 2 s`, `max green = 20 s`
- [ ] Show one experiment where the busier side gets priority
- [ ] Show one experiment where starvation is prevented by the max-green cap

## Evidence Already Available

- [x] Current control-loop target: `200 ms`
- [x] Current telemetry interval: `1000 ms`
- [x] Current thresholds: far `35 cm`, near `18 cm`
- [x] Current message format example: `A,1,0,4,2,2,0,12345`
- [x] Current payload example size: `19 bytes`
- [x] Current yellow transition duration: `2000 ms`
- [x] Current max-green cap: `20000 ms`
- [x] Real hardware upload completed on `Node A` and `Node B`
- [x] Real LoRa backend confirmed on both boards: `RadioLib SX1262`
- [x] Real telemetry transmission confirmed on Node A: `tx=RADIO_TX_OK`
- [x] Real telemetry reception confirmed on Node B: `source=LORA_RADIO | stale=OFF`

## Missing Before Final Packaging

- [ ] create the GitHub repository
- [ ] record the simulator video
- [ ] make the video public on YouTube
- [ ] add the YouTube link to the repository README
- [ ] check that all docs tell the same hardware story

## Suggested Order From Now To Friday

1. Finalize the slide deck from `docs/checkpoint-demo.md` and `docs/april-10-presentation-pack.md`.
2. Record the simulator demo.
3. Create the GitHub repository and upload the project.
4. Add the YouTube link to the README.
5. Rehearse the 5-minute explanation once with the experiment table in front of you.
