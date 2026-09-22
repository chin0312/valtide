"""Validation engine — turns a challenger estimate + reference into an Evidence State.

Pure, deterministic, no I/O. This is the heart of the product; it is the module
to unit-test hardest. All logic and formulas trace to docs/BACKEND_PLAN.md §7,
which in turn traces to METHODOLOGY §10-13.

Key correctness point: the z-score is computed in LOG space using the state sd
directly, NOT by reverse-engineering sigma from asymmetric price bounds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from valtide_api.models import (
    ChallengerEstimate,
    EvidenceState,
    MarketSnapshot,
    ValuationResult,
)


@dataclass(frozen=True)
class Thresholds:
    """Validation thresholds. Research defaults — recalibrate on James's results.

    No threshold should appear as a bare literal in the logic below; they all
    live here so they are auditable and tunable in one place.
    """

    z_support: float = 1.0
    z_challenge: float = 2.0
    # A normal weekend gap (Fri close -> Sun/Mon) is ~50-64h. Auto-abstaining at
    # 48h would make weekend validation — the core use case — impossible, so the
    # default covers a normal weekend and only flags pathologically stale data.
    max_reference_age_s: int = 72 * 3600
    min_token_volume: float = 0.0  # set once we observe real OKX volume
    max_state_sd_log: float = 0.05  # ~5% 1-sigma; tune on James's results
    agree_tolerance: float = 0.01


def validate(
    snapshot: MarketSnapshot,
    estimate: ChallengerEstimate,
    thresholds: Thresholds | None = None,
    model_id: str = "P1a",
    model_version: str = "0.1.0",
    interval_semantics: str = "reference_equivalent_predictive",
) -> ValuationResult:
    """Produce a ValuationResult from a snapshot and challenger estimate.

    The reference under test (Pt) is taken from snapshot.reference_under_test.
    """
    th = thresholds or Thresholds()

    R0 = snapshot.last_trusted_reference
    Tt = snapshot.token_price
    Ft = estimate.fair_value
    Pt = snapshot.reference_under_test

    # --- Step 1: derived quantities (METHODOLOGY §10), price space ---
    observed_token_move = Tt / R0 - 1
    model_implied_move = Ft / R0 - 1
    residual = Tt / Ft - 1

    # --- Step 2: reference deviation + log-space z-score (METHODOLOGY §11) ---
    reference_deviation = Pt / Ft - 1
    z = (math.log(Pt) - estimate.state_m) / estimate.state_sd_log
    inside_interval = estimate.lower_bound <= Pt <= estimate.upper_bound

    reason_codes: list[str] = []

    # --- Step 3: base Evidence State from |z| (BACKEND_PLAN §7) ---
    abs_z = abs(z)
    if abs_z >= th.z_challenge:
        state = EvidenceState.CHALLENGED
    elif abs_z < th.z_support:
        state = EvidenceState.SUPPORTED
    else:
        state = EvidenceState.INCONCLUSIVE

    # --- Step 4: data-quality overrides -> force INCONCLUSIVE (METHODOLOGY §13) ---
    # Any weak-evidence condition means we abstain rather than challenge.
    if snapshot.reference_age_seconds > th.max_reference_age_s:
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("UNDERLYING_REFERENCE_STALE")
    if snapshot.token_volume is not None and snapshot.token_volume < th.min_token_volume:
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("TOKEN_MARKET_QUALITY_LOW")
    if estimate.state_sd_log > th.max_state_sd_log:
        state = EvidenceState.INCONCLUSIVE
        reason_codes.append("MODEL_UNCERTAINTY_HIGH")

    # --- Step 5: descriptive reason codes (canonical METHODOLOGY §13 names) ---
    if not inside_interval:
        reason_codes.append("REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL")
    if abs(Tt - Ft) / Ft < th.agree_tolerance:
        reason_codes.append("TOKEN_AND_CHALLENGER_AGREE")

    return ValuationResult(
        asset=snapshot.asset,
        timestamp=snapshot.observation_ts,
        market_state=snapshot.market_state.value,
        last_trusted_reference=R0,
        token_price=Tt,
        external_constructed_reference=snapshot.external_reference,
        valtide_fair_value=Ft,
        fair_value_lower=estimate.lower_bound,
        fair_value_upper=estimate.upper_bound,
        interval_coverage_target=estimate.coverage_target,
        observed_token_move_pct=observed_token_move * 100,
        model_implied_move_pct=model_implied_move * 100,
        residual_premium_discount_pct=residual * 100,
        reference_under_test=Pt,
        reference_under_test_source=snapshot.reference_under_test_source,
        reference_deviation_pct=reference_deviation * 100,
        standardized_deviation=z,
        evidence_state=state,
        reason_codes=reason_codes,
        confidence=None,
        model_id=model_id,
        model_version=model_version,
        interval_semantics=interval_semantics,
        reference_age_seconds=snapshot.reference_age_seconds,
    )
