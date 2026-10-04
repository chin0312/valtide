from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class CalibrationBounds:
    q_lower:float; q_upper:float; source:str; calibration_type:str; level:float
class P1aCCalibrator:
    def __init__(self,path:str|Path,level:float|None=None):
        x=json.loads(Path(path).read_text()); self.raw=x; self.level=float(level or x['primary_level'])
        cs=x['calibrators']; key=f'{self.level:.2f}'
        self.cal=cs[key] if key in cs else next(v for v in cs.values() if abs(float(v['level'])-self.level)<1e-9)
    def bounds(self,session:str)->CalibrationBounds:
        c=self.cal; use=c['global']; source='global'
        if c['type'].startswith('session_'):
            if session in (c.get('sessions') or {}): use=c['sessions'][session]; source=f'session:{session}'
            else: source='global_fallback'
        if c['type'].endswith('_sym') or c['type']=='global_sym': lo,hi=-float(use['sym']),float(use['sym'])
        else: lo,hi=float(use['lo']),float(use['hi'])
        return CalibrationBounds(lo,hi,source,c['type'],self.level)
