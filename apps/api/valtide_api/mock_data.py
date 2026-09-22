"""A single mock ValuationResult so the frontend can build immediately.

This is the Phase 1 stand-in: a stable, realistic result shape that Valerie can
render the entire dashboard against before any live data or model exists. The
numbers illustrate a CHALLENGED weekend scenario (reference above the challenger
range). Replaced by real replay output in Phase 2.
"""

from datetime import UTC, datetime

from valtide_api.models import EvidenceState, ValuationResult

MOCK_VALUATION = ValuationResult(
    asset="NVDAx",
    timestamp=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
    market_state="closed",
    last_trusted_reference=180.00,
    token_price=185.10,
    external_constructed_reference=None,
    valtide_fair_value=185.70,
    fair_value_lower=184.20,
    fair_value_upper=187.20,
    interval_coverage_target=0.90,
    observed_token_move_pct=2.83,
    model_implied_move_pct=3.17,
    residual_premium_discount_pct=-0.32,
    reference_under_test=190.00,
    reference_under_test_source="okx_xperp_index",
    reference_deviation_pct=2.32,
    standardized_deviation=2.87,
    evidence_state=EvidenceState.CHALLENGED,
    reason_codes=[
        "REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL",
        "TOKEN_AND_CHALLENGER_AGREE",
    ],
    confidence=None,
    model_id="P1a",
    model_version="0.1.0-mock",
    interval_semantics="reference_equivalent_predictive",
    reference_age_seconds=64800,
)
