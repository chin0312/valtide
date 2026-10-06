# Valtide quantitative research handoff

This directory is the auditable handoff for the 5 October 2026 feature freeze. It separates deployable runtime material, research evidence, and raw-data inventory.

- `runtime/` contains only the frozen NVDAx P1a-C package and deterministic checks. It is a snapshot of `valtide-quant-service-p1ac`, not a replacement import path.
- `research/` contains methodology, reproducible experiment code, compact reports, event-level challenger evidence, failure diagnostics, and rejected experiments.
- `data_manifest/` records the five canonical datasets without committing the canonical panels or vendor captures.
- `HANDOFF_MANIFEST.json` records Git-tracked handoff files and their byte counts/SHA-256 hashes. Rejected experiments are intentionally referenced both in `research_artifacts` and `rejected_artifacts`; count unique paths separately from references.

The original source archives/canonical panels are not included in this Git handoff, and the durable shared-storage URIs are still `TBD_SHARED_STORAGE/...`. Do not assume the original archives exist in a checkout or invent storage locations. Dataset identity and metadata consistency can be checked from committed manifests; source-panel hashes and original training lineage require restored source material.

The packaged runtime bundles on this branch are NVDAx P1a-C 0.2.0 plus frozen, asset-bound SPYx, QQQx, and AAPLx P1a-C 0.3.0 research runtimes. The additional bundles are not a claim of production promotion: fresh panels remain external/local, multi-asset schedulers are not production-enabled, and only NVDAx has an X Layer binding. TSLAx remains research-only with no fitted runtime. The five-asset study's raw xStock benchmark is not automatically equivalent to the live OKX X-Perp reference under test. Historical `SUPPORT / WATCH / REVIEW` labels are research classifications; production backend Evidence States are `SUPPORTED / INCONCLUSIVE / CHALLENGED` and are not curator Policy Actions.

The June–September 2026 test windows were inspected repeatedly during development; they are exposed development evidence, not fresh untouched validation. Any future promotion or parameter change requires a genuinely newer chronological holdout.

From the repository root, the lightweight offline checks are:

```bash
python quant/runtime/p1ac/verify_runtime.py
python quant/runtime/p1ac/run_deterministic_tests.py
python quant/research/evaluation/regenerate_summary.py --check
python quant/tools/build_handoff_manifest.py --check
python quant/tools/verify_handoff.py
```

The external fresh Solana validation panels can be replayed and their diagnostics
reproduced without network access or fitting. After installing the backend and
quant packages, provide the four original CSV files explicitly:

```bash
PYTHONPATH=apps/api python quant/tools/evaluate_fresh_panels.py \\
  --panel NVDAx=/path/to/nvdax.csv \\
  --panel SPYx=/path/to/spyx.csv \\
  --panel QQQx=/path/to/qqqx.csv \\
  --panel AAPLx=/path/to/aaplx.csv \\
  --output /tmp/fresh-validation.json
```

The evaluator uses the backend's identity-checked panel loader and chronological
P1a-C replay. It reports current Evidence State and reason-code counts. The
backend now abstains as `INCONCLUSIVE` for the registered OKX X-Perp/index
comparator because the P1a-C predictive uncertainty is not calibrated for
X-Perp residuals. Pairwise xStock/model and xStock/X-Perp figures remain
descriptive; there is not yet a research-validated combined three-source
Evidence State rule. P1a assimilates xStock, so xStock/model disagreement is
model-based evidence, not independent market confirmation. The 2026-09-21 to
2026-10-05 panel bytes are not committed; the manifest hashes are reproducible
only if those exact external files are available.

QQQx's frozen fit is retained without refitting. Its token measurement variance
is at the optimizer upper bound across sessions. In the 4,068-token fresh replay,
the reproduced scalar Kalman gain had mean `0.00005655`, median `0.00005022`,
and maximum `0.00022717`; thus the model assigns very little weight to the
current token input. Its runtime is classified
`QQQ_MODEL_ACCEPTED_WITH_DISCLOSED_BOUNDARY_RISK`: optimizer convergence,
finite causal inference, and parity pass, but fresh MAE/RMSE are worse than raw
xStock. This is a stable, truthful weak-challenger result, not a superior-point
estimate or a production-quality promotion verdict.
