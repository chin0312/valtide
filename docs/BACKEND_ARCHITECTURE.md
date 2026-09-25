# Valtide Backend — Team Guide

**Owner:** Xin Tong · **Code:** `apps/api/` · **Status:** P1a-C backend
integration and X Layer testnet publisher complete

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
assimilate current NVDAx/token observation when available
      ↓
read challenger fair value and interval
      ↓
assimilate current NVDA only for the next timestamp
      ↓
backend validates the selected reference under test
```

The quant runtime requires exact 5-minute state progression. A canonical panel
row with no token observation is retained as `token_price=None`; the quant state
advances without a fabricated measurement and backend validation returns
`INCONCLUSIVE` with `TOKEN_DATA_UNAVAILABLE`.

## 3. Reference-under-test semantics

The reference under test is an explicitly named observation, not a fallback
slot. In live mode the intended reference is the OKX X-Perp index. If it cannot
be fetched, the snapshot keeps that identity with a null value and validation
returns `INCONCLUSIVE` with `COMPARATOR_UNAVAILABLE`. The backend never silently
replaces it with stale NVDA.

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
SUPPORTED      independent evidence provides no material reason to challenge
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
config.py        settings from .env and CORS origins
models.py        MarketSnapshot, ChallengerEstimate, ValuationResult, enums

adapters/
  okx.py         NVDAx token candles
  equity.py      latest available trusted NVDA bar
  reference.py   OKX X-Perp reference under test
  dexscreener.py optional NVDAx diagnostic quote

session.py       timestamp → market session
normalizer.py    shared token/underlying scale invariant
quant_runtime.py thin adapter around packaged QuantService
validation.py    backend Evidence State engine
panel.py         canonical 5-minute panel loader
scenario.py      explicit scripted scenario loader
data_source.py   panel/scenario source selection
replay.py        sequential quant + validation pipeline
live.py          cold-start live diagnostic
clock.py         canonical UTC five-minute boundaries
scheduler.py     single-process warmed live scheduler
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

## 7. Current status and handoffs

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
- The canonical live token input is the exact confirmed OKX OnchainOS NVDAx
  candle at the settled five-minute observation. DexScreener is not substituted
  when that candle is unavailable; its adapter is diagnostic-only.
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
