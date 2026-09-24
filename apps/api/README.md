# Valtide API

Backend orchestration and validation layer. It normalizes market observations,
calls the packaged P1a-C quant runtime, evaluates the selected reference under
test, and serves the result through FastAPI. It also publishes the latest
warmed result to the deployed X Layer testnet control plane when explicitly
enabled. See
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
- Backtest: `http://localhost:8000/api/backtest/NVDAx?source=scenario`
- Runtime status: `http://localhost:8000/api/runtime/NVDAx`
- Onchain status: `http://localhost:8000/api/onchain/NVDAx`
- DemoVault enforcement simulation: `http://localhost:8000/api/onchain/NVDAx/enforcement`
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

Replay and backtest are explicit scenario or historical-panel paths. They do
not seed the live cache. A cold `/api/valuation/{asset}` cache returns `503
data_unavailable`; it never returns a fabricated valuation. The optional
single-process scheduler warms the live runtime on canonical UTC five-minute
boundaries and persists its carried state/latest result in SQLite. A restart
restores that state; a failed tick preserves the last good result and reports
the failure through `/api/runtime/{asset}`. `/api/valuation/{asset}/live` is a
cold-start, on-demand diagnostic and is not equivalent to the warmed runtime.
X Layer publication is disabled by default. The explicit
`POST /api/publish/{asset}` fallback is gated by `PUBLISH_ENABLED`; scheduler-
owned delivery is independently gated by `AUTO_PUBLISH_ENABLED`. Either path
requires `PUBLISHER_PRIVATE_KEY` and `XLAYER_RPC_URL` when enabled. The public
deployment manifest at `deployments/xlayer-testnet.json` supplies the testnet
addresses and IDs; environment address values are optional explicit overrides.
After a successful warmed scheduler tick is persisted, automatic delivery may
call the same publisher and records its status separately in SQLite. A
publication failure leaves the warmed valuation intact and does not stop the
scheduler. The publisher performs chain-ID, bytecode, linkage, policy,
publisher-authorization, monotonic-observation, transaction, and read-back
checks. API reads, replay, and cold diagnostics never publish.

## Layout

```text
valtide_api/
├── config.py        # settings from .env and CORS origins
├── models.py        # canonical snapshots, estimates, results, and enums
├── main.py          # FastAPI app, runtime restore/scheduler lifecycle, routing
├── session.py       # UTC timestamp to market session
├── normalizer.py    # shared token/underlying scale invariant
├── quant_runtime.py # thin adapter around the packaged QuantService
├── validation.py    # backend-owned Evidence State engine
├── panel.py         # canonical 5-minute panel loader
├── replay.py        # sequential quant and validation pipeline + state warm-up
├── clock.py         # canonical UTC five-minute boundaries
├── scheduler.py     # single-process warmed live scheduler
├── runtime_store.py # SQLite state/result and publication status persistence
├── scenario.py      # scripted scenario loader
├── state_store.py   # in-memory computed-result cache
├── publisher.py     # X Layer publication and control-plane verification
├── abis/            # bundled ABIs generated from the deployed contracts
├── routes/          # assets, valuation, replay, backtest, runtime, publish, onchain
└── adapters/        # token, underlying, and reference-under-test sources
```
