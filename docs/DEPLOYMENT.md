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
boundaries and the persisted SQLite state. `VALTIDE_STATE_DB_PATH` points to a
persistent SQLite file under `/data`; it stores operational runtime state and
history, not historical source panels. Historical CSVs are separately
provisioned under `/data/historical` on the same persistent volume and remain
available across container restarts and redeploys.

The three production Historical paths are:

```text
HISTORICAL_PANEL_PATH=/data/historical/panels/20261005/nvdax_historical_5m.csv
SPYX_HISTORICAL_PANEL_PATH=/data/historical/panels/20261005/spyx_historical_5m.csv
AAPLX_HISTORICAL_PANEL_PATH=/data/historical/panels/20261005/aaplx_historical_5m.csv
```

QQQx remains research-only. A previously uploaded QQQx CSV may remain on the
volume, but it is not part of the production manifest and must not be bound to
the production service.

Each file is bound to an asset, Solana chain index/token address, underlying,
OKX X-Perp/index instrument, canonical panel schema, time window, row count,
and SHA-256 in
[`data/manifests/production_historical_panels.json`](../data/manifests/production_historical_panels.json).
Provision only the exact verified bytes; do not use a different asset's panel
or an Ethereum research panel as a fallback. A panel file is not considered
Historical-ready until the backend's canonical identity/replay checks pass.
The reproducible transfer guard is
[`scripts/provision_historical_panels.py`](../scripts/provision_historical_panels.py):
transfer a candidate to a temporary file under the existing volume, then run
the script in the backend container with `--asset` and `--source`. It verifies
the committed SHA and identity manifest, uses the canonical panel inspector,
installs atomically, accepts identical re-provisioning, and refuses to replace
different destination bytes. The source CSVs remain external to Git.

Panel generations are immutable: if an older valid generation already exists
at a previous path, preserve it and point the asset setting to the new
manifest-bound generation instead of overwriting its bytes. For example, after
placing a transfer copy at `/data/historical/.incoming/nvdax.csv`:

```bash
python /app/scripts/provision_historical_panels.py \
  --asset NVDAx \
  --source /data/historical/.incoming/nvdax.csv
```

Repeat for the other two manifest entries, then verify `/api/assets` and the
asset-scoped `source=panel` replay before and after restarting the same service.

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
LIVE_SCHEDULER_ASSETS
LIVE_SETTLEMENT_GRACE_SECONDS
LIVE_SETTLEMENT_MAX_ATTEMPTS
LIVE_SETTLEMENT_RETRY_DELAY_SECONDS
LIVE_UNDERLYING_MAX_AGE_SECONDS
VALTIDE_STATE_DB_PATH
HISTORICAL_PANEL_PATH
SPYX_HISTORICAL_PANEL_PATH
AAPLX_HISTORICAL_PANEL_PATH

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

Each explicitly enabled asset worker waits for its configured settlement grace,
fetches the exact confirmed five-minute OKX OnchainOS candle, and persists a
successful valuation before optional publication is considered. NVDAx is the
only current asset with an onchain binding, so SPYx and AAPLx remain read-only
operational validations. Publication is serialized by one in-process worker
and coalesces pending work to the newest observation. A delivery failure is
recorded separately and does not invalidate the warmed valuation or stop future
scheduler ticks.

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

### Multi-asset control-plane preparation

The Registry and RiskGuard are shared across NVDAx, SPYx, and AAPLx: Registry
attestations are namespaced by `assetId × referenceId`, while RiskGuard policy
is namespaced by `policy owner × assetId × referenceId`. Each asset/reference
pair therefore receives its own `DemoCollateralVault`; do not deploy another
Registry/RiskGuard pair. The existing NVDAx vault remains unchanged. The
committed manifest stays on the legacy NVDAx layout until SPYx and AAPLx have
actually been deployed and their receipts verified; no placeholder addresses
belong in the manifest.

`contracts/script/ProvisionValtideAssets.s.sol` attaches to the pinned existing
testnet Registry/RiskGuard and creates only the SPYx and AAPLx DemoVaults with
the common 900-second policy. It refuses any chain other than 1952, checks
both shared bytecodes, and verifies `RiskGuard.registry()` before reading the
signer key. Foundry requires `REGISTRY_ADDRESS`, `RISK_GUARD_ADDRESS`, and
`DEPLOYER_PRIVATE_KEY`; supply the exact shared addresses above. For simulation,
use only a disposable local key (not a funded or production signer). A later
authorized deployment phase may simulate it with:

```bash
cd contracts
forge script script/ProvisionValtideAssets.s.sol:ProvisionValtideAssets \
  --rpc-url "$XLAYER_RPC_URL"
```

Do not add `--broadcast` to a dry run. Broadcasting is a separate owner-approved
deployment action and is intentionally not performed by this change.

After an authorized broadcast, create a non-secret input file containing only
the confirmed transaction hashes:

```json
{
  "chainId": 1952,
  "registry": "0x1A53C85C66EA212693d36bF842574643C4d9B635",
  "riskGuard": "0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7",
  "deployer": "<confirmed deployer address>",
  "assets": {
    "SPYx": {
      "deploymentTxHash": "<confirmed vault creation tx>",
      "policyConfigurationTxHash": "<confirmed policy tx>"
    },
    "AAPLx": {
      "deploymentTxHash": "<confirmed vault creation tx>",
      "policyConfigurationTxHash": "<confirmed policy tx>"
    }
  }
}
```

The read-only capture helper fetches those receipts and verifies chain, sender,
deployment address, shared contract linkage, immutable asset/reference IDs,
deployed bytecode, and the exact common policy. Then the manifest builder
creates one canonical `assets` map with the existing NVDAx vault and the two
verified new vaults:

```bash
python scripts/capture_xlayer_provisioning_receipt.py \
  --input xlayer-provisioning-tx-hashes.json \
  --output xlayer-provisioning-receipts.json \
  --rpc-url "$XLAYER_RPC_URL"
python scripts/build_xlayer_manifest.py \
  --receipt xlayer-provisioning-receipts.json \
  --output /tmp/xlayer-testnet-multi-asset-candidate.json
```

Review the generated manifest before committing it. Its active source of truth
is `assets.NVDAx`, `assets.SPYx`, and `assets.AAPLx`; legacy `demo` and singular
`contracts.DemoCollateralVault` entries are removed. The original NVDA
deployment history is retained under `initialDeployment`, separate from the
active per-asset bindings.

The deployment can be checked without a publisher key or write operation:

```bash
XLAYER_RPC_URL="$XLAYER_RPC_URL" python scripts/verify_xlayer_asset.py --asset NVDAx
XLAYER_RPC_URL="$XLAYER_RPC_URL" python scripts/verify_xlayer_asset.py --asset SPYx
XLAYER_RPC_URL="$XLAYER_RPC_URL" python scripts/verify_xlayer_asset.py --asset AAPLx
```

This PR prepares deployment tooling only. SPYx/AAPLx remain statically
`onchain=false` until their actual binding is committed and a later backend
deployment explicitly enables those capabilities. Publication flags remain
off by default.

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
