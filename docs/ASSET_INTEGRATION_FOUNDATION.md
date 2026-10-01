# Asset Integration Foundation

This note describes the backend seam for future asset/model promotion. It does
not activate another asset, create another model artifact, or change the
current NVDAx production path.

## Current state

`apps/api/valtide_api/assets.py` is the canonical production asset registry.
It currently contains exactly one enabled entry: `NVDAx`. `/api/assets`, live
source selection, quant dispatch, historical-panel loading, scheduler identity,
and the publisher all resolve through that registered asset boundary. An
unknown or unregistered name fails closed; it cannot inherit NVDAx state,
artifacts, IDs, or a panel path.

The existing NVDAx behavior remains:

```text
OKX OnchainOS NVDAx + Alpaca NVDA + OKX X-Perp NVDA-USD
    -> packaged P1a-C runtime
    -> backend validation
    -> warmed SQLite runtime/history
    -> existing X Layer control-plane binding
```

## Ownership of configuration

- `AssetConfig` owns behavioral identity and source/model selection: asset name,
  underlying symbol, token/reference source names, the OKX X-Perp instrument,
  quant model identity, and the asset-aware historical-panel resolution.
- The deployment manifest remains authoritative for deployed contract addresses,
  `assetId`, `referenceId`, and the deployed model-version hash. The publisher's
  single deployment resolver verifies those values against the registry entry.
- The packaged quant artifact owns the executable P1a-C implementation and its
  runtime metadata. The backend dispatch seam maps the registered NVDAx config
  to the existing default artifact; it does not reimplement model mathematics.
- Existing environment variables remain the compatibility boundary for NVDAx
  deployment/source overrides. They are validated as a pair where applicable.

Adding a config entry alone must never promote an asset to production. Runtime
support, quant artifact readiness, scheduler activation, publication binding,
DemoVault binding, and frontend exposure are independent decisions.

## Future promotion checklist

A future asset requires an explicit review and green evidence for each step:

1. Quant research approved.
2. Data provenance approved.
3. Model and calibration approved.
4. `AssetConfig` created with the correct sources and identity.
5. A compatible quant artifact registered and dispatched explicitly.
6. X Layer deployment IDs and contract bindings created and verified.
7. DemoVault deployed and policy-bound if required.
8. Asset-specific scheduler/runtime activation enabled intentionally.
9. Publisher and onchain read paths pass cross-asset isolation tests.
10. Frontend exposure activated separately.
11. Full backend, quant, contract, and integration checks are green.

The backend currently implements only the NVDAx branch of this checklist.
Research files or a local panel do not make another asset supported, and no
additional asset is published by this foundation refactor.
