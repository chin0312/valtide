"""Read-only verification of an asset's deployed X Layer control-plane binding."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from valtide_api.config import Settings
from valtide_api.publisher import (
    ChainPreflightError,
    _verify_deployment,
    connect_web3,
    resolve_asset_deployment,
)
from valtide_api.xlayer_manifest import (
    SHARED_REGISTRY,
    SHARED_RISK_GUARD,
    XLAYER_TESTNET_CHAIN_ID,
)

_EXPECTED_POLICY = {
    "max_age": 900,
    "on_supported_code": 0,
    "on_inconclusive_code": 2,
    "on_challenged_code": 3,
    "on_stale_code": 2,
    "on_supported": "ALLOW",
    "on_inconclusive": "REQUIRE_REVIEW",
    "on_challenged": "RESTRICT_NEW_RISK",
    "on_stale": "REQUIRE_REVIEW",
}


def verify(asset: str, manifest_path: Path, rpc_url: str) -> dict[str, Any]:
    settings = Settings(
        _env_file=None,
        xlayer_rpc_url=rpc_url,
        xlayer_chain_id=XLAYER_TESTNET_CHAIN_ID,
        deployment_manifest_path=manifest_path,
    )
    config = resolve_asset_deployment(asset, settings)
    if config.chain_id != XLAYER_TESTNET_CHAIN_ID:
        raise ChainPreflightError("deployment manifest chain is not X Layer Testnet (1952)")
    if config.registry_address.lower() != SHARED_REGISTRY.lower():
        raise ChainPreflightError("manifest does not reference the existing shared Registry")
    if config.risk_guard_address.lower() != SHARED_RISK_GUARD.lower():
        raise ChainPreflightError("manifest does not reference the existing shared RiskGuard")
    web3 = connect_web3(config)
    _registry, _guard, _vault, policy = _verify_deployment(web3, config)
    if int(web3.eth.chain_id) != XLAYER_TESTNET_CHAIN_ID:
        raise ChainPreflightError("connected RPC is not X Layer Testnet (1952)")
    if policy != _EXPECTED_POLICY:
        raise ChainPreflightError("deployed policy differs from the required common policy")
    return {
        "asset": config.asset,
        "chainId": config.chain_id,
        "registry": config.registry_address,
        "riskGuard": config.risk_guard_address,
        "demoVault": config.demo_vault_address,
        "assetId": config.asset_id,
        "referenceId": config.reference_id,
        "modelVersion": config.model_version,
        "policyConfigured": True,
        "policy": policy,
        "readOnly": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", choices=("NVDAx", "SPYx", "AAPLx"), required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=REPO_ROOT / "deployments" / "xlayer-testnet.json",
    )
    parser.add_argument(
        "--rpc-url",
        default=None,
        help="read-only RPC endpoint (or set XLAYER_RPC_URL in the process environment)",
    )
    args = parser.parse_args()
    rpc_url = args.rpc_url
    if not rpc_url:
        import os

        rpc_url = os.environ.get("XLAYER_RPC_URL")
    if not rpc_url:
        parser.error("provide --rpc-url or set XLAYER_RPC_URL")
    try:
        result = verify(args.asset, args.manifest, rpc_url)
    except Exception as exc:  # noqa: BLE001 - provider exceptions can include RPC URLs
        # Web3 provider exceptions may embed an authenticated endpoint; do not
        # echo exception text or environment values into console/log output.
        print(f"verification failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
