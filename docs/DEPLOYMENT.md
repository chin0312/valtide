# Railway backend deployment

This document describes the single-service Railway deployment for the Valtide
FastAPI backend. It is a testnet-only hackathon deployment. The X Layer
contracts and deployment manifest are public testnet infrastructure; this
service is not production-ready and has not been audited.

## Container

The root `Dockerfile` installs both packaged runtime components:

1. `valtide-quant-service-p1ac`
2. `apps/api`

The image starts exactly one Uvicorn process:

```text
uvicorn valtide_api.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Railway supplies `PORT`. Do not add Uvicorn workers: each process would start
its own `LiveScheduler` and access the SQLite runtime independently.

The service must therefore run with:

- Railway replicas: `1`
- Uvicorn workers: `1` (the Docker command does not set `--workers`)

The scheduler is enabled in this same process when
`LIVE_SCHEDULER_ENABLED=true`.

## Railway dashboard settings

Create one Railway service from the GitHub repository
`chin0312/valtide`.

- Source: the repository above and the deployment branch/default branch selected by the team
- Build: root-level `Dockerfile`
- Networking: generate a public domain
- Healthcheck path: `/health` using `GET`
- Replicas: `1`
- Persistent volume: mount one Railway volume at `/data`
- Worker service: none

The volume is required because the warmed runtime is deliberately persisted in
SQLite. Set `VALTIDE_STATE_DB_PATH=/data/valtide.sqlite3`; the application
does not hardcode `/data`, and `RuntimeStore` creates missing parent
directories.

No `railway.toml` or `railway.json` is required for this deployment.

## Service variables

Set these variables in the Railway service. Values are intentionally omitted
from this document.

### Required runtime variables

```text
ALPACA_API_KEY
ALPACA_API_SECRET
ALPACA_FEED=iex

XLAYER_RPC_URL

LIVE_SCHEDULER_ENABLED=true
LIVE_SCHEDULER_ASSET=NVDAx
VALTIDE_STATE_DB_PATH=/data/valtide.sqlite3

PUBLISH_ENABLED=false
AUTO_PUBLISH_ENABLED=false
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

`PUBLISH_ENABLED` controls only the explicit `POST /api/publish/{asset}`
fallback. `AUTO_PUBLISH_ENABLED` controls only scheduler-owned delivery after
a successful warmed tick has already been persisted. Browser/API reads and
diagnostic or replay routes never publish.

For the initial no-write deployment, keep both settings false; the warmed
scheduler, valuation/runtime APIs, Registry/RiskGuard read-only status, and
deployment smoke do not require `PUBLISHER_PRIVATE_KEY`. For the public demo
configuration, set `AUTO_PUBLISH_ENABLED=true` while keeping
`PUBLISH_ENABLED=false` so automatic delivery is enabled without exposing the
manual HTTP write route.

`PUBLISHER_PRIVATE_KEY` is required whenever either publication setting is
true. It must be a dedicated X Layer testnet publisher signer, must not hold
user funds, and must never be committed, pasted into logs, or included in an
image layer or deployment manifest. Do not upload it to Railway until
publication is intentionally enabled.

`CORS_ORIGINS` must contain the actual frontend origin once the frontend is
deployed. For example:

```text
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,https://<frontend-domain>
```

Do not use `*` together with credentialed browser requests.

### Optional variables and defaults

```text
XLAYER_CHAIN_ID=1952
PUBLISH_VALIDITY_SECONDS=900
OKX_XPERP_INDEX_ID=NVDA-USD
DEXSCREENER_NVDAX_ADDRESS=
HISTORICAL_PANEL_PATH=data/generated/nvdax_historical_5m.csv
DEPLOYMENT_MANIFEST_PATH=/app/deployments/xlayer-testnet.json
```

`DEPLOYMENT_MANIFEST_PATH` is set to the public manifest location by the
Dockerfile. Do not replace the manifest or its deployed addresses as part of
this deployment preparation.

## Data-source notes

- The OKX X-Perp live reference endpoint used by this path is public.
- The DexScreener NVDAx path does not require an API key.
- OKX OnchainOS credentials are not required for the live scheduler path.
- Alpaca credentials are still required for the NVDA underlying feed.
- X Layer RPC access must be supplied through a Railway environment variable.
- The publisher key is needed only when automatic or explicit publication is
  intentionally enabled.

The default `HISTORICAL_PANEL_PATH` points to `data/generated`, which is an
ignored generated-data directory. There is currently no canonical historical
panel artifact committed in this repository, so historical-panel backtests
are not production-available in the image unless that artifact is supplied by
a separate, reviewed deployment process. Automatic publication does not
depend on historical-panel availability.

## Read-only smoke check

After Railway provides the public domain, run:

```bash
python scripts/smoke_backend_deployment.py https://<backend-domain>
```

The script performs only `GET` requests to `/health`, `/api/assets`,
`/api/runtime/NVDAx`, and `/api/onchain/NVDAx`. It never calls
`POST /api/publish/NVDAx` and cannot broadcast a transaction. An unwarmed
runtime is reported as a non-fatal state. When the onchain endpoint is
available, the script requires chain ID `1952`.

## Scope and safety

This service runs the existing backend/quant vertical slice and the existing
single-process warmed scheduler. Each successful canonical tick is persisted
before optional scheduler-owned delivery is queued. One in-process publication
worker serializes transactions and coalesces pending delivery to the newest
observation, so a slow chain does not delay valuation ticks. A delivery failure
is recorded separately and does not invalidate the operational valuation or
stop the scheduler. On shutdown, the service waits for the bounded worker
shutdown window; an in-flight Web3 worker thread cannot be force-cancelled.
It does not change quant logic, validation semantics,
live-data semantics, contract source, deployed addresses, or frontend code.
It does not claim production readiness, an audit, mainnet deployment, or a
production oracle.
