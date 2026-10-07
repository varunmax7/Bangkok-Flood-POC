# Agent rules — Varun's lane (Bangkok Flood POC)

Full plan: `docs/VARUN_IMPLEMENTATION.md`. These rules apply to every session working in this repo on Varun's lane.

1. **Scope:** Only create/modify paths owned by Varun (§2.2 of the plan doc). Never edit `surrogate/`, `models/hydraulic/`, `terrain/`, `scenarios/BKK-*` or teammates' configs — if a contract mismatch is found, write it to `docs/handoff_issues.md` and stop.
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
