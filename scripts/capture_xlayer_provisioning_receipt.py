"""Read-only verification of SPYx/AAPLx provisioning transaction receipts.

The input is a human-collected, non-secret list of transaction hashes. This
command never signs, sends, or broadcasts transactions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from valtide_api.publisher import keccak_text
from valtide_api.xlayer_manifest import (
    SHARED_REGISTRY,
    SHARED_RISK_GUARD,
    XLAYER_TESTNET_CHAIN_ID,
)

_EXPECTED_POLICY = (900, 0, 2, 3, 2)


def _load_abi(name: str) -> list[dict[str, Any]]:
    return json.loads((REPO_ROOT / "apps" / "api" / "valtide_api" / "abis" / name).read_text())


def _tx_hash(value: Any, label: str, web3: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a transaction hash")
    try:
        normalized = web3.to_hex(hexstr=value).lower()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not a valid transaction hash") from exc
    if len(normalized) != 66:
        raise ValueError(f"{label} is not a 32-byte transaction hash")
    return normalized


def _receipt_record(
    web3: Any,
    asset: str,
    source: dict[str, Any],
    deployer: str,
    guard: Any,
) -> dict[str, Any]:
    deployment_hash = _tx_hash(source.get("deploymentTxHash"), f"{asset} deploymentTxHash", web3)
    policy_hash = _tx_hash(
        source.get("policyConfigurationTxHash"), f"{asset} policyConfigurationTxHash", web3
    )
    deployment_tx = web3.eth.get_transaction(deployment_hash)
    deployment_receipt = web3.eth.get_transaction_receipt(deployment_hash)
    policy_tx = web3.eth.get_transaction(policy_hash)
    policy_receipt = web3.eth.get_transaction_receipt(policy_hash)
    if int(deployment_receipt["status"]) != 1 or int(policy_receipt["status"]) != 1:
        raise ValueError(f"{asset} deployment or policy transaction did not succeed")
    if deployment_tx.get("to") not in (None, "0x", b""):
        raise ValueError(f"{asset} deployment transaction is not contract creation")
    if deployment_tx["from"].lower() != deployer.lower():
        raise ValueError(f"{asset} deployment transaction sender does not match deployer")
    if policy_tx["from"].lower() != deployer.lower():
        raise ValueError(f"{asset} policy transaction sender does not match deployer")
    vault_address = deployment_receipt.get("contractAddress")
    if not vault_address or policy_tx["to"].lower() != vault_address.lower():
        raise ValueError(f"{asset} policy transaction does not target its newly deployed vault")
    if int(policy_receipt["blockNumber"]) < int(deployment_receipt["blockNumber"]):
        raise ValueError(f"{asset} policy transaction predates the vault deployment")
    if not web3.eth.get_code(vault_address):
        raise ValueError(f"{asset} DemoVault has no deployed bytecode")

    from web3 import Web3

    vault = web3.eth.contract(
        address=Web3.to_checksum_address(vault_address), abi=_load_abi("DemoCollateralVault.json")
    )
    expected_asset_id = keccak_text(asset)
    from valtide_api.assets import resolve_asset_config

    asset_config = resolve_asset_config(asset)
    expected_reference_id = keccak_text(asset_config.xlayer_reference_name)
    actual_asset_id = "0x" + bytes(vault.functions.assetId().call()).hex()
    actual_reference_id = "0x" + bytes(vault.functions.referenceId().call()).hex()
    if actual_asset_id.lower() != expected_asset_id.lower():
        raise ValueError(f"{asset} vault assetId does not match the registered identity")
    if actual_reference_id.lower() != expected_reference_id.lower():
        raise ValueError(f"{asset} vault referenceId does not match the registered identity")
    if vault.functions.owner().call().lower() != deployer.lower():
        raise ValueError(f"{asset} vault owner does not match the verified deployer")
    if vault.functions.riskGuard().call().lower() != SHARED_RISK_GUARD.lower():
        raise ValueError(f"{asset} vault is linked to a different RiskGuard")
    policy_values, configured = guard.functions.getPolicy(
        Web3.to_checksum_address(vault_address), bytes.fromhex(expected_asset_id[2:]),
        bytes.fromhex(expected_reference_id[2:]),
    ).call()
    actual_policy = tuple(int(value) for value in policy_values)
    if not configured or actual_policy != _EXPECTED_POLICY:
        raise ValueError(f"{asset} RiskGuard policy is missing or differs from the required default")

    deployment_block = web3.eth.get_block(deployment_receipt["blockNumber"])
    policy_block = web3.eth.get_block(policy_receipt["blockNumber"])
    return {
        "demoVault": Web3.to_checksum_address(vault_address),
        "assetId": expected_asset_id,
        "referenceId": expected_reference_id,
        "modelVersion": _model_version_hash(asset),
        "deployer": Web3.to_checksum_address(deployer),
        "deploymentTxHash": deployment_hash,
        "deploymentBlockNumber": int(deployment_receipt["blockNumber"]),
        "deploymentTimestamp": _iso_timestamp(int(deployment_block["timestamp"])),
        "policyConfigurationTxHash": policy_hash,
        "policyBlockNumber": int(policy_receipt["blockNumber"]),
        "policyTimestamp": _iso_timestamp(int(policy_block["timestamp"])),
        "policyVerified": True,
        "policy": {
            "maxAge": actual_policy[0],
            "onSupported": actual_policy[1],
            "onInconclusive": actual_policy[2],
            "onChallenged": actual_policy[3],
            "onStale": actual_policy[4],
        },
    }


def _model_version_hash(asset: str) -> str:
    from valtide_api.quant_runtime import resolve_quant_runtime

    return keccak_text(resolve_quant_runtime(asset).model_version)


def _iso_timestamp(value: int) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")


def capture(input_path: Path, rpc_url: str) -> dict[str, Any]:
    from web3 import Web3

    source = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(source, dict) or source.get("chainId") != XLAYER_TESTNET_CHAIN_ID:
        raise ValueError("input must declare chainId 1952")
    if str(source.get("registry", "")).lower() != SHARED_REGISTRY.lower():
        raise ValueError("input Registry does not match the existing shared deployment")
    if str(source.get("riskGuard", "")).lower() != SHARED_RISK_GUARD.lower():
        raise ValueError("input RiskGuard does not match the existing shared deployment")
    deployer = Web3.to_checksum_address(source["deployer"])
    assets = source.get("assets")
    if not isinstance(assets, dict) or set(assets) != {"SPYx", "AAPLx"}:
        raise ValueError("input assets must contain exactly SPYx and AAPLx transaction hashes")

    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 20}))
    if not web3.is_connected():
        raise ConnectionError("RPC is unavailable")
    if int(web3.eth.chain_id) != XLAYER_TESTNET_CHAIN_ID:
        raise ValueError("connected RPC is not X Layer Testnet (1952)")
    for label, address in (("Registry", SHARED_REGISTRY), ("RiskGuard", SHARED_RISK_GUARD)):
        if not web3.eth.get_code(address):
            raise ValueError(f"shared {label} has no bytecode")
    guard = web3.eth.contract(
        address=Web3.to_checksum_address(SHARED_RISK_GUARD),
        abi=_load_abi("ValtideRiskGuard.json"),
    )
    linked_registry = guard.functions.registry().call()
    if linked_registry.lower() != SHARED_REGISTRY.lower():
        raise ValueError("shared RiskGuard is linked to a different Registry")

    verified_assets = {
        asset: _receipt_record(web3, asset, assets[asset], deployer, guard)
        for asset in ("SPYx", "AAPLx")
    }
    if len({entry["demoVault"].lower() for entry in verified_assets.values()}) != 2:
        raise ValueError("SPYx and AAPLx must have different DemoVault addresses")
    return {
        "schemaVersion": 1,
        "verified": True,
        "verifiedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "chainId": XLAYER_TESTNET_CHAIN_ID,
        "registry": SHARED_REGISTRY,
        "riskGuard": SHARED_RISK_GUARD,
        "deployer": deployer,
        "assets": verified_assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="non-secret tx-hash input JSON")
    parser.add_argument("--output", type=Path, required=True, help="verified receipt JSON output")
    parser.add_argument("--rpc-url", required=True, help="read-only X Layer RPC endpoint")
    args = parser.parse_args()
    try:
        receipt = capture(args.input, args.rpc_url)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - redact authenticated RPC URLs from exceptions
        print(f"receipt verification failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"verified receipt written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
