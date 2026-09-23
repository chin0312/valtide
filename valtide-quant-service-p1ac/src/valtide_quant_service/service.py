from __future__ import annotations
import json, math
from pathlib import Path
from .artifacts import load_p1a
from .calibration import P1aCCalibrator
from .runtime import P1aCRuntime, FilterState
from .schemas import MarketSnapshot,ValuationResult,LatentStateDetails,public_market_state

class QuantService:
    def __init__(self,runtime:P1aCRuntime): self.runtime=runtime
    @classmethod
    def from_artifacts(cls,model_path,calibrator_path,state:FilterState|None=None):
        return cls(P1aCRuntime(load_p1a(model_path),P1aCCalibrator(calibrator_path),state))
    @classmethod
    def from_default_artifacts(cls,state:FilterState|None=None):
        root=Path(__file__).resolve().parent/'model_artifacts'
        return cls.from_artifacts(root/'p1a_runtime.json',root/'p1a_c_calibrator.json',state)
    @staticmethod
    def _pct(a,b): return None if a is None or b is None or b<=0 else a/b-1
    @staticmethod
    def _status(ref,fair,sd):
        if ref is None or ref<=0 or sd<=0:return None
        z=abs((math.log(ref)-math.log(fair))/sd)
        return 'support' if z<1 else ('watch' if z<2 else 'review')
    def update(self,s:MarketSnapshot):
        e=self.runtime.step(s); r0=s.last_trusted_reference
        primary=self._status(r0,e.fair_value,e.reference_predictive_sd_log) or 'support'
        ext=self._status(s.external_constructed_reference,e.fair_value,e.reference_predictive_sd_log)
        reasons=[]
        if s.token_price is None:reasons.append('token_data_unavailable')
        if s.current_underlying_price is None:reasons.append('current_underlying_unavailable')
        if e.calibration.source=='global_fallback':reasons.append('calibration_global_fallback')
        age=None
        if s.last_trusted_reference_timestamp is not None: age=max(0.0,(s.timestamp-s.last_trusted_reference_timestamp).total_seconds())
        a=self.runtime.artifact
        return ValuationResult(
            asset=s.asset,timestamp=s.timestamp,marketState=public_market_state(s.quant_session),lastTrustedReference=r0,tokenPrice=s.token_price,
            externalConstructedReference=s.external_constructed_reference,valtideFairValue=e.fair_value,fairValueLower=e.primary_lower,fairValueUpper=e.primary_upper,
            intervalCoverageTarget=self.runtime.calibrator.level,confidence=None,observedTokenMovePct=self._pct(s.token_price,r0),modelImpliedMovePct=self._pct(e.fair_value,r0),
            residualPremiumDiscountPct=self._pct(s.token_price,e.fair_value),challengeStatus=primary,externalComparatorStatus=ext,reasonCodes=reasons,
            modelVersion=a.model_version,modelId=a.deployment_model_id,quantSession=s.quant_session,intervalSemantics='reference_equivalent_predictive',
            intervalCalibrationType=e.calibration.calibration_type,intervalCalibrationSource=e.calibration.source,lastTrustedReferenceTimestamp=s.last_trusted_reference_timestamp,
            referenceAgeSeconds=age,latentState=LatentStateDetails(e.fair_value,e.challenger_P_log,e.latent_lower,e.latent_upper))
    def export_state(self): return self.runtime.state.to_dict() if self.runtime.state else None
