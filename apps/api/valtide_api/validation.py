"""Backend-owned validation of a quant estimate against a selected reference."""

from __future__ import annotations

import math
from dataclasses import dataclass

from valtide_api.challenger_detector import (
    detector_evidence,
    resolve_challenger_detector,
)
from valtide_api.models import (
    ChallengerDetectorEvidence,
    ChallengerEstimate,
    EvidenceState,
    MarketSnapshot,
    ValuationResult,
)
from valtide_api.normalizer import is_unit_scale_suspect


@dataclass(frozen=True)
class Thresholds:
    """Auditable research thresholds used by the validation layer."""

    z_support: float = 1.0
    z_challenge: float = 2.0
    max_reference_age_s: int = 72 * 3600
    min_token_volume: float = 0.0
    # Market-quality floor: abstain on a clearly-degenerate (near-dead) DEX pool.
    # Wired but inert by default (0.0) — the threshold must be set from a real
    # liquidity distribution, not an invented constant, before it is relied on.
    min_token_liquidity_usd: float = 0.0
    # Token/underlying ratio outside this band is a probable unit/feed bug, not
    # economics, so we abstain rather than emit a spurious CHALLENGED.
    unit_scale_low: float = 0.5
    unit_scale_high: float = 2.0
    max_state_sd_log: float = 0.05
    agree_tolerance: float = 0.01


def validate(
    snapshot: MarketSnapshot,
    estimate: ChallengerEstimate,
    thresholds: Thresholds | None = None,
) -> ValuationResult:
    """Produce a backend Evidence State from one quantitative estimate.

    Missing token or reference observations are explicit abstentions. The quant
    state may still advance on a missing token, but the backend cannot claim
    token agreement or compute a reference deviation without the corresponding
    observation. X-Perp deviations remain visible, but Evidence State abstains
    until a target-specific X-Perp residual calibration is supported.
    """
    th = thresholds or Thresholds()

    r0 = snapshot.last_trusted_reference
    token = snapshot.token_price
    fair = estimate.fair_value
    reference = snapshot.reference_under_test

    observed_token_move = token / r0 - 1 if token is not None else None
    model_implied_move = fair / r0 - 1
    residual = token / fair - 1 if token is not None else None

    reference_deviation: float | None = None
    standardized_deviation: float | None = None
    xperp_scaled_deviation: float | None = None
    evidence_state_basis = (
        f"selected_reference_under_test:{snapshot.reference_under_test_source}"
        if reference is not None
        else "no_comparator_available"
    )
    reason_codes: list[str] = []

    # Older constructors/persisted snapshots carry X-Perp only in the generic
    # comparator fields. Keep those records readable while making the distinct
    # market evidence explicit on new responses.
    xperp_price = snapshot.xperp_index_price
    xperp_source = snapshot.xperp_index_source
    xperp_ts = snapshot.xperp_index_ts
    if xperp_price is None and snapshot.reference_under_test_source == "okx_xperp_index":
        xperp_price = reference
        xperp_source = snapshot.reference_under_test_source
        xperp_ts = snapshot.reference_under_test_ts

    xperp_vs_p1ac = (
        (xperp_price / fair - 1) * 100
        if xperp_price is not None and fair > 0
        else None
    )
    xstock_vs_xperp = (
        (token / xperp_price - 1) * 100
        if token is not None and xperp_price is not None and xperp_price > 0
        else None
    )

    if token is None:
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("TOKEN_DATA_UNAVAILABLE")

    if reference is None:
        reason_codes.append("COMPARATOR_UNAVAILABLE")
        state = EvidenceState.INCONCLUSIVE
    elif estimate.reference_predictive_sd_log <= 0:
        reason_codes.append("MODEL_UNCERTAINTY_INVALID")
        state = EvidenceState.INCONCLUSIVE
    else:
        reference_deviation = reference / fair - 1
        model_scaled_deviation = (
            math.log(reference) - estimate.state_m
        ) / estimate.reference_predictive_sd_log
        if snapshot.reference_under_test_source == "okx_xperp_index":
            # The current P1a-C predictive variance is calibrated for the
            # underlying target, not for the X-Perp/index residual. Keep the
            # comparison visible as a scaled diagnostic but do not present it
            # as a calibrated z-score or use existing thresholds on it.
            xperp_scaled_deviation = model_scaled_deviation
            evidence_state_basis = "xperp_residual_calibration_unverified"
            state = EvidenceState.INCONCLUSIVE
            reason_codes.append("XPERP_RESIDUAL_CALIBRATION_UNVERIFIED")
        else:
            standardized_deviation = model_scaled_deviation
            inside_interval = estimate.lower_bound <= reference <= estimate.upper_bound
            abs_z = abs(standardized_deviation)
            if abs_z >= th.z_challenge:
                state = EvidenceState.CHALLENGED
            elif abs_z < th.z_support:
                state = EvidenceState.SUPPORTED
            else:
                state = EvidenceState.INCONCLUSIVE
            if not inside_interval:
                reason_codes.append("REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL")

    # Data-quality gates are backend validation concerns, not quant outputs.
    if token is None:
        state = EvidenceState.INCONCLUSIVE
    if snapshot.reference_age_seconds > th.max_reference_age_s:
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("UNDERLYING_REFERENCE_STALE")
    if (
        snapshot.reference_under_test_age_seconds is not None
        and snapshot.reference_under_test_age_seconds > th.max_reference_age_s
    ):
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("REFERENCE_UNDER_TEST_STALE")
    if snapshot.token_volume is not None and snapshot.token_volume < th.min_token_volume:
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("TOKEN_MARKET_QUALITY_LOW")
    if (
        snapshot.token_liquidity_usd is not None
        and snapshot.token_liquidity_usd < th.min_token_liquidity_usd
    ):
        state = EvidenceState.INCONCLUSIVE
        if "TOKEN_MARKET_QUALITY_LOW" not in reason_codes:
            reason_codes.append("TOKEN_MARKET_QUALITY_LOW")
    if is_unit_scale_suspect(
        snapshot.token_price,
        snapshot.underlying_reference,
        low=th.unit_scale_low,
        high=th.unit_scale_high,
    ):
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("TOKEN_UNIT_SUSPECT")
    if estimate.reference_predictive_sd_log > th.max_state_sd_log:
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("MODEL_UNCERTAINTY_HIGH")
    if estimate.interval_calibration_source == "global_fallback":
        reason_codes.append("CALIBRATION_GLOBAL_FALLBACK")

    if token is not None and abs(token - fair) / fair < th.agree_tolerance:
        reason_codes.append("TOKEN_AND_CHALLENGER_AGREE")

    detector_spec = resolve_challenger_detector(snapshot.asset)
    detector_result: ChallengerDetectorEvidence | None = None
    if detector_spec is not None:
        detector_result = detector_evidence(detector_spec, token, estimate)
        band = detector_result.research_band
        if detector_spec.promotion_status != "CHALLENGER_DETECTOR_PROMOTABLE":
            reason_codes.append("P1A_XSTOCK_DETECTOR_NOT_PROMOTED")
        elif band == "watch":
            reason_codes.append("P1A_XSTOCK_REVIEW_THRESHOLD")
        elif band == "review":
            reason_codes.append("P1A_XSTOCK_CHALLENGE_THRESHOLD")
            current_underlying = (
                snapshot.underlying_reference is not None
                and snapshot.underlying_reference_ts == snapshot.observation_ts
            )
            quality_abstentions = {
                "TOKEN_DATA_UNAVAILABLE",
                "UNDERLYING_REFERENCE_STALE",
                "REFERENCE_UNDER_TEST_STALE",
                "TOKEN_MARKET_QUALITY_LOW",
                "TOKEN_UNIT_SUSPECT",
                "MODEL_UNCERTAINTY_INVALID",
                "MODEL_UNCERTAINTY_HIGH",
            }
            if not current_underlying:
                reason_codes.append("UNDERLYING_REFERENCE_NOT_CONTEMPORANEOUS")
            elif quality_abstentions.intersection(reason_codes):
                # Existing quality reasons remain authoritative; the detector
                # cannot override any of these abstentions.
                pass
            elif (
                xperp_price is None
                or xperp_ts != snapshot.observation_ts
                or (
                    snapshot.reference_under_test_age_seconds is not None
                    and snapshot.reference_under_test_age_seconds > 0
                )
            ):
                reason_codes.append("XPERP_EVIDENCE_UNCALIBRATED")
            else:
                assert token is not None
                xperp_log = math.log(xperp_price)
                challenger_gap = abs(xperp_log - estimate.state_m)
                xstock_gap = abs(xperp_log - math.log(token))
                if challenger_gap < xstock_gap:
                    state = EvidenceState.CHALLENGED
                    evidence_state_basis = (
                        "frozen_p1a_xstock_tail_detector_with_xperp_directional_corroboration"
                    )
                    reason_codes.append("XPERP_CORROBORATES_CHALLENGE")
                elif xstock_gap < challenger_gap:
                    state = EvidenceState.INCONCLUSIVE
                    reason_codes.append("XPERP_CONTRADICTS_MODEL_CHALLENGE")
                else:
                    reason_codes.append("XPERP_EVIDENCE_UNCALIBRATED")

    return ValuationResult(
        asset=snapshot.asset,
        timestamp=snapshot.observation_ts,
        market_state=snapshot.market_state.value,
        last_trusted_reference=r0,
        token_price=token,
        token_source=snapshot.token_source,
        token_observed_at=snapshot.token_observed_at,
        token_volume=snapshot.token_volume,
        token_volume_usd=snapshot.token_volume_usd,
        token_liquidity_usd=snapshot.token_liquidity_usd,
        external_constructed_reference=snapshot.external_reference,
        valtide_fair_value=fair,
        fair_value_lower=estimate.lower_bound,
        fair_value_upper=estimate.upper_bound,
        interval_coverage_target=estimate.coverage_target,
        observed_token_move_pct=(
            observed_token_move * 100 if observed_token_move is not None else None
        ),
        model_implied_move_pct=model_implied_move * 100,
        residual_premium_discount_pct=(residual * 100 if residual is not None else None),
        reference_under_test=reference,
        reference_under_test_source=snapshot.reference_under_test_source,
        reference_profile=snapshot.reference_profile,
        reference_under_test_ts=snapshot.reference_under_test_ts,
        reference_under_test_age_seconds=snapshot.reference_under_test_age_seconds,
        reference_deviation_pct=(
            reference_deviation * 100 if reference_deviation is not None else None
        ),
        standardized_deviation=standardized_deviation,
        xperp_index_price=xperp_price,
        xperp_index_source=xperp_source,
        xperp_index_ts=xperp_ts,
        xstock_vs_p1ac_deviation_pct=residual * 100 if residual is not None else None,
        xperp_vs_p1ac_deviation_pct=xperp_vs_p1ac,
        xstock_vs_xperp_deviation_pct=xstock_vs_xperp,
        xperp_deviation_scaled_by_model_predictive_sd=xperp_scaled_deviation,
        evidence_state_basis=evidence_state_basis,
        challenger_detector=detector_result,
        evidence_state=state,
        reason_codes=reason_codes,
        confidence=None,
        model_id=estimate.model_id,
        model_version=estimate.model_version,
        interval_semantics=estimate.interval_semantics,
        interval_calibration_type=estimate.interval_calibration_type,
        interval_calibration_source=estimate.interval_calibration_source,
        reference_age_seconds=snapshot.reference_age_seconds,
        source_provenance=snapshot.source_provenance,
    )
