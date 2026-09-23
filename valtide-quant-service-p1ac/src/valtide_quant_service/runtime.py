from __future__ import annotations
import math
from dataclasses import dataclass, asdict
from datetime import datetime
from .artifacts import P1aArtifact
from .calibration import P1aCCalibrator, CalibrationBounds
from .schemas import MarketSnapshot

FIVE=300.0
class StateGapError(RuntimeError): pass
@dataclass
class FilterState:
    m:float; P:float; timestamp:datetime|None=None
    def to_dict(self): return {'m':self.m,'P':self.P,'timestamp':self.timestamp.isoformat() if self.timestamp else None}
    @classmethod
    def from_dict(cls,d): return cls(float(d['m']),float(d['P']),datetime.fromisoformat(d['timestamp']) if d.get('timestamp') else None)
@dataclass(frozen=True)
class RuntimeEstimate:
    fair_value:float; primary_lower:float; primary_upper:float; latent_lower:float; latent_upper:float
    challenger_m_log:float; challenger_P_log:float; reference_predictive_sd_log:float; calibration:CalibrationBounds

class P1aCRuntime:
    def __init__(self,artifact:P1aArtifact,calibrator:P1aCCalibrator,state:FilterState|None=None): self.artifact=artifact; self.calibrator=calibrator; self.state=state
    @staticmethod
    def _lp(x):
        if x is None:return None
        if not math.isfinite(x) or x<=0: raise ValueError('price must be finite and positive')
        return math.log(x)
    @staticmethod
    def _update(m,P,y,R):
        K=P/(P+R); return m+K*(y-m), max(P-K*P,1e-15)
    def _init(self,s):
        # Prefer last trusted reference as the anchor; current NVDA must not create the current challenger quote.
        if s.last_trusted_reference is not None: self.state=FilterState(math.log(s.last_trusted_reference),self.artifact.r_nvda,None)
        elif s.token_price is not None: self.state=FilterState(math.log(s.token_price),self.artifact.r_nvdax,None)
        else: raise ValueError('cannot initialize without reference or token')
    def step(self,s:MarketSnapshot):
        if s.asset!=self.artifact.asset: raise ValueError('asset mismatch')
        if s.timestamp.tzinfo is None: raise ValueError('timezone-aware timestamp required')
        if self.state and self.state.timestamp:
            dt=(s.timestamp-self.state.timestamp).total_seconds()
            if dt<=0: raise ValueError('timestamps must strictly increase')
            if abs(dt-FIVE)>1: raise StateGapError(f'expected 5-minute step, got {dt}s')
        if self.state is None:self._init(s)
        m=self.state.m; P=self.state.P+float(self.artifact.q_by_session[s.quant_session])
        yt=self._lp(s.token_price)
        if yt is not None:m,P=self._update(m,P,yt,self.artifact.r_nvdax)
        cm,cp=m,P
        sd=math.sqrt(cp+self.artifact.r_nvda); cb=self.calibrator.bounds(s.quant_session)
        lo=math.exp(cm+cb.q_lower*sd); hi=math.exp(cm+cb.q_upper*sd)
        z=1.6448536269514722; llo=math.exp(cm-z*math.sqrt(cp)); lhi=math.exp(cm+z*math.sqrt(cp))
        # Only now assimilate current NVDA for next timestamp.
        yr=self._lp(s.current_underlying_price)
        if yr is not None:m,P=self._update(m,P,yr,self.artifact.r_nvda)
        self.state=FilterState(m,P,s.timestamp)
        return RuntimeEstimate(math.exp(cm),lo,hi,llo,lhi,cm,cp,sd,cb)
