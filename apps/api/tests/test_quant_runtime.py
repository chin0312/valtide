"""Quant runtime tests — verify the single Kalman step behaves correctly.

These check internal consistency and the NVDAx-first update order. The eventual
golden test (asserting equality with James's R output on a shared input) is added
once he provides one sample step.
"""

import math
from datetime import UTC, datetime

from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.quant_runtime import ModelArtifact, estimate

_ART = ModelArtifact(
    model_id="P1a",
    model_version="test",
    Q=4.2e-6,
    R_nvda=1.1e-6,
    R_nvdax=9.5e-6,
    m0=math.log(185.0),
    P0=1e-4,
    coverage_target=0.90,
    calibrator="gaussian",
)


def _snapshot(token_price: float, nvda: float | None) -> MarketSnapshot:
    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=datetime(2026, 9, 20, 14, 0, tzinfo=UTC),
        token_price=token_price,
        token_volume=50_000.0,
        underlying_reference=nvda,
        underlying_reference_ts=None,
        last_trusted_reference=180.0,
        last_trusted_reference_ts=datetime(2026, 9, 19, 20, 0, tzinfo=UTC),
        reference_age_seconds=64_800,
        reference_under_test=190.0,
        reference_under_test_source="okx_xperp_index",
        market_state=MarketState.CLOSED,
    )


def test_challenger_uses_nvdax_only():
    # With no NVDA, the carried state equals the NVDAx-only posterior.
    est = estimate(_snapshot(185.10, None), prior_m=math.log(185.0), prior_P=1e-4, artifact=_ART)
    assert est.state_m == est.state_m_after_nvda
    assert est.state_P_after_nvda == est.state_sd_log**2


def test_fair_value_between_prior_and_observation():
    # The filtered mean moves from the prior toward the NVDAx observation.
    prior_m = math.log(185.0)
    obs_m = math.log(185.10)
    est = estimate(_snapshot(185.10, None), prior_m=prior_m, prior_P=1e-4, artifact=_ART)
    assert prior_m <= est.state_m <= obs_m


def test_interval_brackets_fair_value():
    est = estimate(_snapshot(185.10, None), prior_m=math.log(185.0), prior_P=1e-4, artifact=_ART)
    assert est.lower_bound < est.fair_value < est.upper_bound


def test_nvda_changes_carried_state_only():
    # Folding in NVDA must change the carried state but NOT the challenger read-off.
    snap_no = _snapshot(185.10, None)
    snap_yes = _snapshot(185.10, 184.0)
    a = estimate(snap_no, prior_m=math.log(185.0), prior_P=1e-4, artifact=_ART)
    b = estimate(snap_yes, prior_m=math.log(185.0), prior_P=1e-4, artifact=_ART)
    # Challenger fair value identical (NVDAx-only) ...
    assert a.fair_value == b.fair_value
    assert a.state_m == b.state_m
    # ... but the carried post-NVDA state differs.
    assert a.state_m_after_nvda != b.state_m_after_nvda


def test_uncertainty_shrinks_after_observation():
    # A measurement reduces variance: P1 < P_pred = P0 + Q.
    prior_P = 1e-4
    est = estimate(_snapshot(185.10, None), prior_m=math.log(185.0), prior_P=prior_P, artifact=_ART)
    assert est.state_sd_log**2 < prior_P + _ART.Q
