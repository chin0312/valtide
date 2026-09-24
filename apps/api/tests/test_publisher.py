from datetime import UTC, datetime
from pathlib import Path

import pytest

from valtide_api.config import Settings
from valtide_api.models import EvidenceState, ValuationResult
from valtide_api.publisher import (
    PublishabilityError,
    ReadbackMismatchError,
    _assert_readback,
    build_attestation,
    canonical_evidence_bytes,
    classify_existing_attestation,
    decode_evaluation,
    load_deployment_config,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def deployment_config():
    return load_deployment_config(
        Settings(
            deployment_manifest_path=REPO_ROOT / "deployments" / "xlayer-testnet.json",
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
        reference_under_test_ts=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        reference_under_test_age_seconds=0,
        reference_deviation_pct=0.25,
        standardized_deviation=0.4,
        evidence_state=EvidenceState.INCONCLUSIVE,
        reason_codes=["REFERENCE_DISAGREEMENT"],
        confidence=None,
        model_id="valtide-p1ac",
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


def test_evidence_hash_input_is_deterministic_and_material(result, deployment_config):
    first = canonical_evidence_bytes(result, deployment_config)
    second = canonical_evidence_bytes(result.model_copy(), deployment_config)
    changed = result.model_copy(update={"reason_codes": ["TOKEN_DATA_UNAVAILABLE"]})

    assert first == second
    assert canonical_evidence_bytes(changed, deployment_config) != first


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reference_under_test", None),
        ("reference_deviation_pct", None),
        ("reference_under_test_source", "stale_nvda"),
        ("fair_value_lower", 125.0),
        ("model_version", "0.1.0"),
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
