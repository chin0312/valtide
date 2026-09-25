# Valtide Deployment

This document describes the current hosted topology and the reproducible
configuration boundary for the deployed hackathon prototype.

## Current Hosted Services

| Plane | Provider | URL |
|---|---|---|
| Dashboard | Vercel | [valtide-liard.vercel.app](https://valtide-liard.vercel.app) |
| Backend | Railway | [valtide-api-production.up.railway.app](https://valtide-api-production.up.railway.app) |
| OpenAPI | FastAPI | [API docs](https://valtide-api-production.up.railway.app/docs) |
| Control plane | X Layer Testnet | Chain ID `1952` |

The frontend project is connected to `chin0312/valtide`, deploys from `main`,
and uses `apps/web` as its root directory. Production builds embed:

```text
VITE_API_BASE_URL=https://valtide-api-production.up.railway.app
```

The browser is read-only. Publication and transaction signing remain backend
responsibilities.

## Backend Topology

The hosted backend is one Railway service running:

- one replica in the `sfo` region;
- one Uvicorn process with no worker fan-out;
- the FastAPI application and in-process `LiveScheduler`;
- SQLite runtime state on one persistent `/data` volume; and
- the root `Dockerfile`, which installs `valtide-quant-service-p1ac` and
  `apps/api`.

The container command is:

```text
uvicorn valtide_api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

The scheduler must remain single-process because it owns canonical five-minute
boundaries and the persisted SQLite state. `VALTIDE_STATE_DB_PATH` points to
`/data/valtide.sqlite3` in the hosted environment. The persistent volume also
contains the provisioned historical panel used by the historical replay path.

## Backend Variables

Set values through the hosting provider; do not commit them here. The deployed
variable names are:

```text
ALPACA_API_KEY
ALPACA_API_SECRET
ALPACA_FEED

OKX_API_KEY
OKX_API_SECRET
OKX_API_PASSPHRASE
OKX_NVDAX_CHAIN_INDEX
OKX_NVDAX_TOKEN_ADDRESS
OKX_XPERP_INDEX_ID

LIVE_SCHEDULER_ENABLED
LIVE_SCHEDULER_ASSET
LIVE_SETTLEMENT_GRACE_SECONDS
LIVE_SETTLEMENT_MAX_ATTEMPTS
LIVE_SETTLEMENT_RETRY_DELAY_SECONDS
LIVE_UNDERLYING_MAX_AGE_SECONDS
VALTIDE_STATE_DB_PATH
HISTORICAL_PANEL_PATH

XLAYER_RPC_URL
XLAYER_CHAIN_ID
DEPLOYMENT_MANIFEST_PATH

PUBLISH_ENABLED
AUTO_PUBLISH_ENABLED
PUBLISH_VALIDITY_SECONDS
PUBLISHER_PRIVATE_KEY
CORS_ORIGINS
```

The current public deployment uses the exact production frontend origin in
`CORS_ORIGINS` alongside the local development origins. Do not use `*`.

`PUBLISH_ENABLED` gates the explicit `POST /api/publish/{asset}` fallback.
`AUTO_PUBLISH_ENABLED` gates scheduler-owned delivery after a successful
warmed tick has been persisted. The publisher key is backend-only, must be an
isolated X Layer testnet signer, and must never appear in logs, source, images,
or deployment metadata.

## Live Runtime and Publication

The scheduler waits for the configured settlement grace, fetches the exact
confirmed five-minute OKX OnchainOS NVDAx candle, and persists a successful
valuation before optional publication is queued. Publication is serialized by
one in-process worker and coalesces pending work to the newest observation. A
delivery failure is recorded separately and does not invalidate the warmed
valuation or stop future scheduler ticks.

The backend publishes to the testnet Registry only through its publisher
boundary. API reads, replay, cold diagnostics, and frontend reads do not
publish.

## Frontend Deployment

From the repository root, the Vercel project should use:

```text
Framework: Vite
Root Directory: apps/web
Production Branch: main
Build Command: npm run build
Environment: VITE_API_BASE_URL=<backend origin without /api>
```

The frontend build is static. It must not contain backend API keys, publisher
keys, RPC credentials, or any other secret.

## X Layer Testnet

The public deployment manifest is
[`deployments/xlayer-testnet.json`](../deployments/xlayer-testnet.json). The
deployed control plane is:

- `ValtideValidationRegistry`: `0x1A53C85C66EA212693d36bF842574643C4d9B635`
- `ValtideRiskGuard`: `0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7`
- `DemoCollateralVault`: `0x4beC6Bc1DF651f36758216cA02db62b5603349ce`
- authorized publisher / deployer: `0xBb341F8AE72146CEE60Ca0cCFE8C3Db5c90fC30C`

These are ordinary EVM-compatible testnet contracts. They are not audited
production lending infrastructure, and no mainnet deployment is claimed.

## Reproducing the Backend Deployment

Use the existing Railway project and service rather than creating duplicate
infrastructure. From a clean checkout of `main`, configure the variables above
through Railway and deploy the repository's root Dockerfile using the provider's
existing project/service connection. Preserve one replica, the `/data` volume,
the `/health` healthcheck, and the public backend domain.

No `railway.toml` or `railway.json` is required. Never copy production secrets
into a generic preview environment.

## Read-only Smoke Check

The repository includes a GET-only deployment smoke script:

```bash
python scripts/smoke_backend_deployment.py \
  https://valtide-api-production.up.railway.app
```

It checks liveness, supported assets, runtime status, and read-only X Layer
state. It never calls `POST /api/publish/{asset}` and cannot broadcast a
transaction.

For the historical browser path, the replay response must include:

```text
X-Valtide-Source: historical_panel
```

and the backend CORS response must expose that header to the deployed frontend
origin.

## Safety Boundary

This deployment does not claim production readiness, an audit, mainnet
deployment, a universal oracle, liquidation logic, or real collateral custody.
The quant model remains offchain, the Registry stores attestations, RiskGuard
evaluates curator-owned policy, and a consumer decides how to enforce the
result.
