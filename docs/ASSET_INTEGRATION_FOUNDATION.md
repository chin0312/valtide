# Asset Integration Foundation

This note describes the current multi-asset integration seams and their
readiness limits. Four primary asset identities are visible in the API catalog,
but only NVDAx has a complete runtime bundle and deployed control-plane binding.
Catalog visibility is not operational or historical readiness.

## Current state

`apps/api/valtide_api/assets.py` is the canonical application asset registry.
The public catalog contains `NVDAx`, `SPYx`, `QQQx`, and `AAPLx`; `TSLAx` is a
registered but hidden candidate. Each entry has separate live-data, historical,
quant, warmed-runtime, onchain, and API-exposure capabilities. The three new
primary entries have pinned Solana token identities and adapter configuration,
but remain unavailable for valuation/replay because no verified compatible
P1a-C runtime or matching canonical historical panel is present. Only NVDAx is
currently runtime-ready and deployed on X Layer. Selecting a catalog asset
never substitutes another asset's prices, model, panel, or onchain state.

The existing NVDAx behavior remains:

```text
OKX OnchainOS NVDAx + Alpaca NVDA + OKX X-Perp NVDA-USD
    -> packaged P1a-C runtime
    -> backend validation
    -> warmed SQLite runtime/history
    -> existing X Layer control-plane binding
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
  the registered quant artifact. The current manifest's `demo` binding is
  supported unchanged; a future manifest can use `assets[asset]` with
  `assetId`, `referenceId`, `modelVersion`, and `demoVault` per asset.
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
generic `token_market` boundary and assembles an asset-scoped snapshot. NVDAx
retains its explicit `legacy_xperp_vs_p1ac` profile. The four-asset catalog
declares `xstock_vs_p1ac_challenger`: the observed token is compared with a
challenger that has already assimilated that same token input, so the comparison
is model-based challenger evidence, not two fully independent observations;
disagreement alone does not identify a correct price. The separate NVDAx
`legacy_xperp_vs_p1ac` profile's historical Evidence States are not comparable
with states from the xStock profile. The scheduler retries only absence of the
exact confirmed token candle at the same canonical timestamp.

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
remain the default. `LIVE_SCHEDULER_ASSETS` is an optional explicit list for a
future multi-worker deployment; unready known assets are skipped with a safe
readiness log, while unknown assets remain configuration errors. In-process
publisher calls share a single lock so asset workers cannot race the signer
nonce.

Adding a config entry alone must never promote an asset to production. Runtime
support, quant artifact readiness, historical-data availability, scheduler
activation, publication binding, DemoVault binding, and frontend exposure are
independent readiness decisions. `/api/assets` reports these dimensions; a
catalog entry with `MODEL_FIT_BLOCKED` or `HISTORICAL_DATA_UNAVAILABLE` is not an
operational product capability.

## Current four-asset blocker

The research handoff's five-asset dataset manifest identifies Solana
`chainIndex=501` datasets and records their hashes, but the canonical panels and
metadata are not in Git and their shared-storage locations are still
`TBD_SHARED_STORAGE/...`. A local untracked research tree was inspected but its
v3 panels identify Ethereum (`chainIndex=1`) deployments and different token
addresses; they cannot be used as the Solana production panels. Per-asset
research parameter files/calibrators tied to those inputs therefore do not
constitute verified bundles for the pinned Solana identities. No SPYx, QQQx, or
AAPLx P1a-C runtime has been registered. This PR exposes the identities and
fail-closed readiness surfaces; it does not claim the four-asset operational
or historical acceptance gate is met.

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
selector exposes the four catalog identities and their readiness status, but
no additional runtime, quant artifact, X Layer binding, or live-result path is
activated here.
