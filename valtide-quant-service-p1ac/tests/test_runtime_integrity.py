from pathlib import Path
import sys
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from valtide_quant_service import QuantService,MarketSnapshot

def snap(ts,cur=None,pyth=None,token=181.0):
    return MarketSnapshot('NVDAx',ts,'regular',token,cur,180.0,ts-timedelta(hours=1),pyth)

def test_pyth_cannot_change_fair_value_or_interval():
    t=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
    a=QuantService.from_default_artifacts().update(snap(t,cur=180.5,pyth=170.0))
    b=QuantService.from_default_artifacts().update(snap(t,cur=180.5,pyth=190.0))
    assert a.valtideFairValue==b.valtideFairValue
    assert a.fairValueLower==b.fairValueLower and a.fairValueUpper==b.fairValueUpper

def test_current_nvda_does_not_change_current_challenger_quote():
    t=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
    a=QuantService.from_default_artifacts().update(snap(t,cur=175.0))
    b=QuantService.from_default_artifacts().update(snap(t,cur=190.0))
    assert a.valtideFairValue==b.valtideFairValue
    assert a.fairValueLower==b.fairValueLower and a.fairValueUpper==b.fairValueUpper

def test_default_service_uses_generated_p1ac_calibrator():
    t=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
    result=QuantService.from_default_artifacts().update(snap(t,cur=180.5))
    assert result.modelId=='P1a-C'
    assert result.intervalCalibrationType=='session_sym'
    assert result.intervalCalibrationSource=='session:regular'
    assert result.intervalCoverageTarget==0.9
