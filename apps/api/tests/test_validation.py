"""Validation engine tests — the core product logic.

Uses a fixed challenger estimate and varies the reference under test to exercise
each Evidence State and override path.
"""

import math
from datetime import UTC, datetime, timedelta

import pytest

from valtide_api.challenger_detector import resolve_challenger_detector
from valtide_api.models import (
    ChallengerEstimate,
    EvidenceState,
    MarketSnapshot,
    MarketState,
    ValuationResult,
)
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


def test_promoted_spy_tail_detector_works_without_same_time_underlying():
    spec = resolve_challenger_detector("SPYx")
    assert spec is not None
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    snapshot = _detector_snapshot(
        "SPYx",
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
    assert "P1A_XSTOCK_CHALLENGE_THRESHOLD" in result.reason_codes
    assert "XPERP_CORROBORATES_CHALLENGE" in result.reason_codes
    assert result.standardized_deviation is None
    assert result.validation_target == "xstock_observed_price"
    assert result.evidence_semantics == "p1a_xstock_challenger_xperp_second_market_v1"
    assert result.xperp_role == "second_market_challenger"
    assert "UNDERLYING_REFERENCE_NOT_CONTEMPORANEOUS" not in result.reason_codes


def test_unified_evidence_does_not_vote_on_contemporaneous_underlying_value():
    spec = resolve_challenger_detector("SPYx")
    assert spec is not None
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    snapshot = _detector_snapshot(
        "SPYx",
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


def test_xperp_contradiction_abstains_without_same_time_underlying():
    spec = resolve_challenger_detector("SPYx")
    assert spec is not None
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    snapshot = _detector_snapshot(
        "SPYx",
        spec.threshold_challenge + 1,
        xperp_matches_challenger=False,
        underlying_reference=None,
        underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
        market_state=MarketState.OVERNIGHT,
    )

    result = validate(snapshot, estimate)

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "XPERP_CONTRADICTS_MODEL_CHALLENGE" in result.reason_codes


def test_detector_review_band_does_not_become_a_canonical_state():
    spec = resolve_challenger_detector("SPYx")
    assert spec is not None
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    snapshot = _detector_snapshot(
        "SPYx",
        (spec.threshold_review + spec.threshold_challenge) / 2,
    )

    result = validate(snapshot, estimate)

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert result.challenger_detector is not None
    assert result.challenger_detector.research_band == "watch"
    assert "P1A_XSTOCK_REVIEW_THRESHOLD" in result.reason_codes


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
    assert "XPERP_CORROBORATES_CHALLENGE" in no_truth.reason_codes
    assert qqq.evidence_state == EvidenceState.INCONCLUSIVE
    assert "P1A_XSTOCK_DETECTOR_NOT_PROMOTED" in qqq.reason_codes


def test_promoted_detector_abstains_for_missing_xperp_or_token():
    spec = resolve_challenger_detector("SPYx")
    assert spec is not None
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    snapshot = _detector_snapshot("SPYx", spec.threshold_challenge + 1)

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


def test_promoted_detector_abstains_for_stale_or_ambiguous_xperp():
    spec = resolve_challenger_detector("SPYx")
    assert spec is not None
    timestamp = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    base = _detector_snapshot("SPYx", spec.threshold_challenge + 1)

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


@pytest.mark.parametrize("asset", ["NVDAx", "QQQx", "AAPLx"])
def test_non_spy_detector_cannot_escalate_canonical_evidence(asset):
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    result = validate(
        _detector_snapshot(
            asset,
            500,
            underlying_reference=None,
            underlying_reference_ts=datetime(2026, 9, 20, 13, 55, tzinfo=UTC),
        ),
        estimate,
    )

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert "P1A_XSTOCK_DETECTOR_NOT_PROMOTED" in result.reason_codes
    assert "XPERP_CORROBORATES_CHALLENGE" not in result.reason_codes


@pytest.mark.parametrize("asset", ["NVDAx", "SPYx", "QQQx", "AAPLx"])
def test_unified_detector_low_score_never_implies_supported(asset):
    estimate = _estimate().model_copy(update={"model_version": "0.3.0"})
    result = validate(_detector_snapshot(asset, 0), estimate)

    assert result.evidence_state == EvidenceState.INCONCLUSIVE
    assert result.evidence_semantics == "p1a_xstock_challenger_xperp_second_market_v1"


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
