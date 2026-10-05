# Valtide Backend — Architecture Reference

**Scope:** `apps/api/`

This document describes the as-built backend orchestration, validation,
persistence, scheduler, API, and X Layer publication boundaries.

The backend orchestrates data, the packaged quant runtime, backend-owned
validation, and the API. It does not contain pricing mathematics.

## 1. Who talks to whom

```text
market data
    ↓
backend MarketSnapshot
    ↓
packaged P1a-C QuantService
    ↓
QuantEstimate
    ↓
backend validation
    ↓
SUPPORTED / INCONCLUSIVE / CHALLENGED
    ↓
API / frontend and scheduler-owned X Layer publisher
```

The quant package owns fair value, calibrated intervals, uncertainty metadata,
and carried state. The backend selects the reference under test, performs data
quality checks, determines Evidence State, and exposes reason codes.

## 2. The sequential check

```text
predict prior state
      ↓
assimilate current asset token observation when available
      ↓
read challenger fair value and interval
      ↓
assimilate current underlying only for the next timestamp
      ↓
backend validates the selected reference under test
```

The quant runtime requires exact 5-minute state progression. A canonical panel
row with no token observation is retained as `token_price=None`; the quant state
advances without a fabricated measurement and backend validation returns
`INCONCLUSIVE` with `TOKEN_DATA_UNAVAILABLE`.

## 3. Unified reference and evidence semantics

Current asset selection does not select a reference profile. Each observation
uses its pinned Solana xStock candle as the token/model input, the corresponding
underlying as the configured measurement/anchor, and the asset's separate OKX
X-Perp/index observation as market evidence when available. P1a assimilates the
xStock observation before emitting the challenger estimate, so the token and
challenger are not two fully independent market observations. The X-Perp/index
is a separate market-evidence source; disagreement does not prove which price
is correct. New rows use the unified evidence identity and retain source
provenance. Historical rows from the prior NVDAx reference generation retain
their stored identity for audit and must not be silently relabeled or mixed into
the current generation. Missing configured reference data is never replaced by
another asset or by xStock.

Historical replay may explicitly use `stale_nvda` or a scenario reference; the
identity is then part of the snapshot and is valid for that replay.

The latest available trusted underlying bar is an R0 anchor. It is not assumed
to be an official regular-session close; exchange-calendar and US-holiday
selection remain known limitations of the current adapter.

## 4. Evidence State

Validation is deterministic and threshold-driven, with quality and abstention
gates. It uses the log-space standardized deviation, calibrated interval,
underlying-reference freshness, reference-under-test freshness, token
availability/quality, and model uncertainty.

```text
SUPPORTED      available evidence provides no material reason to challenge
INCONCLUSIVE   evidence is unavailable, weak, stale, or unresolved
CHALLENGED     sufficiently strong evidence materially contradicts the reference
```

These are evidence semantics, not protocol policy actions. The consuming
protocol decides what to do with them.

Global fallback calibration is surfaced as `CALIBRATION_GLOBAL_FALLBACK`; it is
not automatically treated as an abstention. Closed/overnight calibration limits
must remain visible rather than being described as directly observed coverage.

## 5. Where each piece lives

```text
config.py        settings, backward-compatible NVDA env names, worker selection
assets.py        four-asset API catalog, readiness capabilities, panel-key resolution
token_market.py  token candle adapter registry and exact-candle dispatch
market_sources.py underlying/reference adapter registry
models.py        MarketSnapshot, ChallengerEstimate, ValuationResult, enums

adapters/
  okx.py         configured OnchainOS token candles (NVDAx compatibility wrappers)
  equity.py      latest available trusted configured underlying bar
  reference.py   OKX X-Perp reference under test
  dexscreener.py optional NVDAx diagnostic quote

session.py       timestamp → market session
normalizer.py    shared token/underlying scale invariant
quant_runtime.py artifact-backed runtime registry and thin QuantService adapter
validation.py    backend Evidence State engine
panel.py         asset-neutral panel loader and contained legacy NVDA normalization
scenario.py      explicit scripted scenario loader
data_source.py   panel/scenario source selection
replay.py        sequential quant + validation pipeline
live.py          cold-start live diagnostic
clock.py         canonical UTC five-minute boundaries
scheduler.py     explicitly selected, isolated asset workers; only ready bundles start
runtime_store.py SQLite state/result and publication status persistence
history.py      read-only warmed operational history
state_store.py   in-memory compatibility cache for non-HTTP callers
publisher.py     X Layer publication, read-back, and control-plane checks
abis/            bundled Registry, RiskGuard, and DemoVault ABIs
routes/          HTTP endpoints
main.py          app wiring, CORS, restore, and scheduler lifecycle
```

## 6. API

| Method | Route | What |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/api/assets` | supported assets and model availability |
| GET | `/api/valuation/{asset}` | latest durable warmed result |
| GET | `/api/valuation/{asset}/live` | cold-start live diagnostic |
| GET | `/api/history/{asset}` | successful warmed operational results |
| GET | `/api/replay/{asset}` | sequential scenario/panel results |
| GET | `/api/backtest/{asset}` | scenario counts or historical-panel metrics |
| GET | `/api/runtime/{asset}` | warmed runtime and scheduler status |
| GET | `/api/onchain/{asset}` | deployed control-plane status and evaluation |
| GET | `/api/onchain/{asset}/enforcement` | read-only DemoVault gate simulation |
| POST | `/api/publish/{asset}` | publish the latest warmed result when enabled |

A cold valuation cache returns `503 data_unavailable`. Publication returns
`503` while disabled or unconfigured, `409` for a result that is not publishable,
and `502` for a chain, transaction, or read-back failure.

## 7. As-built runtime behavior

- The backend imports the merged P1a-C package through its public service
  boundary.
- The scripted scenario and canonical 5-minute panel are replayed through the
  same inference path.
- The warmed live scheduler is disabled by default, runs one asset in this
  process on canonical UTC five-minute boundaries, and persists carried state,
  latest result, gap steps, and last tick status in SQLite. It advances elapsed
  gaps with hidden no-measurement steps; those steps never become public replay
  or API observations.
- Historical-panel backtests report metrics only for rows with a real
  contemporaneous underlying observation. Scenario backtests report evidence
  counts only and deliberately keep empirical metrics null.
- The canonical live token input is the exact confirmed OKX OnchainOS Solana
  candle for the selected asset at the settled five-minute observation.
  DexScreener is not a fallback. All four assets use one evidence structure with
  their matched underlying and separate OKX X-Perp/index evidence. P1a
  assimilates xStock before emitting its model-based challenger, so these are
  not independent market observations. Only NVDAx has an X Layer binding.
- Operational history is the chronological sequence of successful warmed
  scheduler validations. It is distinct from scenario replay and historical
  backtest metrics.
- The focused API endpoint and live diagnostic are explicit about unavailable
  data; no fabricated valuation is served.
- The public testnet deployment manifest is the source of truth for the
  Registry, RiskGuard, DemoVault, asset ID, reference ID, and model version.
- Publication consumes only the latest warmed runtime result; replay, cold live
  diagnostics, GET requests, and frontend reads cannot publish directly.
- After a successful new scheduler tick is persisted, `AUTO_PUBLISH_ENABLED`
  may request the existing publisher to synchronize that result. Delivery
  status is persisted separately from valuation state. A single in-process
  publication worker serializes delivery, coalesces pending work to the newest
  observation, and does not hold up the scheduler cadence. A delivery failure
  does not invalidate the warmed result or stop the scheduler.
- `PUBLISH_ENABLED` defaults to false and gates only the explicit POST fallback.
  `AUTO_PUBLISH_ENABLED` is independent; a public demo can enable automatic
  delivery while leaving the manual route disabled. A successful write is
  followed by Registry and RiskGuard read-back verification.

Asset identity and public catalog exposure are registry-backed. The API
catalog lists `NVDAx`, `SPYx`, `QQQx`, and `AAPLx`; `TSLAx` remains a hidden
candidate. `/api/assets` reports live, quant, historical, scheduler, and
onchain readiness independently. All four catalog assets have pinned Solana
identities and asset-specific verified P1a-C bundles. A separate
2026-09-21–2026-10-05 provider-history window was collected and replayed locally
for each; its short retrospective metrics are diagnostic only. The source
training-panel bytes for the three imported fits were not supplied for
independent SHA recomputation, and the new panels are not committed or
provisioned to persistent production storage. Thus this repo revision supports
four-asset inference and local historical replay, but does not establish a
production-warmed four-asset deployment. Only NVDAx has an X Layer binding.
Legacy single-worker
`LIVE_SCHEDULER_ASSET` configuration remains supported; an explicit
`LIVE_SCHEDULER_ASSETS` list may select multiple independently ready workers.
Unready known assets are not started. Unknown assets and cross-asset identities
fail closed. See `docs/ASSET_INTEGRATION_FOUNDATION.md` for readiness evidence
and the promotion procedure.

## 8. Run locally

```bash
cd apps/api
python -m pip install -e ../../valtide-quant-service-p1ac
python -m pip install -e ".[dev]"
pytest
uvicorn valtide_api.main:app --reload
```

From the repository root:

```bash
python scripts/demo_value.py
```

> Thin orchestration. Quantitative computation stays in the packaged runtime;
> validation stays in the backend; failures degrade to an honest unavailable
> state rather than a fake number.
