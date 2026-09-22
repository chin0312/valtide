# Valtide Backend — Team Guide

**Owner:** Xin Tong · **Code:** `apps/api/` · **Status:** working end-to-end (37 tests green)

The one-liner:

> The backend fetches prices, asks the model for an independent fair value,
> compares it to the price we're checking, and says **SUPPORTED / INCONCLUSIVE /
> CHALLENGED**. It holds no pricing math — that's the quant model.

---

## 1. Who talks to whom

```
  James (Quant)              Backend (apps/api)               Kai Ze (Contracts)
 ┌────────────┐   params   ┌───────────────────────┐  publish ┌──────────────────┐
 │ fits model │ ─────────▶ │ fetch → model → verify │ ───────▶ │ Registry / Guard │
 └────────────┘            └──────────┬────────────┘          └──────────────────┘
                                      │ JSON / HTTP
                                      ▼
                               Valerie (Frontend)
```

- James → backend: a small JSON of trained numbers (the *artifact*). Backend runs it, never trains.
- Backend → Valerie: stable JSON. She never sees OKX/Alpaca/model internals.
- Backend → Kai Ze: calls his contract to publish a result on-chain.

---

## 2. What happens in one check

```
 NVDAx token price ─┐
 NVDA stock price ──┼─▶ MarketSnapshot ─▶ quant model ─▶ fair value + interval
 reference price ───┘       (one clean       (NVDAx first,       │
                             object)          so it's            ▼
                                              independent)   validation ─▶ ValuationResult
                                                                          (state + reasons)
                                                                              │
                                                                    cache ─▶ API ─▶ frontend
```

**Why "NVDAx first":** the model forms its opinion from the token, *then* looks
at NVDA. So its estimate is independent of the price it's judging — otherwise the
check is circular.

---

## 3. Two ways to run it

| Mode | Source of data | Use | Endpoint |
|---|---|---|---|
| **Replay** | historical panel / scenario | the demo — shows the full story over time | `GET /api/replay/NVDAx` |
| **Live** | DexScreener + Alpaca + X-Perp (real, now) | "what does it look like right now" | `GET /api/valuation/NVDAx/live` |

Replay is the demo (a point-in-time weekend story). Live is a real-time bonus.
**Neither needs the 402-blocked OKX OnchainOS API.**

---

## 4. The decision (validation)

```
z = (ln(referencePrice) − fairValueLog) / uncertainty      # in log space

|z| < 1      → SUPPORTED       reference agrees with us
1 ≤ |z| < 2  → INCONCLUSIVE    not sure
|z| ≥ 2      → CHALLENGED      reference is off

then: if data is weak (stale >72h, thin volume, huge uncertainty)
      → force INCONCLUSIVE  (we abstain rather than guess)
```

Reason codes explain every verdict. All thresholds sit in one `Thresholds` object
— research defaults, to be recalibrated on James's real results.

---

## 5. Where each piece lives (`valtide_api/`)

```
config.py        settings from .env (keys, CORS)
models.py        MarketSnapshot, ChallengerEstimate, ValuationResult, enums

adapters/
  okx.py         NVDAx candles (OKX OnchainOS)      ← historical fetch
  equity.py      NVDA bars (Alpaca)
  reference.py   X-Perp index (reference under test)
  dexscreener.py live NVDAx price (no key, no OKX)

session.py       timestamp → market session
normalizer.py    the shared scale invariant (assert_scale)
quant_runtime.py loads artifact, runs ONE Kalman step   ← only math on the backend
validation.py    the SUPPORTED/INCONCLUSIVE/CHALLENGED engine (pure)

scenario.py      loads scripted scenarios/*.json
panel.py         loads James's p0_panel_5m.csv
data_source.py   picks panel if present, else scenario
replay.py        runs the pipeline over a sequence
live.py          assembles a live snapshot + runs one inference
state_store.py   in-memory cache of latest result
publisher.py     publish to X Layer (Phase 3)

routes/          one file per endpoint
main.py          app wiring, CORS, startup seed
```

Flow of dependencies (no cycles):

```
adapters ─┐
scenario ─┼─▶ replay/live ─▶ quant_runtime ─▶ validation ─▶ models
panel  ───┘        ▲                                          ▲
                   └────────── routes ──────────────────────┘
```

---

## 6. API

| Method | Route | What |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/api/assets` | supported assets |
| GET | `/api/valuation/{asset}` | latest cached result (read-only) |
| GET | `/api/valuation/{asset}/live` | on-demand result from live feeds |
| GET | `/api/replay/{asset}` | the full time-series (demo) |
| GET | `/api/backtest/{asset}` | evaluation metrics |
| POST | `/api/publish/{asset}` | publish on-chain (503 until contracts) |

Swagger: `http://localhost:8000/docs`.

---

## 7. Status

**Works now:** whole pipeline, all 7 endpoints, replay demo arc, **live mode on
real data**, CORS, 37 tests.

**Placeholders (drop-in later):**
- model = tuned mock until James's fitted artifact
- demo data = scenario until James's panel CSV lands in `data/sample/`
- publish = 503 until Kai Ze's contract

---

## 8. What each teammate owes

**James** — (1) fitted artifact JSON (`Q, R_nvda, R_nvdax` + state; schema in
`BACKEND_PLAN.md §4`); (2) his `p0_panel_5m.csv` → drop in `data/sample/`,
auto-used; (3) one sample step to verify the Python port.

**Kai Ze** — X Layer RPC URL, deployed Registry address, contract ABI (Phase 3).

**Valerie** — nothing blocking; build against `/api/valuation` + `/api/replay`
now. Send your dev URL for CORS.

---

## 9. Run it

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,data]"
pytest                                    # tests
uvicorn valtide_api.main:app --reload     # serve; open http://localhost:8000/docs
```

Scripts (run from the repo root):

```bash
python scripts/fetch_data.py   # pull a real NVDAx + NVDA + X-Perp sample into data/sample/
python scripts/demo_value.py   # narrated value demo: stale oracle -> CHALLENGED -> proven right
```

---

## 10. Principle

> Thin orchestration. Math stays in the quant runtime. The challenger stays
> independent of the reference it judges. The demo runs on point-in-time replay.
> Failures degrade to an honest "unavailable", never a fake number.
