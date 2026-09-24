"""API smoke tests for computed-result and explicit data-unavailable paths."""

import pytest
from fastapi.testclient import TestClient

from valtide_api import state_store
from valtide_api.main import app
from valtide_api.replay import replay, run_inference
from valtide_api.runtime_store import RuntimeStore
from valtide_api.scenario import load_scenario

client = TestClient(app)


@pytest.fixture
def runtime_store(tmp_path):
    return RuntimeStore(tmp_path / "runtime.sqlite3")


@pytest.fixture(autouse=True)
def reset_state():
    state_store.reset()
    yield
    state_store.reset()


def _seed_scenario(store: RuntimeStore) -> None:
    snapshots = load_scenario()
    results = replay(snapshots)
    state = None
    for snapshot in snapshots:
        _, state = run_inference(snapshot, state)
    assert state is not None
    store.save_runtime("NVDAx", state, results[-1])


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_valuation_returns_503_without_computed_result():
    resp = client.get("/api/valuation/NVDAx")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "data_unavailable"


def test_valuation_shape_from_computed_scenario_result(monkeypatch, runtime_store):
    import valtide_api.routes.valuation as valuation_route

    monkeypatch.setattr(valuation_route, "get_runtime_store", lambda: runtime_store)
    _seed_scenario(runtime_store)
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


def test_runtime_status_is_explicit_when_live_runtime_is_empty():
    resp = client.get("/api/runtime/NVDAx")

    assert resp.status_code == 200
    body = resp.json()
    assert body["scheduler_enabled"] is False
    assert body["has_state"] is False
    assert body["has_live_result"] is False
    assert body["last_tick_status"] is None
