"""Panel loader and backend × quant replay integration tests."""

from dataclasses import replace
from types import MappingProxyType

import pytest

import valtide_api.assets as assets_module
from valtide_api.config import Settings
from valtide_api.models import EvidenceState
from valtide_api.panel import (
    PanelIdentityError,
    PanelTimestampError,
    inspect_panel_readiness,
    load_panel_snapshots,
)
from valtide_api.replay import replay

_COLS = (
    "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
    "nvda_available,nvdax_available,session_state,time_since_nvda_min"
)
_ROWS = [
    "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
    "2026-09-20T14:05:00Z,NA,NA,NA,NA,FALSE,FALSE,closed,5",
    "2026-09-20T14:10:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,10",
    "2026-09-20T14:15:00Z,NA,NA,180.4,950,FALSE,TRUE,closed,15",
]
_CSV = "\n".join([_COLS, *_ROWS]) + "\n"


def _write(tmp_path, contents: str = _CSV):
    path = tmp_path / "p0_panel_5m.csv"
    path.write_text(contents)
    return path


def _pinned_settings(
    chain="501", address="Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh"
):
    return Settings(
        _env_file=None,
        okx_nvdax_chain_index=chain,
        okx_nvdax_token_address=address,
    )


def test_missing_token_row_is_preserved(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    assert len(snapshots) == 3
    assert snapshots[0].token_price is None
    assert snapshots[0].token_volume_usd is None
    assert snapshots[1].token_price == 180.3


def test_panel_loads_optional_usd_volume_column(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
        "nvdax_volume_usd,nvda_available,nvdax_available,session_state"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,90000,TRUE,TRUE,closed",
        "2026-09-20T14:05:00Z,NA,NA,180.3,900,123456,FALSE,TRUE,closed",
    ]

    snapshots = load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))

    # The first row establishes the trusted anchor and is not emitted as a
    # public snapshot; the next row proves the optional column is preserved.
    assert len(snapshots) == 1
    assert snapshots[0].token_volume_usd == 123_456.0


def test_reference_is_live_then_explicit_stale_reference(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    assert snapshots[0].observation_ts.minute == 5
    assert snapshots[0].reference_under_test == 180.0
    assert snapshots[0].reference_under_test_source == "stale_nvda"
    assert snapshots[0].underlying_reference is None
    assert snapshots[0].last_trusted_reference == 180.0
    assert snapshots[0].last_trusted_reference_ts.minute == 0


def test_legacy_panel_is_explicitly_labelled_diagnostic(tmp_path, monkeypatch):
    import valtide_api.data_source as data_source

    monkeypatch.setattr(data_source, "get_settings", lambda: Settings(_env_file=None))
    path = _write(tmp_path)
    snapshots, source = data_source.resolve_snapshots(
        source="panel",
        panel_path=path,
        asset="NVDAx",
    )
    assert snapshots
    assert source == "legacy_nvda_panel_diagnostic"
    assert snapshots[0].source_provenance["token_deployment_verified"] == "false"


def test_reference_age_grows_over_canonical_grid(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    ages = [snapshot.reference_age_seconds for snapshot in snapshots]
    assert ages == [300, 600, 900]
    assert ages[-1] > ages[0]


def test_panel_replays_through_quant_and_validation(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    results = replay(snapshots)

    assert len(results) == len(snapshots)
    assert results[0].evidence_state == EvidenceState.INCONCLUSIVE
    assert "TOKEN_DATA_UNAVAILABLE" in results[0].reason_codes
    assert results[0].observed_token_move_pct is None
    assert results[0].residual_premium_discount_pct is None
    assert results[0].model_id == "P1a-C"
    assert results[0].interval_calibration_source == "global_fallback"
    assert "CALIBRATION_GLOBAL_FALLBACK" in results[0].reason_codes
    assert results[1].timestamp == snapshots[1].observation_ts
    assert results[1].token_price == 180.3


def test_current_nvda_uses_prior_anchor_and_first_anchor_is_not_public(tmp_path):
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
        "2026-09-20T14:05:00Z,181.0,1000,181.1,500,TRUE,TRUE,closed,5",
        "2026-09-20T14:10:00Z,NA,NA,181.2,500,FALSE,TRUE,closed,10",
    ]
    snapshots = load_panel_snapshots(_write(tmp_path, "\n".join([_COLS, *rows]) + "\n"))

    assert [snapshot.observation_ts.minute for snapshot in snapshots] == [5, 10]
    assert snapshots[0].last_trusted_reference == 180.0
    assert snapshots[0].last_trusted_reference_ts.minute == 0
    assert snapshots[0].underlying_reference == 181.0
    assert snapshots[0].underlying_reference_ts == snapshots[0].observation_ts
    assert snapshots[1].last_trusted_reference == 181.0
    assert snapshots[1].last_trusted_reference_ts.minute == 5


def test_explicit_lookback_anchor_keeps_first_requested_row_causal(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
        "nvda_available,nvdax_available,session_state,last_trusted_reference,"
        "last_trusted_reference_ts"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,"
        "179.0,2026-09-20T13:55:00Z",
        "2026-09-20T14:05:00Z,NA,NA,NA,NA,FALSE,FALSE,closed,"
        "180.0,2026-09-20T14:00:00Z",
    ]
    snapshots = load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))

    assert len(snapshots) == 2
    assert snapshots[0].last_trusted_reference == 179.0
    assert snapshots[0].last_trusted_reference_ts.minute == 55
    assert snapshots[0].underlying_reference == 180.0
    assert snapshots[0].underlying_reference_ts == snapshots[0].observation_ts


def test_explicit_reference_columns_do_not_fill_missing_observations(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
        "nvda_available,nvdax_available,session_state,"
        "reference_under_test,reference_under_test_available,"
        "reference_under_test_source,reference_under_test_ts"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,"
        "190.0,TRUE,okx_xperp_index,2026-09-20T14:00:00Z",
        "2026-09-20T14:05:00Z,NA,NA,NA,NA,FALSE,FALSE,closed,"
        ",FALSE,okx_xperp_index,",
        "2026-09-20T14:10:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,"
        ",FALSE,okx_xperp_index,",
    ]
    snapshots = load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))

    assert len(snapshots) == 2
    assert snapshots[0].reference_under_test is None
    assert snapshots[0].reference_under_test_source == "okx_xperp_index"
    assert snapshots[0].token_price is None
    assert snapshots[1].reference_under_test is None


def test_non_five_minute_panel_fails_explicitly(tmp_path):
    bad_rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
        "2026-09-20T14:10:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,10",
    ]
    with pytest.raises(PanelTimestampError, match="exactly 5 minutes"):
        load_panel_snapshots(_write(tmp_path, "\n".join([_COLS, *bad_rows]) + "\n"))


def test_noncanonical_panel_boundary_fails_explicitly(tmp_path):
    rows = [
        "2026-09-20T14:02:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
        "2026-09-20T14:07:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,5",
    ]
    with pytest.raises(PanelTimestampError, match="canonical 5-minute"):
        load_panel_snapshots(_write(tmp_path, "\n".join([_COLS, *rows]) + "\n"))


def test_panel_rejects_future_reference_observation(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
        "nvda_available,nvdax_available,session_state,"
        "reference_under_test,reference_under_test_available,"
        "reference_under_test_source,reference_under_test_ts"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,"
        "190.0,TRUE,okx_xperp_index,2026-09-20T14:05:00Z",
    ]
    with pytest.raises(PanelTimestampError, match="must not be after"):
        load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))


_GENERIC_COLUMNS = (
    "timestamp_utc,asset,underlying_symbol,token_source,token_chain_index,"
    "token_address,reference_under_test_instrument,session_state,token_close,"
    "token_volume,token_volume_usd,token_available,token_observed_at,"
    "underlying_close,underlying_available,last_trusted_reference,"
    "last_trusted_reference_ts,reference_under_test,reference_under_test_available,"
    "reference_under_test_source,reference_under_test_ts,reference_profile"
)


def _generic_rows(
    asset="NVDAx",
    underlying="NVDA",
    chain="501",
    address="Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh",
):
    instrument = f"{underlying}-USD"
    profile = "unified_xstock_p1ac_xperp_evidence_v1"
    prefix = f"{asset},{underlying},okx_onchainos,{chain},{address},{instrument},closed"
    return [
        f"2026-09-20T14:00:00Z,{prefix},180.1,500,90000,TRUE,"
        "2026-09-20T14:00:00Z,180.0,TRUE,,,180.0,TRUE,okx_xperp_index,"
        f"2026-09-20T14:00:00Z,{profile}",
        f"2026-09-20T14:05:00Z,{prefix},180.3,900,123456,TRUE,"
        "2026-09-20T14:05:00Z,,FALSE,180.0,2026-09-20T14:00:00Z,"
        f"180.5,TRUE,okx_xperp_index,2026-09-20T14:05:00Z,{profile}",
    ]


def test_generic_panel_loads_offline_against_pinned_deployment(tmp_path, monkeypatch):
    from valtide_api.adapters import okx

    monkeypatch.setattr(
        okx,
        "resolve_token_deployment",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network lookup")),
    )
    settings = _pinned_settings()
    config = assets_module.resolve_asset_config("NVDAx", settings)
    rows = _generic_rows(
        chain=config.okx_chain_index or "501", address=config.token_address or "0xtest"
    )
    snapshots = load_panel_snapshots(
        _write(tmp_path, "\n".join([_GENERIC_COLUMNS, *rows]) + "\n"),
        settings=settings,
    )
    assert len(snapshots) == 1
    assert snapshots[0].token_price == 180.3
    assert snapshots[0].token_volume_usd == 123456.0
    assert snapshots[0].last_trusted_reference == 180.0
    assert snapshots[0].last_trusted_reference_ts < snapshots[0].observation_ts
    assert snapshots[0].underlying_reference is None
    assert snapshots[0].xperp_index_price == 180.5
    assert snapshots[0].xperp_index_source == "okx_xperp_index"
    assert snapshots[0].xperp_index_ts == snapshots[0].observation_ts
    assert snapshots[0].source_provenance["token_deployment_verified"] == "true"


def test_bom_readiness_and_loader_agree_and_nonfinite_prices_fail_closed(tmp_path):
    settings = _pinned_settings()
    rows = _generic_rows()
    bom_path = _write(tmp_path, "\ufeff" + "\n".join([_GENERIC_COLUMNS, *rows]) + "\n")

    readiness = inspect_panel_readiness(bom_path, asset="NVDAx", settings=settings)
    snapshots = load_panel_snapshots(bom_path, settings=settings)

    assert readiness.canonical_identity_verified is True
    assert readiness.replay_compatible is True
    assert len(snapshots) == 1

    bad_rows = [rows[0], rows[1].replace(",180.3,", ",NaN,")]
    bad_path = _write(tmp_path, "\n".join([_GENERIC_COLUMNS, *bad_rows]) + "\n")
    bad_readiness = inspect_panel_readiness(bad_path, asset="NVDAx", settings=settings)

    assert bad_readiness.canonical_identity_verified is False
    assert bad_readiness.replay_compatible is False
    with pytest.raises(PanelIdentityError, match="finite and positive"):
        load_panel_snapshots(bad_path, settings=settings)


def test_legacy_normalization_matches_equivalent_canonical_snapshots(tmp_path):
    settings = _pinned_settings()
    config = assets_module.resolve_asset_config("NVDAx", settings)
    rows = _generic_rows(
        chain=config.okx_chain_index or "501", address=config.token_address or "0xtest"
    )
    canonical = load_panel_snapshots(
        _write(tmp_path, "\n".join([_GENERIC_COLUMNS, *rows]) + "\n"),
        settings=settings,
    )
    legacy_columns = (
        "timestamp_utc,nvda_close,nvdax_close,nvdax_volume,nvdax_volume_usd,"
        "nvda_available,nvdax_available,session_state,last_trusted_reference,"
        "last_trusted_reference_ts,reference_under_test,reference_under_test_available,"
        "reference_under_test_source,reference_under_test_ts"
    )
    legacy_rows = [
        "2026-09-20T14:00:00Z,180.0,180.1,500,90000,TRUE,TRUE,closed,,,"
        "180.0,TRUE,okx_xperp_index,2026-09-20T14:00:00Z",
        "2026-09-20T14:05:00Z,,180.3,900,123456,FALSE,TRUE,closed,"
        "180.0,2026-09-20T14:00:00Z,180.5,TRUE,okx_xperp_index,"
        "2026-09-20T14:05:00Z",
    ]
    legacy = load_panel_snapshots(
        _write(tmp_path, "\n".join([legacy_columns, *legacy_rows]) + "\n")
    )
    assert [snapshot.model_dump(exclude={"source_provenance"}) for snapshot in canonical] == [
        snapshot.model_dump(exclude={"source_provenance"}) for snapshot in legacy
    ]
    assert legacy[0].source_provenance["panel_schema"] == "legacy_nvda_diagnostic"
    assert legacy[0].source_provenance["token_deployment_verified"] == "false"


def test_generic_panel_rejects_missing_or_mismatched_identity(tmp_path):
    rows = _generic_rows()
    settings = _pinned_settings()
    with pytest.raises(PanelIdentityError):
        changed = [row.replace(",NVDAx,", ",SPYx,") for row in rows]
        load_panel_snapshots(
            _write(tmp_path, "\n".join([_GENERIC_COLUMNS, *changed]) + "\n"),
            settings=settings,
        )
    with pytest.raises(PanelIdentityError, match="identity fields"):
        changed = [row.replace(",NVDAx,", ",") for row in rows]
        header = _GENERIC_COLUMNS.replace("asset,", "")
        load_panel_snapshots(
            _write(tmp_path, "\n".join([header, *changed]) + "\n"),
            settings=settings,
        )


def test_generic_panel_rejects_wrong_reference_source(tmp_path):
    rows = [row.replace("okx_xperp_index", "another_reference") for row in _generic_rows()]
    with pytest.raises(PanelIdentityError, match="identity"):
        load_panel_snapshots(
            _write(tmp_path, "\n".join([_GENERIC_COLUMNS, *rows]) + "\n"),
            settings=_pinned_settings(),
        )


@pytest.mark.parametrize(
    ("identity_field", "wrong_value", "error"),
    [
        ("asset", "SPYx", "identity does not match"),
        ("token_source", "another_token_source", "identity does not match"),
        ("token_chain_index", "999", "token chain"),
        ("token_address", "0xwrong", "token address"),
    ],
)
def test_hybrid_schema_cannot_hide_wrong_canonical_identity(
    tmp_path, identity_field, wrong_value, error
):
    fields = [*_GENERIC_COLUMNS.split(","), "nvda_close", "nvdax_close"]
    records = [row.split(",") for row in _generic_rows()]
    for record in records:
        record[fields.index(identity_field)] = wrong_value
        record.extend(["180.0", "180.1"])
    lines = [",".join(fields), *(",".join(record) for record in records)]
    with pytest.raises(PanelIdentityError, match=error):
        load_panel_snapshots(_write(tmp_path, "\n".join(lines) + "\n"), settings=_pinned_settings())


def test_legacy_shape_cannot_hide_wrong_reference_source(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvdax_close,nvda_available,nvdax_available,"
        "reference_under_test_source"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,180.1,TRUE,TRUE,wrong_reference",
        "2026-09-20T14:05:00Z,180.0,180.2,TRUE,TRUE,wrong_reference",
    ]
    with pytest.raises(PanelIdentityError, match="reference source"):
        load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))


def test_partial_canonical_columns_plus_legacy_schema_are_ambiguous(tmp_path):
    columns = "timestamp_utc,nvda_close,nvdax_close,token_close"
    rows = [
        "2026-09-20T14:00:00Z,180.0,180.1,180.1",
        "2026-09-20T14:05:00Z,180.0,180.2,180.2",
    ]
    with pytest.raises(PanelIdentityError, match="ambiguous hybrid"):
        load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))


def test_canonical_panel_requires_an_independent_pinned_deployment(tmp_path, monkeypatch):
    from valtide_api.adapters import okx

    monkeypatch.setattr(
        okx,
        "resolve_token_deployment",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network lookup")),
    )
    rows = _generic_rows()
    path = _write(tmp_path, "\n".join([_GENERIC_COLUMNS, *rows]) + "\n")
    with pytest.raises(PanelIdentityError, match="provenance is unverified"):
        load_panel_snapshots(path, settings=Settings(_env_file=None))


@pytest.mark.parametrize(
    ("chain", "address", "error"),
    [
        ("999", "0xtest", "chain"),
        ("501", "0xwrong", "address"),
    ],
)
def test_canonical_panel_rejects_wrong_pinned_deployment(tmp_path, chain, address, error):
    rows = _generic_rows()
    fields = _GENERIC_COLUMNS.split(",")
    records = [row.split(",") for row in rows]
    identity_column = "token_chain_index" if error == "chain" else "token_address"
    wrong_value = chain if error == "chain" else address
    for record in records:
        record[fields.index(identity_column)] = wrong_value
    path = _write(
        tmp_path,
        "\n".join([_GENERIC_COLUMNS, *(",".join(row) for row in records)]) + "\n",
    )
    with pytest.raises(PanelIdentityError, match=error):
        load_panel_snapshots(path, settings=_pinned_settings())


def _spy_canonical_panel(tmp_path, *, chain="501", address=None, mixed=False):
    config = assets_module.resolve_asset_config("SPYx", Settings(_env_file=None))
    token_address = address or config.token_address
    fields = _GENERIC_COLUMNS.split(",")
    rows = [
        row.split(",")
        for row in _generic_rows("SPYx", "SPY", chain, token_address)
    ]
    if mixed:
        fields.extend(("nvda_close", "nvdax_close"))
        for row in rows:
            row.extend(("180.0", "180.1"))
    path = _write(
        tmp_path,
        "\n".join([",".join(fields), *(",".join(row) for row in rows)]) + "\n",
    )
    settings = Settings(_env_file=None, spyx_historical_panel_path=path)
    return path, config, settings


def test_panel_readiness_verifies_canonical_solana_identity_without_replay(tmp_path):
    path, config, settings = _spy_canonical_panel(tmp_path)

    status = inspect_panel_readiness(path, asset="SPYx", settings=settings)

    assert status.file_available is True
    assert status.canonical_identity_verified is True
    assert status.replay_compatible is True
    assert status.error_code is None


def test_panel_readiness_separates_verified_file_from_empty_replay(tmp_path):
    fields = _GENERIC_COLUMNS.split(",")
    path = _write(tmp_path, ",".join(fields) + "\n")
    settings = Settings(_env_file=None, spyx_historical_panel_path=path)

    status = inspect_panel_readiness(path, asset="SPYx", settings=settings)

    assert status.file_available is True
    assert status.canonical_identity_verified is False
    assert status.replay_compatible is False
    assert status.error_code == "PANEL_HAS_NO_REPLAY_OBSERVATIONS"


@pytest.mark.parametrize(
    ("chain", "address", "mixed", "expected_code"),
    [
        ("1", "0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48", False, "PANEL_IDENTITY_INVALID"),
        ("501", "0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48", False, "PANEL_IDENTITY_INVALID"),
        ("1", "0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48", True, "PANEL_IDENTITY_INVALID"),
    ],
)
def test_panel_readiness_fails_closed_for_wrong_or_mixed_deployment(
    tmp_path, chain, address, mixed, expected_code
):
    path, _config, settings = _spy_canonical_panel(
        tmp_path, chain=chain, address=address, mixed=mixed
    )

    status = inspect_panel_readiness(path, asset="SPYx", settings=settings)

    assert status.file_available is True
    assert status.canonical_identity_verified is False
    assert status.replay_compatible is False
    assert status.error_code == expected_code


def test_panel_readiness_fails_closed_for_malformed_csv(tmp_path):
    path = _write(tmp_path, "timestamp_utc,asset\nnot-a-timestamp,SPYx\n")
    settings = Settings(_env_file=None, spyx_historical_panel_path=path)

    status = inspect_panel_readiness(path, asset="SPYx", settings=settings)

    assert status.file_available is True
    assert status.canonical_identity_verified is False
    assert status.replay_compatible is False
    assert status.error_code in {"PANEL_IDENTITY_INVALID", "PANEL_FORMAT_INVALID"}


def test_panel_readiness_rejects_duplicate_identity_headers(tmp_path):
    path, _config, settings = _spy_canonical_panel(tmp_path)
    contents = path.read_text()
    header, *rows = contents.splitlines()
    duplicate_header = f"{header},asset"
    duplicate_rows = [f"{row},SPYx" for row in rows]
    path.write_text("\n".join([duplicate_header, *duplicate_rows]) + "\n")

    status = inspect_panel_readiness(path, asset="SPYx", settings=settings)

    assert status.file_available is True
    assert status.canonical_identity_verified is False
    assert status.replay_compatible is False
    assert status.error_code == "PANEL_IDENTITY_INVALID"


def test_assets_api_does_not_report_ethereum_csv_as_solana_history(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import valtide_api.routes.assets as assets_route
    from valtide_api.main import app

    path, config, settings = _spy_canonical_panel(
        tmp_path,
        chain="1",
        address="0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48",
    )
    config = replace(
        config,
        capabilities=replace(
            config.capabilities,
            quant=True,
            historical_data=True,
            runtime=False,
            api_exposed=True,
        ),
    )
    monkeypatch.setattr(assets_route, "api_asset_configs", lambda: (config,))
    monkeypatch.setattr(assets_route, "get_settings", lambda: settings)
    monkeypatch.setattr(assets_route, "quant_runtime_available", lambda _config: True)
    monkeypatch.setattr(assets_route, "get_runtime_store", lambda: object())
    monkeypatch.setattr(assets_route, "scheduler_asset_enabled", lambda *_args: False)

    response = TestClient(app).get("/api/assets")

    assert response.status_code == 200
    asset = response.json()[0]
    assert asset["historical_panel_file_available"] is True
    assert asset["canonical_panel_verified"] is False
    assert asset["historical_replay_ready"] is False
    assert asset["historical_data_available"] is False
    assert "PANEL_IDENTITY_INVALID" in asset["readiness_error_codes"]


def test_generic_panel_rejects_misdated_underlying_observation(tmp_path):
    columns = _GENERIC_COLUMNS.split(",")
    insert_at = columns.index("underlying_available") + 1
    columns.insert(insert_at, "underlying_observed_at")
    rows = [row.split(",") for row in _generic_rows()]
    rows[0].insert(insert_at, "2026-09-20T14:05:00Z")
    rows[1].insert(insert_at, "")
    with pytest.raises(PanelIdentityError, match="underlying observation"):
        csv_rows = [",".join(columns), *(",".join(row) for row in rows)]
        load_panel_snapshots(
            _write(tmp_path, "\n".join(csv_rows) + "\n"),
            settings=_pinned_settings(),
        )


def test_synthetic_panel_does_not_inherit_nvda_columns(monkeypatch, tmp_path):
    synthetic = replace(
        assets_module.resolve_asset_config("NVDAx"),
        asset="TESTx", underlying_symbol="TEST", okx_chain_index="777",
        token_address="0xsynthetic", allow_token_discovery=False,
        reference_under_test_instrument="TEST-USD",
        quant_runtime_key="missing", historical_panel_key="missing",
        capabilities=replace(assets_module._NVDA_CONFIG.capabilities, api_exposed=False),
    )
    monkeypatch.setattr(
        assets_module, "_ASSET_REGISTRY",
        MappingProxyType({"NVDAx": assets_module._NVDA_CONFIG, "TESTx": synthetic}),
    )
    rows = _generic_rows("TESTx", "TEST", "777", "0xsynthetic")
    snapshots = load_panel_snapshots(
        _write(tmp_path, "\n".join([_GENERIC_COLUMNS, *rows]) + "\n"), asset="TESTx"
    )
    assert snapshots[0].asset == "TESTx"
    assert assets_module.supported_asset_names() == ("NVDAx",)
    with pytest.raises(PanelIdentityError, match="legacy NVDA"):
        load_panel_snapshots(_write(tmp_path, _CSV), asset="TESTx")
