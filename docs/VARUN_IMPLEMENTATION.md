# VARUN_IMPLEMENTATION.md — Agent-executable build plan
## Bangkok Flood POC · CCTV, observation capture & dashboard (Varun's lane) · v2.0 (2026-10-07)

> **This file is written for a CLI AI coding agent** (Claude Code, Codex CLI, Aider, etc.) driven by Varun.
> The agent executes **one task card at a time** (§6), runs that card's **Verify** commands, commits, and stops.
> Anything marked **🧑 HUMAN** is a decision or input only Varun can provide — the agent must stop and ask.

Parent docs (place in `docs/`): `BANGKOK_FLOOD_POC_REQUIREMENTS_AND_WORKFLOW.md` (cited as §NN), `SCENARIO_SCHEMA.md`, `TEAM_TASK_BOARD.md`.
Save this file as `docs/VARUN_IMPLEMENTATION.md`.

---

## 0. How to drive the agent

### 0.1 One-time setup
1. Repo root = `bkk-flood-poc/` (Rishanth's scaffold, R1.1). If it doesn't exist yet, task **T00** creates the parts Varun needs.
2. Copy §1 (Agent rules) into the agent's standing-instructions file at repo root (`CLAUDE.md` for Claude Code, `AGENTS.md` for Codex, `CONVENTIONS.md` for Aider) so the rules load on every session.
3. Create `.env` (git-ignored) from `.env.example` (T00) and fill the 🧑 HUMAN values in §3 as you get them.

### 0.2 Prompt to start each task (copy-paste, change the ID)
```
Read docs/VARUN_IMPLEMENTATION.md sections 1, 2, 3 and task card T40 in section 6.
Execute task card T40 only. Follow the Agent rules exactly.
Create/modify only the files listed in the card. Use fixtures from T01 if real inputs are missing.
When finished: run every Verify command, show the output, update section 4 status for T40,
commit on branch task/T40 with message "T40: <summary>", then stop and report.
If a step needs a 🧑 HUMAN input, stop and ask instead of guessing.
```

### 0.3 Prompt when a step fails
```
Verify for T40 failed with the output above. Diagnose the root cause, fix only files within T40's scope,
re-run all Verify commands, and report. Do not weaken or delete tests to make them pass.
```

### 0.4 Prompt to swap mock → real input when a handoff lands
```
Handoff H2 has landed at outputs/sim/BKK-S07/M000/. Re-run the Verify commands of T40 and T60
against the real data (not fixtures), fix any contract mismatches on my side only, and report
any mismatch that would need a change from Dhanya/Rishanth instead of patching around it.
```

---

## 1. Agent rules (copy into CLAUDE.md / AGENTS.md)

1. **Scope:** Only create/modify paths owned by Varun (§2.2). Never edit `surrogate/`, `models/hydraulic/`, `terrain/`, `scenarios/BKK-*` or teammates' configs — if a contract mismatch is found, write it to `docs/handoff_issues.md` and stop.
2. **One card per session.** Do not start the next card unless told.
3. **No waiting on teammates:** if an upstream artefact (H1/H2/H4/H5) is missing, use the T01 fixtures. Everything mock is prefixed `MOCK_` and carries `is_mock: true`.
4. **Legal gate is enforced in code:** no code may make automated requests to any CCTV or DDS source unless `cctv/legal_status.yaml` says `GO` for that source **and** has `approved_by` filled by a human. The agent must never edit `decision` or `approved_by` fields.
5. **Never commit secrets or snapshot URLs.** Snapshot URL patterns, API keys and endpoints live in `.env` / `secrets/` (git-ignored).
6. **Privacy (PDPA):** CCTV frames are downscaled to ≤ 640 px wide and face/plate-blurred **before** they are written to disk. Raw frames are never persisted. The API never serves anything except blurred frames/thumbnails.
7. **Time & CRS:** store UTC ISO-8601 with `Z`; display ICT (`Asia/Bangkok`). Model grids EPSG:32647; APIs/GeoJSON EPSG:4326; map rendering EPSG:3857.
8. **Never invent data values.** Unknown → `null` + `[DATA GAP]` note. Thresholds that are judgement calls are tagged `[ASSUMPTION]` and mirrored into `docs/assumptions.md`.
9. **Naming:** ASCII, no spaces, follow §29 of the requirements doc. Versions are never overwritten — add a new suffix.
10. **Tests:** every card adds or updates tests; never delete or weaken a test to make it pass. `make test` must be green before commit.
11. **Labels in UI/outputs:** CCTV output is always called "visual flood severity proxy", never "depth". Every screen shows "Feasibility prototype — not for flood warning".
12. **Dependencies:** add Python deps to `environment.yml` (pinned minor versions) and web deps via `npm i` in `dashboard/web` only.
13. **Stop and ask** on any 🧑 HUMAN step, any ambiguity in a contract, or any action that would contact an external website.

---

## 2. Context the agent needs

### 2.1 What Varun's lane delivers
CCTV legal gate · camera registry · CCTV archiver (rate-limited, privacy-blurred) · DDS road-flood/gauge page snapshotter · CCTV flood-severity classifier → `cctv_obs.parquet` (**handoff H6 → Rishanth**) · camera→model-cell mapping for L3 validation · frame renderer (NetCDF → PNG + manifest) · FastAPI backend (§30.2) · React + Vite + MapLibre + deck.gl dashboard with 18 components (§20.1) · what-if prediction endpoint · sensor-ingest stub + spec (§19, O11) · demo.

### 2.2 Paths owned by Varun (agent may write here)
```
configs/cctv.yaml                    configs/thresholds.yaml (CCTV section only, J1 shared)
cctv/**                              validation/cctv/**
ingest/dds.py  ingest/dds_endpoints.example.yaml
dashboard/**                         tools/fixtures/**
docs/VARUN_IMPLEMENTATION.md         docs/sensor_ingestion_spec.md
docs/stakeholder_requests/bma_cctv.md   docs/handoff_issues.md
reports/cctv_classifier_v1.md        reports/demo_script.md
tests/varun/**                       Makefile (only targets listed in §5)
.env.example                         data/cctv/**  data/raw/obs/dds/**  (git-ignored)
```
Shared append-only: `docs/assumptions.md`, `docs/data_gaps.md` (append under a `## Varun` heading).

### 2.3 Inputs from teammates (contracts) and their mock stand-ins
| Handoff | Real path | Contract | Mock (T01) |
|---|---|---|---|
| H1 domain | `configs/domain.yaml`, analysis polygon GeoJSON | EPSG:32647, 20 m, 512 × 704 (x × y), origin snapped to 20 m | `tools/fixtures/out/domain.yaml` computed from bbox `[100.535, 13.775, 100.630, 13.905]` |
| H2 hydraulic output | `outputs/sim/{scenario_id}/{member_id}/depth.nc` | var `depth_m(time,y,x)` float32, `time` UTC, dt 900 s, attrs `crs, model_version, scenario_id, member_id, run_id, data_class` (§15.9) | `MOCK_BKK-S99/M000/depth.nc` |
| H4 observations | `scenarios/{sid}/observations/road_flood_points.geojson`, `citizen_reports.geojson`, `sat_acquisitions.csv`, `sat_floodmask_*.tif` | SCENARIO_SCHEMA §5 | mock GeoJSON + mask tif |
| H5 surrogate | `outputs/sur/{run_id}/pred.nc` (`depth_m`, `sigma_m` at 40 m, 256 × 352), `reports/surrogate/poc-1/metrics.json` | §17.10; OOD flag per run | `MOCK_` copy of hydraulic, block-averaged ×2, sigma = 0.1·depth |
| predict() | `surrogate/infer.py::predict(...)` (Rishanth) | §7 T71 | `dashboard/api/mock_infer.py` |
| Scenarios | `scenarios/BKK-S*/scenario.yaml` | SCENARIO_SCHEMA §3 | `MOCK_BKK-S99/scenario.yaml` |

### 2.4 Outputs Varun's lane produces (contracts others rely on)
| Artefact | Path | Contract |
|---|---|---|
| Camera registry | `cctv/registry/cameras.geojson` | §6 T11 properties |
| Frame metadata | `data/cctv/cctv_frames.parquet` | `cam_id, ts_utc, http_status, path, sha1, phash, width, height, bytes, quality_flag, sat_mean, lap_var` |
| **H6** CCTV obs | `data/cctv/cctv_obs.parquet` | §6 T53 columns |
| Camera→cells | `validation/cctv/cam_cells.parquet` | `cam_id, row, col, grid_res_m` |
| DDS snapshots | `data/raw/obs/dds/{YYYYMMDD}/` + parsed `data/interim/obs/dds_road_flood.parquet`, `data/interim/stations/*.parquet` | §6 T21 |
| Frames | `dashboard/static/frames/{source}/{run_id}/{var}/{t_idx:03d}.png` + `manifest.json` | §6 T40 |
| API | `http://localhost:8000/api/*` | §30.2 + §6 T30 |

---

## 3. 🧑 HUMAN inputs the agent cannot produce

| # | Input | Needed by | Where to put it | If unavailable |
|---|---|---|---|---|
| HU1 | Legal decision per source (read ToS/robots.txt, decide GO / GO_MANUAL / NO_GO) | T20, T21 | Fill `decision`, `approved_by`, `approved_utc` in `cctv/legal_status.yaml` | Archiver stays disabled; manual frames path |
| HU2 | Camera list (name, coords or map position, source ref) | T11 | `cctv/registry/cameras_input.csv` | Agent uses fixture cameras; registry marked MOCK |
| HU3 | Snapshot URL per camera (from browser devtools) | T20 | `secrets/cctv_urls.json` `{cam_id: url}` | Archiver has nothing to fetch |
| HU4 | DDS/floodbangkok/SCADA endpoint URLs (devtools XHR) | T21 | `secrets/dds_endpoints.yaml` | Snapshotter disabled; Dhanya uses manual exports |
| HU5 | Frame labels (200–400) and road ROI per camera | T52 | via labelling app → `cctv/labelling/labels.csv`, ROI into registry | Ship zero-shot v0 only, report as unvalidated |
| HU6 | Agreement with Rishanth on `predict()` signature | T71 | confirm §6 T71 contract at sync | Mock infer stays, watermarked |
| HU7 | Team contact email for User-Agent | T20 | `.env` `FG_CONTACT_EMAIL` | Archiver refuses to start |
| HU8 | Demo recording | T81 | `reports/demo.mp4` | — |

---

## 4. Status board (agent updates its own row; Varun ticks HUMAN rows)

Today is Wed 07 Oct, ~20:00 ICT (Day 2 gate passed). Tick what already exists before starting; unticked items follow the priority order in §4.1.

| Card | Title | Board ID | Status | Notes |
|---|---|---|---|---|
| T00 | Bootstrap (dirs, configs, deps, Makefile, .env.example) | — | DONE | venv on py3.12 (torch/open_clip/geopandas need <3.13); all 3 verify lines pass |
| T01 | Fixtures (mock domain, depth, surrogate, scenarios, cameras, frames, stations) | — | DONE | 10/10 tests green incl. byte-identical rerun; a few schema fields [ASSUMPTION] since parent docs are missing — see docs/assumptions.md, docs/data_gaps.md |
| T10 | Legal review docs + `legal_status.yaml` (🧑 HU1) | V1.1 | TODO | |
| T11 | Camera registry builder + validator | V1.2 | TODO | |
| T20 | CCTV archiver + quality + privacy + compaction + health | V1.3 | TODO | |
| T21 | DDS snapshotter + offline parser | V1.3 | TODO | |
| T30 | FastAPI backend (all §30.2 endpoints) | V1.4/V2.1 | TODO | |
| T31 | Web app skeleton + base layers + panels | V1.4/V2.1 | TODO | |
| T40 | Frame renderer + colormaps | V2.2 | TODO | |
| T41 | Time slider + animation player | V2.2 | TODO | |
| T50 | Zero-shot classifier + embedding cache | V3.1 | TODO | |
| T51 | Labelling app (labels + ROI) | V3.1 | TODO | |
| T52 | Linear probe + classifier report (🧑 HU5) | V3.2 | TODO | |
| T53 | Write `cctv_obs.parquet` (H6) + synthetic obs | V3.2 | TODO | |
| T54 | Camera → model-cell mapping (L3 helper) | V3.2 | TODO | |
| T60 | Real-data integration (hydraulic, stations, satellite, obs, CCTV panel) | V3.3 | TODO | |
| T70 | Surrogate layers, swipe, error, σ, OOD banner | V4.1 | TODO | |
| T71 | What-if `POST /api/predict` | V4.1 | TODO | |
| T80 | Provenance, MOCK watermark, sensor-ingest stub + spec | V4.2 | TODO | |
| T81 | Perf checks, docs, demo script (🧑 HU8 recording) | V4.2 | TODO | |

### 4.1 Execution order (compressed to the remaining POC window)
| Slot (ICT) | Cards | Why this order |
|---|---|---|
| **Wed 20:00–23:00** | T00 → T01 → T10 (stop for HU1) → T11 → T20 → T21 | Live capture first: this week's rain is the only chance to record flood frames (no public CCTV archive) |
| Thu 09:30–11:30 | T30 → T40 | API + renderer needed for H2 real output |
| Thu 11:30–13:00 | T50 → T51 | Classify frames archived overnight; start labelling (HU5) |
| Thu 14:00–18:00 | T52 → T53 → T54 (**H6 by 18:00**) ; T31 + T41 in a parallel agent session | |
| Thu evening | T60 | H4 lands 18:00 |
| Fri 09:30–13:00 | T70 → T71 | H5 lands 13:00 (build on mock before) |
| Fri 14:00–18:00 | T80 → T81 | Gate G4 18:00 |

Parallelism: frontend cards (T31, T41) touch only `dashboard/web/` and can run in a second agent session (separate git worktree) alongside backend/CCTV cards.

---

## 5. Makefile targets (Varun's)
```make
cctv-archive:     ## start archiver (refuses unless legal GO)
	python -m cctv.archiver.archiver
cctv-health:      ## per-camera last-frame age & error rate
	python -m cctv.archiver.health
cctv-compact:     ## jsonl -> cctv_frames.parquet
	python -m cctv.archiver.compact
dds-snapshot:     ## start DDS snapshotter (refuses unless legal GO)
	python -m cctv.archiver.dds_snapshot
dds-parse:
	python -m ingest.dds
cctv-classify:    ## zero-shot or probe over all OK frames -> cctv_obs.parquet
	python -m cctv.classifier.write_obs --model $(or $(MODEL),auto)
label:
	uvicorn cctv.labelling.label_app:app --port 8010
frames:           ## make frames RUN=<run_id> SRC=hydraulic|surrogate NC=<path>
	python -m dashboard.render.render_frames --run-id $(RUN) --source $(SRC) --nc $(NC)
frames-all:
	python -m dashboard.render.render_all
api:
	uvicorn dashboard.api.main:app --reload --port 8000
web:
	cd dashboard/web && npm run dev
dashboard: ; $(MAKE) -j2 api web
fixtures:
	python -m tools.fixtures.make_fixtures
test-varun:
	pytest -q tests/varun
```

---

## 6. Task cards

Card format: **Goal · Depends · Creates · Spec · Verify · Done when · 🧑 HUMAN**.
Paths are relative to repo root. Python package dirs get `__init__.py`.

---

### T00 — Bootstrap
**Goal:** Folder skeleton, configs, deps, Makefile targets, env template.
**Depends:** none.
**Creates:** dirs from §2.2; `configs/cctv.yaml`; CCTV section of `configs/thresholds.yaml`; `.env.example`; `secrets/.gitkeep`; `.gitignore` entries (`.env`, `secrets/*`, `data/**` except `data/catalog/`); Makefile targets (§5); `tests/varun/conftest.py`; `environment.yml` additions.
**Spec:**
```yaml
# configs/thresholds.yaml — CCTV section (J1 shared; do not touch other keys)
wet_threshold_m: 0.10
wet_threshold_sensitivity_m: [0.05, 0.30]
depth_bins_m: [0.05, 0.15, 0.30, 0.50, 1.0]
cctv_classes: [NORMAL, WATERLOGGING, FLOODING, SEVERE_FLOODING, UNUSABLE]
cctv_depth_proxy_bins_m:            # [ASSUMPTION] §18.4
  NORMAL: [0.00, 0.05]
  WATERLOGGING: [0.05, 0.15]
  FLOODING: [0.15, 0.30]
  SEVERE_FLOODING: [0.30, null]
cctv_onset_class: FLOODING          # onset vs model depth >= 0.15 m
```
```yaml
# configs/cctv.yaml
max_cameras: 50
min_interval_s: 120          # ≤ 1 request / camera / 2 min (§18.1)
jitter_s: 20
timeout_s: 15
max_width_px: 640
thumb_width_px: 320
quality:                     # [ASSUMPTION] tune on first frames
  stale_consecutive: 3
  night_mean_saturation: 12
  blur_laplacian_var: 40
dds_snapshot_interval_s: 900
health:
  offline_after_s: 600
  max_error_rate_1h: 0.5
```
`.env.example`: `FG_CONTACT_EMAIL=`, `FG_API_KEY_INGEST=`, `FG_FRAMES_DIR=dashboard/static/frames`, `FG_SURROGATE_MODE=auto` (`auto|mock|real`).
Python deps: `fastapi uvicorn[standard] httpx respx apscheduler pillow imagehash opencv-python-headless open_clip_torch torch scikit-learn duckdb geopandas shapely pyarrow rioxarray rasterio pyproj xarray netcdf4 pyyaml jsonschema pytest`.
**Verify:**
```bash
python -c "import fastapi, httpx, apscheduler, imagehash, cv2, open_clip, sklearn, duckdb, geopandas, rioxarray, pyproj, xarray; print('deps ok')"
make -n cctv-archive frames api test-varun
git check-ignore .env secrets/x data/cctv/x && echo "ignored ok"
```
**Done when:** all three verify lines succeed.

---

### T01 — Fixtures (lets every other card run without teammates)
**Goal:** Deterministic mock data matching every contract in §2.3.
**Depends:** T00.
**Creates:** `tools/fixtures/make_fixtures.py`, outputs under `tools/fixtures/out/` (git-ignored except tiny files), `tests/varun/test_fixtures.py`.
**Spec (seed 42, all mock artefacts `MOCK_`-prefixed, `is_mock: true`):**
1. `domain.yaml`: transform bbox lower-left (100.535, 13.775) to EPSG:32647, floor to 20 m → origin; width 10 240 m, height 14 080 m; `res_m: 20`; `shape: [704, 512]` (y, x); `crs: EPSG:32647`; `datum_offset_m: 0.0`; plus `analysis_polygon.geojson` (bbox polygon, EPSG:4326). Use real `configs/domain.yaml` if present instead.
2. `MOCK_BKK-S99/M000/depth.nc`: dims `time=96, y=704, x=512`, cell-centre coords, `time` from `2026-09-25T00:00:00Z` step 900 s; depth = two Gaussian ponds whose amplitude follows a rise-and-recede curve (peak 0.8 m at t=40), zero elsewhere; attrs per §15.9 with `data_class: SYNTHETIC`, `model_version: mock-0`.
3. `MOCK_BKK-S99/surrogate/pred.nc`: block-average ×2 → 352 × 256, `depth_m` = hydraulic + small noise, `sigma_m` = 0.1·depth + 0.01; attrs `surrogate_version: mock-0`, `ood_flag: false`.
4. `MOCK_BKK-S99/scenario.yaml`: valid against SCENARIO_SCHEMA required fields, `split: TRAIN`, `scenario_type: SYNTHETIC`.
5. `observations/road_flood_points.geojson` (8 points, depth_cm), `citizen_reports.geojson` (10), `sat_acquisitions.csv` (1 usable S1 row), `sat_floodmask_S1A_20260925T2300Z.tif` (values 0/1/255 on 20 m grid).
6. `cameras.geojson`: 10 cameras inside the bbox with all T11 properties.
7. CCTV frames: 10 cams × 30 frames, synthetic 640×360 JPEGs (grey road, lane lines, a blue "water" polygon whose size grows for 5 cams); written via the same path pattern as the archiver; plus a `cctv_frames.parquet`.
8. Stations: `stations.parquet` (5 rain, 3 level gauges) + 96-step time series.
9. `MOCK_metrics.json` mimicking §17.10 keys.
**Verify:**
```bash
make fixtures
pytest -q tests/varun/test_fixtures.py   # shapes, CRS, attrs, coords, monotonic time, is_mock flags
```
**Done when:** tests green; fixtures regenerate byte-identically on rerun (hash check in test).

---

### T10 — Legal review docs + machine-readable gate (V1.1)
**Goal:** Templates the human fills, and a gate file the code enforces.
**Depends:** T00.
**Creates:** `cctv/LEGAL_REVIEW.md`, `cctv/legal_status.yaml`, `cctv/legal_gate.py`, `docs/stakeholder_requests/bma_cctv.md`, `tests/varun/test_legal_gate.py`.
**Spec:**
- `LEGAL_REVIEW.md`: one section per source (BMA Traffic `http://www.bmatraffic.com/index.aspx`, iTIC Live, Longdo Traffic, DDS floodbangkok, DDS SCADA) with fields: checked_utc, checked_by, ToS URL/text, robots.txt lines, automation allowed (YES/NO/SILENT), redistribution, PDPA exposure, decision, conditions (≤ 1 req/cam/2 min, ≤ 50 cams, UA with contact, ≤ 640 px, blur before storage, purpose = flood observation), escalation. Decision rule text: ToS prohibits automation → NO_GO; silent → GO only with all conditions + BMA request sent.
- `legal_status.yaml`:
```yaml
sources:
  bmatraffic:   {decision: PENDING, approved_by: null, approved_utc: null, conditions_ack: false}
  itic:         {decision: PENDING, approved_by: null, approved_utc: null, conditions_ack: false}
  longdo:       {decision: PENDING, approved_by: null, approved_utc: null, conditions_ack: false}
  dds_flood:    {decision: PENDING, approved_by: null, approved_utc: null, conditions_ack: false}
  dds_scada:    {decision: PENDING, approved_by: null, approved_utc: null, conditions_ack: false}
```
- `legal_gate.py::require_go(source) -> None` raises `LegalGateError` unless `decision == "GO"`, `approved_by` non-empty, `conditions_ack is true`.
- `bma_cctv.md`: data-use request (purpose, camera list placeholder, frequency, retention, blurring, no identity analytics, request for official API + camera coordinates/headings, contact).
**Verify:** `pytest -q tests/varun/test_legal_gate.py` (PENDING/NO_GO/GO-without-approver all raise; full GO passes — using temp files, never the real one).
**🧑 HUMAN (HU1):** Varun reads each site's ToS/robots.txt, fills `LEGAL_REVIEW.md`, sets decisions in `legal_status.yaml`. **Agent stops here and reports.**
**Done when:** tests green; human has recorded decisions.

---

### T11 — Camera registry builder (V1.2)
**Goal:** `cameras.geojson` from a human-provided CSV, validated.
**Depends:** T00, T01 (fixture fallback), H1 or fixture domain.
**Creates:** `cctv/registry/build_registry.py`, `cctv/registry/registry.schema.json`, `cctv/registry/cameras_input.example.csv`, `tests/varun/test_registry.py`.
**Spec:**
- Input `cameras_input.csv`: `source, source_cam_ref, name_th, name_en, lon, lat, loc_method, loc_accuracy_m, heading_deg, road_name, refresh_s, calib_refs, priority`.
- Output properties: `cam_id` (`{SRC}-{NNNN}`, SRC ∈ BMAT, ITIC, LNGD), all input fields, `in_domain` (point-in-analysis-polygon), `nearest_dds_point_id`, `dist_dds_m` (from `data/interim/obs/dds_hotspots.geojson` if present else null), `road_roi_px` (null), `status` (ACTIVE).
- **Never** include snapshot URLs (those are in `secrets/cctv_urls.json`).
- Selection helper `select_for_archive(n=50)`: in_domain, ACTIVE, sorted by priority then `dist_dds_m`.
- If input CSV missing → copy fixture cameras and set `is_mock: true` in the FeatureCollection metadata.
**Verify:** `python -m cctv.registry.build_registry && pytest -q tests/varun/test_registry.py` (schema-valid, EPSG:4326, unique cam_id, no URL-like strings in any property).
**🧑 HUMAN (HU2):** provide `cameras_input.csv`.
**Done when:** registry validates; ≤ 50 cams selectable.

---

### T20 — CCTV archiver (V1.3)
**Goal:** Unattended, polite, privacy-preserving frame capture.
**Depends:** T10 (GO), T11, HU3, HU7.
**Creates:** `cctv/archiver/{archiver.py, quality.py, privacy.py, compact.py, health.py}`, `tests/varun/test_archiver.py`, `tests/varun/test_privacy.py`.
**Spec:**
- On start: `require_go(source)` for every source with selected cameras; refuse to start if `FG_CONTACT_EMAIL` empty. User-Agent `FloodGuard-POC/0.1 (flood research; contact: <email>)`.
- Scheduler: APScheduler `AsyncIOScheduler`, one interval job per camera (`min_interval_s`, `jitter_s`, `max_instances=1`, `coalesce=True`), first runs staggered uniformly across the interval. Single shared `httpx.AsyncClient`.
- Per fetch: reject non-200 / non-image → meta row `quality_flag=HTTP_ERROR`. Decode → RGB → downscale to ≤ `max_width_px` → `blur_sensitive()` → pHash → `assess()` → save JPEG q85 to `data/cctv/raw/{cam_id}/{YYYYMMDD}/{cam_id}_{YYYYMMDDTHHMMSSZ}.jpg` → also save thumbnail (≤ 320 px) to `data/cctv/thumbs/` with same name. Raw bytes are never written.
- Meta: append JSON line to `data/cctv/meta/cctv_frames_{YYYYMMDD}.jsonl` (fields §2.4). Exceptions → `quality_flag=EXCEPTION`, `error` (≤ 200 chars); loop never dies.
- `privacy.py` (reference):
```python
import cv2, numpy as np
from PIL import Image
_face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_plate = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_russian_plate_number.xml")
def blur_sensitive(img: Image.Image) -> Image.Image:
    a = np.asarray(img).copy(); g = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    for det in (_face, _plate):
        for (x, y, w, h) in det.detectMultiScale(g, 1.1, 4, minSize=(12, 12)):
            a[y:y+h, x:x+w] = cv2.GaussianBlur(a[y:y+h, x:x+w], (0, 0), sigmaX=max(w, h) / 3)
    return Image.fromarray(a)
```
- `quality.py::assess(img, phash_hist, q)` → `{quality_flag, sat_mean, lap_var}`; order: STALE (last `stale_consecutive` pHashes identical) → NIGHT_IR (mean HSV saturation < threshold) → BLUR (Laplacian variance < threshold) → OK.
- `compact.py`: merge jsonl → `data/cctv/cctv_frames.parquet`, dedupe on `(cam_id, ts_utc)`; idempotent.
- `health.py`: table of cam_id, last frame age, 1-h error rate; exit code 1 if > 20% cams offline; writes `data/cctv/health.json`.
- Run instructions in module docstring: `tmux new -d -s cctv 'make cctv-archive'` and hourly `make cctv-compact`.
**Verify:**
```bash
pytest -q tests/varun/test_archiver.py tests/varun/test_privacy.py
# tests use respx to mock HTTP: rate respected, 404 handled, non-image handled, stale detection,
# legal gate refusal, saved files ≤ 640 px, no file written when decode fails.
```
**🧑 HUMAN:** HU3 URLs + HU7 email, then Varun runs `make cctv-archive` in tmux and checks `make cctv-health` after 15 min.
**Done when:** tests green; (live) ≥ 2 h unattended capture with health OK.
**Fallback:** NO_GO → `cctv/manual/README.md` describing manual capture of ≤ 20 frames, run through `privacy.blur_sensitive` via `python -m cctv.archiver.ingest_manual <dir>`; registry/scenarios use `cctv_available: MANUAL_FRAMES`.

---

### T21 — DDS snapshotter + offline parser (V1.3)
**Goal:** Capture DDS road-flood and gauge pages every 15 min; parse offline for Dhanya (D3.4) and the dashboard.
**Depends:** T10 (GO for dds_*), HU4.
**Creates:** `cctv/archiver/dds_snapshot.py`, `ingest/dds.py`, `ingest/dds_endpoints.example.yaml`, `tests/varun/test_dds.py`, `tests/varun/fixtures/dds_sample.*`.
**Spec:**
- Endpoints loaded from `secrets/dds_endpoints.yaml` (`name, url, kind: road_flood|rain|canal, format: json|html`). One request per endpoint per interval, same UA. Save raw bytes to `data/raw/obs/dds/{YYYYMMDD}/{name}_{YYYYMMDDTHHMMZ}.{ext}` and append `_index.jsonl` (`name, url, ts_utc, status, sha1, bytes`). **No parsing inside the capture loop.**
- `ingest/dds.py` (offline, idempotent): road-flood → `data/interim/obs/dds_road_flood.parquet` with SCENARIO_SCHEMA §5 fields (`point_id, road_name, district, ts_utc, depth_cm, lane, source_ref, data_class=OBSERVED, location_method, loc_accuracy_m`); gauges → `data/interim/stations/{stations,timeseries}.parquet` (`station_id, type rain|level, name, lon, lat, source` / `station_id, ts_utc, value, unit, data_class`). Rain daily totals note the 07:00–07:00 ICT window. Coordinates missing → null + `[DATA GAP]`, never guessed.
- Parser is written against saved samples; if real page structure is unknown, the agent writes the parser for the sample fixture and leaves `# TODO(HU4): adapt to real payload` markers.
**Verify:** `pytest -q tests/varun/test_dds.py` (snapshot writes + index, gate refusal, parser on fixture produces valid schema, rerun idempotent).
**🧑 HUMAN (HU4):** endpoint URLs; one saved real payload per endpoint into `tests/varun/fixtures/` so the agent can adapt the parser.
**Done when:** tests green; live snapshotter running (if GO).

---

### T30 — FastAPI backend (V1.4 / V2.1)
**Goal:** All §30.2 endpoints, file-backed, working on fixtures and real data.
**Depends:** T01 (T21, T40, T53 outputs used when present).
**Creates:** `dashboard/api/{main.py, settings.py, store.py, jobs.py, mock_infer.py}`, `dashboard/api/routers/{domain,scenarios,runs,stations,cctv,observations,validation,predict,ingest,config}.py`, `dashboard/api/schemas/observation.schema.json`, `tests/varun/test_api_contract.py`.
**Spec:**
- `settings.py`: paths from env with defaults; `fixtures_mode` = auto-detect (use `tools/fixtures/out/` when real artefacts missing; every response then carries `is_mock: true`).
- `main.py`: CORS for `http://localhost:5173`; mount `/frames` (frames dir) and `/thumbs` (blurred thumbnails only); `GET /api/health → {status, versions:{api, model_version, surrogate_version}, mode}`.
- `store.py`: read-only loaders with mtime-keyed caching; DuckDB for parquet queries.

| Endpoint | Source | Response |
|---|---|---|
| `GET /api/config` | `configs/thresholds.yaml` | thresholds, depth bins, CCTV classes |
| `GET /api/domain` | domain.yaml + polygon | GeoJSON Feature + `{crs, res_m, shape}` |
| `GET /api/scenarios` | `scenarios/BKK-S*/scenario.yaml` (+ `MOCK_*` only if `include_mock=true` or fixtures mode) | `[{scenario_id, name, categories, split, event_group_id, confidence, data_class_summary, is_mock}]` |
| `GET /api/scenarios/{id}` | same | full YAML as JSON |
| `GET /api/runs?scenario_id=&source=` | scan `frames/*/*/depth/manifest.json` | `[{run_id, source, member_id, model_version, is_mock}]` |
| `GET /api/runs/{run_id}/frames?var=depth\|extent\|sigma\|error` | manifest | manifest + `frame_url_template` (`/frames/{source}/{run_id}/{var}/{t:03d}.png`) |
| `GET /api/runs/{run_id}/satellite` | rendered sat PNGs (T60) | `[{sensor, ts_utc, hours_from_peak, png_url, bounds}]` or `[]` + `gap` |
| `GET /api/stations?type=` | stations parquet | GeoJSON |
| `GET /api/stations/{id}/timeseries?start=&end=` | timeseries parquet | `{ts:[], value:[], unit, data_class}` |
| `GET /api/cctv` | registry | GeoJSON with **public fields only** |
| `GET /api/cctv/{cam_id}/observations?start=&end=` | `cctv_obs.parquet` | `[{ts_utc, class, class_smoothed, probs, quality_flag, thumb_url}]` |
| `GET /api/observations?scenario_id=` | scenario observations | GeoJSON with `kind: road_flood\|citizen` |
| `GET /api/validation/{run_id}` | metrics.json + point hit/miss | `{metrics, targets, points: GeoJSON}` |
| `POST /api/predict`, `GET /api/predict/{run_id}` | T71 | 501 until T71 |
| `POST /ingest/v1/observations` | T80 | 501 until T80 |

- Errors: 404 with `{detail}`; never 500 on missing optional data — return empty + `gap` string.
**Verify:**
```bash
pytest -q tests/varun/test_api_contract.py   # TestClient over every endpoint on fixtures; /api/cctv has no url fields
make api & sleep 3 && curl -s localhost:8000/api/health && curl -s localhost:8000/api/domain | head -c 300; kill %1
```
**Done when:** all endpoints 200 on fixtures; contract test green.

---

### T31 — Web app skeleton, base layers, panels (V1.4 / V2.1)
**Goal:** Map UI with components #1, 2, 5, 6, 7, 12 (static), 15, 18 (footer).
**Depends:** T30 (runs against API; fixtures mode is fine).
**Creates:** `dashboard/web/` (Vite React TS), files:
```
src/App.tsx  src/store.ts  src/api.ts  src/time.ts
src/map/MapView.tsx  src/map/layers/{domainLayer,frameLayer,pointLayers}.ts
src/panels/{ScenarioSelector,StationChart,CameraPanel,WhatIfPanel,MetricsPanel}.tsx
src/components/{TimeSlider,Legend,OodBanner,ProvenanceFooter,MockWatermark}.tsx
```
**Spec:**
- `npm create vite@latest web -- --template react-ts`; deps `maplibre-gl @deck.gl/core @deck.gl/layers @deck.gl/mapbox @deck.gl/extensions recharts zustand`; dev proxy `/api`, `/frames`, `/thumbs` → `http://localhost:8000`.
- Map: MapLibre with Carto Positron raster basemap (OSM/Carto attribution, no key); deck.gl via `MapboxOverlay({interleaved: true})`; fit to domain bounds on load.
- Store (zustand): `scenarioId, runId, source, compareSource, variable, tIdx, playing, swipeLon, layers{...}, manifest, oodFlag`.
- `time.ts`: `fmtICT(isoUtc)` using `Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Bangkok',dateStyle:'medium',timeStyle:'short'})` + " ICT"; tooltip also UTC.
- ScenarioSelector: grouped TRAIN / VAL / TEST / TEST_OOD, badges for data class and MOCK.
- Stations: ScatterplotLayer, radius ∝ 1-h rain; click → StationChart (Recharts line/bar) with daily-window note.
- Cameras: ScatterplotLayer coloured by latest class (grey if none); click → CameraPanel (blurred thumbnail, class badge).
- ProvenanceFooter always visible: data_class · model_version · run_id · "Feasibility prototype — not for flood warning". MockWatermark when any visible item is mock.
- Layout: map + right panel; < 768 px → bottom sheet; WhatIfPanel hidden on mobile.
**Verify:**
```bash
cd dashboard/web && npm run build && npm run lint --if-present
npx tsc --noEmit
```
plus a Playwright smoke test `dashboard/web/tests/smoke.spec.ts` (page loads, map canvas present, footer text present) if Playwright installs; otherwise document manual check.
**Done when:** build passes; with `make dashboard` on fixtures the map shows domain, stations, cameras, selector, footer, MOCK watermark.

---

### T40 — Frame renderer + colormaps (V2.2)
**Goal:** NetCDF → EPSG:3857-aligned RGBA PNGs + manifest (§20.3).
**Depends:** T01 (H2 when available).
**Creates:** `dashboard/render/{render_frames.py, render_all.py, colormaps.py}`, `tests/varun/test_renderer.py`.
**Spec:**
```python
# render_frames.py (core)
import json, numpy as np, xarray as xr, rioxarray  # noqa: F401
from pathlib import Path
from PIL import Image
from pyproj import Transformer
from rasterio.enums import Resampling
from .colormaps import CMAPS

def render(nc_path, run_id, source, var_in="depth_m", var_out="depth", cmap="depth_v1",
           out_root="dashboard/static/frames", da_override=None):
    ds = xr.open_dataset(nc_path)
    da = da_override if da_override is not None else ds[var_in]
    da = da.rio.set_spatial_dims(x_dim="x", y_dim="y").rio.write_crs(ds.attrs.get("crs", "EPSG:32647"))
    merc = da.rio.reproject("EPSG:3857", resampling=Resampling.nearest, nodata=np.nan)
    l, b, r, t = merc.rio.bounds()
    tf = Transformer.from_crs(3857, 4326, always_xy=True)
    (w, s), (e, n) = tf.transform(l, b), tf.transform(r, t)
    out = Path(out_root) / source / run_id / var_out; out.mkdir(parents=True, exist_ok=True)
    for i in range(merc.sizes["time"]):
        Image.fromarray(CMAPS[cmap](merc.isel(time=i).values), "RGBA").save(out / f"{i:03d}.png", optimize=True)
    times = ds["time"].values
    manifest = {"run_id": run_id, "source": source, "var": var_out,
        "bounds_wgs84": [w, s, e, n], "crs_native": str(da.rio.crs),
        "t0_utc": np.datetime_as_string(times[0], unit="s") + "Z",
        "dt_s": int((times[1] - times[0]) / np.timedelta64(1, "s")) if len(times) > 1 else None,
        "n_frames": int(len(times)), "colormap": cmap, "thresholds_m": [0.05, 0.15, 0.30, 0.50, 1.0],
        "data_class": ds.attrs.get("data_class", "SYNTHETIC"),
        "is_mock": run_id.startswith("MOCK_") or bool(ds.attrs.get("is_mock", False)),
        "model_version": ds.attrs.get("model_version") or ds.attrs.get("surrogate_version"),
        "scenario_id": ds.attrs.get("scenario_id"), "max_defensible_dt_s": ds.attrs.get("max_defensible_dt_s")}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest
```
Colormaps (`colormaps.py`, each `f(np.ndarray float) -> uint8 RGBA`; NaN → transparent):

| name | var | rule |
|---|---|---|
| `depth_v1` | depth | < 0.05 transparent; 0.05–0.15 `#c6dbef`; 0.15–0.30 `#6baed6`; 0.30–0.50 `#2171b5`; 0.50–1.0 `#08519c`; ≥ 1.0 `#08306b`; alpha 200 |
| `extent_v1` | extent | ≥ 0.10 `#2b8cbe` alpha 170, else transparent (separate set: 0.10 sits inside a depth class) |
| `sigma_v1` | sigma | < 0.02 transparent; 0.02/0.05/0.10/0.20 m light→dark purple |
| `error_v1` | error (sur − hyd) | \|e\| < 0.05 transparent; ±0.05/0.15/0.30 diverging, red = over, blue = under |
| `satmask_v1` | satellite | 1 → `#e34a33` alpha 170; 0 transparent; 255 → grey alpha 90 |

- CLI: `--run-id --source --nc [--vars depth,extent]`; `render_all.py` scans `outputs/sim/*/*/depth.nc` (source hydraulic) and `outputs/sur/*/pred.nc` (source surrogate, vars depth, extent, sigma) and skips runs whose manifest is newer than the NetCDF.
**Verify:**
```bash
make frames RUN=MOCK_BKK-S99_M000_lfp_mock-0 SRC=hydraulic NC=tools/fixtures/out/MOCK_BKK-S99/M000/depth.nc
pytest -q tests/varun/test_renderer.py
# checks: n PNGs == n_frames; bounds within bbox ± 0.01°; depth 0.02 → alpha 0; known pond-centre pixel at peak → class colour;
# manifest keys match §20.3; rerun is skipped (mtime) unless --force.
```
**Done when:** tests green on fixture; also green on H2 real output once it exists.

---

### T41 — Time slider + animation player (V2.2)
**Goal:** Components #3, #4, #12, #13 on rendered frames.
**Depends:** T31, T40.
**Creates/edits:** `src/components/TimeSlider.tsx`, `src/map/layers/frameLayer.ts`, `src/components/Legend.tsx`.
**Spec:**
- `frameLayer(manifest, tIdx, opts)` → deck.gl `BitmapLayer` (`image` = frame URL, `bounds` = `bounds_wgs84`, `opacity` 0.85).
- Toggle depth vs extent sets; legend from `/api/config` bins.
- Slider steps = `n_frames`, label in ICT; play/pause at 2/3/4 fps; preload next 4 frames with `new Image()`; pause while dragging.
- Frames with `dt_s < max_defensible_dt_s` are greyed and labelled "interpolated".
- Dev perf overlay (`?perf=1`): ms from tIdx change to layer `onLoad`; log rolling mean.
**Verify:** `npm run build`; manual: `?perf=1` mean frame switch ≤ 200 ms on fixtures (record number in §4 notes).
**Done when:** animation plays all fixture frames; perf target recorded.

---

### T50 — Zero-shot classifier + embedding cache (V3.1)
**Goal:** CLIP zero-shot class probabilities + cached embeddings for every usable frame.
**Depends:** T20 frames (or T01 fixture frames).
**Creates:** `cctv/classifier/{prompts.py, clip_model.py, embed.py, zeroshot.py}`, `tests/varun/test_classifier.py`.
**Spec:**
```python
# prompts.py
PROMPTS = {
  "NORMAL": ["a CCTV photo of a dry city road with visible lane markings",
             "a traffic camera image of a wet road after rain, no standing water"],
  "WATERLOGGING": ["a CCTV photo of a road with puddles and standing water patches",
                   "a traffic camera image where lane markings are partly covered by water"],
  "FLOODING": ["a CCTV photo of a flooded street with water across all lanes",
               "a traffic camera image of cars driving through flood water making waves"],
  "SEVERE_FLOODING": ["a CCTV photo of deep flood water above car wheels",
                      "a traffic camera image of a road closed by deep flooding"],
  "UNUSABLE": ["a black or blank camera image", "a blurry camera image covered with raindrops"],
}
```
```python
# clip_model.py
import open_clip, torch
from .prompts import PROMPTS
MODEL, PRETRAINED = "ViT-B-32", "laion2b_s34b_b79k"
CLASSES = list(PROMPTS)
_dev = "cuda" if torch.cuda.is_available() else "cpu"
_model, _, _pre = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED)
_model = _model.to(_dev).eval(); _tok = open_clip.get_tokenizer(MODEL)
with torch.no_grad():
    _T = torch.stack([torch.nn.functional.normalize(
            _model.encode_text(_tok(PROMPTS[c]).to(_dev)).float(), dim=-1).mean(0) for c in CLASSES])
    _T = torch.nn.functional.normalize(_T, dim=-1)

def embed_and_zeroshot(pil_images):
    x = torch.stack([_pre(im) for im in pil_images]).to(_dev)
    with torch.no_grad():
        f = torch.nn.functional.normalize(_model.encode_image(x).float(), dim=-1)
        p = (100.0 * f @ _T.T).softmax(-1)
    return f.cpu().numpy(), p.cpu().numpy()
```
- Crop each frame to the bounding box of the camera's `road_roi_px` before preprocessing (full frame if null).
- `embed.py`: batch over `cctv_frames.parquet` rows with `quality_flag == OK` not yet in cache → append to `cctv/classifier/cache/embeddings_ViT-B-32.parquet` (`cam_id, ts_utc, sha1, emb` list[float32] 512). Resumable.
- `zeroshot.py`: write zero-shot probs keyed by sha1 to `cache/zeroshot_v0.parquet`.
- Frames with `quality_flag != OK` are never embedded; they become UNUSABLE downstream.
**Verify:** `pytest -q tests/varun/test_classifier.py` (on fixture frames: shapes (N,512), probs sum to 1, cache resumes without recompute, larger "water" fixture frames get higher p_flooding+p_severe than dry ones on average — soft check, warn not fail).
**Done when:** cache built for all OK frames.

---

### T51 — Labelling app (V3.1)
**Goal:** Fast keyboard labelling + per-camera road ROI drawing.
**Depends:** T50.
**Creates:** `cctv/labelling/{label_app.py, static/index.html, static/app.js}`, `tests/varun/test_label_app.py`.
**Spec:**
- FastAPI on port 8010 (`make label`); serves frames from blurred archive only.
- Sampling: stratified by zero-shot argmax (so rare classes surface), oversample frames from hours when a gauge within 2 km had ≥ 10 mm/h (uses T21 stations if present), skip already-labelled sha1.
- Keys: `1` NORMAL `2` WATERLOGGING `3` FLOODING `4` SEVERE_FLOODING `0` UNUSABLE `o` OCCLUDED `s` skip `z` undo. Labeller name from query param.
- Writes `cctv/labelling/labels.csv`: `cam_id, ts_utc, sha1, label, labeller, labelled_utc` (append, last write wins per sha1+labeller).
- ROI mode `r`: click polygon on the image → saved to `cctv/registry/roi_overrides.json` `{cam_id: [[x,y],...]}`; `build_registry.py` merges it into `road_roi_px`.
- Progress counter per class.
**Verify:** `pytest -q tests/varun/test_label_app.py` (label POST persists; undo works; ROI saved; only blurred-archive paths served).
**🧑 HUMAN (HU5):** label 200–400 frames; second person double-labels 50 (`labeller=b`).
**Done when:** app works; labels accumulating.

---

### T52 — Linear probe + classifier report (V3.2)
**Goal:** Trained probe with camera-held-out evaluation; honest report.
**Depends:** T50, T51 labels.
**Creates:** `cctv/classifier/probe.py`, `reports/cctv_classifier_v1.md`, `cctv/classifier/models/probe_v1.joblib`, `tests/varun/test_probe_split.py`.
**Spec:**
- Join labels (exclude OCCLUDED and UNUSABLE from training; keep UNUSABLE rule-based) with embeddings.
- Split: `GroupShuffleSplit(test_size=0.3, random_state=42)` grouped by `cam_id`; `assert` disjoint camera sets.
- Model: `LogisticRegression(max_iter=2000, class_weight="balanced")`; pick C ∈ {0.1, 1, 10} by grouped CV on the train part only.
- Evaluate v0 (zero-shot argmax) and v1 on the same held-out cameras: macro-F1, per-class P/R, confusion matrix, support.
- If any class has < 10 labels: also report 3-class variant (NORMAL / WATERLOGGING / FLOODING+SEVERE) and state it.
- Inter-rater κ from double-labelled frames = ceiling.
- Choose shipped model = higher held-out macro-F1; record in `cctv/classifier/models/CHOSEN.txt`.
- Report sections: data (frames, cams, class counts), method, results table, confusion matrix, κ, failure examples (blurred thumbnails), limitations ("visual flood severity proxy", class imbalance, daytime bias).
**Verify:** `python -m cctv.classifier.probe && pytest -q tests/varun/test_probe_split.py`.
**Done when:** report written with real numbers (or explicit "insufficient labels: N" statement).

---

### T53 — Write `cctv_obs.parquet` (H6) + synthetic obs (V3.2)
**Goal:** Deliver H6 to Rishanth by **Thu 08 Oct 18:00 ICT**.
**Depends:** T50 (T52 if available).
**Creates:** `cctv/classifier/{write_obs.py, synth_obs.py}`, `tests/varun/test_obs_schema.py`.
**Spec — columns of `data/cctv/cctv_obs.parquet`:**

| Column | Type | Rule |
|---|---|---|
| `cam_id`, `ts_utc` | str | from frames |
| `class` | str | probe v1 if CHOSEN else zero-shot argmax; `quality_flag != OK` → UNUSABLE |
| `p_normal, p_waterlogging, p_flooding, p_severe, p_unusable` | float | probs (rule-based UNUSABLE → p_unusable = 1) |
| `class_smoothed` | str | majority of the last 3 usable frames per camera (ties → most recent) |
| `depth_proxy_bin` | str | from `cctv_depth_proxy_bins_m`, e.g. `"0.15-0.30"`, UNUSABLE → null |
| `quality_flag`, `frame_sha1` | str | |
| `model_version` | str | `clip-zs-v0` or `clip-probe-v1` |
| `data_class` | str | `OBSERVED` |
| `is_mock` | bool | false |

- `synth_obs.py`: `MOCK_cctv_obs.parquet` (same schema, `is_mock: true`) by sampling each camera's class from hydraulic depth at its cells (T54) over the fixture run — **pipeline testing only, never metrics**.
- Write `docs/handoff_H6.md`: path, row count, cameras, time range, model_version, macro-F1, known limits.
**Verify:** `make cctv-classify && pytest -q tests/varun/test_obs_schema.py` (columns/types, probs sum ≈ 1, no duplicate (cam_id, ts_utc), smoothing correct on a crafted sequence).
**Done when:** file + handoff note committed; Varun notifies Rishanth.

---

### T54 — Camera → model-cell mapping (L3 helper, shared with Rishanth R4.2)
**Goal:** Cells each camera "sees", for comparing CCTV class with model depth.
**Depends:** T11, H1 (or fixture domain); OSM roads (`data/raw/osm/` from Dhanya, else skip road clip).
**Creates:** `validation/cctv/cam_cells.py`, `validation/cctv/compare.py`, `tests/varun/test_cam_cells.py`.
**Spec:**
- For each camera (EPSG:32647): 30 m buffer around the point ∩ (nearest OSM road segment buffered 10 m); if no road data → 30 m buffer alone + flag `road_clip=false`.
- Cells = grid cells whose centres fall inside → `cam_cells.parquet` (`cam_id, row, col, grid_res_m, road_clip`); also a 40 m-grid version for the surrogate (`grid_res_m=40`).
- `compare.py::model_series(depth_nc, cam_cells) -> DataFrame(cam_id, ts_utc, depth_max_m, bin)` using **max** depth over the cells; bins from thresholds.yaml.
- `compare.py::confusion(cctv_obs, model_series, tol_min=7)`: nearest-time join within ±7 min, using `class_smoothed`; returns confusion matrix, Cohen's κ (sklearn), onset error (first FLOODING vs first depth ≥ 0.15 m) per camera. Rishanth owns final L3 reporting; this is the shared function.
**Verify:** `pytest -q tests/varun/test_cam_cells.py` (camera on a fixture pond centre gets max depth ≈ pond peak; cells within 30 m; κ = 1 on identical series).
**Done when:** parquet written for real registry; functions importable by Rishanth.

---

### T60 — Real-data integration (V3.3)
**Goal:** Components #3, 4, 5, 6, 8, 9, 10 + observations on real artefacts.
**Depends:** T30, T31, T40, T41; H2/H4 real data; T21 parsed stations; T53.
**Creates/edits:** `dashboard/render/render_satellite.py`, API store updates, `src/map/layers/pointLayers.ts`, `src/panels/CameraPanel.tsx`.
**Spec:**
- `make frames-all` over every real anchor `M000`; selector lists only runs with manifests.
- Satellite: for each `sat_floodmask_*.tif` render with `satmask_v1` to `frames/satellite/{scenario_id}/{sensor}_{ts}.png` + small manifest; `/api/runs/{run_id}/satellite` lists them with `hours_from_peak` from `sat_acquisitions.csv`; none → `[]` + `gap: "No coincident acquisition [DATA GAP]"` shown in UI.
- Observations: DDS road-flood points labelled with depth in cm, Traffy reports clustered; both filtered to ±30 min of the slider time.
- CameraPanel: latest blurred thumbnail at slider time, class badge "visual flood severity proxy", class timeline (Recharts step chart) for the scenario window.
- Stations: real parsed gauges; rain gauge radius = rain in the hour ending at slider time.
**Verify:** `pytest -q tests/varun/test_api_contract.py` against real data (`FG_DATA_MODE=real`); manual check list in §4 notes: one real anchor animates; satellite layer or explicit gap; DDS points visible at the right time.
**Done when:** listed components work with real data or show explicit data-gap states.

---

### T70 — Surrogate layers, swipe, error, σ, OOD (V4.1)
**Goal:** Components #11, 14, 17.
**Depends:** T40, T41; H5 (build on MOCK_ surrogate first).
**Creates/edits:** `dashboard/render/render_error.py`, `src/map/layers/frameLayer.ts` (clip), `src/panels/MetricsPanel.tsx`, `src/components/OodBanner.tsx`.
**Spec:**
- Render surrogate sets depth/extent/sigma via `render_all`.
- Error = surrogate − hydraulic on the 40 m grid. Block-average hydraulic ×2 by importing Rishanth's function from `surrogate/dataset.py` (do **not** reimplement; if it doesn't exist yet, use a local copy in `render_error.py` marked `# TEMP until surrogate.dataset.block_average lands` and log in `docs/handoff_issues.md`). Render with `error_v1` to var `error` under the surrogate run.
- Swipe: two BitmapLayers (hydraulic, surrogate) with `ClipExtension`; vertical divider sets `clipBounds` `[w, s, swipeLon, n]` and `[swipeLon, s, e, n]`.
- MetricsPanel: wet-RMSE, CSI@0.10, peak-timing error, volume error, B1 comparison, coverage@95 with POC targets (§21) and pass/fail chips; failures displayed, not hidden. Observation points coloured hit/miss.
- σ layer toggle; OOD banner "Outside training envelope — run hydraulic model" when run's `ood_flag` true.
**Verify:** `pytest -q tests/varun/test_renderer.py -k error` (error sign and transparency); `npm run build`; manual: swipe works; banner shows for a fixture run with `ood_flag: true` (and S19/S20 once H5 lands).
**Done when:** components live on mock; re-verified on H5.

---

### T71 — What-if prediction endpoint (V4.1)
**Goal:** Component #16: sliders → surrogate run → frames in ≤ 5 s.
**Depends:** T30, T40, T70; HU6.
**Creates/edits:** `dashboard/api/routers/predict.py`, `dashboard/api/jobs.py`, `dashboard/api/mock_infer.py`, `src/panels/WhatIfPanel.tsx`, `tests/varun/test_predict.py`.
**Spec:**
- Contract with Rishanth (🧑 HU6 confirm):
```python
# surrogate/infer.py (Rishanth owns)
def predict(base_scenario_id: str, rain_scale: float, duration_stretch: float,
            canal_stage_anom_m: float, outfall_stage_offset_m: float, drain_multiplier: float
           ) -> tuple["xr.Dataset", dict]:
    """ds: depth_m, sigma_m (time, y, x) on 40 m grid, CF time UTC, attrs crs.
       meta: {ood_flag: bool, mahalanobis: float, surrogate_version: str}"""
```
- Backend selection: `FG_SURROGATE_MODE=real` → import `surrogate.infer.predict`; `mock` → `mock_infer.predict` (nearest fixture/hydraulic run × rain_scale, `is_mock: true`); `auto` → real if importable else mock.
- Body validation (422 outside): rain_scale 0.5–1.8, duration_stretch 0.5–2.0, canal_stage_anom_m −0.3–0.8, outfall_stage_offset_m 0–0.6, drain_multiplier 0.3–1.2 (= sampler ranges §17.5).
- `run_id = f"{base}_X{sha1(canonical_json(params))[:6]}_sur_{version}"` (what-if member prefix `X`; add to §29 via team). Same params → cached → instant.
- Job: `BackgroundTasks` → predict → write `outputs/sur/whatif/{run_id}/pred.nc` → render first 8 frames synchronously, rest after → status `RUNNING|PARTIAL|DONE|FAILED`; job dict in memory + `jobs.jsonl` log.
- `GET /api/predict/{run_id}` → `{status, manifest_url, ood_flag, elapsed_s, is_mock}`; UI polls every 500 ms, shows elapsed time, loads frames as they appear, shows OOD banner.
**Verify:** `pytest -q tests/varun/test_predict.py` (validation, caching, mock path end-to-end produces manifest, PARTIAL→DONE); timing check on demo machine recorded (target ≤ 5 s to first frames).
**Done when:** works in mock mode; switched to real when H5/infer lands.

---

### T80 — Provenance, MOCK watermark, sensor-ingest stub + spec (V4.2, O11)
**Goal:** Component #18 complete; O11 delivered as design + stub.
**Depends:** T30, T31.
**Creates/edits:** `src/components/{ProvenanceFooter,MockWatermark}.tsx`, `dashboard/api/routers/ingest.py`, `dashboard/api/schemas/observation.schema.json`, `docs/sensor_ingestion_spec.md`, `tests/varun/test_ingest.py`.
**Spec:**
- Footer always: data_class · model_version · surrogate_version · run_id · "Feasibility prototype — not for flood warning". Diagonal "MOCK" watermark whenever any rendered item has `is_mock`. Scenario badges SYNTHETIC/DERIVED/OBSERVED. CCTV text "visual flood severity proxy".
- Observation JSON Schema per §19 payload: `site_id` (`^BKK-(WL|RN|FL|CAM)-\d{4}$`), `sensor_type` enum wl|rain|flow|cam, `ts` date-time Z, `value` number, `unit` enum m|mm|m3s|class, `datum`, `quality` enum raw|qc, optional `battery_v, fw, seq`.
- `POST /ingest/v1/observations`: header `X-API-Key` == `FG_API_KEY_INGEST`; body array ≤ 1000; validate each; idempotency key `site_id+ts+sensor_type` (seen-set persisted to `data/interim/ingest/seen.txt`); accepted rows appended to `data/interim/ingest/obs_{YYYYMMDD}.jsonl`; response `{accepted, rejected:[{index, reason}]}`.
- `sensor_ingestion_spec.md`: architecture (§19 diagram), MQTT topic `floodguard/bkk/{site_id}/{sensor_type}/obs`, TLS + per-device creds, payload + schema, unit/datum normalisation (→ m MSL, mm, UTC), QC flags (range, rate-of-change, flatline, battery), virtual-sensor mapping for DDS/ThaiWater/TMD, PILOT path (EMQX/Mosquitto, TimescaleDB/PostGIS). States "no hardware in POC".
**Verify:** `pytest -q tests/varun/test_ingest.py` (auth, validation, idempotency, partial rejection).
**Done when:** tests green; spec doc complete.

---

### T81 — Perf, privacy, docs, demo script (V4.2)
**Goal:** Gate G4 evidence.
**Depends:** all.
**Creates/edits:** `tests/varun/test_cctv_privacy.py`, `reports/demo_script.md`, README section "Run the demo", appends to `docs/assumptions.md`, `docs/data_gaps.md`, my section draft `reports/POC_SUMMARY_varun.md`.
**Spec:**
- Privacy test: every image under `data/cctv/raw` and `data/cctv/thumbs` ≤ 640 / 320 px wide; API static mounts point only to blurred dirs.
- Perf: API load ≤ 3 s, frame switch ≤ 200 ms, what-if ≤ 5 s — record measured numbers.
- Demo script (~5 min): domain & why CLL → S07 hydraulic animation with DDS hit/miss → swipe hydraulic vs surrogate + error + metrics vs targets → S01 satellite overlay or explicit gap → CCTV frames + class timeline vs model at camera → what-if rain ×1.5, canal +0.5 m → push to S19 → OOD banner → provenance footer & limitations.
- Assumptions to log: quality thresholds, CCTV depth-proxy bins, 30 m cam buffer, ±7 min join tolerance, prompt set. Data gaps: no public CCTV archive, DDS archive depth, camera headings, real DDS payload formats.
- POC summary inputs: legal status per source, frames captured (count, cams, hours of rain covered), classifier macro-F1/κ, L3 κ if computed, 18/18 component checklist, measured latencies, gaps.
**Verify:** `make test-varun` all green; `make dashboard` and walk through the demo script once.
**🧑 HUMAN (HU8):** record `reports/demo.mp4`.
**Done when:** gate G4 items (§7) ticked.

---

## 7. Gate checklists (Varun's items)

**G1 (D1):** ☐ T10 decisions recorded (HU1) ☐ T11 registry ☐ T20 archiver live or NO_GO documented ☐ T21 snapshotter live or blocked ☐ T30/T31 skeleton with domain
**G2 (D2):** ☐ components #1, 2, 5, 6, 7, 12, 15 on mock ☐ T40 renderer on H2 real output ☐ T41 frame switch ≤ 200 ms
**G3 (D3 18:00):** ☐ **H6 delivered** (T53) or legal-block doc ☐ macro-F1 on held-out cameras (T52) ☐ T54 cam_cells shared ☐ T60 real animations + satellite/obs layers or explicit gaps
**G4 (D4 18:00):** ☐ T70 #11, 14, 17 ☐ T71 what-if ≤ 5 s ☐ OOD banner on S19/S20 ☐ T80 provenance + ingest stub ☐ T81 tests green, demo recorded, summary inputs

---

## 8. Risks in Varun's lane (and what the agent should do)

| Risk | Agent behaviour |
|---|---|
| CCTV ToS forbids automation | Gate stays closed; build T20 anyway with tests; manual-frames path; L3 via DDS points |
| No rain on camera → few flood frames | Report class balance honestly; κ only if ≥ 50 labelled event frames (§21), else descriptive |
| Source layout changes / throttling | Raw-snapshot-then-parse; health checks; never increase request rate to compensate |
| Camera coordinates inaccurate | Keep `loc_accuracy_m`; exclude cams > 100 m accuracy from L3 |
| Over-claiming CCTV depth | Enforced wording (rule 11) |
| Teammate artefact late or mismatched | Use fixtures; log mismatch in `docs/handoff_issues.md`; never patch teammates' code |
| Frame misalignment | Reproject to 3857 with real bounds; visual check against OSM canals once |
| Personal data in demo | Blur-before-write, size caps, privacy test, API serves blurred dirs only |

*Feasibility prototype — not for flood warning.*
