# Valtide API

Backend orchestration & API layer. Fetches market data, runs the quant model's
pre-fitted parameters, validates against the reference under test, and serves the
result. See [`docs/BACKEND_PLAN.md`](../../docs/BACKEND_PLAN.md) for the full plan.

## Setup

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ../../valtide-quant-service-p1ac -e ".[dev]"
```

Credentials are read from the repo-root `.env` (see `.env.example`).

## Run

```bash
uvicorn valtide_api.main:app --reload --port 8000
```

- Health:      http://localhost:8000/health
- Valuation:   http://localhost:8000/api/valuation/NVDAx
- Assets:      http://localhost:8000/api/assets
- Swagger UI:  http://localhost:8000/docs

## Test

```bash
pytest
```

## Status

**Phases 1–2 complete** (39 tests passing). Full pipeline works end-to-end on
scripted scenario data: adapters → normalize → quant runtime → validation → API.
The `weekend_divergence` scenario produces a SUPPORTED → INCONCLUSIVE →
CHALLENGED arc, and `/api/valuation/NVDAx` serves it.

Running on production quant artifacts from PR #3:
- **model** — trained P1a parameters with P1a-C session calibration
- **data** — scripted scenario until real data flows (see OKX blocker in
  `docs/BACKEND_ARCHITECTURE.md §10`)
- **X Layer publish** — `POST /api/publish` returns 503 until Kai Ze's contracts

See [`docs/BACKEND_ARCHITECTURE.md`](../../docs/BACKEND_ARCHITECTURE.md) for the
team overview and what's needed from whom.

## Layout

```
valtide_api/
├── config.py        # settings from .env (+ CORS origins)
├── models.py        # MarketSnapshot, ChallengerEstimate, ValuationResult, enums
├── main.py          # FastAPI app, CORS, lifespan seed, router wiring
├── session.py       # UTC -> market session
├── normalizer.py    # raw adapters -> MarketSnapshot
├── quant_runtime.py # loads artifact, runs one Kalman step
├── validation.py    # Evidence State engine (pure)
├── replay.py        # pipeline over a sequence (demo driver)
├── scenario.py      # loads scenarios/*.json
├── state_store.py   # in-memory cache
├── publisher.py     # X Layer publish (Phase 3)
├── mock_data.py     # frontend fallback result
├── routes/          # assets, valuation, replay, backtest, publish
└── adapters/        # okx (token), equity (NVDA), reference (X-Perp)
```
