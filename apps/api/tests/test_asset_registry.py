"""Asset-registry, dispatch, and cross-asset isolation tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from valtide_api import state_store
from valtide_api.assets import (
    AssetConfigurationError,
    UnsupportedAssetError,
    resolve_asset_config,
    supported_asset_names,
)
from valtide_api.config import Settings
from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.panel import load_panel_snapshots
from valtide_api.publisher import build_attestation, load_deployment_config
from valtide_api.quant_runtime import get_quant_service
from valtide_api.replay import run_inference
from valtide_api.runtime_store import RuntimeStateIntegrityError, RuntimeStore
from valtide_api.state_store import KalmanState

REPO_ROOT = Path(__file__).resolve().parents[3]


def _snapshot(asset: str = "NVDAx") -> MarketSnapshot:
    timestamp = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    return MarketSnapshot(
        asset=asset,
        observation_ts=timestamp,
        token_price=121.0,
        token_volume=100.0,
        token_volume_usd=12_100.0,
        token_source="okx_onchainos",
        token_observed_at=timestamp,
        underlying_reference=None,
        underlying_reference_ts=None,
        last_trusted_reference=120.0,
        last_trusted_reference_ts=timestamp - timedelta(minutes=5),
        reference_age_seconds=300,
        reference_under_test=120.5,
        reference_under_test_source="okx_xperp_index",
        reference_under_test_ts=timestamp,
        reference_under_test_age_seconds=0,
        market_state=MarketState.CLOSED,
        source_provenance={"test": "asset_registry"},
    )


def test_registry_contains_only_nvdax_production_asset():
    assert supported_asset_names() == ("NVDAx",)


def test_nvdax_config_keeps_existing_env_backed_bindings():
    settings = Settings(
        _env_file=None,
        okx_nvdax_chain_index="501",
        okx_nvdax_token_address="0x" + "ab" * 20,
        okx_xperp_index_id="NVDA-USD",
    )

    config = resolve_asset_config("NVDAx", settings)

    assert config.asset == "NVDAx"
    assert config.underlying_symbol == "NVDA"
    assert config.token_source == "okx_onchainos"
    assert config.reference_under_test_instrument == "NVDA-USD"
    assert config.quant_model_id == "P1a-C"
    assert config.quant_model_version == "0.2.0"
    assert config.okx_chain_index == "501"


def test_unknown_asset_fails_closed_before_source_or_artifact_selection():
    with pytest.raises(UnsupportedAssetError):
        resolve_asset_config("SPYx", Settings(_env_file=None))
    with pytest.raises(UnsupportedAssetError):
        get_quant_service("SPYx")


def test_partial_nvdax_deployment_binding_is_not_accepted():
    with pytest.raises(AssetConfigurationError, match="configured together"):
        resolve_asset_config(
            "NVDAx",
            Settings(_env_file=None, okx_nvdax_chain_index="501"),
        )


def test_historical_panel_loader_cannot_inherit_nvdax_path_for_unknown_asset(tmp_path):
    with pytest.raises(UnsupportedAssetError):
        load_panel_snapshots(tmp_path / "missing.csv", asset="SPYx")


def test_state_store_keeps_synthetic_asset_keys_independent():
    state_store.reset()
    try:
        timestamp = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
        state_a = KalmanState(m=1.0, P=2.0, last_ts=timestamp)
        state_b = KalmanState(m=3.0, P=4.0, last_ts=timestamp)
        base_result = run_inference(_snapshot(), None)[0]
        result_a = base_result.model_copy(update={"asset": "AssetA"})
        result_b = base_result.model_copy(update={"asset": "AssetB"})

        state_store.save_state("AssetA", state_a)
        state_store.save_state("AssetB", state_b)
        state_store.save_latest_result("AssetA", result_a)
        state_store.save_latest_result("AssetB", result_b)

        assert state_store.load_state("AssetA") == state_a
        assert state_store.load_state("AssetB") == state_b
        assert state_store.get_latest_result("AssetA").asset == "AssetA"
        assert state_store.get_latest_result("AssetB").asset == "AssetB"
        with pytest.raises(ValueError, match="does not match state key"):
            state_store.save_latest_result("AssetA", result_b)
    finally:
        state_store.reset()


def test_runtime_store_rejects_result_under_the_wrong_asset_key(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    timestamp = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    state = KalmanState(m=1.0, P=2.0, last_ts=timestamp)
    result = run_inference(_snapshot(), None)[0].model_copy(update={"asset": "AssetA"})

    with pytest.raises(RuntimeStateIntegrityError, match="does not match runtime key"):
        store.save_runtime("AssetB", state, result)


def test_runtime_history_and_publication_records_remain_asset_scoped(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    base_result, state = run_inference(_snapshot(), None)
    result_a = base_result.model_copy(update={"asset": "AssetA"})
    result_b = base_result.model_copy(update={"asset": "AssetB"})

    store.save_runtime_and_history("AssetA", state, result_a)
    store.save_runtime_and_history("AssetB", state, result_b)
    store.record_publication_success(
        "AssetA",
        result_a.timestamp,
        status="published",
        published_at=1_800_000_000,
        tx_hash="0xasset-a",
    )
    store.record_publication_success(
        "AssetB",
        result_b.timestamp,
        status="already_published",
        published_at=1_800_000_001,
        tx_hash=None,
    )

    assert store.load_runtime("AssetA").latest_result.asset == "AssetA"
    assert store.load_runtime("AssetB").latest_result.asset == "AssetB"
    assert [item.asset for item in store.load_history("AssetA")] == ["AssetA"]
    assert [item.asset for item in store.load_history("AssetB")] == ["AssetB"]
    assert store.load_publication("AssetA").last_publish_tx_hash == "0xasset-a"
    assert store.load_publication("AssetB").last_publish_tx_hash is None


def test_golden_nvdax_quant_to_runtime_boundary_remains_p1ac():
    snapshot = _snapshot()
    result, state = run_inference(snapshot, None)
    config = load_deployment_config(
        Settings(
            _env_file=None,
            deployment_manifest_path=REPO_ROOT / "deployments" / "xlayer-testnet.json",
        )
    )
    payload = build_attestation(
        result,
        config=config,
        validity_seconds=900,
        current_chain_timestamp=int(snapshot.observation_ts.timestamp()) + 1,
        settings=Settings(_env_file=None, publish_validity_seconds=900),
    )

    assert result.asset == "NVDAx"
    assert result.model_id == "P1a-C"
    assert result.model_version == "0.2.0"
    assert result.reference_under_test_source == "okx_xperp_index"
    assert state.last_ts == snapshot.observation_ts
    assert payload["assetId"] == config.asset_id
    assert payload["referenceId"] == config.reference_id
    assert payload["modelVersion"] == config.model_version
    assert payload["observedAt"] == int(snapshot.observation_ts.timestamp())
