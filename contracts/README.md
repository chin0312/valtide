# Valtide X Layer Control Plane

This directory contains the submission-critical onchain control plane for
Valtide. It is an ordinary EVM-compatible Foundry project targeting X Layer.

## Architecture

```text
Offchain validation
        ↓
ValtideValidationRegistry
        ↓ Evidence State
ValtideRiskGuard
        ↓ Policy Action
DemoCollateralVault / consuming application
        ↓ consumer-defined enforcement
```

The contracts follow the product ownership boundary:

- `ValtideValidationRegistry` stores the latest authorized validation
  attestation for an `assetId` and `referenceId` pair. It does not run a model
  or determine policy.
- `ValtideRiskGuard` evaluates a policy owned by the consuming application.
  It maps the Registry's `SUPPORTED`, `INCONCLUSIVE`, or `CHALLENGED` Evidence
  State to that application's configured Policy Action.
- `DemoCollateralVault` is a minimal reference consumer. It demonstrates
  configurable new-exposure gating and does not custody assets, lend, trade,
  calculate LTV, or liquidate.

Valtide determines Evidence State. The policy owner determines the Policy
Action mapping. The consumer enforces the resulting action.

## Data conventions

- `assetId`, `referenceId`, and `modelVersion` are opaque `bytes32` values.
  Recommended deterministic identifiers are:

  ```solidity
  keccak256(bytes("NVDAx"))
  keccak256(bytes("OKX_NVDA_USD_INDEX"))
  keccak256(bytes("0.2.0"))
  ```

- Prices use 8-decimal fixed-point integers (`E8`). For example, `$185.00`
  is represented as `18_500_000_000`.
- `referenceDeviationBps` is a signed basis-point value supplied by the
  offchain validation layer. The Registry stores it and does not recompute it.
- `evidenceHash` is the `keccak256` commitment of a canonical offchain
  evidence payload, such as the normalized observation and model result. It
  links the onchain attestation to provenance; it does not prove that the
  offchain evidence is objectively correct.
- Callers submit `ValidationInput`, which contains the canonical validation
  fields but no `publishedAt`. The Registry constructs the stored
  `ValidationAttestation` and sets `publishedAt` to its own `block.timestamp`.
- `observedAt` is the market timestamp being validated and `validUntil` bounds
  Registry freshness. An existing pair cannot be overwritten by an older
  `observedAt`; equal timestamps are allowed for retries or corrections.

Registry freshness requires an existing attestation and
`block.timestamp <= validUntil`. Risk Guard freshness additionally applies
the policy owner's `maxAge` to `observedAt`, so a late publication cannot make
an old market observation fresh. `evaluate` and `evaluateFor` return
`(evidenceState, policyAction, exists, fresh)`. A missing attestation has
`exists == false`, `fresh == false`, and the policy's `onStale` action; its
`INCONCLUSIVE` Evidence State is only an ABI-safe sentinel, not a published
attestation. Existing stale attestations have `exists == true`, preserve their
attested Evidence State, and return `fresh == false`.

## Local development

The project uses Solidity `^0.8.24`, `forge-std` `v1.9.7`, and OpenZeppelin
Contracts `v5.0.2`.

```bash
cd contracts
forge fmt --check
forge build
forge test -vvv
```

## Deployment configuration

Deployment is intentionally separate from CI and is not performed by this
repository setup. The deployment script reads:

- `DEPLOYER_PRIVATE_KEY` — the deployer's private key, supplied only through
  the local environment;
- `PUBLISHER_ADDRESS` — the address authorized to publish attestations; and
- `XLAYER_RPC_URL` — the RPC endpoint supplied to Foundry.

The script deploys `ValtideValidationRegistry`, `ValtideRiskGuard`, and
`DemoCollateralVault`, authorizes the configured publisher, and configures the
Demo Vault's default 15-minute policy. It prints addresses and canonical demo
identifiers. Private keys, RPC credentials, and other secrets remain local and
are never recorded in the repository.

Example testnet command:

```bash
cd contracts
forge script script/DeployValtide.s.sol:DeployValtide \
  --rpc-url "$XLAYER_RPC_URL" \
  --broadcast
```

The deployment script rejects every other chain ID before broadcasting.

## TESTNET deployment

The first Valtide control-plane deployment is recorded in
[`deployments/xlayer-testnet.json`](../deployments/xlayer-testnet.json).

Network: X Layer testnet, chain ID `1952`

- `ValtideValidationRegistry`: `0x1A53C85C66EA212693d36bF842574643C4d9B635`
- `ValtideRiskGuard`: `0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7`
- `DemoCollateralVault`: `0x4beC6Bc1DF651f36758216cA02db62b5603349ce`
- Deployer and Registry/DemoVault owner: `0xBb341F8AE72146CEE60Ca0cCFE8C3Db5c90fC30C`
- Authorized publisher: `0xBb341F8AE72146CEE60Ca0cCFE8C3Db5c90fC30C`

These are TESTNET contracts only. They are not production contracts, and no
audit or security review is claimed. The deployed backend publisher actively
consumes the Registry and the deployed dashboard exposes the control-plane
state read-only. This deployment record does not claim production lending or
custody.

`DemoCollateralVault` is a reference consumer for the hackathon vertical
slice, not a production lending protocol or financial product.
