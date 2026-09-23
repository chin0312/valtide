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
    assert a.fair_value==b.fair_value
    assert a.lower_bound==b.lower_bound and a.upper_bound==b.upper_bound
    assert a.carried_state==b.carried_state

def test_current_nvda_does_not_change_current_challenger_quote():
    t=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
    a=QuantService.from_default_artifacts().update(snap(t,cur=175.0))
    b=QuantService.from_default_artifacts().update(snap(t,cur=190.0))
    assert a.fair_value==b.fair_value
    assert a.lower_bound==b.lower_bound and a.upper_bound==b.upper_bound


def test_reference_comparator_does_not_create_product_verdict():
    t=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
    a=QuantService.from_default_artifacts().update(snap(t,cur=180.5,pyth=160.0))
    b=QuantService.from_default_artifacts().update(snap(t,cur=180.5,pyth=205.0))
    assert a==b
    payload=a.to_dict()
    legacy_fields=('challenge'+'Status','externalComparator'+'Status')
    assert all(not hasattr(a,field) and field not in payload for field in legacy_fields)

def test_default_service_uses_generated_p1ac_calibrator():
    t=datetime(2026,9,23,12,0,tzinfo=timezone.utc)
    result=QuantService.from_default_artifacts().update(snap(t,cur=180.5))
    assert result.model_id=='P1a-C'
    assert result.interval_calibration_type=='session_sym'
    assert result.interval_calibration_source=='session:regular'
    assert result.interval_coverage_target==0.9
    assert result.carried_state.timestamp==t
