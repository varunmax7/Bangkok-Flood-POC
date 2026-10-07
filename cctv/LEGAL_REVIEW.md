# CCTV / DDS legal review

**🧑 HUMAN (HU1):** this file is a template only — the agent must not fill in
decisions, and must not fetch any of the URLs below itself (that would be an
automated request to an external site before a gate exists). Varun reads
each source's Terms of Service and `robots.txt`, fills every field below,
then sets the matching `decision` / `approved_by` / `approved_utc` /
`conditions_ack` in `cctv/legal_status.yaml`.

**Decision rule:**
- ToS explicitly prohibits automated access / scraping → **NO_GO**.
- ToS is silent (no explicit prohibition, no explicit permission) → **GO**
  only if every condition below is accepted *and* the BMA data-use request
  (`docs/stakeholder_requests/bma_cctv.md`) has been sent.
- ToS explicitly permits this kind of automated, low-rate, research use →
  **GO**.

**Conditions (apply to every GO):**
- ≤ 1 request / camera / 2 minutes (`configs/cctv.yaml: min_interval_s: 120`)
- ≤ 50 cameras (`configs/cctv.yaml: max_cameras: 50`)
- User-Agent identifies the project and includes a contact email
- Frames downscaled to ≤ 640 px wide before being written to disk
- Faces / plates blurred before being written to disk
- Purpose stated as flood observation research only, never redistributed
  outside the project without separate agreement

---

## BMA Traffic — `http://www.bmatraffic.com/index.aspx`

| Field | Value |
|---|---|
| checked_utc | |
| checked_by | |
| ToS URL / text | |
| robots.txt lines (relevant disallow/allow) | |
| Automation allowed (YES / NO / SILENT) | |
| Redistribution terms | |
| PDPA exposure (faces/plates visible?) | |
| **Decision** | |
| Conditions accepted (list any exceptions) | |
| Escalation (if NO_GO or unclear) | |

## iTIC Live

| Field | Value |
|---|---|
| checked_utc | |
| checked_by | |
| ToS URL / text | |
| robots.txt lines | |
| Automation allowed (YES / NO / SILENT) | |
| Redistribution terms | |
| PDPA exposure | |
| **Decision** | |
| Conditions accepted | |
| Escalation | |

## Longdo Traffic

| Field | Value |
|---|---|
| checked_utc | |
| checked_by | |
| ToS URL / text | |
| robots.txt lines | |
| Automation allowed (YES / NO / SILENT) | |
| Redistribution terms | |
| PDPA exposure | |
| **Decision** | |
| Conditions accepted | |
| Escalation | |

## DDS floodbangkok

| Field | Value |
|---|---|
| checked_utc | |
| checked_by | |
| ToS URL / text | |
| robots.txt lines | |
| Automation allowed (YES / NO / SILENT) | |
| Redistribution terms | |
| PDPA exposure | |
| **Decision** | |
| Conditions accepted | |
| Escalation | |

## DDS SCADA

| Field | Value |
|---|---|
| checked_utc | |
| checked_by | |
| ToS URL / text | |
| robots.txt lines | |
| Automation allowed (YES / NO / SILENT) | |
| Redistribution terms | |
| PDPA exposure | |
| **Decision** | |
| Conditions accepted | |
| Escalation | |
