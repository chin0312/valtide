# Valtide Quant Service — P1a-C

This package contains the **actual trained P1a-C deployment artifacts** and a Python runtime suitable for the Valtide FastAPI backend.

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

Closed and overnight use the global fallback because contemporaneous NVDA labels are unavailable in those regimes.

The package also includes the completed calibration report and test interval metrics under `evidence/`.

## Independence

The numerical fair value and interval do **not** use Pyth or another constructed estimator. An optional external comparator may be carried in the API response for display/comparison, but it cannot change `valtideFairValue`, interval bounds, or Kalman state.

The primary `challengeStatus` is computed against the last trusted underlying reference. A separate optional `externalComparatorStatus` is returned for Pyth/other comparators.

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

Thus current NVDA cannot leak into the challenger quote it is used to evaluate.

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

The scheduler/data coordinator should call `QuantService.update(snapshot)` exactly once per canonical 5-minute timestamp and store the returned `ValuationResult`.

`GET /api/valuation/{asset}` must be read-only and should return the cached result rather than advancing the filter.

If the service restarts, either restore a saved `FilterState` or warm-start from a short ordered sequence of recent canonical snapshots.
