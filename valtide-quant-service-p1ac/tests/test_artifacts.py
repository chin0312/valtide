from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from valtide_quant_service.artifacts import load_p1a
from valtide_quant_service.calibration import P1aCCalibrator

def test_exact_trained_parameters_present():
    a=load_p1a(ROOT/'artifacts/p1a_runtime.json')
    assert abs(a.q_by_session['regular']-3.02764671034894e-6)<1e-15
    assert abs(a.r_nvda-9.03220206214169e-7)<1e-15
    assert abs(a.r_nvdax-2.48888251957261e-6)<1e-15

def test_actual_p1ac_90_calibrator():
    c=P1aCCalibrator(ROOT/'artifacts/p1a_c_calibrator.json')
    assert abs(c.bounds('regular').q_upper-1.4520)<1e-9
    assert abs(c.bounds('afterhours').q_upper-1.0122)<1e-9
    assert abs(c.bounds('closed').q_upper-1.3450)<1e-9
    assert c.bounds('closed').source=='global_fallback'

def test_provenance_hashes_match_artifacts():
    provenance=json.loads((ROOT/'artifacts/provenance.json').read_text())
    for name,expected in provenance['artifact_sha256'].items():
        artifact=ROOT/'artifacts'/name
        actual=hashlib.sha256(artifact.read_bytes()).hexdigest()
        assert actual==expected
