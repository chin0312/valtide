"""API smoke tests for computed-result and explicit data-unavailable paths."""

import pytest
from fastapi.testclient import TestClient

from valtide_api import state_store
from valtide_api.main import app
from valtide_api.replay import replay
from valtide_api.scenario import load_scenario

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    state_store.reset()
    yield
    state_store.reset()


def _seed_scenario() -> None:
    result = replay(load_scenario())[-1]
    state_store.save_latest_result("NVDAx", result)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_valuation_returns_503_without_computed_result():
    resp = client.get("/api/valuation/NVDAx")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "data_unavailable"


def test_valuation_shape_from_computed_scenario_result():
    _seed_scenario()
    resp = client.get("/api/valuation/NVDAx")

    assert resp.status_code == 200
    body = resp.json()
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
    assert resp.json()[0]["model_available"] is True
