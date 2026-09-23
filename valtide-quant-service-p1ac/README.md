# Valtide Quant Package — P1a-C

This package owns **independent challenger estimation and uncertainty only**. It contains the actual trained P1a-C deployment artifacts and a sequential Python runtime that can be imported by the Valtide backend.

It does not determine whether a reference under test is supported or challenged, assign an Evidence State, return a Policy Action, or expose a separate HTTP service. Those responsibilities belong to `apps/api`.

## Included trained artifacts

`artifacts/p1a_runtime.json` contains the fitted P1a structural parameters:

- session-specific `Q`
- `R_nvda`
- `R_nvdax`

`artifacts/p1a_c_calibrator.json` is copied directly from the completed P1a-C calibration run. The selected family is `session_sym`; at 90% its empirical multipliers are approximately:

- regular: `1.4520`
- premarket: `1.3802`
- afterhours: `1.0122`
- global fallback: `1.3450`

Closed/overnight intervals use the selected global fallback because contemporaneous NVDA labels are unavailable in those regimes; direct latent-state coverage in those regimes is not observable from this evaluation.

The package also includes the completed calibration report and test interval metrics under `evidence/`.

## Independence

The numerical fair value and interval do **not** use Pyth or another constructed estimator. Optional external or reference-under-test fields may remain on `MarketSnapshot` for backend diagnostics, but they cannot change the challenger estimate, interval bounds, or carried Kalman state.

The backend selects the reference under test and determines the product Evidence State. The quant package returns only quantitative output.

## Architecture boundary

```text
MarketSnapshot
      ↓
P1a-C Quant Runtime
      ↓
Quant Estimate
      ↓
apps/api backend validation
      ↓
SUPPORTED / INCONCLUSIVE / CHALLENGED
```

`QuantEstimate` contains fair value, calibrated interval bounds, uncertainty, calibration metadata, model metadata and carried state. `apps/api` compares that estimate with the selected reference under test and owns the Evidence State.

## Causal update order

For each canonical 5-minute timestamp:

```text
predict P1a state
  ↓
assimilate current NVDAx
  ↓
produce Valtide fair value + P1a-C interval
  ↓
only then assimilate current NVDA (if available)
  ↓
carry state to next timestamp
```

Thus current NVDA cannot leak into the challenger quote it is used to evaluate. External comparator fields cannot alter the fair value, interval or carried state.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest -q
```

Example:

```python
from datetime import datetime, timezone
from valtide_quant_service import QuantService, MarketSnapshot

svc = QuantService.from_default_artifacts()
result = svc.update(MarketSnapshot(
    asset="NVDAx",
    timestamp=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
    quant_session="closed",
    token_price=180.75,
    current_underlying_price=None,
    last_trusted_reference=180.00,
    last_trusted_reference_timestamp=datetime(2026, 9, 22, 20, 0, tzinfo=timezone.utc),
    external_constructed_reference=None,
))
print(result.to_dict())
```

## Backend integration

The scheduler/data coordinator should call `QuantService.update(snapshot)` exactly once per canonical 5-minute timestamp and pass the returned `QuantEstimate` to `apps/api` validation.

The canonical HTTP/API layer is `apps/api`; this package does not provide a second FastAPI application. Backend endpoints should be read-only when returning cached estimates and must not advance the filter implicitly.

If the service restarts, either restore a saved `FilterState` or warm-start from a short ordered sequence of recent canonical snapshots.
