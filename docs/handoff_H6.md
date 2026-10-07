# Handoff H6 — CCTV observations (`cctv_obs.parquet`)

**To:** Rishanth (L3 validation / surrogate team)
**From:** Varun's lane
**Status:** delivered on fixtures, running on the real pipeline end to end — swaps to real camera data automatically once T20 (archiver) is live.

## Path & schema

`data/cctv/cctv_obs.parquet` — columns: `cam_id, ts_utc, class, p_normal, p_waterlogging, p_flooding, p_severe, p_unusable, class_smoothed, depth_proxy_bin, quality_flag, frame_sha1, model_version, data_class, is_mock`. Built by `make cctv-classify` (`python -m cctv.classifier.write_obs --model auto`), which runs the embed → zero-shot → write pipeline end to end and is resumable (never re-embeds a cached frame).

A pipeline-testing-only synthetic twin, `data/cctv/MOCK_cctv_obs.parquet` (`is_mock: true`, `data_class: SYNTHETIC`), is produced by `python -m cctv.classifier.synth_obs` by sampling each camera's class from the fixture hydraulic depth at its nearest grid cell — **never use this one for metrics**, only for exercising downstream code before real classifications are trustworthy.

## This run (on T01 fixtures)

- Rows: 300 (10 cameras × 30 frames)
- Cameras: `BMAT-0000, BMAT-0003, BMAT-0006, BMAT-0009, ITIC-0001, ITIC-0004, ITIC-0007, LNGD-0002, LNGD-0005, LNGD-0008`
- Time range: `2026-09-25T00:00:00Z` – `2026-09-25T00:58:00Z`
- `model_version`: `clip-zs-v0` (zero-shot CLIP; switches to `clip-probe-v1` automatically once T52 writes `cctv/classifier/models/CHOSEN.txt`)
- `quality_flag`: 300/300 `OK`
- Class distribution: 300/300 `NORMAL`

## Macro-F1 / validation

**N/A — not yet measurable.** No labelled frames exist (T51/T52, HU5, haven't run), so there's no held-out evaluation set. Per §21, κ/macro-F1 should only be reported once ≥ 50 labelled event frames exist; until then this is descriptive only.

## Known limits

1. **These are synthetic frames, not real cameras.** T01's fixture CCTV frames are solid-color placeholders ("water" = a plain blue rectangle at the bottom of the frame); CLIP's zero-shot flood probability stays near zero regardless, so every fixture frame here classifies as `NORMAL` even for the 5 cameras T01 marks as "wet". This is expected — see `docs/assumptions.md` — and will change once real frames (T20) or more realistic fixtures exist.
2. **Zero-shot only, unvalidated.** No linear probe exists yet (T52 needs human-labelled frames, HU5). Treat `class`/`class_smoothed` as a rough proxy, not ground truth, until a probe is trained and reported.
3. **`class_smoothed`** is the majority of each camera's last ≤3 *usable* frames (ties broken by most recent); frames with `quality_flag != OK` are always `UNUSABLE` and never enter that window.
4. **`depth_proxy_bin`** comes from `configs/thresholds.yaml`'s `cctv_depth_proxy_bins_m` (an `[ASSUMPTION]`-tagged judgement call, not a measured depth) and is `null` for `UNUSABLE`.
5. **Camera → model-cell mapping (T54) hasn't landed.** `synth_obs.py`'s nearest-cell lookup is a stand-in for T54's 30 m buffer + road-clip logic — fine for schema testing, not for L3 comparison. Switch to `validation.cctv.cam_cells` once T54 exists.
