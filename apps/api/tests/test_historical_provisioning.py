from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
from scripts.provision_historical_panels import (
    DEFAULT_MANIFEST,
    PanelProvisioningError,
    load_manifest,
    provision_panel,
    verify_panel,
)

from valtide_api.assets import resolve_asset_config, resolve_historical_panel_path
from valtide_api.config import Settings
from valtide_api.quant_runtime import resolve_quant_runtime

_ASSETS = ("NVDAx", "SPYx", "AAPLx")
_ROOT = Path(__file__).resolve().parents[3]
_HEADERS = (
    "timestamp_utc",
    "asset",
    "underlying_symbol",
    "token_source",
    "token_chain_index",
    "token_address",
    "reference_under_test_instrument",
    "reference_under_test_source",
    "reference_profile",
    "session_state",
    "token_close",
    "token_volume",
    "token_volume_usd",
    "token_available",
    "token_observed_at",
    "underlying_close",
    "underlying_available",
    "underlying_observed_at",
    "last_trusted_reference",
    "last_trusted_reference_ts",
    "reference_under_test",
    "reference_under_test_available",
    "reference_under_test_ts",
)


def _settings() -> Settings:
    manifest = load_manifest()
    nvda = manifest["assets"]["NVDAx"]
    return Settings(
        _env_file=None,
        okx_nvdax_chain_index=nvda["chain_index"],
        okx_nvdax_token_address=nvda["token_address"],
    )


def _write_fixture(path: Path, asset: str, **first_row_overrides: str) -> list[dict[str, str]]:
    config = resolve_asset_config(asset, _settings())
    rows = []
    for minute, price in ((0, "100.25"), (5, "100.75")):
        timestamp = f"2026-10-01T15:{minute:02d}:00Z"
        row = {
            "timestamp_utc": timestamp,
            "asset": asset,
            "underlying_symbol": config.underlying_symbol,
            "token_source": config.token_source,
            "token_chain_index": config.okx_chain_index or "",
            "token_address": config.token_address or "",
            "reference_under_test_instrument": config.reference_under_test_instrument,
            "reference_under_test_source": config.reference_under_test_source,
            "reference_profile": config.reference_profile,
            "session_state": "regular",
            "token_close": price,
            "token_volume": "10",
            "token_volume_usd": "1000",
            "token_available": "TRUE",
            "token_observed_at": timestamp,
            "underlying_close": price,
            "underlying_available": "TRUE",
            "underlying_observed_at": timestamp,
            "last_trusted_reference": "100.00",
            "last_trusted_reference_ts": f"2026-10-01T14:{55 if minute == 0 else 0:02d}:00Z",
            "reference_under_test": price,
            "reference_under_test_available": "TRUE",
            "reference_under_test_ts": timestamp,
        }
        if not rows:
            row.update(first_row_overrides)
        rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _expected(asset: str, panel: Path) -> dict:
    manifest = load_manifest()
    expected = dict(manifest["assets"][asset])
    with panel.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    expected.update(
        sha256=hashlib.sha256(panel.read_bytes()).hexdigest(),
        rows=len(rows),
        window_start_utc=rows[0]["timestamp_utc"],
        window_end_utc=rows[-1]["timestamp_utc"],
    )
    return expected


def test_production_manifest_binds_four_panels_to_registered_identities() -> None:
    manifest = load_manifest(DEFAULT_MANIFEST)
    fresh_manifest = json.loads(
        (_ROOT / "quant/data_manifest/fresh_validation_20261005.json").read_text(
            encoding="utf-8"
        )
    )
    assert tuple(manifest["assets"]) == _ASSETS
    settings = _settings()
    for asset in _ASSETS:
        expected = manifest["assets"][asset]
        config = resolve_asset_config(asset, settings)
        assert expected["asset"] == asset
        assert expected["token_source"] == config.token_source == "okx_onchainos"
        assert expected["chain_index"] == config.okx_chain_index == "501"
        assert expected["token_address"] == config.token_address
        assert expected["underlying_source"] == config.underlying_source == "alpaca"
        assert expected["underlying_symbol"] == config.underlying_symbol
        assert expected["reference_source"] == config.reference_under_test_source
        assert expected["reference_instrument"] == config.reference_under_test_instrument
        assert expected["reference_profile"] == config.reference_profile
        assert expected["persistent_path"] == (
            f"/data/historical/panels/20261005/{asset.lower()}_historical_5m.csv"
        )
        assert expected["rows"] == 4110
        assert expected["sha256"] == fresh_manifest["assets"][asset]["panel_sha256"]
        runtime = resolve_quant_runtime(config)
        assert expected["model_id"] == runtime.model_id
        assert expected["model_version"] == runtime.model_version


@pytest.mark.parametrize("asset", _ASSETS)
def test_each_asset_resolves_only_its_own_configured_panel(tmp_path: Path, asset: str) -> None:
    paths = {
        "historical_panel_path": tmp_path / "nvdax.csv",
        "spyx_historical_panel_path": tmp_path / "spyx.csv",
        "aaplx_historical_panel_path": tmp_path / "aaplx.csv",
    }
    settings = Settings(_env_file=None, **paths)
    config = resolve_asset_config(asset, settings)
    resolved = resolve_historical_panel_path(config, settings)
    field = {
        "NVDAx": "historical_panel_path",
        "SPYx": "spyx_historical_panel_path",
        "AAPLx": "aaplx_historical_panel_path",
    }[asset]
    assert resolved == paths[field]
    resolved_paths = {
        resolve_historical_panel_path(resolve_asset_config(name, settings), settings)
        for name in _ASSETS
    }
    assert len(resolved_paths) == 3


def test_relative_panel_paths_resolve_from_repository_root() -> None:
    settings = Settings(
        _env_file=None,
        historical_panel_path=Path("data/panels/nvda.csv"),
        spyx_historical_panel_path=Path("data/panels/spy.csv"),
        aaplx_historical_panel_path=Path("data/panels/aapl.csv"),
    )
    paths = {
        asset: resolve_historical_panel_path(resolve_asset_config(asset, settings), settings)
        for asset in _ASSETS
    }
    assert paths == {
        "NVDAx": _ROOT / "data/panels/nvda.csv",
        "SPYx": _ROOT / "data/panels/spy.csv",
        "AAPLx": _ROOT / "data/panels/aapl.csv",
    }


def test_verifier_accepts_canonical_replay_ready_panel(tmp_path: Path) -> None:
    source = tmp_path / "spyx.csv"
    _write_fixture(source, "SPYx")
    expected = _expected("SPYx", source)

    verified = verify_panel(source, asset="SPYx", expected=expected)

    assert verified.asset == "SPYx"
    assert verified.sha256 == expected["sha256"]
    assert verified.rows == 2
    assert verified.window_start_utc == "2026-10-01T15:00:00Z"
    assert verified.window_end_utc == "2026-10-01T15:05:00Z"


def test_verifier_rejects_wrong_sha_asset_chain_and_address(tmp_path: Path) -> None:
    source = tmp_path / "spyx.csv"
    _write_fixture(source, "SPYx")
    expected = _expected("SPYx", source)

    with pytest.raises(PanelProvisioningError, match="SHA-256"):
        verify_panel(source, asset="SPYx", expected={**expected, "sha256": "0" * 64})
    with pytest.raises(PanelProvisioningError, match="asset"):
        verify_panel(source, asset="QQQx", expected=expected)
    with pytest.raises(PanelProvisioningError, match="chain_index"):
        verify_panel(source, asset="SPYx", expected={**expected, "chain_index": "1"})
    with pytest.raises(PanelProvisioningError, match="token_address"):
        verify_panel(source, asset="SPYx", expected={**expected, "token_address": "wrong"})


def test_qqqx_is_not_a_production_provisioning_target() -> None:
    with pytest.raises(PanelProvisioningError, match="requested asset"):
        verify_panel(
            "/does/not/need/to/exist.csv",
            asset="QQQx",
            expected={"asset": "QQQx"},
        )


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    (("model_id", "P1a"), ("model_version", "0.2.0")),
)
def test_verifier_rejects_model_binding_mismatch(
    tmp_path: Path, field: str, wrong_value: str
) -> None:
    source = tmp_path / "spyx.csv"
    _write_fixture(source, "SPYx")
    expected = _expected("SPYx", source)

    with pytest.raises(PanelProvisioningError, match=field):
        verify_panel(
            source,
            asset="SPYx",
            expected={**expected, field: wrong_value},
        )


@pytest.mark.parametrize(
    ("identity_field", "wrong_value"),
    (
        ("asset", "QQQx"),
        ("token_chain_index", "1"),
        ("token_address", "wrong-solana-mint"),
        ("token_source", "ethereum_token_market"),
    ),
)
def test_verifier_rejects_panel_identity_mismatch(
    tmp_path: Path, identity_field: str, wrong_value: str
) -> None:
    source = tmp_path / "mismatched.csv"
    _write_fixture(source, "SPYx")
    with source.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row[identity_field] = wrong_value
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    expected = _expected("SPYx", source)

    with pytest.raises(PanelProvisioningError, match="identity is invalid"):
        verify_panel(source, asset="SPYx", expected=expected)


def test_verifier_rejects_corrupt_or_noncanonical_csv(tmp_path: Path) -> None:
    source = tmp_path / "broken.csv"
    source.write_text("timestamp_utc,asset\n2026-10-01T15:00:00Z,SPYx\n", encoding="utf-8")
    expected = _expected("SPYx", source)

    with pytest.raises(PanelProvisioningError, match="identity is invalid|canonical"):
        verify_panel(source, asset="SPYx", expected=expected)


def test_provisioning_is_idempotent_and_refuses_to_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "spyx.csv"
    _write_fixture(source, "SPYx")
    expected = _expected("SPYx", source)
    destination = tmp_path / "spyx_historical_5m.csv"
    expected["persistent_path"] = str(destination)

    first = provision_panel(source, destination, asset="SPYx", expected=expected)
    second = provision_panel(source, destination, asset="SPYx", expected=expected)
    assert first == second
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == expected["sha256"]

    destination.write_bytes(b"existing different bytes")
    with pytest.raises(PanelProvisioningError, match="refusing to overwrite"):
        provision_panel(source, destination, asset="SPYx", expected=expected)
    assert destination.read_bytes() == b"existing different bytes"


def test_manifest_refuses_nonproduction_destination_mapping(tmp_path: Path) -> None:
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    manifest["assets"]["SPYx"]["persistent_path"] = str(tmp_path / "wrong.csv")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PanelProvisioningError, match="path is invalid"):
        load_manifest(path)
