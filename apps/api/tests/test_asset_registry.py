"""Asset-registry, dispatch, and cross-asset isolation tests."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

import pytest
from fastapi.testclient import TestClient

from valtide_api import assets as assets_module
from valtide_api import quant_runtime, state_store
from valtide_api.assets import (
    AssetConfigurationError,
    UnsupportedAssetError,
    resolve_asset_config,
    supported_asset_names,
)
from valtide_api.config import Settings
from valtide_api.main import app
from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.publisher import build_attestation, load_deployment_config
from valtide_api.quant_runtime import estimate, get_quant_service, resolve_quant_runtime
from valtide_api.replay import run_inference
from valtide_api.runtime_store import RuntimeStateIntegrityError, RuntimeStore
from valtide_api.state_store import KalmanState
from valtide_api.validation import validate

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


def test_registry_exposes_four_primary_assets_and_keeps_tsla_as_hidden_candidate():
    assert supported_asset_names() == ("NVDAx", "SPYx", "QQQx", "AAPLx")
    assert "TSLAx" in {config.asset for config in assets_module.registered_asset_configs()}
    assert not assets_module.is_supported_asset("TSLAx")


def test_nvdax_config_keeps_existing_env_backed_bindings():
    settings = Settings(
        _env_file=None,
        okx_nvdax_chain_index="501",
        okx_nvdax_token_address="Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh",
        okx_xperp_index_id="NVDA-USD",
    )

    config = resolve_asset_config("NVDAx", settings)

    assert config.asset == "NVDAx"
    assert config.underlying_symbol == "NVDA"
    assert config.token_source == "okx_onchainos"
    assert config.reference_under_test_instrument == "NVDA-USD"
    assert config.quant_runtime_key == "nvdax_p1ac_default"
    assert resolve_quant_runtime(config).model_id == "P1a-C"
    assert resolve_quant_runtime(config).model_version == "0.2.0"
    assert config.okx_chain_index == "501"
    assert config.token_address == "Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh"
    assert config.allow_token_discovery is False


def test_nvdax_defaults_to_registered_solana_pin_and_rejects_cross_chain_override():
    config = resolve_asset_config("NVDAx", Settings(_env_file=None))
    assert (config.okx_chain_index, config.token_address) == (
        "501",
        "Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh",
    )
    with pytest.raises(AssetConfigurationError, match="does not match the registered Solana"):
        resolve_asset_config(
            "NVDAx",
            Settings(
                _env_file=None,
                okx_nvdax_chain_index="1",
                okx_nvdax_token_address="0xc845b2894dbddd03858fd2d643b4ef725fe0849d",
            ),
        )


def test_unknown_asset_fails_closed_before_source_or_artifact_selection():
    with pytest.raises(UnsupportedAssetError):
        resolve_asset_config("FOOx", Settings(_env_file=None))
    with pytest.raises(UnsupportedAssetError):
        get_quant_service("FOOx")


@pytest.mark.parametrize(
    ("asset", "underlying", "address"),
    [
        ("SPYx", "SPY", "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W"),
        ("QQQx", "QQQ", "Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ"),
        ("AAPLx", "AAPL", "XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp"),
    ],
)
def test_primary_token_bindings_and_frozen_quant_bundles_are_asset_specific(
    asset, underlying, address
):
    config = resolve_asset_config(asset, Settings(_env_file=None))

    assert (config.underlying_symbol, config.okx_chain_index, config.token_address) == (
        underlying,
        "501",
        address,
    )
    assert config.reference_profile == "unified_xstock_p1ac_xperp_evidence_v1"
    assert config.reference_under_test_source == "okx_xperp_index"
    assert config.reference_under_test_instrument == f"{underlying}-USD"
    assert config.allow_token_discovery is False
    assert config.capabilities.quant is True
    assert config.capabilities.runtime is True
    service = get_quant_service(asset)
    assert service.runtime.artifact.asset == asset
    assert service.runtime.artifact.model_version == "0.3.0"
    assert service.runtime.artifact.source_fit_sha256
    assert service.runtime.artifact.source_dataset_sha256


def test_registered_token_identity_matches_research_data_manifest():
    manifest = json.loads(
        (REPO_ROOT / "quant" / "data_manifest" / "datasets_manifest.json").read_text()
    )
    manifest_by_asset = {row["asset_id"]: row for row in manifest}

    for asset in ("NVDAx", "SPYx", "QQQx", "AAPLx", "TSLAx"):
        source_identity = manifest_by_asset[asset]
        overrides = {}
        if asset == "NVDAx":
            # Its legacy names remain environment-backed; pin the exact public
            # manifest identity in this test rather than invoking discovery.
            overrides = {
                "okx_nvdax_chain_index": str(source_identity["chain_index"]),
                "okx_nvdax_token_address": source_identity["token_address"],
            }
        config = resolve_asset_config(asset, Settings(_env_file=None, **overrides))
        assert config.okx_chain_index == str(source_identity["chain_index"]) == "501"
        assert config.token_address == source_identity["token_address"]
        assert config.underlying_symbol == source_identity["underlying_symbol"]


def test_partial_nvdax_deployment_binding_is_not_accepted():
    with pytest.raises(AssetConfigurationError, match="configured together"):
        resolve_asset_config(
            "NVDAx",
            Settings(_env_file=None, okx_nvdax_chain_index="501"),
        )


def test_quant_runtime_metadata_is_artifact_owned_and_registry_drives_api(monkeypatch):
    from valtide_api.routes.assets import list_assets

    config = resolve_asset_config("NVDAx", Settings(_env_file=None))
    spec = resolve_quant_runtime(config)
    assert (spec.asset, spec.model_id, spec.model_version) == ("NVDAx", "P1a-C", "0.2.0")
    import valtide_api.routes.assets as assets_route

    monkeypatch.setattr(assets_route, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(assets_route, "get_runtime_store", lambda: RuntimeStore(":memory:"))
    listed = list_assets()
    assert [item.asset for item in listed] == ["NVDAx", "SPYx", "QQQx", "AAPLx"]
    assert listed[0].model_available is True
    assert all(item.model_available for item in listed)
    assert all(item.reference_profile == "unified_xstock_p1ac_xperp_evidence_v1" for item in listed)
    assert all(not item.live_market_data_available for item in listed[1:])
    monkeypatch.setattr(quant_runtime, "_QUANT_RUNTIME_FACTORIES", MappingProxyType({}))
    assert list_assets()[0].model_available is False
    assert TestClient(app).get("/api/valuation/NVDAx/live").status_code == 503


def test_incomplete_synthetic_capabilities_do_not_activate_production_layers():
    config = resolve_asset_config("NVDAx", Settings(_env_file=None))
    synthetic = replace(
        config, asset="TESTx", underlying_symbol="TEST",
        quant_runtime_key="nvdax_p1ac_default", historical_panel_key="unregistered",
        capabilities=replace(config.capabilities, api_exposed=False, runtime=False, onchain=False),
    )
    assert "TESTx" not in supported_asset_names()
    with pytest.raises(AssetConfigurationError, match="artifact asset"):
        resolve_quant_runtime(synthetic)
    with pytest.raises(AssetConfigurationError, match="historical panel"):
        assets_module.resolve_historical_panel_path(synthetic)
    with pytest.raises(AssetConfigurationError, match="unknown quant runtime"):
        resolve_quant_runtime(replace(config, quant_runtime_key="unknown"))


def test_api_exposure_and_capabilities_are_independent(monkeypatch):
    base = resolve_asset_config("NVDAx", Settings(_env_file=None))
    synthetic = replace(
        base, asset="TESTx", underlying_symbol="TEST", okx_chain_index="777",
        token_address="0xsynthetic", allow_token_discovery=False,
        capabilities=replace(
            base.capabilities, api_exposed=False, live_data=False,
            runtime=False, onchain=False,
        ),
    )
    monkeypatch.setattr(
        assets_module, "_ASSET_REGISTRY",
        MappingProxyType({"NVDAx": assets_module._NVDA_CONFIG, "TESTx": synthetic}),
    )
    client = TestClient(app)
    assert client.get("/api/runtime/TESTx").status_code == 404
    assert "TESTx" not in [item["asset"] for item in client.get("/api/assets").json()]

    monkeypatch.setattr(
        assets_module, "_ASSET_REGISTRY",
        MappingProxyType({
            "NVDAx": assets_module._NVDA_CONFIG,
            "TESTx": replace(
                synthetic,
                capabilities=replace(
                    synthetic.capabilities,
                    api_exposed=True,
                    live_data=True,
                    quant=False,
                ),
            ),
        }),
    )
    runtime = client.get("/api/runtime/TESTx")
    assert runtime.status_code == 200
    assert runtime.json()["scheduler_enabled"] is False
    assert client.get("/api/onchain/TESTx").json()["detail"] == "ONCHAIN_NOT_CONFIGURED"
    assert client.get("/api/valuation/TESTx/live").json()["detail"] == "MODEL_FIT_BLOCKED"


def test_historical_panel_loader_cannot_inherit_nvdax_path_for_unknown_asset(tmp_path):
    settings = Settings(_env_file=None, historical_panel_path=tmp_path / "nvdax.csv")
    spy = resolve_asset_config("SPYx", settings)
    with pytest.raises(AssetConfigurationError, match="not configured for 'SPYx'"):
        assets_module.resolve_historical_panel_path(spy, settings)


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


# Frozen from the accepted P1a-C 0.2.0 artifact and backend validation on the
# deterministic four-step sequence below, before this dispatch refactor.
# Literal values intentionally protect causal token-first / underlying-after
# ordering and Evidence State decisions; they are never computed from a second
# invocation of the runtime as an oracle.
_GOLDEN_STEPS = [
    (120.3042612160223, 120.09579726009031, 120.51308702658963,
     4.790024043932874, 7.594589496003624e-07, 4.790024043932874,
     7.594589496003624e-07, 0.0012894491675961993, "INCONCLUSIVE",
     ["CALIBRATION_GLOBAL_FALLBACK", "TOKEN_AND_CHALLENGER_AGREE"],
     0.16270311791053427, 1.2607778877130742),
    (120.77006066778506, 120.56538715557272, 120.97508163665631,
     4.793888412628675, 6.871443270832543e-07, 4.794710261865752,
     3.9025181196678715e-07, 0.0012610965598626551, "CHALLENGED",
     ["REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL", "CALIBRATION_GLOBAL_FALLBACK"],
     3.502473468031675, 27.297929254026027),
    (120.86935624741585, 120.6715292493172, 121.06750755996896,
     4.794710261865752, 5.799993071374501e-07, 4.794710261865752,
     5.799993071374501e-07, 0.0012178749990666609, "INCONCLUSIVE",
     ["TOKEN_DATA_UNAVAILABLE", "REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL",
      "CALIBRATION_GLOBAL_FALLBACK"], 2.5901054243854915, 20.99665709443221),
    (120.78200566266659, 120.58379501185405, 120.98054212394223,
     4.793987314658972, 5.879187755101473e-07, 4.788126881881963,
     3.561171186333003e-07, 0.0012211220175413742, "CHALLENGED",
     ["REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL", "CALIBRATION_GLOBAL_FALLBACK",
      "TOKEN_AND_CHALLENGER_AGREE"], -1.0614210747974528, -8.738638018247864),
]


def test_frozen_nvdax_numerical_causal_sequence_and_publication_identity():
    start = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    anchor, anchor_ts = 120.0, start - timedelta(minutes=5)
    state = None
    final_result = None
    for index, (token, underlying, reference) in enumerate(
        [(121.0, None, 120.5), (122.0, 121.0, 125.0),
         (None, None, 124.0), (120.5, 119.0, 119.5)]
    ):
        ts = start + timedelta(minutes=5 * index)
        snapshot = _snapshot().model_copy(update={
            "observation_ts": ts,
            "token_price": token,
            "token_volume": 100.0 if token is not None else None,
            "token_volume_usd": 12_100.0 if token is not None else None,
            "token_source": "okx_onchainos" if token is not None else None,
            "token_observed_at": ts if token is not None else None,
            "underlying_reference": underlying,
            "underlying_reference_ts": ts if underlying is not None else None,
            "last_trusted_reference": anchor,
            "last_trusted_reference_ts": anchor_ts,
            "reference_age_seconds": int((ts - anchor_ts).total_seconds()),
            "reference_under_test": reference,
            "reference_under_test_ts": ts,
            "market_state": MarketState.CLOSED,
            "source_provenance": {"test": "golden"},
        })
        value = estimate(
            snapshot,
            state.m if state else None,
            state.P if state else None,
            state.last_ts if state else None,
        )
        final_result = validate(snapshot, value)
        expected = _GOLDEN_STEPS[index]
        actual = (
            value.fair_value, value.lower_bound, value.upper_bound,
            value.state_m, value.state_sd_log**2, value.state_m_after_nvda,
            value.state_P_after_nvda, value.reference_predictive_sd_log,
            final_result.evidence_state.value, final_result.reason_codes,
            final_result.reference_deviation_pct, final_result.standardized_deviation,
        )
        for got, want in zip(actual, expected, strict=True):
            if isinstance(want, float):
                assert got == pytest.approx(want, rel=1e-11, abs=1e-12)
            else:
                assert got == want
        assert (value.model_id, value.model_version) == ("P1a-C", "0.2.0")
        state = KalmanState(value.state_m_after_nvda, value.state_P_after_nvda, ts)
        if underlying is not None:
            anchor, anchor_ts = underlying, ts

    config = load_deployment_config(Settings(_env_file=None))
    payload = build_attestation(
        final_result, config=config, validity_seconds=900,
        current_chain_timestamp=int(final_result.timestamp.timestamp()) + 1,
        settings=Settings(_env_file=None),
    )
    assert payload["assetId"] == (
        "0xd475b7977c1c808b1faa8fbe092d3f952b6007a6ec418a58f877a69a3945440c"
    )
    assert payload["referenceId"] == (
        "0x53d122bd54a2ebc11b119ef6d5f1bbb7fca155dac4c7cfc997edd3182646850d"
    )
    assert payload["modelVersion"] == (
        "0x177d57055bb57caacc5f72e04f893f984b95e26f8749bff5b374a6d1548ea727"
    )
    assert payload["observedAt"] == int((start + timedelta(minutes=15)).timestamp())
