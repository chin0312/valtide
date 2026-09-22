"""Validation engine tests — the core product logic.

Uses a fixed challenger estimate and varies the reference under test to exercise
each Evidence State and override path.
"""

import math
from datetime import UTC, datetime

from valtide_api.models import ChallengerEstimate, EvidenceState, MarketSnapshot, MarketState
from valtide_api.validation import Thresholds, validate


def _estimate(fair_value: float = 185.70, sd_log: float = 0.008) -> ChallengerEstimate:
    m = math.log(fair_value)
    return ChallengerEstimate(
        fair_value=fair_value,
        lower_bound=math.exp(m - 1.645 * sd_log),
        upper_bound=math.exp(m + 1.645 * sd_log),
        state_m=m,
        state_sd_log=sd_log,
        coverage_target=0.90,
        state_m_after_nvda=m,
        state_P_after_nvda=sd_log**2,
    )


def _snapshot(reference_under_test: float, **overrides) -> MarketSnapshot:
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
        reference_under_test_source="okx_xperp_index",
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


def test_custom_thresholds_respected():
    # Tightening z_challenge to 1.0 turns a mild deviation into CHALLENGED.
    est = _estimate()
    pt = math.exp(est.state_m + 1.2 * est.state_sd_log)
    strict = Thresholds(z_support=0.5, z_challenge=1.0)
    result = validate(_snapshot(pt), est, thresholds=strict)
    assert result.evidence_state == EvidenceState.CHALLENGED
