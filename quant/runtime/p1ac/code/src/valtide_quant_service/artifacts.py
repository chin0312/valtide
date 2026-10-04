from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

SESSIONS=('regular','premarket','afterhours','overnight','closed')
@dataclass(frozen=True)
class P1aArtifact:
    model_family:str; deployment_model_id:str; model_version:str; asset:str; interval_level:float
    q_by_session:dict[str,float]; r_nvda:float; r_nvdax:float; trained_through_utc:str|None

def load_p1a(path:str|Path)->P1aArtifact:
    x=json.loads(Path(path).read_text())
    q={k:float(v) for k,v in x['q_by_session'].items()}
    if any(s not in q for s in SESSIONS): raise ValueError('missing session Q')
    if any(v<=0 for v in q.values()) or float(x['r_nvda'])<=0 or float(x['r_nvdax'])<=0: raise ValueError('variances must be positive')
    return P1aArtifact(x['model_family'],x['deployment_model_id'],x['model_version'],x['asset'],float(x.get('interval_level',.9)),q,float(x['r_nvda']),float(x['r_nvdax']),x.get('trained_through_utc'))
