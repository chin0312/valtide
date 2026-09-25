# Valtide — Backend Build Plan

**Owner:** Xin Tong (Backend / Data)
**Component:** `apps/api/`
**Status:** Working build plan (revised after senior review)
**Last updated:** 2026-09-22

---

## 1. What the backend is responsible for

The backend is an **orchestration and API layer**. It does not contain any
pricing mathematics. Its single job is to connect four things:

```
market data sources  →  quant model  →  frontend
                                      →  X Layer publisher
```

Concretely, the backend must:

1. fetch market data (NVDAx token price, NVDA underlying price, reference under test),
2. normalize it into one canonical `MarketSnapshot`,
3. feed that snapshot to the quant model and get back a fair value + uncertainty,
4. compare the fair value against the **reference under test** to produce an
   Evidence State (the validation step),
5. persist the warmed live state/latest result and serve it over a stable HTTP API,
6. optionally publish an approved result to X Layer.

**Hard rule:** the statistical model (Kalman filter equations, interval math)
lives in the quant layer. The backend never re-implements those equations. It
loads the quant team's fitted parameters and calls a single `estimate()`
interface. This prevents "training-serving skew" — the live path and James's
research path must behave identically, which also means **using the same data
sources James trained on** (see §11).

---

## 2. How this maps to what James built

James's R pipeline (`valtide-r-pipeline/`) does **offline training**:

- downloads historical NVDAx (OKX) + NVDA (Alpaca SIP) 5-minute candles,
- fits a Kalman filter by maximum likelihood,
- outputs fitted parameters `Q`, `R_nvda`, `R_nvdax`.

His model treats NVDA and NVDAx as two noisy observations of one hidden "true
fair value" `m_t`, **in log-price space**:

```
m_t   = m_{t-1} + noise                  (state evolves slowly)
ln(NVDA)  = m_t + observation noise       (visible only when market open)
ln(NVDAx) = m_t + observation noise       (visible ~24/7 on-chain, verify §12/M)
```

When NVDA is unavailable (weekend / overnight), the filter runs on NVDAx alone
and its uncertainty `P_t` grows. That growing uncertainty is exactly what our
validation logic uses to decide whether a deviation is meaningful.

**The division of labour:**

| Concern | Owner | Where |
|---|---|---|
| Fit the model parameters | James | R pipeline (offline) |
| Export fitted params as an artifact | James | `p1a_runtime.json` |
| Run the filter forward, one step per observation | Quant package | `QuantService` |
| Fetch + normalize data | Backend | `apps/api/adapters`, `normalizer` |
| Validation / Evidence State | Backend | `apps/api/validation.py` |
| Serve the API | Backend | `apps/api/main.py` |

The packaged Python quant service owns artifact loading and one-step execution.
The backend keeps only a thin adapter in `quant_runtime.py`, so live inference
and replay consume the same public `QuantService` interface.

---

## 3. The reference under test — define this FIRST

This is the most important design decision and the one the original plan skipped.

**The challenger and the reference under test must be different things, and the
challenger must not have already consumed the reference** — otherwise validation
is circular. James's P0 fair value is built from *both* NVDA and NVDAx, so we
cannot naively "validate NVDA against a model that already ate NVDA."

The methodology resolves this with a strict **update order** (ARCHITECTURE §7,
backend summary §4):

```
1. predict prior state
2. assimilate NVDAx only              →  this is the independent challenger
3. compute Valtide fair value + interval from the NVDAx-only posterior
4. THEN assimilate NVDA (if present)  →  re-anchors state for the next step
```

So the **challenger estimate used for validation is the NVDAx-only posterior**,
before NVDA is folded in.

### What plays the role of the reference under test (`Pt`)?

| Market state | Reference under test `Pt` | Notes |
|---|---|---|
| **REGULAR / open** | current NVDA (Alpaca) | validated against the NVDAx-only challenger |
| **Weekend / CLOSED** | reconstructed reference (see below) | no live NVDA exists |

**DECISION (2026-09-22):** the reference under test is the **OKX X-Perp NVDA
index price**, fetched by the backend itself. It is a real, production-style
bounded reference OKX publishes ~24/7, which gives the strongest demo story
("we independently validated a live production feed"). Fallbacks below remain if
access proves unworkable.

Historical replay may explicitly use a stale-NVDA or scenario-defined reference
when that is the reference being evaluated. In live mode, an unavailable
OKX X-Perp observation remains unavailable; it is never silently replaced by
stale NVDA.

### Accessing the OKX X-Perp index

This is a **different API from OnchainOS**. The NVDAx token price comes from OKX
OnchainOS (`web3.okx.com`, signed). The X-Perp index comes from the OKX
**exchange v5 market-data API** (`www.okx.com/api/v5/...`), whose public
market-data endpoints generally require **no authentication**.

`adapters/reference.py` targets these v5 endpoints:

```
GET /api/v5/market/index-tickers?instId=<INDEX_ID>     # index price
GET /api/v5/public/mark-price?instType=SWAP&instId=<SWAP_ID>   # mark price
```

**CONFIRMED (2026-09-22):** `GET /api/v5/market/index-tickers?instId=NVDA-USD`
is public (no auth) and returns the index price in `idxPx` with a millisecond
`ts`. Verified live response:

```json
{"code":"0","data":[{"instId":"NVDA-USD","idxPx":"228.51","ts":"1790089804702"}]}
```

So `okx_xperp_index_id = "NVDA-USD"` and `adapters/reference.py` are correct as
written; no OKX key is needed for the reference under test.

---

## 4. The packaged model artifact contract

The merged quant package owns the runtime artifact contract. Its packaged files
are provenance-tracked and loaded by `QuantService.from_default_artifacts()`:

```json
{
  "schema_version": 2,
  "model_family": "P1a",
  "deployment_model_id": "P1a-C",
  "model_version": "0.2.0",
  "asset": "NVDAx",
  "interval_level": 0.9,
  "q_by_session": {"regular": "...", "closed": "..."},
  "r_nvda": "...",
  "r_nvdax": "...",
  "calibration_artifact": "p1a_c_calibrator.json"
}
```

- `q_by_session`, `r_nvda`, and `r_nvdax` are the fitted runtime variances.
- `p1a_c_calibrator.json` contains the selected session-aware interval
  calibration, including its global fallback and known closed/overnight limit.
- `QuantEstimate` carries model identity and calibration metadata into the
  backend; the backend does not re-read artifact fields or reproduce equations.

The backend now loads the packaged P1a-C runtime artifacts from the merged quant
package. Their provenance and byte-level integrity are owned by that package.

---

## 5. Data shapes (the canonical objects)

Everything flows through Pydantic models. Define these first; they are the
contract between all backend modules.

### 5.1 MarketSnapshot — input to the model

```python
class MarketSnapshot(BaseModel):
    asset: str                          # "NVDAx"
    observation_ts: datetime            # UTC, the 5-min timestamp being evaluated

    token_price: float | None            # exact confirmed NVDAx close (OKX), if observed
    token_volume: float | None           # native OKX candle volume
    token_volume_usd: float | None       # OKX candle USD volume, if supplied
    token_source: str | None
    token_observed_at: datetime | None
    token_liquidity_usd: float | None    # null unless the source defines it

    underlying_reference: float | None  # current NVDA if market open, else None
    underlying_reference_ts: datetime | None

    last_trusted_reference: float       # latest available trusted underlying bar (R0)
    last_trusted_reference_ts: datetime
    reference_age_seconds: int          # observation_ts - last_trusted_reference_ts

    reference_under_test: float | None   # Pt — see §3, sourced explicitly
    reference_under_test_source: str    # e.g. "nvda_live", "okx_xperp_index"
    reference_under_test_ts: datetime | None
    reference_under_test_age_seconds: int | None

    market_state: MarketState           # enum, see session.py

    corporate_action_multiplier: float = 1.0   # P0: 1.0 + scale assertion (§M3)
    external_reference: float | None = None     # optional Pyth, comparison only

    source_provenance: dict[str, str]   # {source_name: source_timestamp}
```

### 5.2 ChallengerEstimate — output of the quant runtime

Note: carries the **log-space state directly**, not just price bounds, so
validation never has to reverse-engineer σ from asymmetric price bounds (§7).

```python
@dataclass
class ChallengerEstimate:
    fair_value: float          # exp(state_m)
    lower_bound: float         # price-space interval (may be asymmetric)
    upper_bound: float
    state_m: float             # posterior mean in LOG space (NVDAx-only)
    state_sd_log: float        # latent challenger-state uncertainty in LOG space
    reference_predictive_sd_log: float  # reference-equivalent predictive uncertainty
    coverage_target: float
    state_P_after_nvda: float  # posterior variance AFTER folding NVDA, for next step
    state_m_after_nvda: float
    interval_calibration_type: str
    interval_calibration_source: str
    model_id: str
    model_version: str
    interval_semantics: str
```

### 5.3 ValuationResult — output served to frontend / X Layer

```python
class ValuationResult(BaseModel):
    asset: str
    timestamp: datetime
    market_state: str

    last_trusted_reference: float
    token_price: float | None
    external_constructed_reference: float | None

    valtide_fair_value: float
    fair_value_lower: float
    fair_value_upper: float
    interval_coverage_target: float

    observed_token_move_pct: float | None
    model_implied_move_pct: float
    residual_premium_discount_pct: float | None

    reference_under_test: float | None
    reference_under_test_source: str
    reference_under_test_ts: datetime | None
    reference_under_test_age_seconds: int | None
    reference_deviation_pct: float | None
    standardized_deviation: float | None    # log-space z-score (§7)

    evidence_state: EvidenceState           # SUPPORTED / INCONCLUSIVE / CHALLENGED
    reason_codes: list[str]

    confidence: int | None = None           # intentionally null in P0 (§M2)

    model_id: str
    model_version: str
    interval_semantics: str
    reference_age_seconds: int
```

**Vocabulary note:** `EvidenceState` is the only backend validation-state
vocabulary: `SUPPORTED`, `INCONCLUSIVE`, and `CHALLENGED`. The backend produces
that evidence state; a consuming protocol owns any policy action.

---

## 6. Project structure

```
apps/api/
├── pyproject.toml            # dependencies, tooling config
├── README.md                 # how to run locally
├── valtide_api/
│   ├── __init__.py
│   ├── config.py             # settings from .env (pydantic-settings) + CORS origins
│   ├── models.py             # MarketSnapshot, ChallengerEstimate, ValuationResult, enums
│   ├── main.py               # FastAPI app, CORS middleware, route wiring
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── assets.py         # GET /api/assets
│   │   ├── valuation.py      # GET /api/valuation/{asset}
│   │   ├── history.py        # GET /api/history/{asset}
│   │   ├── replay.py         # GET /api/replay/{asset}
│   │   ├── backtest.py       # GET /api/backtest/{asset}
│   │   ├── runtime.py        # GET /api/runtime/{asset}
│   │   └── publish.py        # POST /api/publish/{asset}
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── okx.py            # OKX OnchainOS auth + NVDAx candles
│   │   ├── equity.py         # NVDA underlying price (Alpaca — same as James)
│   │   └── reference.py      # reference-under-test source (§3)
│   │
│   ├── session.py            # market-session classifier
│   ├── normalizer.py         # raw adapter output -> MarketSnapshot
│   ├── quant_runtime.py      # adapts the public QuantService interface
│   ├── validation.py         # snapshot + estimate -> ValuationResult (pure)
│   ├── state_store.py        # in-memory compatibility cache
│   ├── runtime_store.py      # SQLite state/result persistence and tick status
│   ├── clock.py              # canonical UTC five-minute boundaries
│   ├── replay.py             # shared inference + hidden elapsed-time warm-up
│   ├── scheduler.py          # optional single-process warmed live loop
│   └── publisher.py          # X Layer publish (web3)
│
├── scenarios/
│   └── weekend_divergence.json  # scripted demo scenario (§8)
│
└── tests/
    ├── test_validation.py    # pure-function tests for Evidence State logic
    ├── test_session.py       # session boundary tests
    ├── test_normalizer.py
    ├── test_quant_runtime.py # one step must match James's R output
    └── fixtures/
        ├── sample_snapshot.json
        └── okx_candles.json
```

### Why this layout
- **`valtide_api/` package (not loose files):** clean imports, clean testing.
- **`routes/` split per capability:** each file small, maps to one capability
  group; `main.py` just includes routers and configures CORS.
- **`adapters/` isolated:** vendor schemas never leak past this folder. Swapping
  a provider touches only these files. `reference.py` is separate because the
  reference under test is a distinct concern from raw market data (§3).
- **`quant_runtime.py` is only an adapter** on the backend. Quantitative model
  math and artifact loading live in the packaged quant service; the adapter
  only translates snapshots and results.
- **`replay.py` is a first-class module, not an afterthought** (§8): the demo,
  historical panel, and warmed runtime share the same inference path.
- **`runtime_store.py` is the durable live boundary:** SQLite stores one asset's
  carried Kalman state, latest public result, elapsed-gap diagnostics, last tick
  status, and successful warmed valuation history. `state_store.py` remains only
  an in-memory compatibility cache.
- **`tests/` with pure functions first:** validation/session are deterministic
  and must be unit-tested; adapters use recorded fixtures.

---

## 7. Validation logic (the Evidence State rules)

Deterministic threshold logic, not ML. Every formula traces to METHODOLOGY.

**Step 1 — Derived quantities** (METHODOLOGY §10). All in price space:
```
R0 = last_trusted_reference
Tt = token_price
Ft = valtide_fair_value          # = exp(state_m), NVDAx-only challenger (§3)

observed_token_move = Tt / R0 - 1       # null when Tt is unavailable
model_implied_move  = Ft / R0 - 1
residual            = Tt / Ft - 1       # null when Tt is unavailable
```

**Step 2 — Reference deviation + standardized deviation** (METHODOLOGY §11).
The standardized reference deviation is computed **in log space** using the
reference-equivalent predictive uncertainty reported by the quant runtime, NOT
by reverse-engineering σ from asymmetric price bounds:
```
Pt = reference_under_test
reference_deviation = Pt / Ft - 1       # null when Pt is unavailable

z_ref = (ln(Pt) - challenger_m_log) / reference_predictive_sd_log
inside_interval = lower_bound <= Pt <= upper_bound
```
`state_sd_log` is latent challenger-state uncertainty.
`reference_predictive_sd_log` represents the uncertainty scale for comparing a
candidate underlying/reference observation against the challenger. The
lower/upper bounds are separate empirically calibrated reference-equivalent
interval bounds; the calibration is not assumed to be Gaussian.

Why log space: the filter lives in log space and the price interval is
asymmetric (`exp` of a symmetric log interval). Computing z from `(upper-lower)/2`
would be biased for P1a and meaningless for P1a-C's calibrated intervals.

If `Pt` is unavailable, the backend does not calculate a deviation or
standardized score and returns `INCONCLUSIVE + COMPARATOR_UNAVAILABLE`. If
`Tt` is unavailable, it returns `INCONCLUSIVE + TOKEN_DATA_UNAVAILABLE`; the
quant state can still advance.

**Step 3 — Base Evidence State** (backend summary §8 rule, PRD vocabulary):
```
|z| < z_support      → SUPPORTED
z_support ≤ |z| < z_challenge → INCONCLUSIVE
|z| ≥ z_challenge     → CHALLENGED
```

**Step 4 — Data-quality overrides** (METHODOLOGY §13 abstention). Any of these
forces `INCONCLUSIVE` regardless of z — we do not trust the inputs enough to
challenge:
```
reference_age_seconds > max_reference_age_s     → INCONCLUSIVE + UNDERLYING_REFERENCE_STALE
token_volume < min_token_volume                 → INCONCLUSIVE + TOKEN_MARKET_QUALITY_LOW
reference_predictive_sd_log > max_state_sd_log  → INCONCLUSIVE + MODEL_UNCERTAINTY_HIGH
reference_under_test unavailable                → INCONCLUSIVE + COMPARATOR_UNAVAILABLE
token_price unavailable                         → INCONCLUSIVE + TOKEN_DATA_UNAVAILABLE
interval invalid / missing                      → error, not a fabricated result
```
`max_state_sd_log` is the current configuration-field name, but this quality
gate is applied to `reference_predictive_sd_log`. The latter is the
reference-equivalent predictive uncertainty used for standardized reference
validation; it is distinct from latent `state_sd_log`.

**Step 5 — Reason codes** (auditable; canonical names from METHODOLOGY §13 only):
```
not inside_interval          → REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL
|Tt - Ft|/Ft < agree_tol     → TOKEN_AND_CHALLENGER_AGREE (only when Tt exists)
external ref present & tight  → EXTERNAL_REFERENCES_AGREE
external refs dispersed       → EXTERNAL_REFERENCES_DISAGREE
global fallback calibration   → CALIBRATION_GLOBAL_FALLBACK (diagnostic only)
```
(The backend does not emit the old ad-hoc reference or token state names.)

**Thresholds are configuration, never bare literals:**
```python
@dataclass(frozen=True)
class Thresholds:
    z_support: float = 1.0
    z_challenge: float = 2.0
    # Covers a normal weekend gap; research default subject to recalibration.
    max_reference_age_s: int = 72 * 3600
    min_token_volume: float = 0.0      # set once we see real OKX volume
    max_state_sd_log: float = 0.05     # ~5% 1σ; tune on James's results
    agree_tolerance: float = 0.01
```
The 72-hour reference-age default is intended to cover a normal weekend gap.
These are **research defaults**, documented as such, to be re-calibrated on
James's historical results before any accuracy claim.

---

## 8. Replay and warmed live runtime

The scripted **weekend-divergence** scenario remains the deterministic demo
path, while the P0.5 live path is a deliberately small single-process runtime.
Both use the same `run_inference` function. Replay and historical backtest are
explicit data-source paths; they never seed or masquerade as warmed live state.

### Core inference function (shared by replay, scheduler, and one-shot)
```python
def run_inference(snapshot: MarketSnapshot, prior: KalmanState | None,
                  thresholds: Thresholds) -> tuple[ValuationResult, KalmanState]:
    est = quant_runtime.estimate(
        snapshot,
        prior.m if prior else None,
        prior.P if prior else None,
        prior.last_ts if prior else None,
    )   # NVDAx-first (§3)
    result = validation.validate(snapshot, est, thresholds)
    new_state = KalmanState(m=est.state_m_after_nvda,
                            P=est.state_P_after_nvda,
                            last_ts=snapshot.observation_ts)
    return result, new_state
```

### `replay.py`
Feeds historical candles through `run_inference` step by step, warming the
Kalman state forward (addresses the stale-state gap, §10.S2). Powers the demo,
`/api/replay`, and historical backtest. Point-in-time correct: only data
available at or before the requested timestamp is used; a later benchmark is
revealed only on explicit request.

### `scenarios/weekend_divergence.json`
A scripted sequence of snapshots that produces a clean SUPPORTED → CHALLENGED
transition for the demo, so the presentation does not depend on live market luck.

### `scheduler.py` (P0.5)
An optional dependency-free asyncio loop computes the current canonical UTC
five-minute boundary, runs one live tick in a worker thread, and sleeps until
the next boundary. It is the **only** thing that advances warmed live state;
API reads never do. A tick restores the prior SQLite state, inserts hidden
no-measurement transitions for elapsed gaps, processes the real observation,
and atomically persists the new state/result. When `AUTO_PUBLISH_ENABLED=true`,
the scheduler enqueues that newly persisted successful result for one
serialized in-process publication worker. The worker coalesces pending work to
the newest observation, so publication delivery is downstream of valuation and
does not delay the next scheduler cadence. Hidden warm-up rows are never
returned as public observations.

The live scheduler is disabled by default. A one-shot `/api/valuation/{asset}/live`
call is a cold-start diagnostic and does not mutate the warmed cache.

---

## 9. API surface

| Method | Route | Purpose | Reads state? |
|---|---|---|---|
| GET | `/api/assets` | supported assets + data availability | cache |
| GET | `/api/valuation/{asset}` | latest cached ValuationResult | cache only |
| GET | `/api/valuation/{asset}/live` | cold-start live diagnostic | no |
| GET | `/api/history/{asset}?limit=` | warmed operational history | SQLite read only |
| GET | `/api/replay/{asset}?timestamp=` | point-in-time historical result | replay/store |
| GET | `/api/backtest/{asset}?source=` | scenario counts or historical metrics | replay |
| GET | `/api/runtime/{asset}` | warmed state/scheduler/tick and publication status | SQLite |
| POST | `/api/publish/{asset}` | publish attestation to X Layer | writes chain |

- `/api/valuation`, `/api/replay`, and `/api/backtest` **never** advance the
  warmed live Kalman filter.
- `/api/replay` returns only data available at the requested timestamp
  (no look-ahead). The later benchmark is revealed only on explicit request.
- `/api/valuation/{asset}` serves only the latest durable warmed result and
  returns `503 data_unavailable` when none exists. Scenario files are never a
  hidden fallback for this endpoint.
- `/api/runtime/{asset}` exposes whether state/result exist, the last canonical
  state/result timestamps, last tick status/error, hidden gap-step count, and
  optional scheduler-publication status. Publication status never includes
  signer or RPC secrets.
- `/api/history/{asset}` returns only successful warmed scheduler observations in
  chronological order. It is operational history, not empirical accuracy,
  scenario replay, or a backtest.
- `/api/publish` requires server-side authorization and is the only explicit
  HTTP write path; scheduler-owned automatic delivery uses the same publisher
  through its serialized worker when `AUTO_PUBLISH_ENABLED=true`.
- **CORS:** `main.py` must add `CORSMiddleware` with Valerie's Next.js origin
  (`http://localhost:3000` in dev) or the browser cannot call the API at all.
  Allowed origins come from `config.py`, not hardcoded.

---

## 10. State, storage & failure handling

### State and persistence (single-process MVP)
```
per asset:
  latest ValuationResult
  Kalman state: m_t, P_t, last_processed_timestamp
  last tick status/error and hidden gap-step count
```
- **Warmed live runtime:** SQLite in `runtime_store.py` is the source of truth
  for the carried state and latest result. The schema is intentionally one row
  per supported asset; it is not a general event store.
- **Compatibility:** `state_store.py` is updated after a successful tick for
  non-HTTP callers, but API reads use SQLite and startup never seeds from a
  scenario or sample panel.
- Historical datasets stay as CSV/Parquet-style local artifacts shared with
  research and are selected explicitly for replay/backtest.
- `last_processed_timestamp` prevents a duplicate canonical tick from fetching
  or reprocessing another market observation.

### S2 — State warm-up (explicit)
The packaged runtime initializes from its trusted-reference anchor when no
carried state is available. Replay and the first warmed live tick then advance
state one canonical 5-minute step at a time. If the first real observation is
many intervals after the trusted anchor, the backend performs hidden
no-measurement process transitions for each missing interval. If a persisted
state is behind a later tick, the same propagation occurs from the persisted
timestamp. A cold live call is explicitly diagnostic; it is not presented as
an equivalent to a warmed sequential state.

### Failure handling (explicit, never silent)
| Situation | Behaviour |
|---|---|
| NVDAx data missing | return `data_unavailable`; never substitute another venue |
| NVDA missing (market closed) | continue on NVDAx alone; `underlying_reference = null`; uncertainty grows |
| Underlying reference stale | continue; surface `reference_age_seconds` + stale reason code |
| Reference under test missing | Evidence State = INCONCLUSIVE + COMPARATOR_UNAVAILABLE |
| External comparator (Pyth) missing | continue; `external_reference = null` |
| Live source/tick failure | preserve the last durable state/result; expose failure via `/api/runtime/{asset}` |
| Non-canonical or gapped replay | fail explicitly; never round, forward-fill, or fabricate timestamps |
| Model returns invalid interval | return error; **never fabricate bounds** |
| X Layer publish fails | offchain result stays valid; publication error/status is persisted separately and the scheduler continues |

Theme: degrade explicitly and keep provenance. A wrong-but-confident number is
worse than an honest "unavailable".

---

## 11. Data sources — match James to avoid skew

| Quantity | Source | Rationale |
|---|---|---|
| NVDAx token price/candles | OKX OnchainOS exact confirmed 5-minute candle | same as James's training |
| NVDA underlying | **Alpaca (SIP; iex fallback)** | **same as James** — using yfinance here would introduce a different, delayed feed and re-create training-serving skew |
| Reference under test `Pt` | per §3 (OKX X-Perp preferred) | explicit, sourced, independent of challenger |
| Pyth (optional) | Pyth | comparison only, never a challenger feature |

yfinance is acceptable only as an offline last-resort fallback, flagged in
provenance, never as the primary live NVDA source.

For historical replay, `scripts/build_historical_panel.py` joins canonical UTC
five-minute rows from OKX OnchainOS NVDAx candles, Alpaca NVDA bars, and the
public OKX X-Perp index-history endpoint. It preserves rows after the trusted
underlying anchor even when token or reference observations are missing; it
never forward-fills either observation and preserves native/USD token volume
separately. The panel loader rejects non-canonical
or gapped timestamps rather than hiding the data-quality problem.

---

## 12. Tooling & conventions

- **Python 3.11+**, FastAPI, Pydantic v2, `pydantic-settings`.
- **Deps:** `pyproject.toml` (uv or poetry), pinned. `httpx` (OKX), `alpaca-py`
  (NVDA), and `web3` for the X Layer publisher. The P0.5 scheduler
  uses the Python standard library and does not require APScheduler.
- **Lint/format:** `ruff` + `ruff format`. **Types:** annotate; `mypy` on
  `valtide_api/` if time allows.
- **Tests:** `pytest`. Pure logic (`validation`, `session`) fully unit-tested;
  adapters use recorded fixtures (no live calls in CI); `quant_runtime` has a
  golden test asserting one step matches James's R output.
- **Secrets:** only from `.env` via `config.py`. `.env` gitignored;
  `.env.example` documents keys.
- **All timestamps UTC**, timezone-aware.
- **Logging:** structured logs per inference stage (fetch / normalize / estimate
  / validate / cache) so a failed step is diagnosable.

---

## 13. Build order

**Phase 1 — unblock the frontend (today, Sep 22)**
1. `pyproject.toml` + package skeleton, runnable `uvicorn`, CORS configured.
2. `models.py` — `MarketSnapshot`, `ChallengerEstimate`, `ValuationResult`, enums.
3. `routes/valuation.py` serving only a computed replay/scheduler result, or an
   explicit `503 data_unavailable` when no result exists.
4. `adapters/okx.py` — port auth, fetch a real NVDAx candle, verify creds.

**Phase 2 — real data & model (Sep 23)**
5. `adapters/equity.py` (Alpaca) + `adapters/reference.py` (§3).
6. `session.py` + tests.
7. `normalizer.py` + tests (assert NVDAx/NVDA scale ≈ 1; multiplier = 1.0).
8. `quant_runtime.py` — adapt the public P1a-C `QuantService` interface and
   preserve its NVDAx-first update order; detailed runtime integrity tests stay
   in the quant package.
9. `validation.py` + tests (the core — test hardest; log-space z-score).
10. `state_store.py` (in-memory) + `replay.py`.
11. `scenarios/weekend_divergence.json`; replay remains explicit and does not
   seed the warmed `/api/valuation` cache.

**Phase 3 — integration (Sep 23 night → 24)**
12. Keep the packaged P1a-C artifacts and verify backend integration against the
   quant package's public result contract.
13. `routes/replay.py` + `routes/backtest.py` from shared historical data;
    `scripts/build_historical_panel.py` joins point-in-time OKX/Alpaca sources.
14. `publisher.py` + `routes/publish.py` use the public testnet deployment
    manifest, bundled contract ABIs, and explicit runtime signer settings.
15. Connect Valerie's frontend to the live API.

**Phase 4 — P0.5 runtime hardening**
16. Run the optional single-process warmed scheduler on canonical UTC five-minute
    boundaries, persist state/result in SQLite, and expose `/api/runtime` status.
17. Re-calibrate thresholds on James's results; run deterministic replay/demo
    checks; keep live/historical credentialed smoke tests separate from CI.

---

## 14. Interfaces to lock down with the team today

1. **With James:** (a) the model artifact JSON schema (§4); (b) that the runtime
   returns `state_m` + `state_sd_log` and applies the **NVDAx-first** update
   order (§3); (c) `MarketSnapshot` field names (§5.1); (d) a golden one-step
   output to test the Python port against.
2. **With James + Kai Ze:** what is the **reference under test** `Pt` for the
   demo (§3), and is the OKX X-Perp index accessible with our credentials.
3. **With Valerie:** the `ValuationResult` shape (§5.3) + explicit unavailable
   behavior, and her dev origin for CORS.
4. **Deployment handoff:** the public X Layer testnet manifest supplies the
   deployed addresses and IDs. The runtime signer and RPC remain local-only
   settings; the backend does not use deployment/admin keys.

---

## 15. Guiding principle

> Keep the backend a thin orchestration layer. Statistical logic stays in the
> quant runtime; the backend only runs pre-fitted parameters, from the same data
> sources James trained on. Keep the challenger independent of the reference it
> validates. Drive the demo through point-in-time replay. Degrade explicitly and
> preserve provenance on every observation.
