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
and carried state. The backend selects the validation target, preserves the
separate X-Perp signal, performs data-quality checks, determines Evidence State,
and exposes reason codes.

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
backend validates the observed xStock target with P1a-C and X-Perp evidence
```

The quant runtime requires exact 5-minute state progression. A canonical panel
row with no token observation is retained as `token_price=None`; the quant state
advances without a fabricated measurement and backend validation returns
`INCONCLUSIVE` with `TOKEN_DATA_UNAVAILABLE`.

## 3. Validation-target semantics

The production assets use
`unified_xstock_p1ac_xperp_evidence_v1`. The observed xStock is the validation
target, P1a-C is a model-based challenger that has already assimilated that same
xStock observation, and exact-time OKX X-Perp/index is a separately sourced
second-market signal. This is **model-based challenger evidence with separate
market corroboration**, not three independent votes. Disagreement is not proof
of which price is correct.

`reference_under_test` remains in the API and onchain identity for compatibility
and currently carries the X-Perp observation. New consumers must use
`validation_target`, `evidence_semantics`, and `xperp_role` to interpret the
result. Older `legacy_xperp_vs_p1ac` rows remain readable for provenance but are
not the operational classifier and must not be blended with v2 Evidence States.
A missing configured source is never replaced with another asset or fallback.

Historical replay may explicitly use `stale_nvda` or a scenario reference; the
identity is then part of the snapshot and is valid for that replay.

The latest available trusted underlying bar is an R0 anchor. It is not assumed
to be an official regular-session close; exchange-calendar and US-holiday
selection remain known limitations of the current adapter.

## 4. Evidence State

Validation is deterministic, asset-bound, and fail-closed. The unified v2
classifier starts at `INCONCLUSIVE`, applies source/model quality and freshness
gates, then interprets the frozen P1a/xStock disagreement band together with
exact-time X-Perp evidence:

- an authorized support band plus exact-time X-Perp availability may emit
  `SUPPORTED`;
- a watch band remains `INCONCLUSIVE`;
- an authorized review band may emit `CHALLENGED` only when X-Perp is closer to
  P1a-C than to xStock; and
- missing, stale, ambiguous, or quality-gated evidence remains `INCONCLUSIVE`.

Support and challenge authority comes from the asset-bound
`tri_source_capabilities_v2.json` artifact, not from the detector promotion
label alone. The current underlying observation is an ex-post truth proxy for
research evaluation, not a same-time Evidence State voter.

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
assets.py        asset registry, public catalog, readiness capabilities, panel-key resolution
token_market.py  token candle adapter registry and exact-candle dispatch
market_sources.py underlying/reference adapter registry
models.py        MarketSnapshot, ChallengerEstimate, ValuationResult, enums

adapters/
  okx.py         configured OnchainOS token candles (NVDAx compatibility wrappers)
  equity.py      latest available trusted configured underlying bar
  reference.py   OKX X-Perp second-market evidence
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
- The warmed live scheduler is disabled by default. When enabled, it runs one
  isolated worker per explicitly selected, ready asset in the same process on
  canonical UTC five-minute boundaries and persists carried state, latest
  result, gap steps, and last tick status in SQLite. It advances elapsed gaps
  with hidden no-measurement steps; those steps never become public replay or
  API observations.
- Historical-panel backtests report metrics only for rows with a real
  contemporaneous underlying observation. Scenario backtests report evidence
  counts only and deliberately keep empirical metrics null.
- The canonical live token input is the exact confirmed OKX OnchainOS candle
  for the selected asset at the settled five-minute observation. DexScreener is
  not a fallback. NVDAx, SPYx, and AAPLx use the same unified xStock-target,
  P1a-C-challenger, and X-Perp-evidence profile with asset-bound capabilities.
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

Asset identity and public catalog exposure are registry-backed. The public
API catalog lists `NVDAx`, `SPYx`, and `AAPLx`; `QQQx` remains offline
research-only and `TSLAx` remains a hidden candidate. `/api/assets` reports
live, quant, historical, detector/state authority, scheduler, and onchain
readiness independently. NVDAx, SPYx, and AAPLx have asset-specific P1a-C
bundles, canonical historical panels, and independently selectable live
runtimes. All three have asset-specific publication bindings to the shared
ValidationRegistry and RiskGuard on X Layer testnet. Legacy single-worker
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
