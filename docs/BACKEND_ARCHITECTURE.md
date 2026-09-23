# Valtide Backend — Team Guide

**Owner:** Xin Tong · **Code:** `apps/api/` · **Status:** P1a-C integration in
progress

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
API / frontend and later X Layer publisher
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
  dexscreener.py live NVDAx quote

session.py       timestamp → market session
normalizer.py    shared token/underlying scale invariant
quant_runtime.py thin adapter around packaged QuantService
validation.py    backend Evidence State engine
panel.py         canonical 5-minute panel loader
scenario.py      explicit scripted scenario loader
data_source.py   panel/scenario source selection
replay.py        sequential quant + validation pipeline
live.py          cold-start live diagnostic
state_store.py   in-memory computed-result cache
publisher.py     X Layer publication boundary (not deployed yet)
routes/          HTTP endpoints
main.py          app wiring, CORS, and startup seed
```

## 6. API

| Method | Route | What |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/api/assets` | supported assets and model availability |
| GET | `/api/valuation/{asset}` | latest computed cached result |
| GET | `/api/valuation/{asset}/live` | cold-start live diagnostic |
| GET | `/api/replay/{asset}` | sequential scenario/panel results |
| GET | `/api/backtest/{asset}` | scenario-derived evidence counts |
| POST | `/api/publish/{asset}` | X Layer publication boundary |

A cold valuation cache returns `503 data_unavailable`. Publication returns `503`
until Registry configuration and contracts are available.

## 7. Current status and handoffs

- The backend imports the merged P1a-C package through its public service
  boundary.
- The scripted scenario and canonical 5-minute panel are replayed through the
  same inference path.
- The focused API endpoint and live diagnostic are explicit about unavailable
  data; no fabricated valuation is served.
- X Layer publication is intentionally pending the Registry, RPC, ABI, and
  publisher configuration.
- Broader historical metrics, scheduler behavior, and deployment wiring remain
  separate follow-up work; they do not alter the backend/quant boundary.

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
