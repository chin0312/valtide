# Valtide quantitative research handoff

This directory is the auditable handoff for the 5 October 2026 feature freeze. It separates deployable runtime material, research evidence, and raw-data inventory.

- `runtime/` contains only the frozen NVDAx P1a-C package and deterministic checks. It is a snapshot of `valtide-quant-service-p1ac`, not a replacement import path.
- `research/` contains methodology, reproducible experiment code, compact reports, event-level challenger evidence, failure diagnostics, and rejected experiments.
- `data_manifest/` records the five canonical datasets without committing the canonical panels or vendor captures.
- `HANDOFF_MANIFEST.json` is generated from the files in this directory and records their SHA-256 hashes.

The original archives under `brush-up stats/` are intentionally left in place and ignored by Git. They should be retained until this handoff and the shared-storage copy have been independently verified.

The exposed June–September 2026 test windows are development evidence because they were inspected repeatedly during model development. Any future promotion or parameter change requires a genuinely newer chronological holdout.
