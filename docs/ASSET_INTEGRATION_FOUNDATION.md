# Asset Integration Foundation

This note describes the backend seam for future asset/model promotion. It does
not activate another asset, create another model artifact, or change the
current NVDAx production path.

## Current state

`apps/api/valtide_api/assets.py` is the production asset registry. It contains
only `NVDAx`. A registered asset has separate capability declarations for live
data, historical data, quant, warmed runtime, onchain use, and API exposure.
Registration alone starts no scheduler and exposes no route. All asset-scoped
routes check exposure and their required capabilities before reading state.

The existing NVDAx behavior remains:

```text
OKX OnchainOS NVDAx + Alpaca NVDA + OKX X-Perp NVDA-USD
    -> packaged P1a-C runtime
    -> backend validation
    -> warmed SQLite runtime/history
    -> existing X Layer control-plane binding
```

## Ownership of configuration

- `AssetConfig` owns behavioral identity, source/adapter keys, token-market
  deployment selection, reference instrument and Registry reference name,
  quant runtime key, historical panel key, and capability declarations. The
  current NVDAx environment overrides still resolve its token pin, reference
  instrument, and panel path.
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
address. Pinned values take precedence; only the current NVDAx compatibility
config permits cached discovery. Future assets must pin a deployment.

`market_sources.py` dispatches the underlying symbol and reference instrument
for live and historical reads. The current adapters remain Alpaca and the
public OKX X-Perp index. `live.py` assembles an asset-scoped snapshot; the
scheduler retries only absence of the exact confirmed token candle at the same
canonical timestamp. Quant and validation behavior remain unchanged.

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

`build_enabled_schedulers` accepts an explicit asset tuple and builds one
independent worker per selected, ready asset. The current Railway settings
select only `LIVE_SCHEDULER_ASSET=NVDAx`. In-process publisher calls share a
single lock so separate future asset workers cannot race the signer nonce.

Adding a config entry alone must never promote an asset to production. Runtime
support, quant artifact readiness, scheduler activation, publication binding,
DemoVault binding, and frontend exposure are independent decisions.

## Future promotion checklist

A future asset requires an explicit review and green evidence for each step:

1. Quant research approved.
2. Data provenance approved.
3. Model and calibration approved.
4. `AssetConfig` created with correct sources, pinned token deployment, keys,
   and initially disabled capabilities/exposure.
5. Source adapters registered in `token_market.py` / `market_sources.py`.
6. Real canonical historical panel and asset-bound path registered.
7. Validated quant artifact and factory registered in `quant_runtime.py`.
8. X Layer asset binding added to the deployment manifest and checked against
   the artifact version; DemoVault deployed and policy-bound if required.
9. Runtime worker enabled explicitly; existing Railway NVDAx env remains the
   one-worker default. Additional worker selection needs explicit deployment
   configuration, not merely a registry entry.
10. Isolation, numerical regression, and control-plane tests pass.
11. API exposure and frontend activation occur as separate reviewed steps.

Research files or a local panel do not make an asset supported. No additional
asset, quant artifact, X Layer binding, or frontend exposure is activated here.
