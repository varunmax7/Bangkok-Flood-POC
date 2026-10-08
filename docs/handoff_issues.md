# Handoff issues

Contract mismatches or missing teammate artefacts found while building Varun's lane. Append-only; whoever owns the module should follow up.

## `surrogate/dataset.py::block_average` (Rishanth) — not yet built

**Found in:** T70 (`dashboard/render/render_error.py`)
**What's needed:** `render_error.py` needs to block-average the hydraulic depth grid ×2 (20 m → 40 m) to compare against the surrogate's native 40 m grid, computing `error = surrogate − hydraulic`. Per §6 T70, this should reuse `surrogate/dataset.py::block_average` rather than reimplementing it, but that module doesn't exist in the repo yet.
**Current workaround:** `render_error.py` has a local `block_average()` function marked `# TEMP until surrogate.dataset.block_average lands`. It's a plain NumPy block-mean (reshape + mean over the two trailing axes) — the same logic `tools/fixtures/make_fixtures.py::make_surrogate_nc` and `validation/cctv/cam_cells.py::_grid_centers` already duplicate for the same 20→40 m block-average, so there are now three independent copies of this in the repo.
**Follow-up:** once `surrogate/dataset.py::block_average` exists, swap the import in `render_error.py` and consider whether the other two copies should also switch to it for consistency, or whether `block_average` belongs in a shared location both lanes can import from.
