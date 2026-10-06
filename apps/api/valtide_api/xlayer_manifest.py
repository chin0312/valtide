"""Build the canonical multi-asset manifest from verified deployment receipts."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from valtide_api.publisher import keccak_text

XLAYER_TESTNET_CHAIN_ID = 1952
SHARED_REGISTRY = "0x1A53C85C66EA212693d36bF842574643C4d9B635"
SHARED_RISK_GUARD = "0x8e17a4eB93074ea74d05D9bc316d85AD3B540CE7"
PRODUCTION_ASSETS = ("NVDAx", "SPYx", "AAPLx")
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


class ManifestBuildError(ValueError):
    """Raised when verified deployment data cannot safely form a manifest."""


def _require_address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ADDRESS_RE.fullmatch(value):
        raise ManifestBuildError(f"{label} must be a 20-byte hexadecimal address")
    if int(value[2:], 16) == 0:
        raise ManifestBuildError(f"{label} cannot be the zero address")
    return value


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ManifestBuildError(f"{label} must be a 32-byte hexadecimal hash")
    return value.lower()


def _require_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ManifestBuildError(f"{label} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestBuildError(f"{label} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ManifestBuildError(f"{label} must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _compatibility(
    asset: str, reference_id: str, model_id: str, model_version: str
) -> dict[str, str]:
    from valtide_api.assets import resolve_asset_config
    from valtide_api.quant_runtime import resolve_quant_runtime

    config = resolve_asset_config(asset)
    runtime = resolve_quant_runtime(config)
    if runtime.model_id != model_id or runtime.model_version != model_version:
        raise ManifestBuildError(f"{asset} compatibility does not match the registered runtime")
    return {
        "asset": asset,
        "referenceId": reference_id,
        "referenceProfile": config.reference_profile,
        "evidenceSemantics": "p1a_xstock_band_with_xperp_review_corroboration_v2",
        "modelId": model_id,
        "modelVersion": model_version,
    }


def _asset_identity(asset: str) -> tuple[str, str, str, str]:
    from valtide_api.assets import resolve_asset_config
    from valtide_api.quant_runtime import resolve_quant_runtime

    config = resolve_asset_config(asset)
    runtime = resolve_quant_runtime(config)
    return (
        keccak_text(asset),
        keccak_text(config.xlayer_reference_name),
        keccak_text(runtime.model_version),
        runtime.model_id,
    )


def _checked_receipt_asset(
    asset: str, value: Any, expected_deployer: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("policyVerified") is not True:
        raise ManifestBuildError(f"{asset} deployment receipt is not chain-verified")
    demo_vault = _require_address(value.get("demoVault"), f"{asset} demoVault")
    deployment_hash = _require_hash(value.get("deploymentTxHash"), f"{asset} deploymentTxHash")
    policy_hash = _require_hash(
        value.get("policyConfigurationTxHash"), f"{asset} policyConfigurationTxHash"
    )
    deployment_block = value.get("deploymentBlockNumber")
    policy_block = value.get("policyBlockNumber")
    if (
        isinstance(deployment_block, bool)
        or not isinstance(deployment_block, int)
        or deployment_block <= 0
        or isinstance(policy_block, bool)
        or not isinstance(policy_block, int)
        or policy_block < deployment_block
    ):
        raise ManifestBuildError(f"{asset} receipt block numbers are invalid")
    deployment_time = _require_timestamp(
        value.get("deploymentTimestamp"), f"{asset} deploymentTimestamp"
    )
    policy_time = _require_timestamp(value.get("policyTimestamp"), f"{asset} policyTimestamp")
    asset_deployer = _require_address(value.get("deployer"), f"{asset} deployer")
    if asset_deployer.lower() != expected_deployer.lower():
        raise ManifestBuildError(f"{asset} receipt deployer differs from the verified deployer")
    expected_policy = {
        "maxAge": 900,
        "onSupported": 0,
        "onInconclusive": 2,
        "onChallenged": 3,
        "onStale": 2,
    }
    policy = value.get("policy")
    if (
        not isinstance(policy, dict)
        or set(policy) != set(expected_policy)
        or any(type(policy[key]) is not int for key in expected_policy)
        or policy != expected_policy
    ):
        raise ManifestBuildError(f"{asset} policy does not match the production default")
    asset_id, reference_id, model_version, model_id = _asset_identity(asset)
    if not isinstance(value.get("assetId"), str) or value["assetId"].lower() != asset_id.lower():
        raise ManifestBuildError(f"{asset} verified receipt has the wrong assetId")
    if (
        not isinstance(value.get("referenceId"), str)
        or value["referenceId"].lower() != reference_id.lower()
    ):
        raise ManifestBuildError(f"{asset} verified receipt has the wrong referenceId")
    if (
        not isinstance(value.get("modelVersion"), str)
        or value["modelVersion"].lower() != model_version.lower()
    ):
        raise ManifestBuildError(f"{asset} verified receipt has the wrong modelVersion")
    binding = {
        "demoVault": demo_vault,
        "assetId": asset_id,
        "referenceId": reference_id,
        "modelVersion": model_version,
        "publicationCompatibility": _compatibility(
            asset, reference_id, model_id, "0.3.0"
        ),
        "deploymentReceipt": {
            "deployer": asset_deployer,
            "deploymentTxHash": deployment_hash,
            "deploymentBlockNumber": deployment_block,
            "deploymentTimestamp": deployment_time,
            "policyConfigurationTxHash": policy_hash,
            "policyBlockNumber": policy_block,
            "policyTimestamp": policy_time,
        },
    }
    return binding


def build_multi_asset_manifest(
    base_manifest: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    """Return a canonical manifest; never invent vault addresses or receipts."""
    if not isinstance(base_manifest, dict) or not isinstance(receipt, dict):
        raise ManifestBuildError("base manifest and verified receipt must be JSON objects")
    if receipt.get("verified") is not True or receipt.get("chainId") != XLAYER_TESTNET_CHAIN_ID:
        raise ManifestBuildError("receipt must be verified on X Layer Testnet (1952)")
    if base_manifest.get("chainId") != XLAYER_TESTNET_CHAIN_ID:
        raise ManifestBuildError("base manifest is not pinned to X Layer Testnet (1952)")
    contracts = base_manifest.get("contracts")
    if not isinstance(contracts, dict):
        raise ManifestBuildError("base manifest is missing contracts")
    registry = _require_address(
        contracts.get("ValtideValidationRegistry"), "Registry address"
    )
    risk_guard = _require_address(contracts.get("ValtideRiskGuard"), "RiskGuard address")
    if (
        registry.lower() != SHARED_REGISTRY.lower()
        or risk_guard.lower() != SHARED_RISK_GUARD.lower()
    ):
        raise ManifestBuildError("base manifest does not use the existing shared contracts")
    if (
        str(receipt.get("registry", "")).lower() != registry.lower()
        or str(receipt.get("riskGuard", "")).lower() != risk_guard.lower()
    ):
        raise ManifestBuildError("verified receipt shared contract addresses do not match base")
    deployer = _require_address(receipt.get("deployer"), "receipt deployer")
    receipt_assets = receipt.get("assets")
    if not isinstance(receipt_assets, dict) or set(receipt_assets) != {"SPYx", "AAPLx"}:
        raise ManifestBuildError("verified receipt must contain exactly SPYx and AAPLx")

    nvda_legacy = base_manifest.get("demo")
    legacy_vault = contracts.get("DemoCollateralVault")
    if not isinstance(nvda_legacy, dict):
        raise ManifestBuildError("legacy NVDA binding is missing from the base manifest")
    nvda_vault = _require_address(legacy_vault, "legacy NVDA DemoVault")
    nvda_ids = _asset_identity("NVDAx")
    legacy_nvda_ids = tuple(
        str(nvda_legacy.get(key, "")).lower()
        for key in ("assetId", "referenceId", "modelVersion")
    )
    if legacy_nvda_ids != tuple(value.lower() for value in nvda_ids[:3]):
        raise ManifestBuildError("legacy NVDA IDs do not match current registered identity")
    _, nvda_reference, nvda_model_hash, nvda_model_id = nvda_ids
    assets: dict[str, dict[str, Any]] = {
        "NVDAx": {
            "demoVault": nvda_vault,
            "assetId": nvda_ids[0],
            "referenceId": nvda_reference,
            "modelVersion": nvda_model_hash,
            "publicationCompatibility": _compatibility(
                "NVDAx", nvda_reference, nvda_model_id, "0.2.0"
            ),
        },
        "SPYx": _checked_receipt_asset("SPYx", receipt_assets["SPYx"], deployer),
        "AAPLx": _checked_receipt_asset("AAPLx", receipt_assets["AAPLx"], deployer),
    }
    vaults = [entry["demoVault"].lower() for entry in assets.values()]
    if len(set(vaults)) != len(vaults):
        raise ManifestBuildError("each production asset must have a distinct DemoVault")
    transaction_hashes = {
        assets[asset]["deploymentReceipt"][field].lower()
        for asset in ("SPYx", "AAPLx")
        for field in ("deploymentTxHash", "policyConfigurationTxHash")
    }
    if len(transaction_hashes) != 4:
        raise ManifestBuildError("each asset must have distinct deployment and policy receipts")

    output = deepcopy(base_manifest)
    output["contracts"] = {
        "ValtideValidationRegistry": registry,
        "ValtideRiskGuard": risk_guard,
    }
    output["assets"] = assets
    output.pop("demo", None)
    initial_deployment = output.pop("deployment", None)
    if initial_deployment is not None:
        output["initialDeployment"] = initial_deployment
    output["deploymentReceipts"] = {
        "schemaVersion": 1,
        "chainId": XLAYER_TESTNET_CHAIN_ID,
        "deployer": deployer,
        "verifiedAt": _require_timestamp(receipt.get("verifiedAt"), "receipt verifiedAt"),
    }
    return output
