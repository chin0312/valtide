# Quant runtime and backend handoff

## Canonical NVDAx package

The production import path is the root package, `valtide-quant-service-p1ac`, installed by the backend environment (for example, `python -m pip install -e ./valtide-quant-service-p1ac`). `quant/runtime/p1ac/code/` is a compatibility snapshot for review and handoff, not a second production import path. The snapshot's source tree and embedded parameter/calibrator files are checked byte-for-byte against the root package; canonical copies also appear under `params/` and `calibration/` for explicit inspection.

The expected API is:

```python
from valtide_quant_service import FilterState, MarketSnapshot, QuantService

service = QuantService.from_default_artifacts(state=restored_filter_state)
estimate = service.update(snapshot)  # one ordered canonical observation
next_state = service.export_state()  # m, P, timestamp; restore via FilterState.from_dict
```

`MarketSnapshot` carries `asset`, timezone-aware `timestamp`, `quant_session`, `token_price`, `current_underlying_price`, `last_trusted_reference`, `last_trusted_reference_timestamp`, and optional `external_constructed_reference`. `QuantEstimate` carries fair value, calibrated interval, predictive uncertainty, model metadata, and `carried_state`. The runtime rejects an asset mismatch, non-increasing timestamps, and gaps other than one canonical 300-second step. Restore state and resume in canonical order; do not advance the filter from an API read.

## Frozen artifact identity and causal contract

The sole checked-in runtime is `NVDAx` / `P1a-C` / `0.2.0`, bound in `p1ac/metadata/runtime_binding.json` to dataset SHA-256 `722929383e6ca1aa28382e828879efeccb60faabdf2bd5e05f14a721f7fc740d`. The parameter and calibrator bytes, embedded package copies, and metadata hashes are verified by:

```bash
python quant/runtime/p1ac/verify_runtime.py
python quant/runtime/p1ac/run_deterministic_tests.py
```

This proves current artifact identity/integrity and the declared chronological ordering: the parameter metadata says training ended 2026-06-23, before the calibrator metadata's 2026-09-22 generation time. It does **not** independently prove the original fit consumed that exact dataset: the original training run/fold evidence and canonical source panel are not included in this Git handoff. The runtime binding is a recorded association, not a cryptographic training-lineage attestation.

The causal update order is frozen: predict state, assimilate the current xStock observation, emit the challenger estimate/interval, and only then assimilate the current underlying observation for the next timestamp. Keep the current reference-under-test observation outside the quant update. `external_constructed_reference` is not used by the estimator. Preserve the documented last-trusted-reference initialization contract; do not substitute the current reference-under-test value as that anchor.

The model returns quantitative estimates only. The backend owns the canonical Evidence States `SUPPORTED`, `INCONCLUSIVE`, and `CHALLENGED`; historical research labels `SUPPORT`, `WATCH`, and `REVIEW` are research classifications, not aliases for those production states or for a curator's Policy Action. Likewise, the five-asset study's raw xStock benchmark is not automatically equivalent to the live OKX X-Perp reference under test.

## Research scope and promotion boundary

The study covers NVDAx, SPYx, QQQx, TSLAx, and AAPLx. **Only NVDAx has a checked-in runtime artifact and is approved for the current production runtime.** SPYx, QQQx, AAPLx, and TSLAx remain research-only; a pitch shortlist does not alter that status. The exposed development test windows were inspected during research and are not fresh prospective validation.

Before promoting another asset, the integrator/research owner must:

1. restore its canonical source data from approved storage and verify dataset/deployment identity and hashes;
2. produce and independently verify asset-specific fitted P1a parameters and calibrators;
3. evaluate on an independent, later chronological holdout with pre-agreed quality thresholds;
4. register the validated artifact and bind its source, state, and deployment identities;
5. isolate scheduler state and add cross-asset and golden regression tests;
6. only then separately approve runtime, API, onchain, and frontend exposure.

Do not import rejected lag/dislocation-gate, P1m, or P1m-C experiments, and do not copy the handoff snapshot as a second package. PR #17 can consume the root package interface above and its artifact identity checks; no non-NVDA asset is made production-ready by this handoff.
