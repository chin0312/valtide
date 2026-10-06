"""API smoke tests for computed-result and explicit data-unavailable paths."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from valtide_api import config as config_module
from valtide_api import publisher as publisher_module
from valtide_api import state_store
from valtide_api.config import Settings
from valtide_api.main import app
from valtide_api.replay import replay, run_inference
from valtide_api.routes import publish as publish_route
from valtide_api.routes import runtime as runtime_route
from valtide_api.runtime_store import (
    RuntimeStateIntegrityError,
    RuntimeStore,
    runtime_identity_for_asset,
)
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
    store.save_runtime(
        "NVDAx", state, results[-1], identity=runtime_identity_for_asset("NVDAx")
    )


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_weekend_demo_uses_v2_classifier_and_naturally_exercises_all_states():
    snapshots = load_scenario("weekend_divergence")
    results = replay(snapshots)

    assert len(snapshots) == len(results) == 6
    assert all(
        snapshot.reference_profile == "unified_xstock_p1ac_xperp_evidence_v1"
        and snapshot.xperp_index_price is not None
        and snapshot.xperp_index_source == "okx_xperp_index"
        and snapshot.xperp_index_ts == snapshot.observation_ts
        for snapshot in snapshots
    )
    assert [result.evidence_state.value for result in results] == [
        "SUPPORTED",
        "SUPPORTED",
        "SUPPORTED",
        "INCONCLUSIVE",
        "CHALLENGED",
        "CHALLENGED",
    ]
    assert all(
        result.reference_profile == "unified_xstock_p1ac_xperp_evidence_v1"
        and result.evidence_semantics
        == "p1a_xstock_band_with_xperp_review_corroboration_v2"
        and result.validation_target == "xstock_observed_price"
        and result.xperp_role == "second_market_challenger"
        for result in results
    )
    assert "P1A_XSTOCK_SUPPORT_BAND" in results[0].reason_codes
    assert "P1A_XSTOCK_WATCH_BAND" in results[3].reason_codes
    assert "P1A_XSTOCK_REVIEW_BAND" in results[4].reason_codes
    assert "XPERP_CORROBORATES_P1A" in results[4].reason_codes


def test_manual_publish_route_rejects_unverified_legacy_semantics_before_rpc(
    runtime_store, tmp_path, monkeypatch
):
    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo_root / "deployments" / "xlayer-testnet.json").read_text())
    nvda = manifest["assets"]["NVDAx"]
    manifest["demo"] = {
        key: nvda[key] for key in ("assetId", "referenceId", "modelVersion")
    }
    manifest["contracts"]["DemoCollateralVault"] = nvda["demoVault"]
    manifest.pop("assets")
    manifest.pop("deploymentReceipts", None)
    manifest["deployment"] = manifest.pop("initialDeployment")
    legacy_manifest = tmp_path / "legacy-nvdax-manifest.json"
    legacy_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        publish_enabled=True,
        deployment_manifest_path=legacy_manifest,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr(publish_route, "get_settings", lambda: settings)
    monkeypatch.setattr(publish_route, "get_runtime_store", lambda: runtime_store)
    monkeypatch.setattr(publisher_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        publisher_module,
        "connect_web3",
        lambda _config: pytest.fail("semantic gate must run before RPC access"),
    )
    _seed_scenario(runtime_store)

    response = client.post("/api/publish/NVDAx")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "deployed binding does not declare compatible evidence semantics"
    )


def test_runtime_exposes_semantic_publication_block_without_secret_fields(
    runtime_store, monkeypatch
):
    settings = Settings(
        _env_file=None,
        auto_publish_enabled=True,
        deployment_manifest_path=Path(__file__).resolve().parents[3]
        / "deployments"
        / "xlayer-testnet.json",
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    monkeypatch.setattr(runtime_route, "get_settings", lambda: settings)
    monkeypatch.setattr(runtime_route, "get_runtime_store", lambda: runtime_store)
    _seed_scenario(runtime_store)
    timestamp = runtime_store.load_runtime("NVDAx").latest_result.timestamp
    runtime_store.record_publication_blocked_semantic_mismatch("NVDAx", timestamp)

    response = client.get("/api/runtime/NVDAx")

    assert response.status_code == 200
    payload = response.json()
    assert payload["last_publish_status"] == "publication_blocked_semantic_mismatch"
    assert payload["last_publish_error"] == "deployed_binding_semantics_unverified"
    assert payload["auto_publish_enabled"] is True
    assert "publisher_private_key" not in payload
    assert "xlayer_rpc_url" not in payload


def test_cors_exposes_historical_source_header():
    resp = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert resp.headers["access-control-expose-headers"] == "X-Valtide-Source"


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
        "validation_target",
        "evidence_semantics",
        "xperp_role",
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
    assert resp.json()[0]["token_source"] == "okx_onchainos"
    assert resp.json()[0]["underlying_source"] == "alpaca"
    assert resp.json()[0]["model_available"] is True
    assert resp.json()[0]["challenger_detector_status"] == (
        "CHALLENGER_DETECTOR_NOT_PROMOTABLE"
    )
    assert resp.json()[0]["evidence_state_capability"] == (
        "TRI_SOURCE_SUPPORTED_AND_CHALLENGED"
    )
    assert [item["asset"] for item in resp.json()] == ["NVDAx", "SPYx", "AAPLx"]


def test_runtime_status_is_explicit_when_live_runtime_is_empty(monkeypatch, tmp_path):
    import valtide_api.routes.runtime as runtime_route

    empty_store = RuntimeStore(tmp_path / "empty-runtime.sqlite3")
    monkeypatch.setattr(runtime_route, "get_runtime_store", lambda: empty_store)
    resp = client.get("/api/runtime/NVDAx")

    assert resp.status_code == 200
    body = resp.json()
    assert body["scheduler_enabled"] is False
    assert body["has_state"] is False
    assert body["has_live_result"] is False
    assert body["last_tick_status"] is None


def test_runtime_status_exposes_publication_delivery_without_secrets(monkeypatch, tmp_path):
    import valtide_api.routes.runtime as runtime_route

    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    observed_at = datetime(2026, 9, 19, 13, 5, tzinfo=UTC)
    store.record_publication_attempt("NVDAx", observed_at)
    store.record_publication_failure(
        "NVDAx",
        observed_at,
        error="PublicationError",
    )
    monkeypatch.setattr(
        runtime_route,
        "get_settings",
        lambda: SimpleNamespace(
            live_scheduler_enabled=True,
            live_scheduler_asset="NVDAx",
            auto_publish_enabled=True,
        ),
    )
    monkeypatch.setattr(runtime_route, "get_runtime_store", lambda: store)

    response = client.get("/api/runtime/NVDAx")

    assert response.status_code == 200
    body = response.json()
    assert body["auto_publish_enabled"] is True
    assert body["last_publish_status"] == "failed"
    assert body["last_publish_observation_ts"] == observed_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert body["last_publish_error"] == "PublicationError"
    assert "publisher_private_key" not in body
    assert "xlayer_rpc_url" not in body


def test_runtime_status_reports_corrupt_publication_without_hiding_runtime(monkeypatch):
    import valtide_api.routes.runtime as runtime_route

    class CorruptPublicationStore:
        def load_runtime(self, asset, **_kwargs):  # noqa: ARG002
            return SimpleNamespace(
                state=None,
                latest_result=None,
                identity_verified=True,
                last_tick_status="success",
                last_tick_attempt_at=None,
                last_tick_error=None,
                last_gap_steps=0,
            )

        def load_publication(self, asset):  # noqa: ARG002
            raise RuntimeStateIntegrityError("secret-looking corruption detail")

        def raw_status(self, asset):  # noqa: ARG002
            return {}

    monkeypatch.setattr(
        runtime_route,
        "get_settings",
        lambda: SimpleNamespace(
            live_scheduler_enabled=False,
            live_scheduler_asset="NVDAx",
            auto_publish_enabled=True,
        ),
    )
    monkeypatch.setattr(runtime_route, "get_runtime_store", CorruptPublicationStore)

    response = client.get("/api/runtime/NVDAx")

    assert response.status_code == 200
    body = response.json()
    assert body["last_tick_status"] == "success"
    assert body["last_publish_status"] == "invalid"
    assert body["last_publish_error"] == (
        "RuntimeStateIntegrityError: publication state is invalid"
    )
    assert "secret-looking corruption detail" not in response.text


def test_runtime_status_reports_publication_when_runtime_state_is_corrupt(monkeypatch):
    import valtide_api.routes.runtime as runtime_route

    publication = SimpleNamespace(
        last_publish_status="published",
        last_publish_attempt_at=datetime(2026, 9, 19, 13, 5, tzinfo=UTC),
        last_publish_observation_ts=datetime(2026, 9, 19, 13, 5, tzinfo=UTC),
        last_published_observation_ts=datetime(2026, 9, 19, 13, 5, tzinfo=UTC),
        last_published_at=1_800_000_000,
        last_publish_tx_hash="0x" + "11" * 32,
        last_publish_error=None,
    )

    class CorruptRuntimeStore:
        def load_runtime(self, asset, **_kwargs):  # noqa: ARG002
            raise RuntimeStateIntegrityError("secret-looking corruption detail")

        def load_publication(self, asset):  # noqa: ARG002
            return publication

        def raw_status(self, asset):  # noqa: ARG002
            return {"last_gap_steps": 1}

    monkeypatch.setattr(
        runtime_route,
        "get_settings",
        lambda: SimpleNamespace(
            live_scheduler_enabled=False,
            live_scheduler_asset="NVDAx",
            auto_publish_enabled=True,
        ),
    )
    monkeypatch.setattr(runtime_route, "get_runtime_store", CorruptRuntimeStore)

    response = client.get("/api/runtime/NVDAx")

    assert response.status_code == 200
    body = response.json()
    assert body["last_error"] == "RuntimeStateIntegrityError: runtime state is invalid"
    assert body["last_publish_status"] == "published"
    assert body["last_publish_tx_hash"] == "0x" + "11" * 32
    assert "secret-looking corruption detail" not in response.text
