# POC summary — Varun's lane (CCTV, dashboard, API)

Feasibility prototype — not for flood warning. Inputs for the broader team POC summary; see `docs/VARUN_IMPLEMENTATION.md` for the full task-by-task status board.

## Legal status (T10)

All five CCTV/DDS sources are still `PENDING` in `cctv/legal_status.yaml` — HU1 (reading each source's ToS/robots.txt and making the GO/NO_GO call) hasn't happened yet. The code-enforced gate (`cctv/legal_gate.py::require_go`) is built and tested (8/8 tests); the archiver (T20) and DDS snapshotter (T21) refuse to start until it does.

| Source | Decision |
|---|---|
| bmatraffic | PENDING |
| itic | PENDING |
| longdo | PENDING |
| dds_flood | PENDING |
| dds_scada | PENDING |

## Frames captured

**0 real frames** — the archiver has never run against a real source (blocked on the legal gate above plus HU2/HU3: a real camera list and snapshot URLs). Everything below is the T01 synthetic fixture, used to build and test the entire pipeline so it's ready the moment real inputs land:

- 10 synthetic cameras, 30 frames each = 300 frames, covering a synthetic 58-minute window (not real rain).
- 30 unique images (the other 270 are byte-identical duplicates by the fixture generator's own design — correctly deduplicated by the embedding cache, not a bug).
- All classify `NORMAL` under zero-shot CLIP — the fixture's "water" is a flat blue rectangle, nothing like a real flood photo (see `docs/assumptions.md`).

## Classifier (T50/T52/T53)

- **Model**: zero-shot CLIP (`ViT-B-32`, `laion2b_s34b_b79k`), `model_version: clip-zs-v0`.
- **macro-F1 / inter-rater κ: N/A.** No labelled frames exist — T52 needs HU5 (200–400 human-labelled frames, 50 double-labelled) and the labelling app (T51) is built and ready, but no one has used it yet.
- **H6 delivered**: `data/cctv/cctv_obs.parquet` (handoff to Rishanth, `docs/handoff_H6.md`) — honest about running on synthetic fixtures with no validated accuracy yet.

## L3 validation (T54)

The shared comparison functions (`validation/cctv/compare.py::model_series`, `::confusion`) are built and unit-tested (κ=1 on an identical synthetic series, exact pond-centre depth recovery, cells correctly bounded to the 30 m buffer) but **never run against real CCTV classifications or a real hydraulic run** — both inputs are still synthetic. `road_clip` is always `false` (no OSM roads file from Dhanya yet); the real intersect-with-roads code path exists, just unexercised.

## Component checklist (18 total)

15/18 live and working today (on fixtures); 3/18 blocked on real data from teammates (T60) — their API contract already exists and returns an explicit gap rather than failing silently.

| # | Component | Status |
|---|---|---|
| 1 | Map / base layers | ✅ live |
| 2 | Domain boundary layer | ✅ live |
| 3 | Time slider | ✅ live |
| 4 | Animation player (play/pause/fps/preload) | ✅ live |
| 5 | Scenario selector | ✅ live |
| 6 | Stations layer + chart | ✅ live |
| 7 | Camera layer + panel | ✅ live |
| 8 | Satellite overlay | ⏳ blocked on H4 (real acquisitions) — `GET /api/runs/{id}/satellite` already returns a clean gap |
| 9 | DDS/road-flood observations | ⏳ blocked on H4 — `GET /api/observations` already returns a clean gap |
| 10 | Citizen report observations | ⏳ blocked on H4 — same endpoint as #9 |
| 11 | Surrogate layers (depth/extent/σ) | ✅ live |
| 12 | Static frame rendering | ✅ live |
| 13 | Frame preloading | ✅ live |
| 14 | Hydraulic↔surrogate swipe | ✅ live |
| 15 | Legend / variable toggle | ✅ live |
| 16 | What-if panel | ✅ live |
| 17 | Error layer + OOD banner | ✅ live |
| 18 | Provenance footer + MOCK watermark | ✅ live |

## Measured latencies (this machine, fixtures)

| Metric | Target | Measured |
|---|---|---|
| Dashboard initial load | ≤3s | ~350–485ms |
| Frame switch (steady state, preloaded) | ≤200ms | ~1–2ms mean |
| What-if first frames | ≤5s | ~0.7–0.9s |

## Known gaps

- **Parent requirements docs aren't in this repo** (`BANGKOK_FLOOD_POC_REQUIREMENTS_AND_WORKFLOW.md`, `SCENARIO_SCHEMA.md`, `TEAM_TASK_BOARD.md`) — several field lists, POC validation targets (§21), and the sensor-ingestion architecture (§19) had to be reconstructed from cross-references inside the plan itself rather than the real spec. Every spot this mattered is flagged `[ASSUMPTION]` in `docs/assumptions.md`.
- **No real CCTV or DDS data** — legal clearance (T10), a camera list (HU2), snapshot URLs (HU3), and DDS endpoints (HU4) are all still pending.
- **No real hydraulic/observation/surrogate data** — H2, H4, H5 haven't landed from the hydraulic/surrogate team.
- **No labelled CCTV frames** — HU5 (200–400 labels) hasn't started; the labelling app (T51) is ready.
- **No public CCTV archive** — the only way to capture a real flood frame is live, during actual rain, once the above unblocks.
- **No OSM roads file** from Dhanya yet — `road_clip` stays `false` everywhere in the L3 helper.

## What's demo-ready right now

Everything above the "known gaps" section: the full dashboard — map, animation, swipe, what-if, OOD banner, provenance, CCTV panel, metrics with pass/fail — works end to end on the T01 fixtures with no human setup beyond `make dashboard`. See `reports/demo_script.md` for the guided walkthrough.
