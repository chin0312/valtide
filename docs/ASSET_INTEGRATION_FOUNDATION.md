# Asset Integration Foundation

This note describes the current multi-asset integration seams and their
readiness limits. The public API catalog exposes NVDAx, SPYx, and AAPLx; QQQx
remains offline research-only and TSLAx remains a hidden candidate. The three
public assets have complete runtime, historical, and X Layer bindings, while
each readiness dimension remains independently fail-closed.

## Current state

`apps/api/valtide_api/assets.py` is the canonical application asset registry.
Each entry has separate live-data, historical, quant, warmed-runtime, onchain,
and API-exposure capabilities. NVDAx, SPYx, and AAPLx have pinned Solana token
identities, asset-specific P1a-C bundles, canonical historical panels, live
runtimes, and publication-compatible X Layer bindings. QQQx retains an offline
quant bundle and historical panel but has no live runtime, public API route, or
onchain binding. Selecting an asset never substitutes another asset's prices,
model, panel, or onchain state.

The public asset path is:

```text
OKX OnchainOS xStock + Alpaca underlying + asset-matched OKX X-Perp
    -> packaged P1a-C runtime
    -> backend validation
    -> warmed SQLite runtime/history
    -> asset-specific X Layer control-plane binding
```

## Ownership of configuration

- `AssetConfig` owns behavioral identity, source/adapter keys, the pinned token
  market identity, reference profile/instrument and Registry reference name,
  quant runtime key, historical panel key, and capability declarations. The
  existing NVDAx environment overrides remain supported. SPYx/QQQx/AAPLx token
  pins match the Solana identities in `quant/data_manifest/datasets_manifest.json`.
- The deployment manifest remains authoritative for deployed contract addresses,
  `assetId`, `referenceId`, and the deployed model-version hash. The publisher's
  resolver checks the hashes against asset identity, reference identity, and
  the registered quant artifact. The current manifest uses `assets[asset]` with
  `assetId`, `referenceId`, `modelVersion`, `demoVault`, and an explicit
  publication-compatibility declaration per public asset. The legacy
  single-asset `demo` binding is no longer active.
- The packaged quant artifact owns model ID and version. `quant_runtime.py`
  registers a factory plus artifact metadata loader under a runtime key. It
  checks the loaded artifact's asset, model ID, and version before inference.
  `/api/assets.model_available` queries this registration, not a model-name
  constant in the route.
- Existing environment variables remain the compatibility boundary for NVDAx
  deployment/source overrides. They are validated as a pair where applicable.

## Data and runtime boundaries

`token_market.py` dispatches exact confirmed and historical token candles by
adapter key. The OKX adapter accepts the configured chain index and token
address. All registered production/catalog assets are pinned to their Solana
`chainIndex=501` identity from the data manifest; the legacy NVDAx env names
remain accepted only when they match its registered pin. Production dispatch
does not discover or select another chain by volume. Future assets must pin a
deployment.

`market_sources.py` dispatches the underlying symbol and reference instrument
for live and historical reads. The adapters are Alpaca and the public OKX
X-Perp index. `live.py` obtains the exact confirmed token candle through the
generic `token_market` boundary and assembles an asset-scoped snapshot. The
current `unified_xstock_p1ac_xperp_evidence_v1` profile treats the observed
xStock as the validation target, P1a-C as a model-based challenger that has
already assimilated that token input, and exact-time X-Perp as separately
sourced market evidence. Older `legacy_xperp_vs_p1ac` rows remain readable for
provenance, but their Evidence States are not comparable with unified-v2
states. The scheduler retries only absence of the exact confirmed token candle
at the same canonical timestamp.

New panels use asset-neutral columns (`token_close`, `underlying_close`,
availability, volumes, exact timestamps, trusted anchor, and reference under
test) plus `asset`, underlying symbol, token source, token chain/address, and
reference instrument identity. The loader verifies this identity and rejects
cross-asset use. Existing NVDA panels with `nvdax_*` / `nvda_*` fields are
normalized in one legacy compatibility function; only NVDAx may use them. A
canonical panel is accepted as production-grade historical evidence only when
the configured chain-index and token-address pins both exist and match its
deployment columns. Loading is offline and never performs OKX discovery. A
legacy panel has no independently verifiable deployment identity: replay marks
it `legacy_nvda_panel_diagnostic`, and historical backtest metrics are omitted.

`build_enabled_schedulers` accepts an explicit asset tuple and builds an
independent worker only when that asset has a ready runtime and quant bundle.
The legacy `LIVE_SCHEDULER_ENABLED` plus `LIVE_SCHEDULER_ASSET=NVDAx` settings
remain the local default. `LIVE_SCHEDULER_ASSETS` selects the independently
ready workers in a multi-asset deployment; unready known assets are skipped
with a safe readiness log, while unknown assets remain configuration errors.
In-process publisher calls share a single lock so asset workers cannot race the
signer nonce.

Adding a config entry alone must never promote an asset to production. Runtime
support, quant artifact readiness, historical-data availability, scheduler
activation, publication binding, DemoVault binding, and frontend exposure are
independent readiness decisions. `/api/assets` reports these dimensions; a
catalog entry with `MODEL_FIT_BLOCKED` or `HISTORICAL_DATA_UNAVAILABLE` is not an
operational product capability.

## Current readiness split

NVDAx, SPYx, and AAPLx have passed the runtime, canonical-panel, public-API,
scheduler, and X Layer binding gates. QQQx retains offline quant and historical
research but is deliberately excluded from live data, warmed runtime, public
HTTP, and onchain publication. TSLAx remains a registered hidden candidate and
has not passed the quant/runtime/publication gates. The SPYx, QQQx, and AAPLx
bundles were exported from checksum-verified frozen fits without retraining;
their original training-panel bytes were not supplied, so the declared
training dataset hashes have not been independently recomputed.

## Future promotion checklist

A future asset requires an explicit review and green evidence for each step:

1. Quant research approved.
2. Data provenance approved.
3. Model and calibration approved.
4. `AssetConfig` created with correct sources, pinned token deployment, keys,
   and capabilities left false until each readiness gate passes.
5. Source adapters registered in `token_market.py` / `market_sources.py`.
6. Restore/verify the canonical asset-matched source data, publish a canonical
   historical panel and bind its path with verifiable identity.
7. Fit asset-specific P1a parameters from the approved training interval,
   generate compatible P1a-C calibration from a later independent interval,
   and register the validated artifact/factory in `quant_runtime.py`.
8. Evaluate on a fresh later period, record sample size and uncertainty, and
   pass pre-agreed quality thresholds before enabling runtime capability.
9. X Layer asset binding added to the deployment manifest and checked against
   the artifact version; DemoVault deployed and policy-bound if required.
10. Enable the asset's scheduler only after source, model, persistence-isolation
    and operational tests pass. This does not require onchain writes.
11. Isolation, numerical regression, and control-plane tests pass.
12. API exposure and frontend activation occur as separate reviewed steps.

Research files or a local panel do not make an asset operational. The Console
selector exposes the three public assets only. QQQx remains available to
offline quant and historical research, and TSLAx remains hidden until their
separate readiness gates are explicitly promoted.
