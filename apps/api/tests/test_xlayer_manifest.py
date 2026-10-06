import json
from pathlib import Path

import pytest

from valtide_api.assets import resolve_asset_config
from valtide_api.config import Settings
from valtide_api.publisher import keccak_text, resolve_asset_deployment
from valtide_api.quant_runtime import resolve_quant_runtime
from valtide_api.xlayer_manifest import (
    SHARED_REGISTRY,
    SHARED_RISK_GUARD,
    ManifestBuildError,
    build_multi_asset_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _verified_receipt():
    assets = {}
    for index, asset in enumerate(("SPYx", "AAPLx"), start=1):
        config = resolve_asset_config(asset)
        runtime = resolve_quant_runtime(config)
        assets[asset] = {
            "demoVault": "0x" + f"{index:040x}",
            "assetId": keccak_text(asset),
            "referenceId": keccak_text(config.xlayer_reference_name),
            "modelVersion": keccak_text(runtime.model_version),
            "deployer": "0x" + "ab" * 20,
            "deploymentTxHash": "0x" + f"{index:064x}",
            "deploymentBlockNumber": 100 + index,
            "deploymentTimestamp": "2026-10-01T00:00:00Z",
            "policyConfigurationTxHash": "0x" + f"{index + 10:064x}",
            "policyBlockNumber": 110 + index,
            "policyTimestamp": "2026-10-01T00:05:00Z",
            "policyVerified": True,
            "policy": {
                "maxAge": 900,
                "onSupported": 0,
                "onInconclusive": 2,
                "onChallenged": 3,
                "onStale": 2,
            },
        }
    return {
        "verified": True,
        "verifiedAt": "2026-10-01T01:00:00Z",
        "chainId": 1952,
        "registry": SHARED_REGISTRY,
        "riskGuard": SHARED_RISK_GUARD,
        "deployer": "0x" + "ab" * 20,
        "assets": assets,
    }


def test_builder_makes_assets_map_canonical_and_keeps_shared_contracts():
    base = json.loads((REPO_ROOT / "deployments" / "xlayer-testnet.json").read_text())

    manifest = build_multi_asset_manifest(base, _verified_receipt())

    assert set(manifest["assets"]) == {"NVDAx", "SPYx", "AAPLx"}
    assert manifest["contracts"] == {
        "ValtideValidationRegistry": SHARED_REGISTRY,
        "ValtideRiskGuard": SHARED_RISK_GUARD,
    }
    assert "demo" not in manifest
    assert "DemoCollateralVault" not in manifest["contracts"]
    assert "deployment" not in manifest
    assert manifest["initialDeployment"] == base["deployment"]
    assert manifest["assets"]["NVDAx"]["demoVault"] == base["contracts"]["DemoCollateralVault"]
    assert manifest["assets"]["SPYx"]["publicationCompatibility"]["referenceId"] == (
        manifest["assets"]["SPYx"]["referenceId"]
    )
    assert manifest["assets"]["NVDAx"]["publicationCompatibility"]["modelVersion"] == "0.2.0"
    assert manifest["assets"]["SPYx"]["publicationCompatibility"]["modelVersion"] == "0.3.0"
    assert manifest["assets"]["AAPLx"]["deploymentReceipt"]["policyConfigurationTxHash"]
    assert manifest["deploymentReceipts"]["chainId"] == 1952


def test_built_canonical_manifest_resolves_all_three_asset_bindings(tmp_path):
    base = json.loads((REPO_ROOT / "deployments" / "xlayer-testnet.json").read_text())
    manifest = build_multi_asset_manifest(base, _verified_receipt())
    path = tmp_path / "canonical-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(_env_file=None, deployment_manifest_path=path)

    resolved = {
        asset: resolve_asset_deployment(asset, settings)
        for asset in ("NVDAx", "SPYx", "AAPLx")
    }

    assert resolved["NVDAx"].demo_vault_address == base["contracts"]["DemoCollateralVault"]
    assert resolved["SPYx"].demo_vault_address == manifest["assets"]["SPYx"]["demoVault"]
    assert resolved["AAPLx"].demo_vault_address == manifest["assets"]["AAPLx"]["demoVault"]
    assert len({binding.asset_id for binding in resolved.values()}) == 3
    assert len({binding.reference_id for binding in resolved.values()}) == 3
    assert {binding.registry_address for binding in resolved.values()} == {
        manifest["contracts"]["ValtideValidationRegistry"]
    }
    assert {binding.risk_guard_address for binding in resolved.values()} == {
        manifest["contracts"]["ValtideRiskGuard"]
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update(verified=False),
        lambda receipt: receipt.update(chainId=1),
        lambda receipt: receipt.update(registry="0x" + "01" * 20),
        lambda receipt: receipt["assets"]["SPYx"].update(policyVerified=False),
        lambda receipt: receipt["assets"]["SPYx"].update(assetId="0x" + "00" * 32),
        lambda receipt: receipt["assets"]["SPYx"].update(
            demoVault=receipt["assets"]["AAPLx"]["demoVault"]
        ),
        lambda receipt: receipt["assets"]["AAPLx"].update(deployer="0x" + "cd" * 20),
        lambda receipt: receipt["assets"]["AAPLx"].update(
            deploymentTxHash=receipt["assets"]["SPYx"]["deploymentTxHash"]
        ),
        lambda receipt: receipt["assets"]["SPYx"]["policy"].update(maxAge=60),
    ],
)
def test_builder_rejects_unverified_or_inconsistent_deployment_data(mutate):
    base = json.loads((REPO_ROOT / "deployments" / "xlayer-testnet.json").read_text())
    receipt = _verified_receipt()
    mutate(receipt)

    with pytest.raises(ManifestBuildError):
        build_multi_asset_manifest(base, receipt)


def test_builder_never_fabricates_missing_new_asset_receipts():
    base = json.loads((REPO_ROOT / "deployments" / "xlayer-testnet.json").read_text())
    receipt = _verified_receipt()
    del receipt["assets"]["AAPLx"]

    with pytest.raises(ManifestBuildError, match="exactly SPYx and AAPLx"):
        build_multi_asset_manifest(base, receipt)
