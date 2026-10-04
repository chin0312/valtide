# Valtide quantitative research handoff

This directory is the auditable handoff for the 5 October 2026 feature freeze. It separates deployable runtime material, research evidence, and raw-data inventory.

- `runtime/` contains only the frozen NVDAx P1a-C package and deterministic checks. It is a snapshot of `valtide-quant-service-p1ac`, not a replacement import path.
- `research/` contains methodology, reproducible experiment code, compact reports, event-level challenger evidence, failure diagnostics, and rejected experiments.
- `data_manifest/` records the five canonical datasets without committing the canonical panels or vendor captures.
- `HANDOFF_MANIFEST.json` records Git-tracked handoff files and their byte counts/SHA-256 hashes. Rejected experiments are intentionally referenced both in `research_artifacts` and `rejected_artifacts`; count unique paths separately from references.

The original source archives/canonical panels are not included in this Git handoff, and the durable shared-storage URIs are still `TBD_SHARED_STORAGE/...`. Do not assume the original archives exist in a checkout or invent storage locations. Dataset identity and metadata consistency can be checked from committed manifests; source-panel hashes and original training lineage require restored source material.

The frozen runtime is NVDAx P1a-C only. SPYx, QQQx, TSLAx, and AAPLx have research results but no approved production runtime. The five-asset study's raw xStock benchmark is not automatically equivalent to the live OKX X-Perp reference under test. Historical `SUPPORT / WATCH / REVIEW` labels are research classifications; production backend Evidence States are `SUPPORTED / INCONCLUSIVE / CHALLENGED` and are not curator Policy Actions.

The June–September 2026 test windows were inspected repeatedly during development; they are exposed development evidence, not fresh untouched validation. Any future promotion or parameter change requires a genuinely newer chronological holdout.

From the repository root, the lightweight offline checks are:

```bash
python quant/runtime/p1ac/verify_runtime.py
python quant/runtime/p1ac/run_deterministic_tests.py
python quant/research/evaluation/regenerate_summary.py --check
python quant/tools/build_handoff_manifest.py --check
python quant/tools/verify_handoff.py
```
