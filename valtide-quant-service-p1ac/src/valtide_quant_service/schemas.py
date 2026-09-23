from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from .runtime import FilterState

QuantSession=Literal['regular','premarket','afterhours','overnight','closed']

@dataclass(frozen=True)
class MarketSnapshot:
    asset:str
    timestamp:datetime
    quant_session:QuantSession
    token_price:Optional[float]
    current_underlying_price:Optional[float]
    last_trusted_reference:Optional[float]
    last_trusted_reference_timestamp:Optional[datetime]
    external_constructed_reference:Optional[float]=None

@dataclass(frozen=True)
class QuantEstimate:
    """Quantitative challenger output; product validation is owned by apps/api."""

    asset:str; timestamp:datetime
    fair_value:float; lower_bound:float; upper_bound:float; interval_coverage_target:float
    challenger_m_log:float; challenger_P_log:float; reference_predictive_sd_log:float
    interval_semantics:str; interval_calibration_type:str; interval_calibration_source:str
    model_id:str; model_version:str; quant_session:QuantSession
    latent_lower_bound:float; latent_upper_bound:float
    carried_state:'FilterState'

    def to_dict(self):
        d=asdict(self)
        d['timestamp']=d['timestamp'].isoformat().replace('+00:00','Z')
        if d['carried_state']['timestamp'] is not None:
            d['carried_state']['timestamp']=d['carried_state']['timestamp'].isoformat().replace('+00:00','Z')
        return d
