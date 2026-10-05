# Asset Integration Foundation

This note describes the four-asset runtime foundation and its current evidence
limits. NVDAx, SPYx, QQQx, and AAPLx have explicit Solana identities and
asset-specific P1a-C runtime bundles. Only NVDAx has an X Layer binding. A
loaded model artifact is not, by itself, evidence that a fresh historical panel
or production operational path is ready.

## Current state

`apps/api/valtide_api/assets.py` is the canonical application asset registry.
The public catalog contains `NVDAx`, `SPYx`, `QQQx`, and `AAPLx`; `TSLAx` is a
registered but hidden candidate. Each primary entry has separate live-data,
historical, quant, warmed-runtime, onchain, and API-exposure capabilities. The
three non-NVDAx quant bundles were exported from James's frozen RDS fits and
their matching P1a-C calibrators after checksum and dataset-binding checks;
the R/Python sequential parity fixture passes. The original Solana source CSVs
were not in the private handoff, so their declared dataset hashes have not been
independently recomputed. On 2026-10-05, the configured OKX OnchainOS, Alpaca,
and OKX index adapters each returned a successful exact-identity live tick for
all four assets, and 2026-09-21 through 2026-10-05 canonical panels were
collected and replayed locally. These checks are retrospective/local; panel CSVs
remain outside Git and are not provisioned on persistent production storage.
They do not establish sustained scheduler operation or production readiness.
Only NVDAx has an X Layer deployment. Selecting an asset never substitutes
another asset's prices, model, panel, or onchain state. Exact panel SHA-256s and
observed counts are recorded in
`quant/data_manifest/fresh_validation_20261005.json`.

The existing NVDAx behavior remains:

```text
OKX OnchainOS Solana xStock + Alpaca underlying + matching OKX X-Perp/index
    -> asset-specific packaged P1a-C runtime
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

`market_sources.py` dispatches each configured underlying and separate OKX
X-Perp/index instrument for live and historical reads. All four current product
assets use one evidence identity. The Solana xStock observation is assimilated
by P1a before the model-based challenger estimate is emitted; it is therefore
not an independent second market observation. The separately sourced
X-Perp/index is retained as distinct market evidence. Disagreement does not
prove which price is correct. Prior NVDAx generations retain their original
profile identity for audit and are not relabeled. The scheduler retries only
absence of the exact confirmed token candle at the same canonical timestamp.

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

The handoff's five-asset manifest declares Solana `chainIndex=501` dataset
identities and hashes; the original canonical panels and metadata are absent
from the private ZIP and Git. Its `TBD_SHARED_STORAGE/valtide/2026-10-01/{asset}/`
locations remain external dependencies. The three supplied frozen model fits
and calibrators are hash-bound to those declared dataset hashes, but the source
CSV bytes are not available for an independent hash recomputation. A separate
local untracked research tree contained Ethereum (`chainIndex=1`) panels; those
are not used for model export, fresh validation, replay, or runtime promotion.
They do not establish which chain James used for the handoff research.

QQQx's frozen fit reports convergence, but its token measurement log-variance
is at the optimizer's upper bound for all sessions. The artifact is preserved
unchanged and its fresh-period behavior must be reviewed; no fitting or
threshold change is inferred from the bound.

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

Research files or an artifact alone do not make an asset operational. The
Console selector exposes the four primary identities and per-asset readiness;
the three new X Layer bindings remain unconfigured, and fresh live/history
evidence is required before the four-asset acceptance gate can be claimed.
