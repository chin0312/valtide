"""Thin adapter from backend snapshots to the packaged P1a-C quant service.

The quant package owns model execution, calibrated intervals, and carried state.
This module only translates backend objects at the integration boundary; product
validation remains in :mod:`valtide_api.validation`.
"""

from __future__ import annotations

import math
from datetime import datetime

from valtide_quant_service import (
    FilterState,
    QuantService,
    StateGapError,
)
from valtide_quant_service import (
    MarketSnapshot as QuantMarketSnapshot,
)

from valtide_api.models import ChallengerEstimate, MarketSnapshot


def estimate(
    snapshot: MarketSnapshot,
    prior_m: float | None = None,
    prior_P: float | None = None,
    prior_ts: datetime | None = None,
) -> ChallengerEstimate:
    """Run one public P1a-C service update and translate its quantitative result.

    ``prior_m``/``prior_P``/``prior_ts`` are the backend's serialized carried
    state. The packaged service then preserves its causal order: predict,
    assimilate NVDAx, read the challenger estimate, and only then assimilate
    current NVDA for the next timestamp.
    """
    if (prior_m is None) != (prior_P is None):
        raise ValueError("prior_m and prior_P must be provided together")

    state = (
        FilterState(m=prior_m, P=prior_P, timestamp=prior_ts)
        if prior_m is not None and prior_P is not None
        else None
    )
    service = QuantService.from_default_artifacts(state=state)
    quant_snapshot = QuantMarketSnapshot(
        asset=snapshot.asset,
        timestamp=snapshot.observation_ts,
        quant_session=snapshot.market_state.value,
        token_price=snapshot.token_price,
        current_underlying_price=snapshot.underlying_reference,
        last_trusted_reference=snapshot.last_trusted_reference,
        last_trusted_reference_timestamp=snapshot.last_trusted_reference_ts,
        external_constructed_reference=snapshot.external_reference,
    )
    quant_result = service.update(quant_snapshot)
    carried = quant_result.carried_state

    return ChallengerEstimate(
        fair_value=quant_result.fair_value,
        lower_bound=quant_result.lower_bound,
        upper_bound=quant_result.upper_bound,
        state_m=quant_result.challenger_m_log,
        state_sd_log=math.sqrt(quant_result.challenger_P_log),
        reference_predictive_sd_log=quant_result.reference_predictive_sd_log,
        coverage_target=quant_result.interval_coverage_target,
        interval_calibration_type=quant_result.interval_calibration_type,
        interval_calibration_source=quant_result.interval_calibration_source,
        state_m_after_nvda=carried.m,
        state_P_after_nvda=carried.P,
        model_id=quant_result.model_id,
        model_version=quant_result.model_version,
        interval_semantics=quant_result.interval_semantics,
    )


__all__ = ["StateGapError", "estimate"]
