from __future__ import annotations
from pathlib import Path
from .artifacts import load_p1a
from .calibration import P1aCCalibrator
from .runtime import P1aCRuntime, FilterState
from .schemas import MarketSnapshot,QuantEstimate

class QuantService:
    def __init__(self,runtime:P1aCRuntime): self.runtime=runtime
    @classmethod
    def from_artifacts(cls,model_path,calibrator_path,state:FilterState|None=None):
        return cls(P1aCRuntime(load_p1a(model_path),P1aCCalibrator(calibrator_path),state))
    @classmethod
    def from_default_artifacts(cls,state:FilterState|None=None):
        root=Path(__file__).resolve().parent/'model_artifacts'
        return cls.from_artifacts(root/'p1a_runtime.json',root/'p1a_c_calibrator.json',state)
    def update(self,s:MarketSnapshot):
        e=self.runtime.step(s)
        if self.runtime.state is None: raise RuntimeError('runtime did not carry state')
        a=self.runtime.artifact
        return QuantEstimate(
            asset=s.asset,timestamp=s.timestamp,fair_value=e.fair_value,lower_bound=e.primary_lower,upper_bound=e.primary_upper,
            interval_coverage_target=self.runtime.calibrator.level,challenger_m_log=e.challenger_m_log,
            challenger_P_log=e.challenger_P_log,reference_predictive_sd_log=e.reference_predictive_sd_log,
            interval_semantics='reference_equivalent_predictive',interval_calibration_type=e.calibration.calibration_type,
            interval_calibration_source=e.calibration.source,model_id=a.deployment_model_id,model_version=a.model_version,
            quant_session=s.quant_session,latent_lower_bound=e.latent_lower,latent_upper_bound=e.latent_upper,
            carried_state=self.runtime.state)
    def export_state(self): return self.runtime.state.to_dict() if self.runtime.state else None
