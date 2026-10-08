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
frames-satellite: ## render every scenario's satellite acquisitions (T60)
	python -m dashboard.render.render_satellite
api:
	uvicorn dashboard.api.main:app --reload --port 8000
web:
	cd dashboard/web && npm run dev
dashboard: ; $(MAKE) -j2 api web
fixtures:
	python -m tools.fixtures.make_fixtures
test-varun:
	pytest -q tests/varun

.PHONY: cctv-archive cctv-health cctv-compact dds-snapshot dds-parse cctv-classify label frames frames-all frames-satellite api web dashboard fixtures test-varun
