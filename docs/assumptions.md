# Assumptions

Shared, append-only. Each teammate adds under their own heading; never edit another section.

## Varun

- **T00 Python environment:** torch / open_clip_torch / geopandas / rasterio wheels aren't published for Python 3.14 yet (the system default here), so `environment.yml` targets Python 3.12. A local venv at `bkk-flood-poc/.venv` (Python 3.12) is used instead of conda (conda isn't installed in this environment); exact resolved versions are frozen in `requirements-lock.txt`.
- **T01 depth.nc rise/recede shape:** amplitude(t) is a triangular pulse (linear rise to 0.8 m at t=40, linear recede to 0 by t=95) — the card only pins the peak value/index, not the curve shape.
- **T01 pond footprint cutoff:** values are hard-zeroed below a Gaussian density of 1e-2 so "zero elsewhere" is exact, not just small.
- **T01 GeoJSON `is_mock` placement:** T11 asks for "`is_mock: true` in the FeatureCollection metadata" but GeoJSON has no standard metadata key. Fixtures set it under a `metadata` object at the FeatureCollection root *and* on every feature's `properties`, since the real consumer (store.py, not yet built) isn't known to prefer one location.
- **T01 citizen_reports.geojson schema:** SCENARIO_SCHEMA.md isn't in this repo, so the field list (`report_id, ts_utc, depth_cm, description, source_ref, data_class`) mirrors `road_flood_points.geojson`'s contract rather than a confirmed spec.
- **T01 scenario.yaml `categories`:** set to `["pluvial"]` — the category taxonomy isn't defined anywhere available in this repo.
- **T01 MOCK_metrics.json keys:** `wet_rmse_m, csi_0.10, peak_timing_error_min, volume_error_pct, b1_comparison, coverage_95` — reconstructed from the metric names referenced in VARUN_IMPLEMENTATION.md's T70 MetricsPanel spec, not from §17.10 itself (that parent doc isn't in the repo).
