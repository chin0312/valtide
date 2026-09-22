"""Phase 1 smoke tests: the app boots and the mock endpoints answer."""

from fastapi.testclient import TestClient

from valtide_api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_valuation_shape():
    resp = client.get("/api/valuation/NVDAx")
    assert resp.status_code == 200
    body = resp.json()
    # Fields the frontend depends on.
    for key in (
        "valtide_fair_value",
        "fair_value_lower",
        "fair_value_upper",
        "reference_under_test",
        "standardized_deviation",
        "evidence_state",
        "reason_codes",
    ):
        assert key in body
    assert body["evidence_state"] in ("SUPPORTED", "INCONCLUSIVE", "CHALLENGED")


def test_unknown_asset_404():
    resp = client.get("/api/valuation/FOOx")
    assert resp.status_code == 404


def test_assets_list():
    resp = client.get("/api/assets")
    assert resp.status_code == 200
    assert resp.json()[0]["asset"] == "NVDAx"
