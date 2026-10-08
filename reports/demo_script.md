# Demo script (~5 min) — Varun's lane

**Adapted from the card's template.** The original script references real scenario IDs (S07 hydraulic, S01 satellite, S19/S20 for the OOD banner) that don't exist in this repo yet — H2 (real hydraulic runs), H4 (real observations), H5 (real surrogate) are teammate handoffs that haven't landed (see §3 HU1–HU7, `docs/handoff_issues.md`). This script walks the identical eight beats using the `MOCK_BKK-S99` fixture scenario, which exercises the same UI/API path end to end. Swap in the real scenario IDs the moment T60 (real-data integration) lands — nothing else about the flow changes.

**Before starting:**
```bash
make fixtures
python -m cctv.registry.build_registry
python -m dashboard.render.render_frames --run-id MOCK_BKK-S99_M000_lfp_mock-0 --source hydraulic \
  --nc tools/fixtures/out/MOCK_BKK-S99/M000/depth.nc --vars depth,extent
python -m dashboard.render.render_frames --run-id MOCK_BKK-S99_M000_sur_mock-0 --source surrogate \
  --nc tools/fixtures/out/MOCK_BKK-S99/surrogate/pred.nc --vars depth,extent,sigma
python -m dashboard.render.render_error --hydraulic-nc tools/fixtures/out/MOCK_BKK-S99/M000/depth.nc \
  --surrogate-nc tools/fixtures/out/MOCK_BKK-S99/surrogate/pred.nc --run-id MOCK_BKK-S99_M000_sur_mock-0
make frames-satellite
make cctv-classify
make dashboard   # api :8000 + web :5173
```
Open `http://localhost:5173`.

---

1. **Domain & why this area** (30s)
   Point at the domain boundary outline on the map and the scenario selector (TRAIN group, badges SYNTHETIC/MOCK). Explain: this is the feasibility-prototype domain, chosen to cover the canal/drainage area the CCTV cameras and DDS gauges fall inside.

2. **Hydraulic animation** (original: S07 with DDS hit/miss) — *adapted*
   Press play on the time slider (2 fps default). Watch the two synthetic ponds rise and recede over the 24h window. Toggle "📍 show observations" — fixture DDS road-flood points (depth-cm labelled, coloured by severity) and clustered citizen reports appear and disappear as the slider passes within ±30 min of each one's timestamp (T60). Be upfront: these are the T01 synthetic fixtures, not real DDS data (H4 hasn't landed) — the UI/API path is fully real, the points underneath aren't yet.

3. **Swipe: hydraulic vs surrogate + error + metrics vs targets**
   Click "⇄ compare vs surrogate" — the map splits into a draggable hydraulic/surrogate swipe. Toggle the Legend to `sigma` to show the surrogate's own uncertainty layer. Open the Metrics panel: six metrics, each with a PASS/FAIL chip against the POC targets (`[ASSUMPTION]`-tagged in `docs/assumptions.md` since §21's real targets aren't in this repo). All six pass on the fixture today — say that plainly, since a POC built to always pass its own targets isn't informative; the honest claim is "the dashboard shows pass/fail clearly, not that these specific numbers are validated."

4. **Satellite overlay or explicit gap** (original: S01) — *adapted*
   Toggle "🛰️ show satellite" — the fixture's synthetic flood-mask acquisition renders over the domain (T60, `render_satellite.py`). Point out the gap path too: querying a run with no rendered acquisition for its scenario returns `{"items": [], "gap": "No coincident acquisition [DATA GAP]"}` — that's what a real scenario without a coincident Sentinel-1 pass (H4) would show today.

5. **CCTV frames + class timeline vs model at camera**
   Click a camera marker — CameraPanel shows the blurred thumbnail nearest the slider's current time (not just the newest overall, T60), its class badge ("visual flood severity proxy", never "depth"), timestamp, and a step-chart timeline of its class over the whole scenario window. Be upfront: on these synthetic fixture frames, the zero-shot CLIP classifier reads every frame as `NORMAL` (the "water" in the fixture is a flat blue rectangle, nothing like a real flood photo — see `docs/assumptions.md`). This is real, working CLIP inference on CCTV-shaped images; it just hasn't seen a real flood yet.

6. **What-if: rain ×1.5, canal +0.5 m** (original: "push to S19")  — *adapted*
   In the What If panel, drag `rain_scale` to 1.5 and `canal_stage_anom_m` to 0.5, click "Run what-if". First frames land in well under a second (measured: ~0.7–0.9s on this machine; target ≤5s). Watch the status go `PARTIAL` → `DONE` as the rest of the run finishes in the background.

7. **OOD banner**
   Re-run what-if with the sliders pushed to their extremes (`rain_scale` 1.8, `duration_stretch` 2.0, `canal_stage_anom_m` 0.8, `outfall_stage_offset_m` 0.6, `drain_multiplier` 1.2) — the OOD banner ("Outside training envelope — run hydraulic model") appears. This is the stand-in for the card's static S19/S20 OOD scenarios, which don't exist yet; the banner logic itself is fully real, just triggered via the what-if path instead of a pre-built OOD fixture.

8. **Provenance footer & limitations**
   Point at the footer, always visible: `data_class · model_version · surrogate_version · run_id · "Feasibility prototype — not for flood warning"`. Toggle back to the hydraulic run to show the diagonal MOCK watermark (it's there whenever anything on screen — domain, frame, stations, cameras — is mock data). Close by naming the real gaps out loud: no legal clearance yet for any CCTV/DDS source (T10, all `PENDING`), no real camera list or snapshot URLs (HU2/HU3), no labelled frames yet for the classifier (T52), no real hydraulic/observation/surrogate data yet (H2/H4/H5).

---

**Measured latencies** (this machine, fixtures, recorded for `reports/POC_SUMMARY_varun.md`):
- Dashboard initial load (nav → metrics + slider visible): **~350–485ms** (target ≤3s)
- Frame switch, steady state with preloading: **~1–2ms mean** (target ≤200ms)
- What-if first frames: **~0.7–0.9s** (target ≤5s)
