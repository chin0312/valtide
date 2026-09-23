from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal, Optional

QuantSession=Literal['regular','premarket','afterhours','overnight','closed']
PublicMarketState=Literal['regular','extended','overnight','closed','unknown']
ChallengeStatus=Literal['support','watch','review']

def public_market_state(s:QuantSession)->PublicMarketState:
    return 'extended' if s in ('premarket','afterhours') else s  # type: ignore

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
class LatentStateDetails:
    mean:float
    variance_log:float
    lower:float
    upper:float

@dataclass(frozen=True)
class ValuationResult:
    asset:str; timestamp:datetime; marketState:PublicMarketState
    lastTrustedReference:Optional[float]; tokenPrice:Optional[float]; externalConstructedReference:Optional[float]
    valtideFairValue:float; fairValueLower:float; fairValueUpper:float; intervalCoverageTarget:float
    confidence:Optional[float]
    observedTokenMovePct:Optional[float]; modelImpliedMovePct:Optional[float]; residualPremiumDiscountPct:Optional[float]
    challengeStatus:ChallengeStatus; externalComparatorStatus:Optional[ChallengeStatus]
    reasonCodes:list[str]; modelVersion:str; modelId:str; quantSession:QuantSession
    intervalSemantics:str; intervalCalibrationType:str; intervalCalibrationSource:str
    lastTrustedReferenceTimestamp:Optional[datetime]; referenceAgeSeconds:Optional[float]
    latentState:LatentStateDetails
    def to_dict(self):
        d=asdict(self)
        for k in ('timestamp','lastTrustedReferenceTimestamp'):
            if d[k] is not None: d[k]=d[k].isoformat().replace('+00:00','Z')
        return d
