"""Validation engine tests — the core product logic.

Uses a fixed challenger estimate and varies the reference under test to exercise
each Evidence State and override path.
"""

import math
from datetime import UTC, datetime, timedelta

import pytest

from valtide_api import replay as replay_module
from valtide_api.challenger_detector import resolve_challenger_detector
from valtide_api.models import (
    ChallengerEstimate,
    EvidenceState,
    MarketSnapshot,
    MarketState,
    ValuationResult,
)
from valtide_api.state_store import KalmanState
from valtide_api.validation import Thresholds, validate


def _estimate(fair_value: float = 185.70, sd_log: float = 0.008) -> ChallengerEstimate:
    m = math.log(fair_value)
    return ChallengerEstimate(
        fair_value=fair_value,
        lower_bound=math.exp(m - 1.645 * sd_log),
        upper_bound=math.exp(m + 1.645 * sd_log),
        state_m=m,
        state_sd_log=sd_log,
        reference_predictive_sd_log=sd_log,
        coverage_target=0.90,
        state_m_after_nvda=m,
        state_P_after_nvda=sd_log**2,
        model_id="P1a-C",
        model_version="0.2.0",
        interval_semantics="reference_equivalent_predictive",
    )


def _production_estimate(asset: str) -> ChallengerEstimate:
    version = "0.2.0" if asset == "NVDAx" else "0.3.0"
    return _estimate().model_copy(update={"model_version": version})


def _snapshot(reference_under_test: float | None, **overrides) -> MarketSnapshot:
    base = dict(
        asset="NVDAx",
        observation_ts=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
        token_price=185.10,
        token_volume=50_000.0,
        underlying_reference=None,
        underlying_reference_ts=None,
        last_trusted_reference=180.00,
        last_trusted_reference_ts=datetime(2026, 9, 19, 20, 0, tzinfo=UTC),
        reference_age_seconds=64_800,
        reference_under_test=reference_under_test,
        reference_under_test_source="calibrated_reference_fixture",
        market_state=MarketState.CLOSED,
    )
    base.update(overrides)
    return MarketSnapshot(**base)


def test_supported_when_reference_near_fair_value():
    # Reference ~= fair value -> |z| small -> SUPPORTED.
    result = validate(_snapshot(185.70), _estimate())
    assert result.evidence_state == EvidenceState.SUPPORTED
    assert abs(result.standardized_deviation) < 1.0


def test_challenged_when_reference_far_above():
    # Reference $190 vs fair $185.70 with tight sd -> large z -> CHALLENGED.
    result = validate(_snapshot(190.00), _estimate())
    assert result.evidence_state == EvidenceState.CHALLENGED
    assert result.standardized_deviation > 2.0
    assert "REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL" in result.reason_codes


def test_inconclusive_between_thresholds():
    # Choose a reference giving 1 <= |z| < 2.
    est = _estimate()
    target_z = 1.5
    pt = math.exp(est.state_m + target_z * est.state_sd_log)
    result = validate(_snapshot(pt), est)
    assert result.evidence_state == EvidenceState.INCONCLUSIVE


def test_stale_reference_forces_inconclusive():
    # Even a far reference is abstained when the underlying is pathologically old
    # (beyond a normal weekend gap).
    result = validate(
        _snapshot(190.00, reference_age_seconds=80 * 3600),  # > 72h
        _estimate(),
    )
    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "UNDERLYING_REFERENCE_STALE" in result.reason_codes


def test_stale_reference_under_test_forces_inconclusive():
    result = validate(
        _snapshot(190.00, reference_under_test_age_seconds=80 * 3600),
        _estimate(),
    )
    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "REFERENCE_UNDER_TEST_STALE" in result.reason_codes


def test_high_uncertainty_forces_inconclusive():
    # A wide interval (high sd) should abstain rather than challenge.
    result = validate(_snapshot(190.00), _estimate(sd_log=0.10))
    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "MODEL_UNCERTAINTY_HIGH" in result.reason_codes


def test_z_score_is_log_space():
    # z = (ln(Pt) - m) / sd_log, independent of price-space asymmetry.
    est = _estimate()
    pt = 190.00
    result = validate(_snapshot(pt), est)
    expected_z = (math.log(pt) - est.state_m) / est.state_sd_log
    assert result.standardized_deviation == expected_z


def test_derived_quantities():
    result = validate(_snapshot(190.00), _estimate())
    # observed token move = 185.10/180 - 1 = +2.833%
    assert round(result.observed_token_move_pct, 2) == 2.83
    # reference deviation = 190/185.70 - 1 = +2.316%
    assert round(result.reference_deviation_pct, 2) == 2.32


def test_xstock_and_xperp_are_explicit_pairwise_evidence_not_a_new_state_rule():
    snapshot = _snapshot(
        190.0,
        reference_under_test_source="okx_xperp_index",
        xperp_index_price=190.0,
        xperp_index_source="okx_xperp_index",
        xperp_index_ts=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
    )

    result = validate(snapshot, _estimate())

    assert result.xperp_index_price == 190.0
    assert result.xperp_index_source == "okx_xperp_index"
    assert result.xstock_vs_p1ac_deviation_pct == pytest.approx(
        (185.10 / 185.70 - 1) * 100
    )
    assert result.xperp_vs_p1ac_deviation_pct == pytest.approx(
        (190.0 / 185.70 - 1) * 100
    )
    assert result.xstock_vs_xperp_deviation_pct == pytest.approx(
        (185.10 / 190.0 - 1) * 100
    )
    # No X-Perp-specific residual calibration exists. Pairwise values remain
    # descriptive and the backend abstains rather than applying unrelated gates.
    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert result.standardized_deviation is None
    assert result.xperp_deviation_scaled_by_model_predictive_sd is not None
    assert "XPERP_RESIDUAL_CALIBRATION_UNVERIFIED" in result.reason_codes
    assert result.evidence_state_basis == (
        "xperp_residual_calibration_unverified"
    )


def _detector_snapshot(asset: str, score_bps: float, *, xperp_matches_challenger=True, **overrides):
    timestamp = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    estimate = _estimate()
    token = math.exp(estimate.state_m + score_bps / 10_000)
    xperp = estimate.fair_value if xperp_matches_challenger else token
    values = {
        "asset": asset,
        "token_price": token,
        "underlying_reference": estimate.fair_value,
        "underlying_reference_ts": timestamp,
        "reference_under_test": xperp,
        "reference_under_test_source": "okx_xperp_index",
        "reference_under_test_ts": timestamp,
        "reference_under_test_age_seconds": 0,
        "xperp_index_price": xperp,
        "xperp_index_source": "okx_xperp_index",
        "xperp_index_ts": timestamp,
        "observation_ts": timestamp,
        "reference_profile": "unified_xstock_p1ac_xperp_evidence_v1",
    }
    values.update(overrides)
    values.pop("reference_under_test")
    return _snapshot(xperp, **values)


def _detector_snapshot_at_score(asset: str, score: float, **overrides):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    score_bps = (
        score * _estimate().reference_predictive_sd_log * 10_000
        if spec.score_name == "disagreement_z"
        else score
    )
    return _detector_snapshot(asset, score_bps, **overrides)


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_production_tail_detector_works_without_same_time_underlying(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    estimate = _production_estimate(asset)
    snapshot = _detector_snapshot_at_score(
        asset,
        spec.threshold_challenge + 1,
        xperp_matches_challenger=True,
        underlying_reference=None,
        underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
        market_state=MarketState.CLOSED,
    )

    result = validate(snapshot, estimate)

    assert result.evidence_state == EvidenceState.CHALLENGED
    assert result.challenger_detector is not None
    assert result.challenger_detector.research_band == "review"
    assert "P1A_XSTOCK_REVIEW_BAND" in result.reason_codes
    assert "XPERP_CORROBORATES_P1A" in result.reason_codes
    assert result.standardized_deviation is None
    assert result.validation_target == "xstock_observed_price"
    assert result.evidence_semantics == "p1a_xstock_band_with_xperp_review_corroboration_v2"
    assert result.xperp_role == "second_market_challenger"
    assert "UNDERLYING_REFERENCE_NOT_CONTEMPORANEOUS" not in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_unified_evidence_does_not_vote_on_contemporaneous_underlying_value(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    estimate = _production_estimate(asset)
    snapshot = _detector_snapshot_at_score(
        asset,
        spec.threshold_challenge + 1,
        xperp_matches_challenger=True,
        underlying_reference=None,
        underlying_reference_ts=None,
    )
    no_current_underlying = validate(snapshot, estimate)
    with_unrelated_current_underlying = validate(
        snapshot.model_copy(
            update={
                "underlying_reference": 900.0,
                "underlying_reference_ts": snapshot.observation_ts,
            }
        ),
        estimate,
    )

    assert no_current_underlying.evidence_state == EvidenceState.CHALLENGED
    assert with_unrelated_current_underlying.evidence_state == EvidenceState.CHALLENGED
    assert "TOKEN_UNIT_SUSPECT" not in with_unrelated_current_underlying.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_xperp_contradiction_abstains_without_same_time_underlying(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    estimate = _production_estimate(asset)
    snapshot = _detector_snapshot_at_score(
        asset,
        spec.threshold_challenge + 1,
        xperp_matches_challenger=False,
        underlying_reference=None,
        underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
        market_state=MarketState.OVERNIGHT,
    )

    result = validate(snapshot, estimate)

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_CORROBORATES_XSTOCK" in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_detector_watch_band_does_not_become_a_canonical_state(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    estimate = _production_estimate(asset)
    snapshot = _detector_snapshot_at_score(
        asset,
        (spec.threshold_review + spec.threshold_challenge) / 2,
    )

    result = validate(snapshot, estimate)

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert result.challenger_detector is not None
    assert result.challenger_detector.research_band == "watch"
    assert "P1A_XSTOCK_WATCH_BAND" in result.reason_codes


def test_spy_detector_does_not_require_contemporaneous_underlying_and_qqq_is_not_promoted():
    spy_spec = resolve_challenger_detector("SPYx")
    qqq_spec = resolve_challenger_detector("QQQx")
    assert spy_spec is not None and qqq_spec is not None
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    timestamp = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)

    no_truth = validate(
        _detector_snapshot(
            "SPYx",
            spy_spec.threshold_challenge + 1,
            underlying_reference_ts=timestamp - timedelta(minutes=5),
        ),
        estimate,
    )
    qqq = validate(
        _detector_snapshot(
            "QQQx",
            qqq_spec.threshold_challenge + 1,
        ),
        estimate,
    )

    assert no_truth.evidence_state == EvidenceState.CHALLENGED
    assert "UNDERLYING_REFERENCE_NOT_CONTEMPORANEOUS" not in no_truth.reason_codes
    assert "XPERP_CORROBORATES_P1A" in no_truth.reason_codes
    assert qqq.evidence_state == EvidenceState.INCONCLUSIVE
    assert "P1A_XSTOCK_CHALLENGE_NOT_PROMOTED" in qqq.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_production_detector_abstains_for_missing_xperp_or_token(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    estimate = _production_estimate(asset)
    snapshot = _detector_snapshot_at_score(asset, spec.threshold_challenge + 1)

    missing_xperp = validate(
        snapshot.model_copy(
            update={
                "reference_under_test": None,
                "reference_under_test_ts": None,
                "reference_under_test_age_seconds": None,
                "xperp_index_price": None,
                "xperp_index_ts": None,
            }
        ),
        estimate,
    )
    missing_token = validate(
        snapshot.model_copy(update={"token_price": None, "token_volume": None}),
        estimate,
    )

    assert missing_xperp.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_UNAVAILABLE" in missing_xperp.reason_codes
    assert "XPERP_EVIDENCE_UNCALIBRATED" not in missing_xperp.reason_codes
    assert missing_token.evidence_state == EvidenceState.INCONCLUSIVE
    assert "TOKEN_DATA_UNAVAILABLE" in missing_token.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_missing_xperp_also_blocks_support_state(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    snapshot = _detector_snapshot_at_score(asset, spec.threshold_review / 2).model_copy(
        update={
            "reference_under_test": None,
            "reference_under_test_ts": None,
            "reference_under_test_age_seconds": None,
            "xperp_index_price": None,
            "xperp_index_ts": None,
        }
    )
    result = validate(
        snapshot,
        _production_estimate(asset),
    )

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "P1A_XSTOCK_SUPPORT_BAND" in result.reason_codes
    assert "XPERP_EVIDENCE_UNAVAILABLE" in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_support_band_rejects_wrong_source_or_nonexact_xperp(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    base = _detector_snapshot_at_score(asset, spec.threshold_review / 2)
    estimate = _production_estimate(asset)

    wrong_source = validate(
        base.model_copy(
            update={
                "xperp_index_source": "other_market",
                "reference_under_test_source": "other_market",
            }
        ),
        estimate,
    )
    stale = validate(
        base.model_copy(
            update={
                "xperp_index_ts": base.observation_ts - timedelta(minutes=5),
                "reference_under_test_ts": base.observation_ts - timedelta(minutes=5),
                "reference_under_test_age_seconds": 300,
            }
        ),
        estimate,
    )
    invalid = validate(
        base.model_copy(
            update={
                "xperp_index_price": math.nan,
                "reference_under_test": math.nan,
            }
        ),
        estimate,
    )

    assert wrong_source.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_UNAVAILABLE" in wrong_source.reason_codes
    assert stale.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_STALE" in stale.reason_codes
    assert invalid.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_STALE" in invalid.reason_codes
    assert invalid.xperp_vs_p1ac_deviation_pct is None
    assert invalid.xstock_vs_xperp_deviation_pct is None


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_invalid_model_uncertainty_blocks_tri_source_state(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    result = validate(
        _detector_snapshot_at_score(asset, spec.threshold_review / 2),
        _estimate(sd_log=0).model_copy(
            update={"model_version": "0.2.0" if asset == "NVDAx" else "0.3.0"}
        ),
    )

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "MODEL_UNCERTAINTY_INVALID" in result.reason_codes
    assert "XPERP_CORROBORATES_XSTOCK" not in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_high_model_uncertainty_and_stale_anchor_block_tri_source_support(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    snapshot = _detector_snapshot_at_score(asset, spec.threshold_review / 2)

    high_uncertainty = validate(
        snapshot,
        _estimate(sd_log=0.10).model_copy(
            update={"model_version": "0.2.0" if asset == "NVDAx" else "0.3.0"}
        ),
    )
    stale_anchor = validate(
        snapshot.model_copy(update={"reference_age_seconds": 80 * 3600}),
        _production_estimate(asset),
    )

    assert high_uncertainty.evidence_state == EvidenceState.INCONCLUSIVE
    assert "MODEL_UNCERTAINTY_HIGH" in high_uncertainty.reason_codes
    assert stale_anchor.evidence_state == EvidenceState.INCONCLUSIVE
    assert "UNDERLYING_REFERENCE_STALE" in stale_anchor.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_production_detector_abstains_for_stale_or_ambiguous_xperp(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    timestamp = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    estimate = _production_estimate(asset)
    base = _detector_snapshot_at_score(asset, spec.threshold_challenge + 1)

    stale = validate(
        base.model_copy(
            update={
                "xperp_index_ts": timestamp - timedelta(minutes=5),
                "reference_under_test_ts": timestamp - timedelta(minutes=5),
                "reference_under_test_age_seconds": 300,
            }
        ),
        estimate,
    )
    assert stale.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_STALE" in stale.reason_codes

    midpoint = math.exp(
        (estimate.state_m + math.log(base.token_price)) / 2
    )
    ambiguous = validate(
        base.model_copy(
            update={
                "reference_under_test": midpoint,
                "xperp_index_price": midpoint,
            }
        ),
        estimate,
    )
    assert ambiguous.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_AMBIGUOUS" in ambiguous.reason_codes


def test_research_only_qqq_detector_cannot_escalate_canonical_evidence():
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    result = validate(
        _detector_snapshot(
            "QQQx",
            500,
            underlying_reference=None,
            underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
        ),
        estimate,
    )

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "P1A_XSTOCK_CHALLENGE_NOT_PROMOTED" in result.reason_codes
    assert "XPERP_CORROBORATES_P1A" not in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_support_band_and_xperp_closer_to_xstock_can_emit_supported_without_truth(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    score = min(spec.threshold_review / 2, 20.0)
    snapshot = _detector_snapshot_at_score(
        asset,
        score,
        xperp_matches_challenger=False,
        underlying_reference=None,
        underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
        market_state=MarketState.OVERNIGHT,
    )
    result = validate(
        snapshot,
        _estimate().model_copy(update={"model_version": "0.3.0"}),
    )

    assert result.evidence_state == EvidenceState.SUPPORTED
    assert "P1A_XSTOCK_SUPPORT_BAND" in result.reason_codes
    assert "XPERP_CORROBORATES_XSTOCK" in result.reason_codes
    assert "UNDERLYING_REFERENCE_NOT_CONTEMPORANEOUS" not in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_support_band_emits_supported_for_any_valid_xperp_direction(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    estimate = _production_estimate(asset)
    p1a_side_snapshot = _detector_snapshot_at_score(asset, spec.threshold_review / 2)
    sided_with_p1a = validate(p1a_side_snapshot, estimate)
    token_and_model_equal = validate(
        _detector_snapshot(asset, 0),
        estimate,
    )

    assert sided_with_p1a.evidence_state == EvidenceState.SUPPORTED
    assert "XPERP_CORROBORATES_P1A" in sided_with_p1a.reason_codes
    assert token_and_model_equal.evidence_state == EvidenceState.SUPPORTED
    assert "XPERP_EVIDENCE_AMBIGUOUS" in token_and_model_equal.reason_codes
    assert "TOKEN_AND_CHALLENGER_AGREE" in token_and_model_equal.reason_codes

    # xStock/P1a agreement is descriptive only. Exact-time X-Perp availability
    # is still required before the tri-source classifier can emit SUPPORTED.
    without_xperp = validate(
        p1a_side_snapshot.model_copy(
            update={
                "reference_under_test": None,
                "reference_under_test_ts": None,
                "reference_under_test_age_seconds": None,
                "xperp_index_price": None,
                "xperp_index_source": None,
                "xperp_index_ts": None,
            }
        ),
        estimate,
    )
    assert without_xperp.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_UNAVAILABLE" in without_xperp.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_asset_enabled_tri_source_review_band_can_emit_challenged(asset):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    result = validate(
        _detector_snapshot_at_score(
            asset,
            spec.threshold_challenge + 1,
            xperp_matches_challenger=True,
            underlying_reference=None,
            underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
            market_state=MarketState.CLOSED,
        ),
        _production_estimate(asset),
    )

    assert result.evidence_state == EvidenceState.CHALLENGED
    assert "P1A_XSTOCK_REVIEW_BAND" in result.reason_codes
    assert "XPERP_CORROBORATES_P1A" in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_operational_inference_and_historical_replay_share_the_same_classifier(
    monkeypatch, asset
):
    spec = resolve_challenger_detector(asset)
    assert spec is not None
    snapshot = _detector_snapshot_at_score(
        asset,
        spec.threshold_challenge + 1,
        xperp_matches_challenger=True,
        underlying_reference=None,
        underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
        market_state=MarketState.OVERNIGHT,
    )

    fixed_estimate = _production_estimate(asset)

    def fixed_quant_step(current_snapshot, _prior):
        return fixed_estimate, KalmanState(
            m=fixed_estimate.state_m_after_nvda,
            P=fixed_estimate.state_P_after_nvda,
            last_ts=current_snapshot.observation_ts,
        )

    monkeypatch.setattr(replay_module, "_quant_step", fixed_quant_step)
    operational, _state = replay_module.run_inference(snapshot, None)
    historical = replay_module.replay([snapshot])[0]
    direct_validation = validate(snapshot, fixed_estimate)

    assert operational.evidence_state == direct_validation.evidence_state
    assert operational.reason_codes == direct_validation.reason_codes
    assert historical.evidence_state == direct_validation.evidence_state
    assert historical.reason_codes == direct_validation.reason_codes
    assert operational.evidence_state == EvidenceState.CHALLENGED


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "AAPLx"])
def test_unified_support_band_needs_healthy_exact_xperp_but_not_direction(asset):
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    result = validate(_detector_snapshot(asset, 0), estimate)

    assert result.evidence_state == EvidenceState.SUPPORTED
    assert result.evidence_semantics == "p1a_xstock_band_with_xperp_review_corroboration_v2"
    assert result.evidence_state_basis == (
        "frozen_p1a_xstock_support_band_with_exact_xperp_available"
    )


def test_research_only_qqq_does_not_gain_v2_state_authority():
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    result = validate(_detector_snapshot("QQQx", 0), estimate)

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "P1A_XSTOCK_SUPPORT_NOT_PROMOTED" in result.reason_codes


def test_unified_xperp_source_mismatch_is_unavailable_not_a_reference_vote():
    spec = resolve_challenger_detector("SPYx")
    assert spec is not None
    snapshot = _detector_snapshot("SPYx", spec.threshold_challenge + 1)
    snapshot = snapshot.model_copy(
        update={"xperp_index_source": "other_source", "reference_under_test_source": "other_source"}
    )

    result = validate(snapshot, _estimate().model_copy(update={"model_version": "0.3.0"}))

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_EVIDENCE_UNAVAILABLE" in result.reason_codes


def test_legacy_valuation_json_gets_compatible_semantic_defaults():
    payload = validate(_snapshot(185.70), _estimate()).model_dump()
    payload.pop("validation_target")
    payload.pop("evidence_semantics")
    payload.pop("xperp_role")

    restored = ValuationResult.model_validate(payload)

    assert restored.validation_target == "reference_under_test"
    assert restored.evidence_semantics == "legacy_reference_under_test_v1"
    assert restored.xperp_role == "reference_under_test"


def test_custom_thresholds_respected():
    # Tightening z_challenge to 1.0 turns a mild deviation into CHALLENGED.
    est = _estimate()
    pt = math.exp(est.state_m + 1.2 * est.state_sd_log)
    strict = Thresholds(z_support=0.5, z_challenge=1.0)
    result = validate(_snapshot(pt), est, thresholds=strict)
    assert result.evidence_state == EvidenceState.CHALLENGED


def test_missing_token_is_inconclusive_without_token_derived_fields():
    result = validate(_snapshot(190.00, token_price=None, token_volume=None), _estimate())

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "TOKEN_DATA_UNAVAILABLE" in result.reason_codes
    assert result.observed_token_move_pct is None
    assert result.residual_premium_discount_pct is None
    assert "TOKEN_AND_CHALLENGER_AGREE" not in result.reason_codes


def test_missing_reference_is_inconclusive_without_deviation_fields():
    result = validate(_snapshot(None), _estimate())

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "COMPARATOR_UNAVAILABLE" in result.reason_codes
    assert result.reference_deviation_pct is None
    assert result.standardized_deviation is None
    assert "REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL" not in result.reason_codes


def test_gross_unit_mismatch_forces_inconclusive():
    # Token at ~3x the current underlying is a unit/feed bug, not economics.
    result = validate(_snapshot(185.70, underlying_reference=60.0), _estimate())
    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "TOKEN_UNIT_SUSPECT" in result.reason_codes


def test_moderate_depeg_is_challenged_not_unit_suspect():
    # A real ~2.7% divergence stays economics: judged as CHALLENGED via z, and
    # never silenced as a unit problem or a 503.
    result = validate(_snapshot(190.00, underlying_reference=185.00), _estimate())
    assert result.evidence_state == EvidenceState.CHALLENGED
    assert "TOKEN_UNIT_SUSPECT" not in result.reason_codes


def test_low_liquidity_forces_inconclusive():
    # The floor is inert by default; exercise the gate with an explicit threshold.
    strict = Thresholds(min_token_liquidity_usd=25_000.0)
    result = validate(
        _snapshot(185.70, token_liquidity_usd=1_000.0), _estimate(), thresholds=strict
    )
    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "TOKEN_MARKET_QUALITY_LOW" in result.reason_codes


def test_healthy_liquidity_does_not_abstain():
    strict = Thresholds(min_token_liquidity_usd=25_000.0)
    result = validate(
        _snapshot(185.70, token_liquidity_usd=2_000_000.0), _estimate(), thresholds=strict
    )
    assert result.evidence_state == EvidenceState.SUPPORTED
    assert "TOKEN_MARKET_QUALITY_LOW" not in result.reason_codes


def test_global_fallback_calibration_is_visible_without_forcing_abstention():
    estimate = _estimate().model_copy(update={"interval_calibration_source": "global_fallback"})

    result = validate(_snapshot(185.70), estimate)

    assert result.evidence_state == EvidenceState.SUPPORTED
    assert "CALIBRATION_GLOBAL_FALLBACK" in result.reason_codes
