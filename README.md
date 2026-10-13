# Valtide

<p align="center">
  <img src="docs/assets/valtide-logo.svg" alt="Valtide" width="96" />
</p>

**A validation layer for tokenized equity collateral.**

Valtide helps DeFi curators and risk teams assess whether an observed xStock
price has enough supporting evidence for a collateral-risk decision. It does
not claim to discover an exact “true price.”

[Live App](https://valtide-liard.vercel.app) · [Demo Video](https://youtu.be/HTbjq2vxzHY) · [Backend API](https://valtide-api-production.up.railway.app) · [OpenAPI / API Docs](https://valtide-api-production.up.railway.app/docs) · Originally built for OKX Dev Day 2026 — Build a Market

## The Problem

Tokenized equities can trade around the clock, while their underlying equity
markets do not provide continuous, equivalent price discovery. This is not
inherently a trading problem. It matters when a DeFi protocol relies on an
observed tokenized-equity price for collateral decisions, including while the
underlying market is closed or its latest reference is stale.

Valtide adds a validation and evidence layer to that decision. It helps
reviewers understand what is observed, what the model estimates, whether
required sources are available, and when the result should remain
`INCONCLUSIVE`.

## Current Product Scope

| Asset | Model | Operational | Historical replay | X Layer binding |
|---|---|---:|---:|---:|
| NVDAx | P1a-C v0.2.0 | Yes | Yes | Yes |
| SPYx | P1a-C v0.3.0 | Yes | Yes | Yes |
| AAPLx | P1a-C v0.3.0 | Yes | Yes | Yes |
| QQQx | Research-only | No public API/runtime | Offline research | No |

TSLAx remains research-only. The three operational assets use asset-specific
runtime and historical data, and their own bindings to a shared X Layer
`ValidationRegistry` and `RiskGuard`.

## How It Works

```mermaid
flowchart TB
    X[Observed xStock<br/>validation target + model input]
    U[Prior Underlying Anchor<br/>model context]
    M[P1a-C runtime]
    F[Valtide Fair Value<br/>+ calibrated Valuation Range]
    P[Exact-time X-Perp<br/>separately sourced]
    V[Backend validation]
    E{Evidence State}
    R[Shared ValidationRegistry]
    G[Shared RiskGuard<br/>curator-owned policy]
    C[Asset-specific consumer]
    N[Current underlying<br/>assimilated for next state]

    U --> M
    X --> M
    M --> F
    X --> V
    F --> V
    P --> V
    V --> E --> R --> G --> C
    N -. next state .-> M
```

P1a-C assimilates the current xStock observation, so xStock-versus-model
disagreement is model-based challenger evidence—not two independent market
observations. X-Perp is separately sourced market evidence. The Underlying
Anchor provides model context; the same-time underlying is not an Evidence
State voter. It may update the model state for the next observation and serve
as an offline/ex-post benchmark.

Evidence State is one of:

- `SUPPORTED` — the frozen low-disagreement band applies and required sources
  and quality checks pass;
- `INCONCLUSIVE` — evidence is unavailable, stale, weak, or unresolved; or
- `CHALLENGED` — the frozen high-disagreement band applies and exact-time
  X-Perp sides with the model challenger, with quality checks passing.

`SUPPORT`, `WATCH`, and `REVIEW` are research detector bands, not aliases for
the canonical Evidence States. Evidence State and Policy Action are separate:
the curator or protocol defines its policy, and the consuming protocol owns
enforcement.

The model and validation engine run offchain. The shared X Layer contracts
store authorized attestations and evaluate configured policy; they do not run
the quant model, custody user funds, or liquidate positions.

## Live Deployment

| Component | Deployment |
|---|---|
| Frontend | [valtide-liard.vercel.app](https://valtide-liard.vercel.app) |
| Backend API | [valtide-api-production.up.railway.app](https://valtide-api-production.up.railway.app) |
| OpenAPI | [FastAPI docs](https://valtide-api-production.up.railway.app/docs) |
| Network | X Layer Testnet · Chain ID `1952` |

The browser is read-only and never signs or submits transactions. The backend
scheduler owns authorized publication; publisher credentials are never
exposed to frontend code.

## X Layer Contracts

The current testnet control plane is recorded in
[`deployments/xlayer-testnet.json`](deployments/xlayer-testnet.json).

| Component | Address | Purpose |
|---|---|---|
| `ValtideValidationRegistry` | `0x1A53C85C66EA212693d36bF842574643C4d9B635` | Shared Registry for the three asset bindings |
| `ValtideRiskGuard` | `0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7` | Shared policy evaluator; bindings are asset/reference scoped |

Each asset has its own reference and DemoVault binding recorded in the
[`deployment manifest`](deployments/xlayer-testnet.json). These are testnet
contracts and reference consumers, not audited production lending
infrastructure. `evidenceHash` links an attestation to canonical offchain
evidence; it is a provenance commitment, not proof that the evidence is
objectively correct.

## Key Technical Properties

- **Three-asset operational scope** — NVDAx, SPYx, and AAPLx each have
  asset-specific live runtime, canonical historical replay, and X Layer
  bindings; QQQx remains offline research-only.
- **Point-in-time integrity** — historical replay prevents future-information
  leakage and preserves causal trusted anchors.
- **Explicit abstention** — unavailable, stale, weak, or conflicting evidence
  can produce `INCONCLUSIVE` rather than fabricated certainty.
- **Calibrated uncertainty** — P1a-C returns a challenger estimate with
  calibrated interval bounds, not only a point estimate.
- **Evidence / policy separation** — `Evidence State != Policy Action !=
  Enforcement`.
- **Fail-closed historical provenance** — Historical mode requires
  `X-Valtide-Source: historical_panel` before accepting panel replay as
  research evidence.
- **Persistent operational state** — the warmed scheduler persists carried
  state, results, gaps, and publication status in SQLite.
- **Separate chain delivery** — publisher failures are tracked separately
  from valuation state and do not replace an honest backend result.

## Local Development

```bash
git clone https://github.com/chin0312/valtide.git
cd valtide
cp .env.example .env
```

### Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ../../valtide-quant-service-p1ac -e ".[dev]"
uvicorn valtide_api.main:app --reload --port 8000
```

The local scheduler is disabled by default and publication is disabled by
default. Add only the credentials needed for the data path you are exercising.

### Frontend

```bash
cd apps/web
npm ci
printf 'VITE_API_BASE_URL=http://localhost:8000\n' > .env.local
npm run dev -- --host 127.0.0.1
```

The development dashboard is available at `http://127.0.0.1:5173`.

### Contracts

```bash
cd contracts
forge build
forge test -vvv
```

Deployment is separate from local development and requires explicitly supplied
testnet environment variables. Never commit private keys or RPC credentials.

## Testing

```bash
# Backend
python -m pytest apps/api/tests -q

# Quant
python -m pytest valtide-quant-service-p1ac/tests -q

# Frontend
cd apps/web
npm test
npm run typecheck
npm run build

# Contracts
cd ../../contracts
forge fmt --check
forge build
forge test -vvv
```

GitHub Actions runs the integrated backend, quant, frontend, quality/demo, and
contract checks.

## Repository Structure

```text
apps/api/                    FastAPI backend, adapters, scheduler, publisher
apps/web/                    Vite + React + TypeScript dashboard
valtide-quant-service-p1ac/  P1a-C runtime, calibration, artifacts, tests
contracts/                   X Layer Registry, RiskGuard, DemoVault, tests
deployments/                 public testnet deployment metadata
data/                        ignored generated panels and runtime state
scripts/                     diagnostics, panel-building, and demo utilities
docs/                        product, architecture, methodology, and deployment references
```

## Documentation

| Reference | Description |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | As-built system, trust boundaries, and module responsibilities |
| [Methodology](docs/METHODOLOGY.md) | Challenger model, uncertainty, evidence states, and evaluation |
| [Product Requirements](docs/PRD.md) | Product workflow, users, principles, and limitations |
| [Market Research](docs/USER_MARKET_RESEARCH.md) | User context, market landscape, and competitive infrastructure |
| [Backend Architecture](docs/BACKEND_ARCHITECTURE.md) | Runtime, data, scheduler, persistence, and API design |
| [Deployment](docs/DEPLOYMENT.md) | Hosted topology and reproducibility guidance |
| [Product Semantics](docs/PRODUCT_SEMANTICS.md) | Operational, Historical, Demo, policy, and publication boundaries |
| [Contract control plane](contracts/README.md) | Solidity interfaces, deployment, and trust boundaries |

## Team

| Member | GitHub | Role |
|---|---|---|
| Kai Ze | [@chin0312](https://github.com/chin0312) | Product, Smart Contracts & Systems Integration |
| Xin Tong | [@landonzhao](https://github.com/landonzhao) | Backend & API Engineering |
| James | [@Orange-eat97](https://github.com/Orange-eat97) | Quantitative Research & Product |
| Valerie | [@valeriexylim](https://github.com/valeriexylim) | Frontend Engineering & UI/UX Design |

- **Kai Ze** — product strategy and system design; X Layer smart contracts;
  cross-stack integration; frontend/backend integration; deployment and
  end-to-end delivery.
- **Xin Tong** — backend/API engineering, data adapters, backend implementation
  and runtime services.
- **James** — quantitative research, P1a-C model, uncertainty calibration and
  backtesting; contributed to early product design and demo framing.
- **Valerie** — frontend engineering, UI/UX design, interaction design and
  curator-facing product experience.

## Disclaimer

Valtide is a research prototype. It is not an audited production oracle,
audited lending system, financial product, or financial advice.
