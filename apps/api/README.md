# Valtide API

Backend orchestration and validation layer. It normalizes market observations,
calls the packaged P1a-C quant runtime, evaluates the selected reference under
test, and serves the result through FastAPI. See
[`docs/BACKEND_PLAN.md`](../../docs/BACKEND_PLAN.md) for the working plan.

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

- Health: `http://localhost:8000/health`
- Valuation: `http://localhost:8000/api/valuation/NVDAx`
- Replay: `http://localhost:8000/api/replay/NVDAx`
- Assets: `http://localhost:8000/api/assets`
- Swagger UI: `http://localhost:8000/docs`

## Test

```bash
pytest
```

## Current boundary

```text
MarketSnapshot
      ↓
packaged QuantService / P1a-C runtime
      ↓
QuantEstimate
      ↓
backend validation
      ↓
SUPPORTED / INCONCLUSIVE / CHALLENGED
```

The quant package owns challenger fair value, calibrated uncertainty, and
carried state. The backend selects the reference under test and owns Evidence
State and reason codes. The backend does not duplicate model equations or
silently substitute a different reference.

Replay uses the scripted scenario when no sample panel is available. A cold
`/api/valuation/{asset}` cache returns `503 data_unavailable`; it never returns
a fabricated valuation. `/api/valuation/{asset}/live` is a cold-start,
on-demand diagnostic. X Layer publication remains a clear `503` placeholder
until the Registry configuration and contracts are available.

## Layout

```text
valtide_api/
├── config.py        # settings from .env and CORS origins
├── models.py        # canonical snapshots, estimates, results, and enums
├── main.py          # FastAPI app, lifespan seed, and router wiring
├── session.py       # UTC timestamp to market session
├── normalizer.py    # shared token/underlying scale invariant
├── quant_runtime.py # thin adapter around the packaged QuantService
├── validation.py    # backend-owned Evidence State engine
├── panel.py         # canonical 5-minute panel loader
├── replay.py        # sequential quant and validation pipeline
├── scenario.py      # scripted scenario loader
├── state_store.py   # in-memory computed-result cache
├── publisher.py     # X Layer publication boundary
├── routes/          # assets, valuation, replay, backtest, publish
└── adapters/        # token, underlying, and reference-under-test sources
```
