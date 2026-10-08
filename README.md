# Bangkok Flood POC

Feasibility prototype — not for flood warning. See `docs/VARUN_IMPLEMENTATION.md` for the full build plan (Varun's lane: CCTV, dashboard, API).

## Run the demo

```bash
# one-time setup
python3.12 -m venv .venv && .venv/bin/pip install -r <(grep -v '^#' environment.yml)  # or: conda env create -f environment.yml
source .venv/bin/activate
cd dashboard/web && npm install && cd ../..

# generate fixtures + frames (safe to re-run; skips work that's already up to date)
make fixtures
python -m cctv.registry.build_registry
python -m dashboard.render.render_frames --run-id MOCK_BKK-S99_M000_lfp_mock-0 --source hydraulic \
  --nc tools/fixtures/out/MOCK_BKK-S99/M000/depth.nc --vars depth,extent
python -m dashboard.render.render_frames --run-id MOCK_BKK-S99_M000_sur_mock-0 --source surrogate \
  --nc tools/fixtures/out/MOCK_BKK-S99/surrogate/pred.nc --vars depth,extent,sigma
python -m dashboard.render.render_error --hydraulic-nc tools/fixtures/out/MOCK_BKK-S99/M000/depth.nc \
  --surrogate-nc tools/fixtures/out/MOCK_BKK-S99/surrogate/pred.nc --run-id MOCK_BKK-S99_M000_sur_mock-0
make cctv-classify

# run it
make dashboard   # api on :8000, web on :5173
```

Open `http://localhost:5173`. Walk through `reports/demo_script.md` for the guided ~5 minute tour.

Everything above runs on the T01 synthetic fixtures (`is_mock: true`, shown with a MOCK watermark) — no teammate handoff or CCTV/DDS legal clearance is required to see the full UI working end to end. See `docs/VARUN_IMPLEMENTATION.md` §4 for what's still pending real data, and `docs/assumptions.md` / `docs/data_gaps.md` for every judgement call and known gap along the way.

### Running the test suite

```bash
make test-varun        # Python (pytest)
cd dashboard/web && npx playwright test   # frontend (needs `make dashboard` running)
```
