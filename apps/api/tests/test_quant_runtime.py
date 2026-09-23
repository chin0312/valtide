"""Backend integration checks for the public P1a-C quant boundary."""

import math
from datetime import UTC, datetime, timedelta

from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.quant_runtime import estimate


def _snapshot(
    token_price: float | None,
    nvda: float | None,
    *,
    external: float | None = None,
    observation_ts: datetime | None = None,
) -> MarketSnapshot:
    ts = observation_ts or datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=ts,
        token_price=token_price,
        token_volume=50_000.0 if token_price is not None else None,
        underlying_reference=nvda,
        underlying_reference_ts=(ts if nvda is not None else None),
        last_trusted_reference=180.0,
        last_trusted_reference_ts=datetime(2026, 9, 19, 20, 0, tzinfo=UTC),
        reference_age_seconds=64_800,
        reference_under_test=190.0,
        reference_under_test_source="okx_xperp_index",
        reference_under_test_ts=ts,
        reference_under_test_age_seconds=0,
        market_state=MarketState.CLOSED,
        external_reference=external,
    )


def test_default_runtime_returns_quant_only_p1ac_estimate():
    result = estimate(_snapshot(185.10, None))

    assert result.model_id == "P1a-C"
    assert result.model_version
    assert result.interval_semantics == "reference_equivalent_predictive"
    assert result.lower_bound < result.fair_value < result.upper_bound
    assert result.coverage_target == 0.9


def test_current_nvda_changes_carried_state_only():
    without_nvda = estimate(_snapshot(185.10, None))
    with_nvda = estimate(_snapshot(185.10, 184.0))

    assert without_nvda.fair_value == with_nvda.fair_value
    assert without_nvda.lower_bound == with_nvda.lower_bound
    assert without_nvda.upper_bound == with_nvda.upper_bound
    assert without_nvda.state_m == with_nvda.state_m
    assert without_nvda.state_m_after_nvda != with_nvda.state_m_after_nvda


def test_external_comparator_cannot_change_quant_estimate():
    without_external = estimate(_snapshot(185.10, None, external=None))
    with_external = estimate(_snapshot(185.10, None, external=250.0))

    assert with_external == without_external


def test_missing_token_still_advances_quant_state():
    result = estimate(_snapshot(None, None))

    assert math.isfinite(result.fair_value)
    assert result.state_m_after_nvda == result.state_m
    assert result.state_P_after_nvda == result.state_sd_log**2


def test_backend_passes_carried_state_to_next_five_minute_step():
    first_ts = datetime(2026, 9, 20, 14, 0, tzinfo=UTC)
    first = estimate(_snapshot(185.10, None, observation_ts=first_ts))
    second = estimate(
        _snapshot(
            185.20,
            None,
            observation_ts=first_ts + timedelta(minutes=5),
        ),
        prior_m=first.state_m_after_nvda,
        prior_P=first.state_P_after_nvda,
        prior_ts=first_ts,
    )

    assert second.fair_value != first.fair_value
