import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from web3 import Web3

import valtide_api.publisher as publisher_module
from valtide_api.assets import resolve_asset_config
from valtide_api.config import Settings
from valtide_api.models import EvidenceState, ValuationResult
from valtide_api.publisher import (
    ChainPreflightError,
    EnforcementVerificationError,
    PublicationError,
    PublicationSemanticMismatchError,
    PublishabilityError,
    ReadbackMismatchError,
    _assert_readback,
    _custom_error_abi,
    _receipt_from_state,
    assert_publication_compatible,
    build_attestation,
    canonical_evidence_bytes,
    check_demo_vault_enforcement,
    classify_existing_attestation,
    decode_evaluation,
    load_deployment_config,
    publish,
    read_control_plane,
    resolve_asset_deployment,
)
from valtide_api.quant_runtime import resolve_quant_runtime

REPO_ROOT = Path(__file__).resolve().parents[3]


def _compatible_manifest(tmp_path):
    manifest = json.loads((REPO_ROOT / "deployments" / "xlayer-testnet.json").read_text())
    manifest["assets"]["NVDAx"]["publicationCompatibility"] = {
        "asset": "NVDAx",
        "referenceId": manifest["assets"]["NVDAx"]["referenceId"],
        "referenceProfile": "unified_xstock_p1ac_xperp_evidence_v1",
        "evidenceSemantics": "p1a_xstock_band_with_xperp_review_corroboration_v2",
        "modelId": "P1a-C",
        "modelVersion": "0.2.0",
    }
    path = tmp_path / "compatible-xlayer-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _legacy_nvdax_manifest():
    manifest = json.loads((REPO_ROOT / "deployments" / "xlayer-testnet.json").read_text())
    nvda = manifest["assets"]["NVDAx"]
    manifest["demo"] = {
        key: nvda[key] for key in ("assetId", "referenceId", "modelVersion")
    }
    manifest["contracts"]["DemoCollateralVault"] = nvda["demoVault"]
    manifest.pop("assets")
    manifest.pop("deploymentReceipts", None)
    manifest["deployment"] = manifest.pop("initialDeployment")
    return manifest


def _multi_asset_manifest(tmp_path):
    source = json.loads((REPO_ROOT / "deployments" / "xlayer-testnet.json").read_text())
    for index, asset in enumerate(("SPYx", "AAPLx"), start=2):
        asset_config = resolve_asset_config(asset)
        runtime = resolve_quant_runtime(asset_config)
        reference_id = publisher_module.keccak_text(asset_config.xlayer_reference_name)
        source["assets"][asset] = {
            "demoVault": "0x" + f"{index:040x}",
            "assetId": publisher_module.keccak_text(asset),
            "referenceId": reference_id,
            "modelVersion": publisher_module.keccak_text(runtime.model_version),
            "publicationCompatibility": {
                "asset": asset,
                "referenceId": reference_id,
                "referenceProfile": asset_config.reference_profile,
                "evidenceSemantics": "p1a_xstock_band_with_xperp_review_corroboration_v2",
                "modelId": runtime.model_id,
                "modelVersion": runtime.model_version,
            },
        }
    path = tmp_path / "multi-asset-manifest.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    return path, source


@pytest.fixture()
def deployment_config(tmp_path):
    return load_deployment_config(
        Settings(
            _env_file=None,
            deployment_manifest_path=_compatible_manifest(tmp_path),
            publish_validity_seconds=900,
        )
    )


@pytest.fixture()
def result():
    return ValuationResult(
        asset="NVDAx",
        timestamp=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        market_state="regular",
        last_trusted_reference=120.0,
        token_price=121.0,
        external_constructed_reference=120.5,
        valtide_fair_value=121.25,
        fair_value_lower=119.0,
        fair_value_upper=123.0,
        interval_coverage_target=0.9,
        observed_token_move_pct=0.01,
        model_implied_move_pct=0.008,
        residual_premium_discount_pct=0.002,
        reference_under_test=120.5,
        reference_under_test_source="okx_xperp_index",
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1",
        evidence_semantics="p1a_xstock_band_with_xperp_review_corroboration_v2",
        reference_under_test_ts=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        reference_under_test_age_seconds=0,
        reference_deviation_pct=0.25,
        standardized_deviation=0.4,
        evidence_state=EvidenceState.INCONCLUSIVE,
        reason_codes=["REFERENCE_DISAGREEMENT"],
        confidence=None,
        model_id="P1a-C",
        model_version="0.2.0",
        interval_semantics="price_space",
        interval_calibration_type="session_sym",
        interval_calibration_source="global",
        reference_age_seconds=0,
    )


def test_attestation_maps_enums_hashes_and_units(result, deployment_config):
    attestation = build_attestation(
        result,
        config=deployment_config,
        validity_seconds=900,
        current_chain_timestamp=int(result.timestamp.timestamp()),
    )

    assert attestation["referencePriceE8"] == 12_050_000_000
    assert attestation["fairValueE8"] == 12_125_000_000
    assert attestation["lowerBoundE8"] == 11_900_000_000
    assert attestation["upperBoundE8"] == 12_300_000_000
    assert attestation["referenceDeviationBps"] == 25
    assert attestation["evidenceState"] == 1
    assert attestation["modelVersion"] == deployment_config.model_version
    assert attestation["validUntil"] == attestation["observedAt"] + 900
    assert len(attestation["evidenceHash"]) == 66


def test_legacy_single_nvdax_and_asset_map_manifests_resolve_same_binding(
    tmp_path, deployment_config
):
    source = _legacy_nvdax_manifest()
    legacy_path = tmp_path / "legacy-nvdax-manifest.json"
    legacy_path.write_text(json.dumps(source), encoding="utf-8")
    legacy = load_deployment_config(
        Settings(_env_file=None, deployment_manifest_path=legacy_path)
    )
    assert legacy.asset_id == deployment_config.asset_id
    assert legacy.reference_id == deployment_config.reference_id
    assert legacy.model_version == deployment_config.model_version
    assert legacy.demo_vault_address == deployment_config.demo_vault_address

    nvda = source.pop("demo")
    vault = source["contracts"].pop("DemoCollateralVault")
    source["assets"] = {"NVDAx": {**nvda, "demoVault": vault}}
    path = tmp_path / "asset-map-shape.json"
    path.write_text(json.dumps(source))
    resolved = load_deployment_config(Settings(_env_file=None, deployment_manifest_path=path))
    assert resolved.asset_id == deployment_config.asset_id
    assert resolved.reference_id == deployment_config.reference_id
    assert resolved.model_version == deployment_config.model_version
    assert resolved.demo_vault_address == deployment_config.demo_vault_address

    source["assets"] = {}
    path.write_text(json.dumps(source))
    with pytest.raises(publisher_module.PublisherNotConfigured, match="no binding"):
        load_deployment_config(Settings(_env_file=None, deployment_manifest_path=path))


def test_multi_asset_manifest_resolves_three_pairs_with_shared_control_plane(tmp_path):
    path, manifest = _multi_asset_manifest(tmp_path)
    settings = Settings(
        _env_file=None,
        deployment_manifest_path=path,
        demo_vault_address="0x" + "99" * 20,
    )

    resolved = {asset: resolve_asset_deployment(asset, settings) for asset in manifest["assets"]}

    assert set(resolved) == {"NVDAx", "SPYx", "AAPLx"}
    assert len({item.asset_id for item in resolved.values()}) == 3
    assert len({item.reference_id for item in resolved.values()}) == 3
    assert len({item.model_version for item in resolved.values()}) == 2
    assert len({item.demo_vault_address.lower() for item in resolved.values()}) == 3
    assert resolved["NVDAx"].demo_vault_address == manifest["assets"]["NVDAx"]["demoVault"]
    assert resolved["SPYx"].demo_vault_address == manifest["assets"]["SPYx"]["demoVault"]
    assert resolved["AAPLx"].demo_vault_address == manifest["assets"]["AAPLx"]["demoVault"]
    assert {item.registry_address for item in resolved.values()} == {
        manifest["contracts"]["ValtideValidationRegistry"]
    }
    assert {item.risk_guard_address for item in resolved.values()} == {
        manifest["contracts"]["ValtideRiskGuard"]
    }
    assert {item.chain_id for item in resolved.values()} == {1952}
    assert {item.manifest_publisher for item in resolved.values()} == {manifest["publisher"]}
    assert resolved["SPYx"].publication_compatibility.reference_id == resolved["SPYx"].reference_id
    assert (
        resolved["AAPLx"].publication_compatibility.reference_id
        == resolved["AAPLx"].reference_id
    )


@pytest.mark.parametrize(
    ("asset", "field", "value", "message"),
    [
        ("SPYx", "assetId", "0x" + "01" * 32, "asset ID"),
        ("SPYx", "referenceId", "0x" + "02" * 32, "reference ID"),
        ("SPYx", "modelVersion", "0x" + "03" * 32, "model version"),
    ],
)
def test_multi_asset_manifest_rejects_wrong_identity_or_model(
    tmp_path, asset, field, value, message
):
    path, manifest = _multi_asset_manifest(tmp_path)
    manifest["assets"][asset][field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(publisher_module.PublisherNotConfigured, match=message):
        resolve_asset_deployment(asset, Settings(_env_file=None, deployment_manifest_path=path))


def test_multi_asset_manifest_rejects_shared_vault_and_missing_binding(tmp_path):
    path, manifest = _multi_asset_manifest(tmp_path)
    manifest["assets"]["SPYx"]["demoVault"] = manifest["assets"]["AAPLx"]["demoVault"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(_env_file=None, deployment_manifest_path=path)
    with pytest.raises(publisher_module.PublisherNotConfigured, match="reuses one DemoVault"):
        resolve_asset_deployment("SPYx", settings)

    manifest["assets"].pop("SPYx")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(publisher_module.PublisherNotConfigured, match="no binding"):
        resolve_asset_deployment("SPYx", settings)


def test_evidence_hash_input_is_deterministic_and_material(result, deployment_config):
    first = canonical_evidence_bytes(result, deployment_config)
    second = canonical_evidence_bytes(result.model_copy(), deployment_config)
    changed = result.model_copy(update={"reason_codes": ["TOKEN_DATA_UNAVAILABLE"]})

    assert first == second
    assert canonical_evidence_bytes(changed, deployment_config) != first


def test_publisher_rejects_cross_asset_result_and_deployment_binding(result, deployment_config):
    foreign_result = result.model_copy(update={"asset": "SPYx"})

    with pytest.raises(PublishabilityError):
        build_attestation(
            foreign_result,
            config=deployment_config,
            validity_seconds=900,
        )

    with pytest.raises(PublishabilityError):
        canonical_evidence_bytes(foreign_result, deployment_config)

    with pytest.raises(PublishabilityError):
        build_attestation(
            result,
            config=replace(deployment_config, asset="SPYx"),
            validity_seconds=900,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reference_under_test", None),
        ("reference_deviation_pct", None),
        ("reference_under_test_source", "stale_nvda"),
        ("fair_value_lower", 125.0),
        ("model_version", "0.1.0"),
        ("model_id", "another-model"),
        ("reference_profile", "legacy_xperp_vs_p1ac"),
    ],
)
def test_unpublishable_results_are_rejected(result, deployment_config, field, value):
    candidate = result.model_copy(update={field: value})
    with pytest.raises(PublishabilityError):
        build_attestation(candidate, config=deployment_config, validity_seconds=900)


def test_chain_stale_result_is_rejected(result, deployment_config):
    with pytest.raises(PublishabilityError):
        build_attestation(
            result,
            config=deployment_config,
            validity_seconds=900,
            current_chain_timestamp=int(result.timestamp.timestamp()) + 901,
        )


def test_idempotency_and_observation_monotonicity():
    candidate = {"observedAt": 100, "validUntil": 1000, "evidenceHash": "0x" + "11" * 32}
    assert classify_existing_attestation({"exists": False}, candidate) == "publish"
    assert (
        classify_existing_attestation(
            {
                "exists": True,
                "observedAt": 100,
                "validUntil": 1000,
                "evidenceHash": "0x" + "11" * 32,
            },
            candidate,
        )
        == "already_published"
    )
    with pytest.raises(PublishabilityError):
        classify_existing_attestation(
            {
                "exists": True,
                "observedAt": 101,
                "validUntil": 1000,
                "evidenceHash": "0x" + "22" * 32,
            },
            candidate,
        )


def test_registry_readback_mismatch_is_rejected():
    candidate = {
        "referenceId": "0x" + "01" * 32,
        "referencePriceE8": 1,
        "fairValueE8": 2,
        "lowerBoundE8": 1,
        "upperBoundE8": 3,
        "referenceDeviationBps": 4,
        "evidenceState": 1,
        "evidenceHash": "0x" + "02" * 32,
        "modelVersion": "0x" + "03" * 32,
        "observedAt": 100,
        "validUntil": 1000,
    }
    actual = {**candidate, "exists": True, "publishedAt": 101}
    _assert_readback(candidate, actual)
    with pytest.raises(ReadbackMismatchError):
        _assert_readback(candidate, {**actual, "evidenceState": 2})


def test_missing_attestation_control_plane_evaluation_is_inconclusive():
    evaluation = decode_evaluation((1, 2, False, False))

    assert evaluation == {
        "evidence_state_code": 1,
        "evidence_state": "INCONCLUSIVE",
        "policy_action_code": 2,
        "policy_action": "REQUIRE_REVIEW",
        "exists": False,
        "fresh": False,
    }


class _FakeCall:
    def __init__(self, value=None, error: Exception | None = None):
        self.value = value
        self.error = error

    def call(self):
        if self.error is not None:
            raise self.error
        return self.value


class _FakeRevert(Exception):
    def __init__(self, data):
        self.data = data


class _FakePublishCall:
    def __init__(self, registry, asset_id, input_tuple):
        self.registry = registry
        self.asset_id = asset_id
        self.input_tuple = input_tuple

    def build_transaction(self, parameters):
        self.registry.build_parameters = parameters
        self.registry.input_tuple = self.input_tuple
        return {**parameters, "data": "0xdeadbeef"}


class _FakeRegistryFunctions:
    def __init__(self, registry):
        self.registry = registry

    def getLatest(self, _asset_id, _reference_id):
        if self.registry.exists and self.registry.stale_reads_after_commit:
            self.registry.stale_reads_after_commit -= 1
            return _FakeCall((None, False))
        return _FakeCall((self.registry.attestation, self.registry.exists))

    def isFresh(self, _asset_id, _reference_id):
        return _FakeCall(self.registry.fresh)

    def isPublisher(self, _address):
        return _FakeCall(self.registry.authorized)

    def publishValidation(self, asset_id, input_tuple):
        return _FakePublishCall(self.registry, asset_id, input_tuple)


class _FakeRegistry:
    def __init__(self):
        self.functions = _FakeRegistryFunctions(self)
        self.attestation = None
        self.exists = False
        self.fresh = False
        self.authorized = True
        self.build_parameters = None
        self.input_tuple = None
        self.published_at = 777
        self.mismatch_field = None
        self.stale_reads_after_commit = 0

    def commit_input(self):
        input_tuple = self.input_tuple
        self.attestation = {
            "referenceId": "0x" + input_tuple[0].hex(),
            "referencePriceE8": int(input_tuple[1]),
            "fairValueE8": int(input_tuple[2]),
            "lowerBoundE8": int(input_tuple[3]),
            "upperBoundE8": int(input_tuple[4]),
            "referenceDeviationBps": int(input_tuple[5]),
            "evidenceState": int(input_tuple[6]),
            "evidenceHash": "0x" + input_tuple[7].hex(),
            "modelVersion": "0x" + input_tuple[8].hex(),
            "observedAt": int(input_tuple[9]),
            "publishedAt": self.published_at,
            "validUntil": int(input_tuple[10]),
        }
        if self.mismatch_field is not None:
            self.attestation[self.mismatch_field] = self.attestation[self.mismatch_field] + 1
        self.exists = True
        self.fresh = True


class _FakeGuardFunctions:
    def __init__(self, guard):
        self.guard = guard

    def registry(self):
        return _FakeCall(self.guard.registry_address)

    def getPolicy(self, _owner, _asset_id, _reference_id):
        return _FakeCall((self.guard.policy_values, self.guard.policy_configured))

    def evaluateFor(self, _owner, _asset_id, _reference_id):
        return _FakeCall(self.guard.evaluation)


class _FakeGuard:
    def __init__(self, config):
        self.functions = _FakeGuardFunctions(self)
        self.registry_address = config.registry_address
        self.evaluation = (1, 2, False, False)
        self.policy_values = (900, 0, 2, 3, 2)
        self.policy_configured = True


class _FakeVaultFunctions:
    def __init__(self, vault):
        self.vault = vault

    def riskGuard(self):
        return _FakeCall(self.vault.risk_guard_address)

    def assetId(self):
        return _FakeCall(bytes.fromhex(self.vault.asset_id[2:]))

    def referenceId(self):
        return _FakeCall(bytes.fromhex(self.vault.reference_id[2:]))

    def requestNewExposure(self, _amount):
        return _FakeCall(self.vault.call_value, self.vault.call_error)


class _FakeVault:
    def __init__(self, config):
        self.functions = _FakeVaultFunctions(self)
        self.risk_guard_address = config.risk_guard_address
        self.asset_id = config.asset_id
        self.reference_id = config.reference_id
        self.call_value = None
        self.call_error = None


class _FakeAccount:
    def __init__(self, eth):
        self.eth = eth
        self.signer = SimpleNamespace(address="0x" + "aa" * 20)
        self.sign_calls = []

    def from_key(self, _private_key):
        return self.signer

    def sign_transaction(self, transaction, private_key):
        self.sign_calls.append((transaction, private_key))
        return SimpleNamespace(raw_transaction=b"signed-transaction")


class _FakeEth:
    def __init__(self, config):
        self.chain_id = config.chain_id
        self.block_timestamp = 1_790_251_201
        self.codes = {
            config.registry_address.lower(): b"\x60\x00",
            config.risk_guard_address.lower(): b"\x60\x00",
            config.demo_vault_address.lower(): b"\x60\x00",
        }
        self.registry = _FakeRegistry()
        self.guard = _FakeGuard(config)
        self.vault = _FakeVault(config)
        self.account = _FakeAccount(self)
        self.gas_price = 10
        self.estimate_gas_calls = []
        self.sent_raw_transactions = []
        self.receipt_status = 1
        self.receipt_tx_hash = bytes.fromhex("ab" * 32)
        self.contracts = {
            config.registry_address.lower(): self.registry,
            config.risk_guard_address.lower(): self.guard,
            config.demo_vault_address.lower(): self.vault,
        }

    def get_code(self, address):
        return self.codes[address.lower()]

    def contract(self, address, abi):  # noqa: ARG002 - fake matches Web3's interface
        return self.contracts[address.lower()]

    def get_block(self, _block):
        return {"timestamp": self.block_timestamp}

    def get_transaction_count(self, _address, _status):
        return 4

    def estimate_gas(self, transaction):
        self.estimate_gas_calls.append(transaction)
        return 100_000

    def send_raw_transaction(self, raw_transaction):
        self.sent_raw_transactions.append(raw_transaction)
        return self.receipt_tx_hash

    def wait_for_transaction_receipt(self, _tx_hash, timeout):  # noqa: ARG002
        if self.receipt_status == 1:
            self.registry.commit_input()
            self.guard.evaluation = (self.registry.attestation["evidenceState"], 2, True, True)
        return {"status": self.receipt_status}


class _FakeWeb3:
    def __init__(self, config):
        self.eth = _FakeEth(config)
        self.codec = Web3().codec

    @staticmethod
    def to_checksum_address(address):
        return address


@pytest.fixture()
def publisher_settings(tmp_path):
    return Settings(
        _env_file=None,
        xlayer_rpc_url="http://fake-xlayer",
        publisher_private_key="test-private-key",
        publish_enabled=True,
        publish_validity_seconds=900,
        deployment_manifest_path=_compatible_manifest(tmp_path),
    )


@pytest.fixture()
def fake_chain(publisher_settings):
    config = load_deployment_config(publisher_settings)
    return config, _FakeWeb3(config)


def test_publish_preflight_rejects_wrong_chain(result, publisher_settings, fake_chain):
    _config, w3 = fake_chain
    w3.eth.chain_id = 1
    with pytest.raises(ChainPreflightError, match="chain ID"):
        publish(result, settings=publisher_settings, web3_client=w3)


@pytest.mark.parametrize(
    "missing_address", ["registry_address", "risk_guard_address", "demo_vault_address"]
)
def test_publish_preflight_rejects_missing_bytecode(
    result, publisher_settings, fake_chain, missing_address
):
    config, w3 = fake_chain
    w3.eth.codes[getattr(config, missing_address).lower()] = b""
    with pytest.raises(ChainPreflightError, match="bytecode"):
        publish(result, settings=publisher_settings, web3_client=w3)


def test_publish_preflight_rejects_unauthorized_signer(result, publisher_settings, fake_chain):
    _config, w3 = fake_chain
    w3.eth.registry.authorized = False
    with pytest.raises(ChainPreflightError, match="authorized"):
        publish(result, settings=publisher_settings, web3_client=w3)


def test_publish_preflight_rejects_demo_vault_bound_to_another_asset(
    result, publisher_settings, fake_chain
):
    _config, w3 = fake_chain
    w3.eth.vault.asset_id = "0x" + "99" * 32

    with pytest.raises(ChainPreflightError, match="asset ID"):
        publish(result, settings=publisher_settings, web3_client=w3)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("risk_guard_address", "0x" + "99" * 20, "different RiskGuard"),
        ("reference_id", "0x" + "88" * 32, "reference ID"),
    ],
)
def test_chain_verification_rejects_wrong_vault_binding(
    publisher_settings, fake_chain, field, value, message
):
    config, w3 = fake_chain
    if field == "risk_guard_address":
        w3.eth.vault.risk_guard_address = value
    else:
        w3.eth.vault.reference_id = value

    with pytest.raises(ChainPreflightError, match=message):
        publisher_module._verify_deployment(w3, config)


def test_read_only_preflight_rejects_unconfigured_asset_policy(publisher_settings, fake_chain):
    config, w3 = fake_chain
    w3.eth.guard.policy_configured = False

    with pytest.raises(ChainPreflightError, match="policy is not configured"):
        publisher_module._verify_deployment(w3, config)


def test_publish_rejects_result_asset_different_from_requested_asset(
    result, publisher_settings, fake_chain
):
    _config, w3 = fake_chain
    foreign_result = result.model_copy(update={"asset": "SPYx"})

    with pytest.raises(PublishabilityError, match="result asset"):
        publish(
            foreign_result,
            settings=publisher_settings,
            web3_client=w3,
            asset="NVDAx",
        )


def test_legacy_binding_is_readable_but_not_publish_compatible(
    tmp_path, result, publisher_settings, fake_chain
):
    _config, w3 = fake_chain
    legacy_path = tmp_path / "legacy-nvdax-manifest.json"
    legacy_path.write_text(json.dumps(_legacy_nvdax_manifest()), encoding="utf-8")
    legacy_settings = publisher_settings.model_copy(
        update={"deployment_manifest_path": legacy_path}
    )

    class NoRpcAccess:
        @property
        def eth(self):
            raise AssertionError("semantic mismatch must be rejected before RPC use")

    with pytest.raises(PublicationSemanticMismatchError, match="does not declare"):
        publish(result, settings=legacy_settings, web3_client=NoRpcAccess())

    assert w3.eth.sent_raw_transactions == []
    assert w3.eth.account.sign_calls == []

    status = read_control_plane(settings=legacy_settings, web3_client=w3)
    assert status["configured"] is True
    assert status["deployed"] is True
    assert status["publication_compatible"] is False
    assert status["publication_compatibility_status"] == "not_declared"


@pytest.mark.parametrize(
    "field",
    [
        "asset",
        "reference_id",
        "reference_profile",
        "evidence_semantics",
        "model_id",
        "model_version",
    ],
)
def test_publication_semantic_contract_mismatch_fails_closed(result, deployment_config, field):
    declaration = deployment_config.publication_compatibility
    assert declaration is not None
    changed = replace(declaration, **{field: f"wrong-{field}"})
    config = replace(deployment_config, publication_compatibility=changed)

    with pytest.raises(PublicationSemanticMismatchError):
        build_attestation(result, config=config, validity_seconds=900)


def test_v2_result_and_explicit_v2_declaration_are_compatible(result, deployment_config):
    resolved = assert_publication_compatible(result, config=deployment_config)

    assert resolved.publication_compatibility is not None
    assert (
        resolved.publication_compatibility.evidence_semantics
        == "p1a_xstock_band_with_xperp_review_corroboration_v2"
    )


def test_v1_result_is_rejected_by_v2_publication_contract(result, deployment_config):
    v1_result = result.model_copy(
        update={"evidence_semantics": "p1a_xstock_challenger_xperp_second_market_v1"}
    )

    with pytest.raises(PublicationSemanticMismatchError):
        build_attestation(v1_result, config=deployment_config, validity_seconds=900)


def test_v2_result_is_rejected_by_v1_publication_declaration(result, deployment_config):
    declaration = deployment_config.publication_compatibility
    assert declaration is not None
    v1_deployment = replace(
        deployment_config,
        publication_compatibility=replace(
            declaration,
            evidence_semantics="p1a_xstock_challenger_xperp_second_market_v1",
        ),
    )

    with pytest.raises(PublicationSemanticMismatchError):
        build_attestation(result, config=v1_deployment, validity_seconds=900)


def test_publish_idempotency_returns_existing_published_at(result, publisher_settings, fake_chain):
    config, w3 = fake_chain
    candidate = build_attestation(
        result,
        config=config,
        validity_seconds=900,
        current_chain_timestamp=w3.eth.block_timestamp,
    )
    w3.eth.registry.input_tuple = (
        bytes.fromhex(candidate["referenceId"][2:]),
        candidate["referencePriceE8"],
        candidate["fairValueE8"],
        candidate["lowerBoundE8"],
        candidate["upperBoundE8"],
        candidate["referenceDeviationBps"],
        candidate["evidenceState"],
        bytes.fromhex(candidate["evidenceHash"][2:]),
        bytes.fromhex(candidate["modelVersion"][2:]),
        candidate["observedAt"],
        candidate["validUntil"],
    )
    w3.eth.registry.commit_input()
    w3.eth.registry.published_at = 987
    w3.eth.registry.attestation["publishedAt"] = 987
    w3.eth.guard.evaluation = (1, 2, True, True)

    receipt = publish(result, settings=publisher_settings, web3_client=w3)

    assert receipt.status == "already_published"
    assert receipt.tx_hash is None
    assert receipt.published_at == 987
    assert w3.eth.sent_raw_transactions == []


def test_publish_success_exercises_signed_write_and_readback(
    result, publisher_settings, fake_chain
):
    config, w3 = fake_chain
    receipt = publish(result, settings=publisher_settings, web3_client=w3)
    candidate = build_attestation(
        result,
        config=config,
        validity_seconds=900,
        current_chain_timestamp=w3.eth.block_timestamp,
    )
    actual = w3.eth.registry.attestation

    assert receipt.status == "published"
    assert receipt.tx_hash == "0x" + "ab" * 32
    assert receipt.exists is True
    assert receipt.published_at == 777
    assert receipt.evidence_state == "INCONCLUSIVE"
    assert receipt.policy_action == "REQUIRE_REVIEW"
    assert w3.eth.sent_raw_transactions == [b"signed-transaction"]
    assert len(w3.eth.account.sign_calls) == 1
    assert len(w3.eth.estimate_gas_calls) == 1
    assert actual["referenceId"] == candidate["referenceId"]
    assert actual["referencePriceE8"] == candidate["referencePriceE8"]
    assert actual["fairValueE8"] == candidate["fairValueE8"]
    assert actual["lowerBoundE8"] == candidate["lowerBoundE8"]
    assert actual["upperBoundE8"] == candidate["upperBoundE8"]
    assert actual["referenceDeviationBps"] == candidate["referenceDeviationBps"]
    assert actual["evidenceState"] == candidate["evidenceState"]
    assert actual["evidenceHash"] == candidate["evidenceHash"]
    assert actual["modelVersion"] == candidate["modelVersion"]
    assert actual["observedAt"] == candidate["observedAt"]
    assert actual["validUntil"] == candidate["validUntil"]


def test_publish_retries_transient_stale_readback(
    result, publisher_settings, fake_chain, monkeypatch
):
    _config, w3 = fake_chain
    w3.eth.registry.stale_reads_after_commit = 1
    monkeypatch.setattr(publisher_module.time, "sleep", lambda _seconds: None)

    receipt = publish(result, settings=publisher_settings, web3_client=w3)

    assert receipt.status == "published"
    assert receipt.tx_hash == "0x" + "ab" * 32
    assert receipt.published_at == 777


def test_receipt_without_attestation_keeps_published_at_none(deployment_config):
    candidate = {
        "observedAt": 100,
        "validUntil": 1000,
        "evidenceHash": "0x" + "11" * 32,
        "evidenceState": 1,
    }
    receipt = _receipt_from_state(
        "already_published",
        None,
        deployment_config,
        candidate,
        {"attestation": None, "exists": False, "fresh": False, "policy_action": "REQUIRE_REVIEW"},
    )

    assert receipt.published_at is None


def test_publish_failed_receipt_raises_publication_error(result, publisher_settings, fake_chain):
    _config, w3 = fake_chain
    w3.eth.receipt_status = 0
    with pytest.raises(PublicationError, match="reverted"):
        publish(result, settings=publisher_settings, web3_client=w3)


def test_publish_readback_mismatch_raises(result, publisher_settings, fake_chain):
    _config, w3 = fake_chain
    w3.eth.registry.mismatch_field = "fairValueE8"
    with pytest.raises(ReadbackMismatchError, match="fairValueE8"):
        publish(result, settings=publisher_settings, web3_client=w3)


def _new_exposure_error(w3, evaluation):
    selector, input_types = _custom_error_abi(
        "DemoCollateralVault", "NewExposureNotAllowed"
    )
    encoded = w3.codec.encode(
        input_types,
        (
            evaluation["evidence_state_code"],
            evaluation["policy_action_code"],
            evaluation["exists"],
            evaluation["fresh"],
        ),
    )
    return bytes.fromhex(selector[2:]) + encoded


@pytest.mark.parametrize("policy_code", [0, 1])
def test_demo_vault_allow_and_monitor_require_success(policy_code, fake_chain):
    _config, w3 = fake_chain
    w3.eth.guard.evaluation = (0, policy_code, True, True)
    w3.eth.vault.call_value = policy_code

    result = check_demo_vault_enforcement(
        settings=Settings(
            xlayer_rpc_url="http://fake-xlayer",
            deployment_manifest_path=REPO_ROOT / "deployments" / "xlayer-testnet.json",
        ),
        web3_client=w3,
    )

    assert result["passed"] is True
    assert result["returned_action_code"] == policy_code
    assert result["reverted"] is False


@pytest.mark.parametrize("policy_code", [2, 3])
def test_demo_vault_restrictive_policy_requires_specific_custom_error(policy_code, fake_chain):
    _config, w3 = fake_chain
    w3.eth.guard.evaluation = (1, policy_code, False, False)
    w3.eth.vault.call_error = _FakeRevert(
        _new_exposure_error(w3, {
            "evidence_state_code": 1,
            "policy_action_code": policy_code,
            "exists": False,
            "fresh": False,
        })
    )

    result = check_demo_vault_enforcement(
        settings=Settings(
            xlayer_rpc_url="http://fake-xlayer",
            deployment_manifest_path=REPO_ROOT / "deployments" / "xlayer-testnet.json",
        ),
        web3_client=w3,
    )

    assert result["passed"] is True
    assert result["reverted"] is True
    assert result["returned_action_code"] is None


def test_demo_vault_unrelated_exception_is_not_enforcement_success(fake_chain):
    _config, w3 = fake_chain
    w3.eth.guard.evaluation = (1, 2, False, False)
    w3.eth.vault.call_error = RuntimeError("RPC transport failed")

    with pytest.raises(EnforcementVerificationError, match="expected NewExposureNotAllowed"):
        check_demo_vault_enforcement(
            settings=Settings(
                xlayer_rpc_url="http://fake-xlayer",
                deployment_manifest_path=REPO_ROOT / "deployments" / "xlayer-testnet.json",
            ),
            web3_client=w3,
        )
