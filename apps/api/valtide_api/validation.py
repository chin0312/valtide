"""Backend-owned validation of a quant estimate against a selected reference."""

from __future__ import annotations

import math
from dataclasses import dataclass

from valtide_api.models import (
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
    observation.
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
    inside_interval = False
    reason_codes: list[str] = []

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
        standardized_deviation = (
            math.log(reference) - estimate.state_m
        ) / estimate.reference_predictive_sd_log
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

    return ValuationResult(
        asset=snapshot.asset,
        timestamp=snapshot.observation_ts,
        market_state=snapshot.market_state.value,
        last_trusted_reference=r0,
        token_price=token,
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
        reference_under_test_ts=snapshot.reference_under_test_ts,
        reference_under_test_age_seconds=snapshot.reference_under_test_age_seconds,
        reference_deviation_pct=(
            reference_deviation * 100 if reference_deviation is not None else None
        ),
        standardized_deviation=standardized_deviation,
        evidence_state=state,
        reason_codes=reason_codes,
        confidence=None,
        model_id=estimate.model_id,
        model_version=estimate.model_version,
        interval_semantics=estimate.interval_semantics,
        interval_calibration_type=estimate.interval_calibration_type,
        interval_calibration_source=estimate.interval_calibration_source,
        reference_age_seconds=snapshot.reference_age_seconds,
    )
